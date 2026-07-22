from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func

from app.extensions import db
from app.models import StorageObject, UploadBatch, UploadBatchItem, UploadSelectionSession, UserRole
from app.storage.exceptions import StorageAuthorizationError, StorageNotFoundError, StorageValidationError
from app.storage.keys import build_original_key, normalize_storage_module
from app.storage.providers import get_storage_provider
from app.storage.validation import validate_file_metadata


VALID_SCOPES = {("project_documents", "folder"), ("company_media", "album")}


def create_upload_selection_session(*, user, module_type, target_type, target_id, declared_files, declared_size_bytes):
    _require_active_user(user)
    if (module_type, target_type) not in VALID_SCOPES: raise StorageValidationError("Scope upload không hợp lệ.")
    try: declared_files, declared_size_bytes = int(declared_files), int(declared_size_bytes)
    except (TypeError, ValueError): raise StorageValidationError("Thông tin lựa chọn không hợp lệ.")
    if declared_files < 1 or declared_files > int(_config("UPLOAD_SELECTION_MAX_FILES")) or declared_size_bytes < 1 or declared_size_bytes > int(_config("UPLOAD_SELECTION_MAX_BYTES")):
        raise StorageValidationError("Lựa chọn vượt quá giới hạn 500 tệp hoặc 2 GB.")
    session = UploadSelectionSession(module_type=module_type, target_type=target_type, target_id=int(target_id), created_by_id=user.id, declared_files=declared_files, declared_size_bytes=declared_size_bytes, expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=int(_config("UPLOAD_SELECTION_TTL_SECONDS"))))
    _add(session); db.session.commit(); return {"selection_session_id": session.id, "expires_at": session.expires_at.isoformat()}

def finalize_upload_selection_session(*, user, selection_session_id, module_type, target_type, target_id):
    session = _selection_session(user, selection_session_id, module_type, target_type, target_id)
    session.status = "completed"; session.completed_at = datetime.now(timezone.utc).replace(tzinfo=None); db.session.commit()
    return {"selection_session_id": session.id, "status": session.status}

def create_upload_batch_presign(*, user, module_type, target_type, target_id, files, selection_session_id=None, provider=None):
    _require_active_user(user)
    if (module_type, target_type) not in VALID_SCOPES:
        raise StorageValidationError("Scope upload không hợp lệ.")
    _check_phase_one_scope(user)
    files = list(files or [])
    max_files = int(_config("STORAGE_MAX_FILES_PER_BATCH"))
    if not files or len(files) > max_files:
        raise StorageValidationError("Số lượng file trong batch không hợp lệ.")
    declared_total = sum(_safe_size(item.get("size")) for item in files if isinstance(item, dict))
    if declared_total > int(_config("STORAGE_MAX_BATCH_SIZE_MB")) * 1024 * 1024:
        raise StorageValidationError("Tổng dung lượng batch vượt quá giới hạn.")
    if any(_safe_size(item.get("size")) > int(_config("UPLOAD_SINGLE_FILE_MAX_BYTES")) for item in files if isinstance(item, dict)):
        raise StorageValidationError("Một tệp vượt quá giới hạn 300 MB.")
    selection = _selection_session(user, selection_session_id, module_type, target_type, target_id) if selection_session_id else None
    if selection and (selection.presigned_files + len(files) > selection.declared_files or selection.presigned_size_bytes + declared_total > selection.declared_size_bytes):
        raise StorageValidationError("Batch vượt số lượng hoặc dung lượng đã khai báo.")
    from app.storage.quota import ensure_storage_capacity
    try: ensure_storage_capacity(declared_total)
    except ValueError as exc: raise StorageValidationError(str(exc))
    client_ids = [str(item.get("client_file_id", "")) for item in files if isinstance(item, dict)]
    if len(set(client_ids)) != len(client_ids) or any(not value for value in client_ids):
        raise StorageValidationError("client_file_id phải duy nhất và không được để trống.")

    provider = provider or get_storage_provider()
    storage_module = normalize_storage_module(module_type)
    batch = UploadBatch(module_type=module_type, target_type=target_type, target_id=int(target_id), created_by_id=user.id, selection_session_id=selection.id if selection else None, total_files=len(files))
    _add(batch)
    db.session.flush()
    response_items = []
    for item in files:
        client_file_id = str(item["client_file_id"])
        try:
            meta = validate_file_metadata(item.get("filename"), item.get("mime_type"), item.get("size"), item.get("checksum_sha256"), module_type=module_type)
            object_key = build_original_key(storage_module, uuid4().hex, meta["filename"], _config("STORAGE_PREFIX"))
            storage_object = StorageObject(bucket=_config("STORAGE_BUCKET"), object_key=object_key, storage_module=storage_module, original_filename=meta["filename"], mime_type=meta["mime_type"], file_ext=meta["file_ext"], file_size=meta["file_size"], checksum_sha256=meta["checksum_sha256"], uploaded_by_id=user.id)
            _add(storage_object)
            db.session.flush()
            batch_item = UploadBatchItem(upload_batch_id=batch.id, storage_object_id=storage_object.id, client_file_id=client_file_id, original_filename=meta["filename"], mime_type=meta["mime_type"], file_size=meta["file_size"], status="accepted")
            _add(batch_item)
            # SQLite/SQLAlchemy can defer INSERT until commit; response contract
            # requires this id before the browser starts direct upload.
            db.session.flush()
            upload = provider.create_presigned_upload(storage_object.bucket, storage_object.object_key, storage_object.mime_type, storage_object.file_size, _config("STORAGE_UPLOAD_URL_TTL_SECONDS"), metadata={"sha256": storage_object.checksum_sha256} if storage_object.checksum_sha256 else None)
            batch.accepted_files += 1
            response_items.append({"client_file_id": client_file_id, "accepted": True, "upload_batch_item_id": batch_item.id, "storage_object_id": storage_object.id, **upload})
        except StorageValidationError as exc:
            rejected = UploadBatchItem(upload_batch_id=batch.id, client_file_id=client_file_id, original_filename=str(item.get("filename", ""))[:255], mime_type=str(item.get("mime_type", ""))[:255], file_size=_safe_size(item.get("size")), status="rejected", error_message=str(exc))
            _add(rejected)
            batch.failed_files += 1
            response_items.append({"client_file_id": client_file_id, "accepted": False, "error": str(exc)})
    batch.status = "uploading" if batch.accepted_files else "failed"
    if selection:
        selection.presigned_files += batch.accepted_files; selection.presigned_size_bytes += sum(item.storage_object.file_size for item in batch.items if item.storage_object_id)
    db.session.commit()
    return {"upload_batch_id": batch.id, "status": batch.status, "items": response_items}

def _selection_session(user, selection_session_id, module_type, target_type, target_id):
    if not selection_session_id: raise StorageValidationError("selection_session_id là bắt buộc.")
    session = db.session.get(UploadSelectionSession, selection_session_id)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if not session or session.created_by_id != user.id or session.module_type != module_type or session.target_type != target_type or session.target_id != int(target_id): raise StorageAuthorizationError("Upload selection không hợp lệ.")
    if session.status != "pending" or session.expires_at <= now:
        if session.status == "pending": session.status = "expired"; db.session.commit()
        raise StorageValidationError("Upload selection đã hết hạn hoặc hoàn tất.")
    return session


def complete_upload_item(*, user, upload_batch_item_id, reported_etag=None, checksum_sha256=None, provider=None):
    _require_active_user(user)
    item = db.session.get(UploadBatchItem, upload_batch_item_id)
    if item is None or item.storage_object is None:
        raise StorageNotFoundError("Upload item không tồn tại.")
    _check_item_owner_or_admin(user, item)
    storage_object = item.storage_object
    if storage_object.upload_status == "active" and item.status == "completed":
        return _complete_response(item, idempotent=True)
    if storage_object.upload_status != "pending" or item.status not in {"accepted", "uploading"}:
        raise StorageValidationError("Upload item không ở trạng thái có thể hoàn tất.")
    provider = provider or get_storage_provider()
    try:
        head = provider.head_object(storage_object.bucket, storage_object.object_key)
        _validate_head(storage_object, head, checksum_sha256)
    except (StorageNotFoundError, StorageValidationError):
        _mark_item_failed(item, terminal=True)
        db.session.commit()
        raise
    storage_object.upload_status = "active"
    storage_object.completed_at = datetime.now(timezone.utc)
    item.status = "completed"
    item.error_message = None
    _refresh_batch(item.upload_batch)
    db.session.commit()
    return _complete_response(item)


def create_signed_download_url(*, user, storage_object_id, disposition=None, provider=None):
    _require_active_user(user)
    storage_object = db.session.get(StorageObject, storage_object_id)
    if storage_object is None or storage_object.upload_status != "active" or storage_object.deleted_at is not None:
        raise StorageNotFoundError("File không sẵn sàng.")
    if storage_object.uploaded_by_id != user.id and not user.has_role(UserRole.SUPER_ADMIN.value) and not user.has_role(UserRole.ADMIN.value):
        raise StorageAuthorizationError("Bạn không có quyền tải file này.")
    safe_disposition = disposition if disposition in {"inline", "attachment"} else ("inline" if storage_object.mime_type.startswith(("image/", "video/", "audio/")) else "attachment")
    provider = provider or get_storage_provider()
    return provider.create_presigned_download(storage_object.bucket, storage_object.object_key, _config("STORAGE_DOWNLOAD_URL_TTL_SECONDS"), safe_disposition, storage_object.original_filename)


def cleanup_pending_uploads(*, older_than_hours=None, dry_run=True, provider=None):
    provider = provider or get_storage_provider()
    threshold = datetime.now(timezone.utc) - timedelta(hours=int(older_than_hours or _config("STORAGE_PENDING_UPLOAD_HOURS")))
    objects = StorageObject.query.filter(StorageObject.upload_status == "pending", StorageObject.created_at < threshold).all()
    result = {"matched": len(objects), "cleaned": 0, "dry_run": dry_run}
    if dry_run:
        return result
    for storage_object in objects:
        provider.delete_object(storage_object.bucket, storage_object.object_key)
        storage_object.upload_status = "failed"
        storage_object.deleted_at = datetime.now(timezone.utc)
        for item in storage_object.batch_items:
            if item.status in {"accepted", "uploading"}:
                _mark_item_failed(item, terminal=True)
        result["cleaned"] += 1
    db.session.commit()
    return result


def _validate_head(storage_object, head, checksum_sha256):
    if int(head.get("size", -1)) != storage_object.file_size:
        raise StorageValidationError("Kích thước object không khớp.")
    content_type = (head.get("content_type") or "").lower()
    if content_type and content_type != storage_object.mime_type:
        raise StorageValidationError("MIME type object không khớp.")
    expected = checksum_sha256 or storage_object.checksum_sha256
    actual = head.get("checksum_sha256")
    if expected and actual and expected.lower() != actual.lower():
        raise StorageValidationError("Checksum object không khớp.")


def _refresh_batch(batch):
    batch.completed_files = sum(item.status == "completed" for item in batch.items)
    batch.failed_files = sum(item.status in {"rejected", "failed", "cancelled"} for item in batch.items)
    if batch.completed_files == batch.accepted_files and batch.failed_files == 0:
        batch.status = "completed"
        batch.completed_at = datetime.now(timezone.utc)
    elif batch.completed_files or batch.failed_files:
        batch.status = "partial_failed" if batch.completed_files else "failed"
        if batch.completed_files + batch.failed_files >= batch.total_files:
            batch.completed_at = datetime.now(timezone.utc)


def _mark_item_failed(item, terminal):
    if terminal:
        item.status = "failed"
        item.error_message = item.error_message or "Không thể xác minh upload."
        _refresh_batch(item.upload_batch)


def _check_phase_one_scope(user):
    # Future folder/album ACL hooks replace this owner/admin-only foundation.
    return None


def _check_item_owner_or_admin(user, item):
    if item.upload_batch.created_by_id != user.id and not user.has_role(UserRole.SUPER_ADMIN.value) and not user.has_role(UserRole.ADMIN.value):
        raise StorageAuthorizationError("Bạn không có quyền hoàn tất upload này.")


def _require_active_user(user):
    if not user or not getattr(user, "is_authenticated", False) or not user.is_active:
        raise StorageAuthorizationError("Người dùng không hợp lệ.")


def _safe_size(value):
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _config(name):
    from flask import current_app
    return current_app.config[name]


def _add(instance):
    if instance.id is None and db.engine.name == "sqlite":
        max_id = db.session.query(func.max(type(instance).id)).scalar() or 0
        instance.id = max_id + 1
    db.session.add(instance)


def _complete_response(item, idempotent=False):
    return {"upload_batch_item_id": item.id, "storage_object_id": item.storage_object_id, "status": item.status, "upload_status": item.storage_object.upload_status, "idempotent": idempotent}
