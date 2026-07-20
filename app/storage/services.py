from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from app.extensions import db
from app.models import StorageObject, UploadBatch, UploadBatchItem, UserRole
from app.storage.exceptions import StorageAuthorizationError, StorageNotFoundError, StorageValidationError
from app.storage.keys import generate_original_key
from app.storage.providers import get_storage_provider
from app.storage.validation import validate_file_metadata


VALID_SCOPES = {("project_documents", "folder"), ("company_media", "album")}


def create_upload_batch_presign(*, user, module_type, target_type, target_id, files, provider=None):
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
    client_ids = [str(item.get("client_file_id", "")) for item in files if isinstance(item, dict)]
    if len(set(client_ids)) != len(client_ids) or any(not value for value in client_ids):
        raise StorageValidationError("client_file_id phải duy nhất và không được để trống.")

    provider = provider or get_storage_provider()
    batch = UploadBatch(module_type=module_type, target_type=target_type, target_id=int(target_id), created_by_id=user.id, total_files=len(files))
    _add(batch)
    db.session.flush()
    response_items = []
    for item in files:
        client_file_id = str(item["client_file_id"])
        try:
            meta = validate_file_metadata(item.get("filename"), item.get("mime_type"), item.get("size"), item.get("checksum_sha256"))
            object_key = generate_original_key(meta["file_ext"], _config("STORAGE_PREFIX"))
            storage_object = StorageObject(bucket=_config("STORAGE_BUCKET"), object_key=object_key, original_filename=meta["filename"], mime_type=meta["mime_type"], file_ext=meta["file_ext"], file_size=meta["file_size"], checksum_sha256=meta["checksum_sha256"], uploaded_by_id=user.id)
            _add(storage_object)
            db.session.flush()
            batch_item = UploadBatchItem(upload_batch_id=batch.id, storage_object_id=storage_object.id, client_file_id=client_file_id, original_filename=meta["filename"], mime_type=meta["mime_type"], file_size=meta["file_size"], status="accepted")
            _add(batch_item)
            upload = provider.create_presigned_upload(storage_object.bucket, storage_object.object_key, storage_object.mime_type, storage_object.file_size, _config("STORAGE_UPLOAD_URL_TTL_SECONDS"), metadata={"sha256": storage_object.checksum_sha256} if storage_object.checksum_sha256 else None)
            batch.accepted_files += 1
            response_items.append({"client_file_id": client_file_id, "accepted": True, "upload_batch_item_id": batch_item.id, "storage_object_id": storage_object.id, **upload})
        except StorageValidationError as exc:
            rejected = UploadBatchItem(upload_batch_id=batch.id, client_file_id=client_file_id, original_filename=str(item.get("filename", ""))[:255], mime_type=str(item.get("mime_type", ""))[:255], file_size=_safe_size(item.get("size")), status="rejected", error_message=str(exc))
            _add(rejected)
            batch.failed_files += 1
            response_items.append({"client_file_id": client_file_id, "accepted": False, "error": str(exc)})
    batch.status = "uploading" if batch.accepted_files else "failed"
    db.session.commit()
    return {"upload_batch_id": batch.id, "status": batch.status, "items": response_items}


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
