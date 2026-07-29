"""Direct-to-object-storage upload sessions used only by Daily Reports."""
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import delete, or_, select, update

from app.admin.services import add_with_sqlite_id
from app.extensions import db
from app.models import (CompanyMediaFile, DownloadEvent, MediaProcessingJob,
                        ProjectDocumentFile, ReportAttachment,
                        StorageDerivative, StorageObject, UploadBatch,
                        UploadBatchItem, UploadSelectionSession)
from app.storage.exceptions import (StorageAuthorizationError, StorageNotFoundError,
                                    StorageValidationError)
from app.storage.keys import build_original_key
from app.storage.providers import get_storage_provider
from app.storage.quota import ensure_storage_capacity
from app.storage.services import _validate_head
from app.storage.validation import validate_file_metadata
from app.reports.constants import MAX_ATTACHMENTS_PER_REPORT_SECTION

SCOPE = ("daily_reports", "project")


@dataclass(frozen=True)
class NoAttachments:
    """Canonical report request with no selected attachment files."""


@dataclass(frozen=True)
class CompletedUpload:
    session: UploadSelectionSession
    items: list
    mapping: dict


class UploadSessionCleanupError(RuntimeError):
    """Raised when a selected upload session cannot be cleaned completely."""


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _session(user, project_id, session_id, *, allow_finalized=False):
    session = db.session.get(UploadSelectionSession, session_id)
    if not session or session.created_by_id != user.id or (session.module_type, session.target_type, session.target_id) != (*SCOPE, int(project_id)):
        raise StorageAuthorizationError("Phiên tải ảnh không hợp lệ.")
    if session.expires_at <= _now() and session.status not in {"finalized", "cancelled", "expired"}:
        session.status = "expired"; db.session.commit()
    if session.status in {"cancelled", "expired"} or (session.status == "finalized" and not allow_finalized):
        raise StorageValidationError("Phiên tải ảnh đã hết hạn hoặc đã đóng.")
    return session


def create_session(*, user, project_id, declared_files, declared_size_bytes):
    try: declared_files, declared_size_bytes = int(declared_files), int(declared_size_bytes)
    except (TypeError, ValueError): raise StorageValidationError("Thông tin tải ảnh không hợp lệ.")
    if not 1 <= declared_files <= int(_cfg("DAILY_REPORT_MAX_FILES")) or not 1 <= declared_size_bytes <= int(_cfg("DAILY_REPORT_MAX_TOTAL_BYTES")):
        raise StorageValidationError("Tối đa 30 ảnh và 300 MB cho một báo cáo.")
    session = UploadSelectionSession(module_type=SCOPE[0], target_type=SCOPE[1], target_id=int(project_id), created_by_id=user.id,
        declared_files=declared_files, declared_size_bytes=declared_size_bytes, status="pending", expires_at=_now() + timedelta(seconds=int(_cfg("DAILY_REPORT_SESSION_TTL_SECONDS"))))
    add_with_sqlite_id(session); db.session.commit()
    return session_payload(session)


def session_payload(session):
    items = UploadBatchItem.query.join(UploadBatch).filter(UploadBatch.selection_session_id == session.id).all()
    return {"upload_session_id": session.id, "status": session.status, "expires_at": session.expires_at.isoformat(),
            "items": [{"id": item.id, "client_file_id": item.client_file_id, "client_section_id": item.client_section_id,
                       "status": item.status, "filename": item.original_filename} for item in items]}


def presign(*, user, project_id, session_id, files, provider=None):
    session = _session(user, project_id, session_id)
    files = list(files or [])
    if not files or len(files) > int(_cfg("DAILY_REPORT_MAX_FILES")):
        raise StorageValidationError("Danh sách ảnh không hợp lệ.")
    if session.status not in {"pending", "uploading", "ready"}:
        raise StorageValidationError("Phiên tải ảnh không sẵn sàng.")
    ids = [str(row.get("client_file_id", "")) for row in files if isinstance(row, dict)]
    if len(ids) != len(files) or not all(ids) or len(set(ids)) != len(ids):
        raise StorageValidationError("client_file_id phải duy nhất.")
    metas = []
    for row in files:
        if not isinstance(row, dict) or not str(row.get("client_section_id", "")).strip()[:80]:
            raise StorageValidationError("client_section_id là bắt buộc.")
        meta = validate_file_metadata(row.get("filename"), row.get("mime_type"), row.get("size"), row.get("checksum_sha256"), module_type="daily_reports")
        if meta["file_ext"] not in {"jpg", "png", "webp"}:
            raise StorageValidationError("Chỉ cho phép tệp jpg, jpeg, png hoặc webp.")
        if meta["file_size"] > int(_cfg("DAILY_REPORT_MAX_FILE_BYTES")):
            raise StorageValidationError("Mỗi ảnh không được vượt quá 25 MB.")
        metas.append(meta)
    total = sum(row["file_size"] for row in metas)
    if session.presigned_files + len(files) > min(session.declared_files, int(_cfg("DAILY_REPORT_MAX_FILES"))) or session.presigned_size_bytes + total > min(session.declared_size_bytes, int(_cfg("DAILY_REPORT_MAX_TOTAL_BYTES"))):
        raise StorageValidationError("Ảnh vượt quá giới hạn của phiên tải.")
    ensure_storage_capacity(total)
    provider = provider or get_storage_provider()
    batch = UploadBatch(module_type=SCOPE[0], target_type=SCOPE[1], target_id=int(project_id), created_by_id=user.id, selection_session_id=session.id, total_files=len(files), status="uploading")
    add_with_sqlite_id(batch); db.session.flush(); output = []
    for row, meta in zip(files, metas):
        key = build_original_key("daily-reports", uuid4().hex, meta["filename"], _cfg("STORAGE_PREFIX"))
        obj = StorageObject(bucket=_cfg("STORAGE_BUCKET"), object_key=key, storage_module="daily-reports", original_filename=meta["filename"], mime_type=meta["mime_type"], file_ext=meta["file_ext"], file_size=meta["file_size"], checksum_sha256=meta["checksum_sha256"], uploaded_by_id=user.id, upload_status="pending")
        add_with_sqlite_id(obj); db.session.flush()
        item = UploadBatchItem(upload_batch_id=batch.id, storage_object_id=obj.id, client_file_id=str(row["client_file_id"]), client_section_id=str(row["client_section_id"]).strip()[:80], original_filename=meta["filename"], mime_type=meta["mime_type"], file_size=meta["file_size"], status="accepted")
        add_with_sqlite_id(item); db.session.flush()
        upload = provider.create_presigned_put(obj.bucket, obj.object_key, obj.mime_type, obj.file_size, int(_cfg("DAILY_REPORT_PRESIGN_TTL_SECONDS")), metadata={"sha256": obj.checksum_sha256} if obj.checksum_sha256 else None)
        batch.accepted_files += 1
        output.append({"client_file_id": item.client_file_id, "upload_batch_item_id": item.id, "storage_object_id": obj.id, **upload})
    session.presigned_files += len(files); session.presigned_size_bytes += total; session.status = "uploading"; db.session.commit()
    return {"upload_session_id": session.id, "items": output}


def v2_presign(*, user, project_id, session_id, files, provider=None):
    """Idempotent V2 presign: one object/item for each browser file UUID.

    Unlike the legacy form flow, retries reuse the original database records
    and only mint a fresh PUT URL.  This prevents duplicate orphan objects.
    """
    session = _session(user, project_id, session_id)
    files = list(files or [])
    if not files or len(files) > int(_cfg("DAILY_REPORT_MAX_FILES")):
        raise StorageValidationError("Danh sách ảnh không hợp lệ.")
    ids = [str(row.get("client_file_id", "")) for row in files if isinstance(row, dict)]
    if len(ids) != len(files) or not all(ids) or len(set(ids)) != len(ids):
        raise StorageValidationError("client_file_id phải duy nhất.")
    if session.status not in {"pending", "uploading", "ready"}:
        raise StorageValidationError("Phiên tải ảnh không sẵn sàng.")
    provider = provider or get_storage_provider()
    existing = {item.client_file_id: item for item in UploadBatchItem.query.join(UploadBatch).filter(
        UploadBatch.selection_session_id == session.id).all()}
    if len(existing) + len([file_id for file_id in ids if file_id not in existing]) > session.declared_files:
        raise StorageValidationError("Ảnh vượt quá giới hạn của phiên tải.")
    per_section = {}
    for item in existing.values():
        per_section[item.client_section_id] = per_section.get(item.client_section_id, 0) + 1
    for row in files:
        client_file_id = str(row.get("client_file_id", "")) if isinstance(row, dict) else ""
        client_section_id = str(row.get("client_section_id", "")).strip()[:80] if isinstance(row, dict) else ""
        prior = existing.get(client_file_id)
        if prior and prior.client_section_id != client_section_id:
            raise StorageValidationError("Thông tin ảnh không khớp với lần tải trước.")
        if not prior:
            per_section[client_section_id] = per_section.get(client_section_id, 0) + 1
    if any(count > MAX_ATTACHMENTS_PER_REPORT_SECTION for count in per_section.values()):
        raise StorageValidationError("Mỗi đầu mục chỉ được có tối đa 10 ảnh.")
    output = []
    for row in files:
        if not isinstance(row, dict) or not str(row.get("client_section_id", "")).strip()[:80]:
            raise StorageValidationError("client_section_id là bắt buộc.")
        meta = validate_file_metadata(row.get("filename"), row.get("mime_type"), row.get("size"), row.get("checksum_sha256"), module_type="daily_reports")
        if meta["file_ext"] not in {"jpg", "png", "webp"}:
            raise StorageValidationError("Chỉ cho phép tệp jpg, jpeg, png hoặc webp.")
        if meta["file_size"] > int(_cfg("DAILY_REPORT_MAX_FILE_BYTES")):
            raise StorageValidationError("Mỗi ảnh không được vượt quá 25 MB.")
        item = existing.get(str(row["client_file_id"]))
        if item:
            if (item.client_section_id != str(row["client_section_id"]).strip()[:80] or item.file_size != meta["file_size"]
                    or item.original_filename != meta["filename"]):
                raise StorageValidationError("Thông tin ảnh không khớp với lần tải trước.")
            if item.status == "completed":
                output.append({"client_file_id": item.client_file_id, "upload_batch_item_id": item.id, "status": "completed"})
                continue
            item.status = "accepted"; item.error_message = None
            obj = item.storage_object
        else:
            if session.presigned_size_bytes + meta["file_size"] > session.declared_size_bytes:
                raise StorageValidationError("Ảnh vượt quá giới hạn của phiên tải.")
            ensure_storage_capacity(meta["file_size"])
            batch = UploadBatch(module_type=SCOPE[0], target_type=SCOPE[1], target_id=int(project_id), created_by_id=user.id,
                selection_session_id=session.id, total_files=1, accepted_files=1, status="uploading")
            add_with_sqlite_id(batch); db.session.flush()
            key = build_original_key("daily-reports", uuid4().hex, meta["filename"], _cfg("STORAGE_PREFIX"))
            obj = StorageObject(bucket=_cfg("STORAGE_BUCKET"), object_key=key, storage_module="daily-reports", original_filename=meta["filename"], mime_type=meta["mime_type"], file_ext=meta["file_ext"], file_size=meta["file_size"], checksum_sha256=meta["checksum_sha256"], uploaded_by_id=user.id, upload_status="pending")
            add_with_sqlite_id(obj); db.session.flush()
            item = UploadBatchItem(upload_batch_id=batch.id, storage_object_id=obj.id, client_file_id=str(row["client_file_id"]), client_section_id=str(row["client_section_id"]).strip()[:80], original_filename=meta["filename"], mime_type=meta["mime_type"], file_size=meta["file_size"], status="accepted")
            add_with_sqlite_id(item); db.session.flush()
            session.presigned_files += 1; session.presigned_size_bytes += meta["file_size"]
        upload = provider.create_presigned_put(obj.bucket, obj.object_key, obj.mime_type, obj.file_size,
            int(_cfg("DAILY_REPORT_PRESIGN_TTL_SECONDS")), metadata={"sha256": obj.checksum_sha256} if obj.checksum_sha256 else None)
        output.append({"client_file_id": item.client_file_id, "upload_batch_item_id": item.id, "storage_object_id": obj.id, "status": "presigned", **upload})
    session.status = "uploading"
    db.session.commit()
    return {"upload_session_id": session.id, "items": output}


def complete(*, user, project_id, session_id, item_id, checksum_sha256=None, provider=None):
    session = _session(user, project_id, session_id)
    item = db.session.get(UploadBatchItem, item_id)
    if not item or item.upload_batch.selection_session_id != session.id or not item.storage_object:
        raise StorageAuthorizationError("Upload item không thuộc phiên này.")
    if item.status == "completed" and item.storage_object.upload_status == "uploaded":
        return {"upload_batch_item_id": item.id, "status": "completed", "idempotent": True}
    if item.status not in {"accepted", "uploading"}: raise StorageValidationError("Upload item không thể hoàn tất.")
    try:
        _validate_head(item.storage_object, (provider or get_storage_provider()).head_object(item.storage_object.bucket, item.storage_object.object_key), checksum_sha256)
    except (StorageNotFoundError, StorageValidationError):
        item.status = "failed"; item.error_message = "Không thể xác minh ảnh đã tải."; db.session.commit(); raise
    item.status = "completed"; item.storage_object.upload_status = "uploaded"; item.storage_object.completed_at = _now(); item.error_message = None
    if all(row.status == "completed" for row in UploadBatchItem.query.join(UploadBatch).filter(UploadBatch.selection_session_id == session.id)):
        session.status = "ready"
    db.session.commit()
    return {"upload_batch_item_id": item.id, "status": "completed", "idempotent": False}


def parse_report_attachment_manifest(*, user, project_id, section_inputs, form):
    """Lock and validate the only attachment manifest accepted by report save.

    A complete session must be consumed as a whole.  This deliberately avoids
    orphaned uploaded originals and makes retry-after-duplicate-date safe.
    """
    marker = str(form.get("direct_upload_expected", "")).strip()
    selected_raw = str(form.get("direct_upload_selected_count", "0")).strip()
    try:
        selected_count = int(selected_raw)
    except (TypeError, ValueError) as exc:
        raise StorageValidationError("Thông tin ảnh đính kèm không hợp lệ.") from exc
    if selected_count < 0:
        raise StorageValidationError("Thông tin ảnh đính kèm không hợp lệ.")
    session_id = form.get("upload_session_id", type=int) if hasattr(form, "get") else None
    raw_manifest = form.get("attachment_manifest", "").strip()
    if not raw_manifest:
        # Native no-JS text-only forms remain valid. JavaScript submissions
        # always include the explicit canonical empty manifest below.
        if selected_count == 0 and not session_id and marker in {"", "0"}:
            return NoAttachments()
        raise StorageValidationError("Ảnh đính kèm chưa được tải lên hoàn tất. Vui lòng thử lại.")
    try:
        manifest = json.loads(raw_manifest)
    except (TypeError, ValueError) as exc:
        raise StorageValidationError("Ảnh đính kèm chưa được tải lên hoàn tất. Vui lòng thử lại.") from exc
    if not isinstance(manifest, dict) or not isinstance(manifest.get("attachments"), list):
        raise StorageValidationError("Ảnh đính kèm chưa được tải lên hoàn tất. Vui lòng thử lại.")
    attachments = manifest["attachments"]
    manifest_session_id = manifest.get("upload_session_id")
    if selected_count == 0:
        if marker not in {"", "0"} or session_id is not None or manifest_session_id is not None or attachments:
            raise StorageValidationError("Ảnh đính kèm chưa được tải lên hoàn tất. Vui lòng thử lại.")
        return NoAttachments()
    if marker != "1" or not session_id or manifest_session_id != session_id or not attachments or len(attachments) != selected_count or len(attachments) > int(_cfg("DAILY_REPORT_MAX_FILES")):
        raise StorageValidationError("Danh sách ảnh đính kèm không hợp lệ.")

    # Keep the lock until the report transaction commits or rolls back.
    session = db.session.scalar(select(UploadSelectionSession).where(
        UploadSelectionSession.id == session_id,
        UploadSelectionSession.created_by_id == user.id,
        UploadSelectionSession.module_type == SCOPE[0],
        UploadSelectionSession.target_type == SCOPE[1],
        UploadSelectionSession.target_id == int(project_id),
    ).with_for_update())
    if not session:
        raise StorageAuthorizationError("Phiên tải ảnh không hợp lệ.")
    if session.expires_at <= _now() or session.status != "ready":
        raise StorageValidationError("Ảnh đính kèm chưa được tải lên hoàn tất. Vui lòng thử lại.")

    valid_sections = {str(section.get("client_section_id", "")): section for section in section_inputs}
    if "" in valid_sections or len(valid_sections) != len(section_inputs):
        raise StorageValidationError("Mã phần báo cáo không hợp lệ.")
    ids, mapping, per_section = [], {}, {}
    for attachment in attachments:
        if not isinstance(attachment, dict):
            raise StorageValidationError("Danh sách ảnh đính kèm không hợp lệ.")
        item_id = attachment.get("upload_item_id")
        client_section_id = attachment.get("client_section_id")
        sort_order = attachment.get("sort_order")
        if isinstance(item_id, bool) or not isinstance(item_id, int) or not isinstance(client_section_id, str) or not client_section_id or isinstance(sort_order, bool) or not isinstance(sort_order, int) or sort_order < 0:
            raise StorageValidationError("Danh sách ảnh đính kèm không hợp lệ.")
        if client_section_id not in valid_sections:
            raise StorageValidationError("Ảnh không thuộc phần báo cáo đã chọn.")
        ids.append(item_id); mapping[item_id] = valid_sections[client_section_id]
        per_section[client_section_id] = per_section.get(client_section_id, 0) + 1
    if len(ids) != len(set(ids)):
        raise StorageValidationError("Danh sách ảnh đính kèm không hợp lệ.")
    if any(count > MAX_ATTACHMENTS_PER_REPORT_SECTION for count in per_section.values()):
        raise StorageValidationError("Mỗi phần chỉ được có tối đa 10 ảnh.")

    items = db.session.scalars(select(UploadBatchItem).join(UploadBatch).where(
        UploadBatch.selection_session_id == session.id,
    ).with_for_update()).all()
    item_by_id = {item.id: item for item in items}
    # No item in this session may be silently skipped or reused.
    if set(ids) != set(item_by_id) or any(
        item.status != "completed" or item.finalized_at is not None or not item.storage_object
        or item.storage_object.upload_status != "uploaded" for item in items
    ):
        raise StorageValidationError("Ảnh đính kèm chưa được tải lên hoàn tất. Vui lòng thử lại.")
    if sum(item.file_size for item in items) > int(_cfg("DAILY_REPORT_MAX_TOTAL_BYTES")):
        raise StorageValidationError("Tổng dung lượng ảnh vượt giới hạn.")
    for item in items:
        expected = next(row["client_section_id"] for row in attachments if row["upload_item_id"] == item.id)
        if item.client_section_id != expected:
            raise StorageValidationError("Ảnh không thuộc phần báo cáo đã chọn.")
    return CompletedUpload(session=session, items=items, mapping=mapping)


def session_items_for_finalize(*, user, project_id, session_id=None, section_inputs, form):
    """Backward-compatible entry point for callers not yet using the parser."""
    return parse_report_attachment_manifest(
        user=user, project_id=project_id, section_inputs=section_inputs, form=form,
    )


def finalize_session(session):
    session.status = "finalized"; session.completed_at = _now()


def cancel_upload_session_for_actor(*, actor, project, session_id, provider=None):
    """Cancel and clean exactly one Daily Reports upload session.

    This is deliberately distinct from ``cleanup_expired_sessions``.  A web
    request is never allowed to select other users' cancelled or expired
    sessions merely because they are eligible for the trusted global job.
    """
    from app.auth.permissions import can_create_report, project_accepts_report_mutation
    from app.project_memberships import is_project_admin

    if not project_accepts_report_mutation(project) or not can_create_report(actor, project.id):
        raise StorageAuthorizationError("Bạn không có quyền tạo báo cáo cho dự án này.")

    session = db.session.scalar(select(UploadSelectionSession).where(
        UploadSelectionSession.id == session_id,
    ).with_for_update())
    if not session or (session.module_type, session.target_type, session.target_id) != (*SCOPE, project.id):
        raise StorageAuthorizationError("Phiên tải ảnh không hợp lệ.")
    if session.created_by_id != actor.id and not is_project_admin(actor):
        raise StorageAuthorizationError("Phiên tải ảnh không hợp lệ.")
    if session.status == "finalized":
        raise StorageValidationError("Không thể hủy phiên tải ảnh đã hoàn tất.")

    if session.status not in {"cancelled", "expired"}:
        session.status = "expired" if session.expires_at <= _now() else "cancelled"

    # Persist eligibility before touching provider bytes.  If the provider is
    # unavailable, the trusted bounded cleanup can discover and retry this
    # selected session instead of losing the cancellation state on rollback.
    db.session.commit()

    cleanup = cleanup_upload_session_objects(session, provider=provider)
    db.session.commit()
    return session, cleanup


def cleanup_upload_session_objects(session, *, provider=None):
    """Clean objects proven to be owned exclusively by one session.

    The caller owns transaction finalization.  Bytes are removed before their
    metadata so a retry can safely treat a missing object as already removed.
    If anything cannot safely be removed, no selected-session metadata is
    changed and the caller receives an explicit incomplete result.
    """
    batches = UploadBatch.query.filter_by(selection_session_id=session.id).all()
    batch_ids = [batch.id for batch in batches]
    items = UploadBatchItem.query.filter(UploadBatchItem.upload_batch_id.in_(batch_ids or [-1])).all()
    blocked_item_ids = []
    objects_by_id = {}
    for item in items:
        if item.finalized_at is not None:
            blocked_item_ids.append(item.id)
            continue
        if item.storage_object and not _storage_object_is_exclusive_to_session(item.storage_object_id, session.id):
            blocked_item_ids.append(item.id)
            continue
        if item.storage_object:
            objects_by_id[item.storage_object_id] = item.storage_object

    summary = {
        "session_id": session.id,
        "batches": len(batches),
        "items": len(items),
        "storage_objects": len(objects_by_id),
        "complete": not blocked_item_ids,
        "blocked_item_ids": blocked_item_ids,
    }
    if blocked_item_ids:
        return summary

    storage_ids = list(objects_by_id)
    derivatives = StorageDerivative.query.filter(
        StorageDerivative.storage_object_id.in_(storage_ids or [-1]),
    ).all()
    provider = provider or get_storage_provider()
    _delete_session_storage_bytes(provider, [*derivatives, *objects_by_id.values()])

    derivative_ids = [derivative.id for derivative in derivatives]
    if derivative_ids:
        db.session.execute(update(DownloadEvent).where(
            DownloadEvent.derivative_id.in_(derivative_ids)
        ).values(derivative_id=None))
        db.session.execute(delete(StorageDerivative).where(
            StorageDerivative.id.in_(derivative_ids)
        ))
    if storage_ids:
        db.session.execute(delete(MediaProcessingJob).where(
            MediaProcessingJob.storage_object_id.in_(storage_ids)
        ))
        db.session.execute(update(DownloadEvent).where(
            DownloadEvent.storage_object_id.in_(storage_ids)
        ).values(storage_object_id=None))
    if items:
        db.session.execute(delete(UploadBatchItem).where(
            UploadBatchItem.id.in_([item.id for item in items])
        ))
    if batch_ids:
        db.session.execute(delete(UploadBatch).where(UploadBatch.id.in_(batch_ids)))
    if storage_ids:
        db.session.execute(delete(StorageObject).where(StorageObject.id.in_(storage_ids)))
    db.session.flush()
    return summary


def _storage_object_is_exclusive_to_session(storage_object_id, session_id):
    """Return false whenever another live record could own this object."""
    if db.session.scalar(select(UploadBatchItem.id).join(UploadBatch).where(
        UploadBatchItem.storage_object_id == storage_object_id,
        UploadBatch.selection_session_id != session_id,
    ).limit(1)):
        return False
    if db.session.scalar(select(ReportAttachment.id).where(
        ReportAttachment.storage_object_id == storage_object_id,
    ).limit(1)):
        return False
    if db.session.scalar(select(ProjectDocumentFile.id).where(
        ProjectDocumentFile.storage_object_id == storage_object_id,
    ).limit(1)):
        return False
    return not db.session.scalar(select(CompanyMediaFile.id).where(
        CompanyMediaFile.storage_object_id == storage_object_id,
    ).limit(1))


def _delete_session_storage_bytes(provider, objects):
    failures = []
    for obj in objects:
        try:
            provider.delete_object(obj.bucket, obj.object_key)
        except StorageNotFoundError:
            continue
        except Exception as exc:
            failures.append(f"{obj.bucket}/{obj.object_key}: {exc}")
    if failures:
        raise UploadSessionCleanupError(
            "Không thể xóa toàn bộ tệp của phiên tải ảnh: " + "; ".join(failures)
        )


def cleanup_expired_sessions(*, dry_run=True, provider=None, batch_size=100):
    """Trusted, bounded global cleanup for expired/cancelled report sessions."""
    try:
        batch_size = max(1, int(batch_size))
    except (TypeError, ValueError) as exc:
        raise ValueError("batch_size must be a positive integer") from exc
    sessions = UploadSelectionSession.query.filter(
        UploadSelectionSession.module_type == SCOPE[0],
        UploadSelectionSession.target_type == SCOPE[1],
        UploadSelectionSession.status != "finalized",
        or_(UploadSelectionSession.expires_at <= _now(), UploadSelectionSession.status == "cancelled"),
    ).order_by(UploadSelectionSession.id.asc()).limit(batch_size).all()
    result = {"matched": len(sessions), "cleaned": 0, "partial": 0, "failed": 0, "dry_run": dry_run}
    if dry_run:
        return result
    for session in sessions:
        try:
            if session.status != "cancelled":
                session.status = "expired"
            summary = cleanup_upload_session_objects(session, provider=provider)
            db.session.commit()
            if summary["complete"]:
                result["cleaned"] += 1
            else:
                result["partial"] += 1
        except UploadSessionCleanupError:
            db.session.rollback()
            result["failed"] += 1
    return result


def _cfg(name):
    from flask import current_app
    return current_app.config[name]
