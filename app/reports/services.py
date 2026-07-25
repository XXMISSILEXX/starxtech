import hashlib
import tempfile
from datetime import datetime
from types import SimpleNamespace

from flask import current_app, request
from flask_login import current_user
from PIL import Image, UnidentifiedImageError
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError

from app.admin.services import add_with_sqlite_id, audit
from app.extensions import db
from app.models import (
    DailyReport,
    DailyReportSection,
    DailyReportStatus,
    Project,
    ReportAttachment,
    ReportCategory,
    SectionStatus,
    StorageDerivative,
    StorageObject,
    MediaProcessingJob,
    DownloadEvent,
    UploadBatchItem,
    ProjectDocumentFile,
    CompanyMediaFile,
)
from app.storage.keys import build_original_key
from app.storage.providers import get_storage_provider
from app.storage.exceptions import StorageNotFoundError
from app.storage.quota import ensure_storage_capacity
from app.project_memberships import accessible_project_ids

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "heic", "heif"}
IMAGE_FORMATS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp", "HEIF": "heic"}
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:  # pragma: no cover
    pass


class ReportValidationError(ValueError):
    def __init__(self, message, errors=None):
        super().__init__(message)
        self.errors = errors or {}


def accessible_projects_query():
    query = Project.query.filter(Project.deleted_at.is_(None))
    ids = accessible_project_ids(current_user, ("can_view_project",))
    if ids is not None:
        query = query.filter(Project.id.in_(ids or [0]))
    return query.order_by(Project.code.asc(), Project.name.asc())


def reports_query():
    query = DailyReport.query.join(DailyReport.project)
    ids = accessible_project_ids(current_user, ("can_view_reports",))
    if ids is not None:
        query = query.filter(DailyReport.project_id.in_(ids or [0]))
    return query


def categories_for_create(project_id):
    return (
        ReportCategory.query.filter(
            ReportCategory.project_id == project_id,
            ReportCategory.deleted_at.is_(None),
            ReportCategory.is_active.is_(True),
        )
        .order_by(ReportCategory.sort_order.asc(), ReportCategory.name.asc())
        .all()
    )


def categories_for_report(report):
    used_ids = [section.report_category_id for section in report.sections]
    query = ReportCategory.query.filter(
        ReportCategory.project_id == report.project_id,
        ReportCategory.deleted_at.is_(None),
    ).filter((ReportCategory.is_active.is_(True)) | (ReportCategory.id.in_(used_ids or [0])))
    return query.order_by(ReportCategory.sort_order.asc(), ReportCategory.name.asc()).all()


def parse_report_date(value):
    if not value:
        raise ReportValidationError("Vui lòng chọn ngày báo cáo.", {"report_date": "Vui lòng chọn ngày báo cáo."})
    for pattern in ("%d/%m/%Y", "%Y-%m-%d"):  # ISO remains accepted for API/backwards compatibility.
        try:
            return datetime.strptime(value, pattern).date()
        except ValueError:
            pass
    try:
        raise ValueError(value)
    except ValueError as exc:
        raise ReportValidationError("Ngày báo cáo phải đúng định dạng DD/MM/YYYY.", {"report_date": "Ngày báo cáo phải đúng định dạng DD/MM/YYYY."}) from exc


def format_report_date(value):
    return value.strftime("%d/%m/%Y") if value else ""


def _duplicate_report_error(report_date, existing_report_id=None):
    message = f"Dự án này đã có báo cáo cho ngày {format_report_date(report_date)}."
    errors = {"report_date": message}
    if existing_report_id is not None:
        errors["duplicate_report_id"] = existing_report_id
    return ReportValidationError(message, errors)


def _is_daily_report_date_constraint(exc):
    origin = getattr(exc, "orig", None)
    diagnostic = getattr(origin, "diag", None)
    if getattr(diagnostic, "constraint_name", None) == "uq_daily_reports_project_date":
        return True
    return "uq_daily_reports_project_date" in str(origin or exc)


def _existing_report(project_id, report_date, *, exclude_id=None):
    statement = select(DailyReport).where(
        DailyReport.project_id == project_id,
        DailyReport.report_date == report_date,
    )
    if exclude_id is not None:
        statement = statement.where(DailyReport.id != exclude_id)
    with db.session.no_autoflush:
        return db.session.scalar(statement)


def create_report(project, form, files=None):
    validate_report_form(form, project.id)
    report_date = parse_report_date(form.get("report_date", "").strip())
    # Keep this in lockstep with the database unique constraint: soft-deleted
    # rows also reserve their project/date pair.
    existing = _existing_report(project.id, report_date)
    if existing:
        raise _duplicate_report_error(report_date, existing.id)

    section_inputs = parse_sections(form)
    prepared_upload = _prepare_direct_uploads(project.id, form, section_inputs)
    report = DailyReport(project_id=project.id, created_by_user_id=current_user.id)
    add_with_sqlite_id(report)
    _assign_report_fields(report, form)
    report.report_date = report_date
    try:
        db.session.flush()
    except IntegrityError as exc:
        db.session.rollback()
        if _is_daily_report_date_constraint(exc):
            raise _duplicate_report_error(report_date) from exc
        raise

    _replace_sections(report, section_inputs)
    db.session.flush()
    job_ids = _attach_direct_uploads(report, section_inputs, prepared_upload)
    audit("report.create", "DailyReport", report.id, new_values=report_snapshot(report))
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        if _is_daily_report_date_constraint(exc):
            raise _duplicate_report_error(report_date) from exc
        raise
    _dispatch_derivatives_after_commit(job_ids)
    return report


def update_report(report, form, files=None):
    validate_report_form(form, report.project_id)
    old_values = report_snapshot(report)
    proposed_date = parse_report_date(form.get("report_date", "").strip())
    duplicate = _existing_report(report.project_id, proposed_date, exclude_id=report.id)
    if duplicate:
        raise _duplicate_report_error(proposed_date, duplicate.id)

    try:
        section_inputs = parse_sections(form)
        prepared_upload = _prepare_direct_uploads(report.project_id, form, section_inputs)
        report.report_date = proposed_date
        _assign_report_fields(report, form)
        report.updated_by_user_id = current_user.id
        _replace_sections(report, section_inputs)
        db.session.flush()
        job_ids = _attach_direct_uploads(report, section_inputs, prepared_upload)
        audit("report.update", "DailyReport", report.id, old_values, report_snapshot(report))
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        if _is_daily_report_date_constraint(exc):
            raise _duplicate_report_error(proposed_date) from exc
        raise
    _dispatch_derivatives_after_commit(job_ids)
    return report


class ReportDeletionError(RuntimeError):
    pass


def _delete_storage_objects(storage_objects, derivatives):
    """Delete only collected report bytes; missing objects are idempotent."""
    provider = get_storage_provider()
    failures = []
    for item in [*derivatives, *storage_objects]:
        try:
            provider.delete_object(item.bucket, item.object_key)
        except StorageNotFoundError:
            # A prior failed purge may already have removed bytes while its DB
            # transaction rolled back.  Metadata cleanup must be retry-safe.
            continue
        except Exception as exc:
            failures.append(f"{item.bucket}/{item.object_key}: {exc}")
    if failures:
        raise ReportDeletionError("Không thể xóa toàn bộ tệp S3: " + "; ".join(failures))
    return None


def hard_delete_reports(reports, *, dry_run=False):
    """Permanently remove reports and every Daily Reports storage artifact."""
    reports = list(reports)
    report_ids = [report.id for report in reports]
    sections = DailyReportSection.query.filter(DailyReportSection.daily_report_id.in_(report_ids)).all() if report_ids else []
    section_ids = [section.id for section in sections]
    attachments = ReportAttachment.query.filter(ReportAttachment.daily_report_section_id.in_(section_ids)).all() if section_ids else []
    storage_ids = sorted({attachment.storage_object_id for attachment in attachments if attachment.storage_object_id})
    storage_objects = StorageObject.query.filter(StorageObject.id.in_(storage_ids)).all() if storage_ids else []
    derivatives = StorageDerivative.query.filter(StorageDerivative.storage_object_id.in_(storage_ids)).all() if storage_ids else []
    summary = {
        "reports": len(reports), "sections": len(sections), "attachments": len(attachments),
        "storage_objects": len(storage_objects), "storage_derivatives": len(derivatives),
        "storage_objects_to_delete": len(storage_objects) + len(derivatives),
    }
    if dry_run or not reports:
        return summary

    _delete_storage_objects(storage_objects, derivatives)
    derivative_ids = [item.id for item in derivatives]
    # Only jobs belonging to these storage objects are candidates.  A corrupt
    # derivative provenance reference must never cause an unrelated job delete.
    job_ids = [row[0] for row in db.session.execute(select(MediaProcessingJob.id).where(
        MediaProcessingJob.storage_object_id.in_(storage_ids)
    )).all()] if storage_ids else []
    try:
        if derivative_ids:
            db.session.execute(update(DownloadEvent).where(
                DownloadEvent.derivative_id.in_(derivative_ids)
            ).values(derivative_id=None))
            # Must precede MediaProcessingJob: derivatives retain provenance
            # through storage_derivatives.created_by_job_id.
            db.session.execute(delete(StorageDerivative).where(
                StorageDerivative.id.in_(derivative_ids)
            ))
            db.session.flush()
        if job_ids:
            db.session.execute(delete(MediaProcessingJob).where(
                MediaProcessingJob.id.in_(job_ids),
                MediaProcessingJob.storage_object_id.in_(storage_ids),
            ))
        if storage_ids:
            db.session.execute(update(DownloadEvent).where(
                DownloadEvent.storage_object_id.in_(storage_ids)
            ).values(storage_object_id=None))
            # Finalized direct-upload items retain their audit/session record,
            # but must not retain a foreign-key reference to a purged object.
            db.session.execute(update(UploadBatchItem).where(
                UploadBatchItem.storage_object_id.in_(storage_ids)
            ).values(storage_object_id=None))
        if attachments:
            db.session.execute(delete(ReportAttachment).where(
                ReportAttachment.id.in_([attachment.id for attachment in attachments])
            ))
        if section_ids:
            db.session.execute(delete(DailyReportSection).where(DailyReportSection.id.in_(section_ids)))
        for report in reports:
            audit("report.delete", "DailyReport", report.id, old_values=report_snapshot(report), new_values={"deleted": "permanent"})
        if report_ids:
            db.session.execute(delete(DailyReport).where(DailyReport.id.in_(report_ids)))
        db.session.flush()
        if storage_ids:
            db.session.execute(delete(StorageObject).where(StorageObject.id.in_(storage_ids)))
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return summary


def delete_report(report):
    return hard_delete_reports([report])


def delete_attachment(attachment):
    """Permanently remove an attachment and its unshared storage artifacts."""
    storage_object = attachment.storage_object
    storage_id = attachment.storage_object_id
    derivatives = StorageDerivative.query.filter_by(storage_object_id=storage_id).all() if storage_id else []
    if storage_object and _storage_object_has_other_references(storage_id, attachment.id):
        storage_object = None
        derivatives = []
    if storage_object:
        _delete_storage_objects([storage_object], derivatives)
    derivative_ids = [row.id for row in derivatives]
    try:
        if derivative_ids:
            db.session.execute(update(DownloadEvent).where(
                DownloadEvent.derivative_id.in_(derivative_ids)
            ).values(derivative_id=None))
            db.session.execute(delete(StorageDerivative).where(
                StorageDerivative.id.in_(derivative_ids)
            ))
        if storage_id and storage_object:
            db.session.execute(delete(MediaProcessingJob).where(
                MediaProcessingJob.storage_object_id == storage_id
            ))
            db.session.execute(update(DownloadEvent).where(
                DownloadEvent.storage_object_id == storage_id
            ).values(storage_object_id=None))
            db.session.execute(update(UploadBatchItem).where(
                UploadBatchItem.storage_object_id == storage_id
            ).values(storage_object_id=None))
        attachment_id = attachment.id
        db.session.delete(attachment)
        db.session.flush()
        if storage_id and storage_object:
            db.session.execute(delete(StorageObject).where(StorageObject.id == storage_id))
        audit(
            "attachment.delete",
            "ReportAttachment",
            attachment_id,
            old_values={"daily_report_section_id": attachment.daily_report_section_id},
            new_values={"deleted": "permanent"},
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def _storage_object_has_other_references(storage_object_id, attachment_id):
    """Avoid deleting a byte object if a different module still owns it."""
    if db.session.scalar(select(ReportAttachment.id).where(
        ReportAttachment.storage_object_id == storage_object_id,
        ReportAttachment.id != attachment_id,
    ).limit(1)):
        return True
    if db.session.scalar(select(ProjectDocumentFile.id).where(
        ProjectDocumentFile.storage_object_id == storage_object_id,
    ).limit(1)):
        return True
    return bool(db.session.scalar(select(CompanyMediaFile.id).where(
        CompanyMediaFile.storage_object_id == storage_object_id,
    ).limit(1)))
    audit(
        "attachment.delete",
        "ReportAttachment",
        attachment.id,
        old_values={"daily_report_section_id": attachment.daily_report_section_id},
        new_values={"deleted_at": True},
    )
    db.session.commit()


def parse_sections(form):
    indexes = set()
    for key in form.keys():
        if key.startswith("sections-"):
            parts = key.split("-")
            if len(parts) >= 3 and parts[1].isdigit():
                indexes.add(int(parts[1]))

    sections = []
    seen_categories = set()
    for index in sorted(indexes):
        category_raw = form.get(f"sections-{index}-category_id", "").strip()
        status = form.get(f"sections-{index}-status", "").strip()
        content = form.get(f"sections-{index}-content", "").strip()
        if not category_raw and not status and not content:
            continue
        if not category_raw:
            raise ReportValidationError("Vui lòng chọn hạng mục.", {f"sections-{index}-category_id": "Vui lòng chọn hạng mục."})
        if not content:
            raise ReportValidationError("Mỗi phần báo cáo phải có nội dung.", {f"sections-{index}-content": "Mỗi phần báo cáo phải có nội dung."})
        if status not in [item.value for item in SectionStatus]:
            raise ReportValidationError("Vui lòng chọn trạng thái.", {f"sections-{index}-status": "Vui lòng chọn trạng thái."})
        try:
            category_id = int(category_raw)
        except ValueError as exc:
            raise ReportValidationError("Hạng mục báo cáo không hợp lệ.") from exc
        if category_id in seen_categories:
            raise ReportValidationError("Hạng mục không được trùng trong cùng báo cáo.")
        seen_categories.add(category_id)
        sections.append(
            {
                "index": index,
                "report_category_id": category_id,
                "status": status,
                "content": content,
                "sort_order": len(sections),
                "client_section_id": form.get(f"sections-{index}-client-section-id", "").strip(),
            }
        )
    return sections


def validate_categories(project_id, section_inputs):
    category_ids = {section["report_category_id"] for section in section_inputs}
    if not category_ids:
        return
    valid_count = ReportCategory.query.filter(
        ReportCategory.project_id == project_id,
        ReportCategory.id.in_(category_ids),
        ReportCategory.deleted_at.is_(None),
    ).count()
    if valid_count != len(category_ids):
        raise ReportValidationError("Tất cả hạng mục phải thuộc dự án này.")


def report_snapshot(report):
    return {
        "project_id": report.project_id,
        "report_date": report.report_date.isoformat() if report.report_date else None,
        "overall_status": report.overall_status,
        "highlight": report.highlight,
        "summary_note": report.summary_note,
    }


def active_attachments(section):
    return [attachment for attachment in section.attachments if attachment.deleted_at is None]


def _assign_report_fields(report, form):
    overall_status = form.get("overall_status", "").strip()
    highlight = form.get("highlight", "").strip()
    if overall_status not in [item.value for item in DailyReportStatus]:
        raise ReportValidationError("Vui lòng chọn trạng thái.", {"overall_status": "Vui lòng chọn trạng thái."})
    if not highlight:
        raise ReportValidationError("Vui lòng nhập điểm nổi bật.", {"highlight": "Vui lòng nhập điểm nổi bật."})
    report.overall_status = overall_status
    report.highlight = highlight
    report.summary_note = form.get("summary_note", "").strip() or None


def _replace_sections(report, section_inputs):
    validate_categories(report.project_id, section_inputs)
    existing_by_category = {section.report_category_id: section for section in report.sections}
    submitted_category_ids = {section["report_category_id"] for section in section_inputs}

    for section in report.sections:
        if section.report_category_id not in submitted_category_ids:
            section.deleted_at = db.func.now()
            for attachment in section.attachments:
                if attachment.deleted_at is None:
                    attachment.deleted_at = db.func.now()

    for section_input in section_inputs:
        section = existing_by_category.get(section_input["report_category_id"])
        if section is None:
            section = DailyReportSection(
                report_category_id=section_input["report_category_id"],
            )
            add_with_sqlite_id(section)
            report.sections.append(section)
        section.deleted_at = None
        section.status = section_input["status"]
        section.content = section_input["content"]
        section.sort_order = section_input["sort_order"]
        section._form_index = str(section_input["index"])


def _save_section_uploads(report, files):
    section_by_index = {}
    for section in report.sections:
        if section.deleted_at is None and hasattr(section, "_form_index"):
            section_by_index[section._form_index] = section

    for index, section in section_by_index.items():
        uploads = [
            file
            for file in files.getlist(f"sections-{index}-images")
            if file and file.filename
        ]
        if not uploads:
            continue
        current_count = len(active_attachments(section))
        max_images = current_app.config["MAX_IMAGES_PER_SECTION"]
        if current_count + len(uploads) > max_images:
            raise ReportValidationError("Mỗi phần chỉ được có tối đa 3 ảnh đang hoạt động.")
        for upload in uploads:
            attachment = _store_attachment(report, section, upload)
            db.session.flush()
            audit(
                "attachment.create",
                "ReportAttachment",
                attachment.id,
                new_values={"daily_report_section_id": section.id},
            )


def _prepare_direct_uploads(project_id, form, section_inputs):
    """Validate direct-upload state before any DailyReport rows are inserted."""
    session_id = form.get("upload_session_id", type=int) if hasattr(form, "get") else None
    from app.reports.direct_uploads import parse_report_attachment_manifest
    from app.storage.exceptions import StorageAuthorizationError, StorageValidationError
    try:
        return parse_report_attachment_manifest(
            user=current_user, project_id=project_id, section_inputs=section_inputs,
            form=form,
        )
    except (StorageAuthorizationError, StorageValidationError) as exc:
        raise ReportValidationError(str(exc)) from exc


def _attach_direct_uploads(report, section_inputs, prepared_upload):
    """Attach verified direct uploads; browser files are deliberately ignored."""
    from app.reports.direct_uploads import CompletedUpload
    if not isinstance(prepared_upload, CompletedUpload):
        return []
    from app.reports.direct_uploads import finalize_session
    session, items, mapping = prepared_upload.session, prepared_upload.items, prepared_upload.mapping
    section_by_index = {int(section._form_index): section for section in report.sections if section.deleted_at is None and hasattr(section, "_form_index")}
    existing = [attachment for section in section_by_index.values() for attachment in active_attachments(section)]
    if len(existing) + len(items) > int(current_app.config["DAILY_REPORT_MAX_FILES"]):
        raise ReportValidationError("Báo cáo chỉ được có tối đa 30 ảnh.")
    if sum(attachment.file_size for attachment in existing) + sum(item.file_size for item in items) > int(current_app.config["DAILY_REPORT_MAX_TOTAL_BYTES"]):
        raise ReportValidationError("Tổng dung lượng ảnh của báo cáo vượt giới hạn.")
    additions_by_section = {}
    for item in items:
        additions_by_section[mapping[item.id]["index"]] = additions_by_section.get(mapping[item.id]["index"], 0) + 1
    if any(len(active_attachments(section_by_index[index])) + count > int(current_app.config["DAILY_REPORT_MAX_FILES_PER_SECTION"])
           for index, count in additions_by_section.items()):
        raise ReportValidationError("Mỗi phần chỉ được có tối đa 3 ảnh đang hoạt động.")
    objects = []
    for item in items:
        section = section_by_index[mapping[item.id]["index"]]
        attachment = ReportAttachment(daily_report_section_id=section.id, original_filename=item.original_filename,
            storage_object_id=item.storage_object_id, mime_type=item.mime_type, file_size=item.file_size,
            uploaded_by_user_id=current_user.id)
        add_with_sqlite_id(attachment)
        item.storage_object.upload_status = "active"
        objects.append(item.storage_object)
        item.finalized_at = datetime.utcnow()
        audit("attachment.create", "ReportAttachment", attachment.id, new_values={"daily_report_section_id": section.id})
    finalize_session(session)
    from app.media_processing.services import stage_media_processing_jobs
    return stage_media_processing_jobs(objects)


def _dispatch_derivatives_after_commit(job_ids):
    if not job_ids:
        return
    from app.media_processing.services import dispatch_media_processing_job
    for job_id in job_ids:
        try:
            dispatch_media_processing_job(job_id)
        except Exception:
            # The committed pending job is reconciled later; report creation is
            # deliberately never rolled back because a broker is unavailable.
            current_app.logger.exception("daily_report.media_dispatch_failed job_id=%s", job_id)


def _store_attachment(report, section, upload: FileStorage):
    original_filename = secure_filename(upload.filename or "")
    extension = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else ""
    if extension not in ALLOWED_EXTENSIONS:
        raise ReportValidationError("Chỉ cho phép tệp jpg, jpeg, png, webp, heic và heif.")

    raw = upload.read()
    if not raw:
        raise ReportValidationError("Tệp tải lên không phải ảnh hợp lệ.")
    image = None
    try:
        image = Image.open(__import__("io").BytesIO(raw))
        image.verify()
        image = Image.open(__import__("io").BytesIO(raw))
        image.load()
    except (UnidentifiedImageError, OSError):
        if extension not in {"heic", "heif"}:
            raise ReportValidationError("Tệp tải lên không phải ảnh hợp lệ.")

    image_format = image.format if image else None
    if image and image_format not in IMAGE_FORMATS:
        raise ReportValidationError("Chỉ cho phép tệp jpg, jpeg, png, webp, heic và heif.")
    stored_extension = IMAGE_FORMATS.get(image_format, extension)
    ensure_storage_capacity(len(raw))
    object_key = build_original_key("daily-reports", __import__("uuid").uuid4().hex, original_filename, current_app.config["STORAGE_PREFIX"])
    from app.models import StorageObject
    storage_object = StorageObject(bucket=current_app.config["STORAGE_BUCKET"], object_key=object_key,
        storage_module="daily-reports", original_filename=original_filename or upload.filename,
        mime_type=Image.MIME.get(image_format, "image/heic" if extension in {"heic", "heif"} else f"image/{stored_extension}"), file_ext=stored_extension,
        file_size=len(raw), checksum_sha256=hashlib.sha256(raw).hexdigest(), width=image.width if image else None,
        height=image.height if image else None, uploaded_by_id=current_user.id, upload_status="active")
    db.session.add(storage_object); db.session.flush()
    with tempfile.NamedTemporaryFile(prefix="daily-report-", suffix=f".{stored_extension}") as temp:
        temp.write(raw); temp.flush()
        get_storage_provider().upload_object(storage_object.bucket, storage_object.object_key, temp.name,
            storage_object.mime_type, {"sha256": storage_object.checksum_sha256})

    attachment = ReportAttachment(
        daily_report_section_id=section.id,
        original_filename=original_filename or upload.filename,
        storage_object_id=storage_object.id,
        mime_type=storage_object.mime_type,
        file_size=storage_object.file_size,
        image_width=image.width if image else None,
        image_height=image.height if image else None,
        uploaded_by_user_id=current_user.id,
    )
    add_with_sqlite_id(attachment)
    from app.media_processing.services import enqueue_media_processing_for_storage_object
    # defer dispatch until the current session has a stable attachment row
    db.session.flush()
    enqueue_media_processing_for_storage_object(storage_object.id)
    return attachment


def validate_report_form(form, project_id):
    errors = {}
    report_date_raw = form.get("report_date", "").strip()
    overall_status = form.get("overall_status", "").strip()
    highlight = form.get("highlight", "").strip()

    if not report_date_raw:
        errors["report_date"] = "Vui lòng chọn ngày báo cáo."
    else:
        try:
            parse_report_date(report_date_raw)
        except (ValueError, ReportValidationError):
            errors["report_date"] = "Ngày báo cáo phải đúng định dạng DD/MM/YYYY."

    if overall_status not in [item.value for item in DailyReportStatus]:
        errors["overall_status"] = "Vui lòng chọn trạng thái."
    if not highlight:
        errors["highlight"] = "Vui lòng nhập điểm nổi bật."

    section_indexes = _section_indexes(form)
    if not section_indexes:
        errors["sections"] = "Vui lòng thêm ít nhất một phần báo cáo."

    seen_categories = set()
    category_ids = set()
    for index in section_indexes:
        category_raw = form.get(f"sections-{index}-category_id", "").strip()
        status = form.get(f"sections-{index}-status", "").strip()
        content = form.get(f"sections-{index}-content", "").strip()

        if not category_raw:
            errors[f"sections-{index}-category_id"] = "Vui lòng chọn hạng mục."
        else:
            try:
                category_id = int(category_raw)
                category_ids.add(category_id)
                if category_id in seen_categories:
                    errors[f"sections-{index}-category_id"] = "Hạng mục không được trùng trong cùng báo cáo."
                seen_categories.add(category_id)
            except ValueError:
                errors[f"sections-{index}-category_id"] = "Hạng mục báo cáo không hợp lệ."

        if status not in [item.value for item in SectionStatus]:
            errors[f"sections-{index}-status"] = "Vui lòng chọn trạng thái."
        if not content:
            errors[f"sections-{index}-content"] = "Mỗi phần báo cáo phải có nội dung."

    if category_ids:
        valid_ids = {
            row[0]
            for row in ReportCategory.query.with_entities(ReportCategory.id)
            .filter(
                ReportCategory.project_id == project_id,
                ReportCategory.id.in_(category_ids),
                ReportCategory.deleted_at.is_(None),
            )
            .all()
        }
        for index in section_indexes:
            category_raw = form.get(f"sections-{index}-category_id", "").strip()
            if category_raw.isdigit() and int(category_raw) not in valid_ids:
                errors[f"sections-{index}-category_id"] = "Hạng mục phải thuộc dự án này."

    if errors:
        first_message = next(iter(errors.values()))
        raise ReportValidationError(first_message, errors)


def build_report_form_data(form, report=None):
    existing_by_category = {}
    if report:
        for section in report.sections:
            if section.deleted_at is None:
                existing_by_category[section.report_category_id] = section

    sections = []
    for sort_order, index in enumerate(_section_indexes(form)):
        category_raw = form.get(f"sections-{index}-category_id", "").strip()
        category_id = int(category_raw) if category_raw.isdigit() else None
        existing = existing_by_category.get(category_id)
        sections.append(
            SimpleNamespace(
                form_index=index,
                report_category_id=category_id,
                status=form.get(f"sections-{index}-status", "").strip(),
                content=form.get(f"sections-{index}-content", ""),
                sort_order=sort_order,
                deleted_at=None,
                attachments=existing.attachments if existing else [],
            )
        )

    return SimpleNamespace(
        report_date=form.get("report_date", ""),
        overall_status=form.get("overall_status", ""),
        highlight=form.get("highlight", ""),
        summary_note=form.get("summary_note", ""),
        sections=sections,
    )


def _section_indexes(form):
    indexes = set()
    for key in form.keys():
        if key.startswith("sections-"):
            parts = key.split("-")
            if len(parts) >= 3 and parts[1].isdigit():
                indexes.add(int(parts[1]))
    return sorted(indexes)
