import uuid
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from flask import current_app, request
from flask_login import current_user
from PIL import Image, UnidentifiedImageError
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

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
    UserRole,
)

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
IMAGE_FORMATS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}
MAX_IMAGE_WIDTH = 1920


class ReportValidationError(ValueError):
    def __init__(self, message, errors=None):
        super().__init__(message)
        self.errors = errors or {}


def accessible_projects_query():
    query = Project.query.filter(Project.deleted_at.is_(None))
    if current_user.role in {UserRole.REPORTER.value, UserRole.PROJECT_MANAGER.value}:
        query = query.join(Project.user_assignments).filter_by(user_id=current_user.id)
    return query.order_by(Project.code.asc(), Project.name.asc())


def reports_query():
    query = DailyReport.query.filter(DailyReport.deleted_at.is_(None)).join(DailyReport.project)
    if current_user.role in {UserRole.REPORTER.value, UserRole.PROJECT_MANAGER.value}:
        query = query.join(Project.user_assignments).filter_by(user_id=current_user.id)
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
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ReportValidationError("Ngày báo cáo phải đúng định dạng YYYY-MM-DD.") from exc


def create_report(project, form, files):
    validate_report_form(form, project.id)
    report_date = parse_report_date(form.get("report_date", "").strip())
    existing = DailyReport.query.filter_by(project_id=project.id, report_date=report_date).first()
    if existing:
        return existing, True

    report = DailyReport(project_id=project.id, created_by_user_id=current_user.id)
    add_with_sqlite_id(report)
    _assign_report_fields(report, form)
    report.report_date = report_date
    db.session.flush()

    section_inputs = parse_sections(form)
    _replace_sections(report, section_inputs)
    db.session.flush()
    _save_section_uploads(report, files)
    audit("report.create", "DailyReport", report.id, new_values=report_snapshot(report))
    db.session.commit()
    return report, False


def update_report(report, form, files):
    validate_report_form(form, report.project_id)
    old_values = report_snapshot(report)
    report.report_date = parse_report_date(form.get("report_date", "").strip())

    duplicate = DailyReport.query.filter(
        DailyReport.project_id == report.project_id,
        DailyReport.report_date == report.report_date,
        DailyReport.id != report.id,
    ).first()
    if duplicate:
        raise ReportValidationError("Dự án đã có báo cáo cho ngày này.")

    _assign_report_fields(report, form)
    report.updated_by_user_id = current_user.id
    _replace_sections(report, parse_sections(form))
    db.session.flush()
    _save_section_uploads(report, files)
    audit("report.update", "DailyReport", report.id, old_values, report_snapshot(report))
    db.session.commit()
    return report


def delete_report(report):
    old_values = report_snapshot(report)
    report.deleted_at = db.func.now()
    audit("report.delete", "DailyReport", report.id, old_values, {"deleted_at": True})
    db.session.commit()


def delete_attachment(attachment):
    attachment.deleted_at = db.func.now()
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


def _store_attachment(report, section, upload: FileStorage):
    original_filename = secure_filename(upload.filename or "")
    extension = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else ""
    if extension not in ALLOWED_EXTENSIONS:
        raise ReportValidationError("Chỉ cho phép tệp jpg, jpeg, png và webp.")

    try:
        image = Image.open(upload.stream)
        image.verify()
        upload.stream.seek(0)
        image = Image.open(upload.stream)
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ReportValidationError("Tệp tải lên không phải ảnh hợp lệ.") from exc

    image_format = image.format
    if image_format not in IMAGE_FORMATS:
        raise ReportValidationError("Chỉ cho phép tệp jpg, jpeg, png và webp.")
    stored_extension = IMAGE_FORMATS[image_format]

    image = _normalize_image(image, stored_extension)
    if image.width > MAX_IMAGE_WIDTH:
        new_height = int(image.height * (MAX_IMAGE_WIDTH / image.width))
        image = image.resize((MAX_IMAGE_WIDTH, new_height), Image.Resampling.LANCZOS)

    stored_filename = f"{uuid.uuid4().hex}.{stored_extension}"
    target_dir = _attachment_dir(report, section)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / stored_filename
    save_format = "JPEG" if stored_extension == "jpg" else stored_extension.upper()
    image.save(target_path, format=save_format, quality=88, optimize=True)

    attachment = ReportAttachment(
        daily_report_section_id=section.id,
        original_filename=original_filename or upload.filename,
        stored_filename=stored_filename,
        file_path=str(target_path.relative_to(Path(current_app.config["UPLOAD_ROOT"]))),
        mime_type=Image.MIME.get(save_format, f"image/{stored_extension}"),
        file_size=target_path.stat().st_size,
        image_width=image.width,
        image_height=image.height,
        uploaded_by_user_id=current_user.id,
    )
    add_with_sqlite_id(attachment)
    return attachment


def _normalize_image(image, stored_extension):
    if stored_extension == "jpg":
        if image.mode not in ("RGB", "L"):
            return image.convert("RGB")
        return image.copy()
    if stored_extension == "png":
        return image.copy()
    return image.copy()


def _attachment_dir(report, section):
    report_date = report.report_date
    slug = secure_filename(report.project.code or report.project.name).lower() or str(report.project_id)
    root = Path(current_app.config["UPLOAD_ROOT"])
    return (
        root
        / f"project_{report.project_id}_{slug}"
        / f"{report_date:%Y}"
        / f"{report_date:%m}"
        / f"{report_date:%d}"
        / f"report_{report.id}"
        / f"section_{section.id}"
    )


def validate_report_form(form, project_id):
    errors = {}
    report_date_raw = form.get("report_date", "").strip()
    overall_status = form.get("overall_status", "").strip()
    highlight = form.get("highlight", "").strip()

    if not report_date_raw:
        errors["report_date"] = "Vui lòng chọn ngày báo cáo."
    else:
        try:
            datetime.strptime(report_date_raw, "%Y-%m-%d").date()
        except ValueError:
            errors["report_date"] = "Ngày báo cáo phải đúng định dạng YYYY-MM-DD."

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
