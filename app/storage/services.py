from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import StorageObject, UploadBatch, UploadBatchItem, UploadSelectionSession, UserRole
from app.storage.company_media_errors import file_size_error, item_error, upload_error
from app.storage.exceptions import (StorageAuthorizationError, StorageNotFoundError, StorageUploadContractError,
                                    StorageValidationError)
from app.storage.keys import build_original_key, normalize_storage_module
from app.storage.limits import get_company_media_upload_limits
from app.storage.providers import get_storage_provider
from app.storage.validation import max_file_size_for_category, validate_file_metadata


VALID_SCOPES = {("project_documents", "folder"), ("company_media", "album")}


def create_upload_selection_session(*, user, module_type, target_type, target_id, declared_files, declared_size_bytes):
    _require_active_user(user)
    if (module_type, target_type) not in VALID_SCOPES: raise StorageValidationError("Scope upload không hợp lệ.")
    if module_type == "company_media":
        limits = get_company_media_upload_limits()
        declared_files = _declared_positive_integer(declared_files, "files")
        declared_size_bytes = _declared_positive_integer(declared_size_bytes, "bytes")
        if declared_files > limits["max_selection_files"]:
            raise upload_error(
                "selection_file_count_exceeded",
                f"Bạn đã chọn {declared_files} tệp, tối đa {limits['max_selection_files']} tệp mỗi lần tải.",
                details={"actual_files": declared_files, "max_files": limits["max_selection_files"]},
            )
        if declared_size_bytes > limits["max_selection_bytes"]:
            raise upload_error(
                "selection_total_bytes_exceeded",
                "Tổng dung lượng đã chọn vượt quá giới hạn.",
                details={"actual_bytes": declared_size_bytes, "max_bytes": limits["max_selection_bytes"]},
            )
        session_ttl_seconds = limits["session_ttl_seconds"]
    else:
        try: declared_files, declared_size_bytes = int(declared_files), int(declared_size_bytes)
        except (TypeError, ValueError): raise StorageValidationError("Thông tin lựa chọn không hợp lệ.")
        if declared_files < 1 or declared_files > int(_config("UPLOAD_SELECTION_MAX_FILES")) or declared_size_bytes < 1 or declared_size_bytes > int(_config("UPLOAD_SELECTION_MAX_BYTES")):
            raise StorageValidationError("Lựa chọn vượt quá giới hạn 500 tệp hoặc 2 GB.")
        session_ttl_seconds = int(_config("UPLOAD_SELECTION_TTL_SECONDS"))
    session = UploadSelectionSession(module_type=module_type, target_type=target_type, target_id=int(target_id), created_by_id=user.id, declared_files=declared_files, declared_size_bytes=declared_size_bytes, expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=session_ttl_seconds))
    _add(session); db.session.commit(); return {"selection_session_id": session.id, "expires_at": session.expires_at.isoformat()}

def finalize_upload_selection_session(*, user, selection_session_id, module_type, target_type, target_id,
                                      failed_upload_batch_item_ids=None):
    if module_type == "company_media":
        return _finalize_company_media_selection_session(
            user=user,
            selection_session_id=selection_session_id,
            target_type=target_type,
            target_id=target_id,
            failed_upload_batch_item_ids=failed_upload_batch_item_ids,
        )
    session = _selection_session(user, selection_session_id, module_type, target_type, target_id)
    failed_ids = _normalize_failed_item_ids(failed_upload_batch_item_ids)
    items = UploadBatchItem.query.join(UploadBatch).filter(
        UploadBatch.selection_session_id == session.id,
    ).all()
    retryable = {item.id: item for item in items if item.status in {"accepted", "uploading"}}
    failed_or_retryable = {item.id for item in items if item.status in {"accepted", "uploading", "failed"}}
    if set(failed_ids) - failed_or_retryable:
        raise StorageValidationError("Danh sách tệp lỗi không hợp lệ.")
    for item_id in failed_ids:
        if item_id in retryable:
            _mark_item_failed(retryable[item_id], terminal=True)
    unfinished = [item for item in items if item.status not in {"completed", "failed", "rejected", "cancelled"}]
    if unfinished:
        raise StorageValidationError("Một số tệp chưa hoàn tất tải lên.")
    session.status = "completed"
    session.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.session.commit()
    return {
        "selection_session_id": session.id,
        "status": session.status,
        "succeeded_files": sum(item.status == "completed" for item in items),
        "failed_files": sum(item.status in {"failed", "rejected", "cancelled"} for item in items),
    }

def create_upload_batch_presign(*, user, module_type, target_type, target_id, files, selection_session_id=None, provider=None):
    _require_active_user(user)
    if (module_type, target_type) not in VALID_SCOPES:
        raise StorageValidationError("Scope upload không hợp lệ.")
    _check_phase_one_scope(user)
    files = list(files or [])
    company_media = module_type == "company_media"
    limits = get_company_media_upload_limits() if company_media else None
    max_files = limits["max_files_per_batch"] if company_media else int(_config("STORAGE_MAX_FILES_PER_BATCH"))
    if not files:
        if company_media:
            raise upload_error("empty_presign_batch", "Batch tải lên không có tệp.")
        raise StorageValidationError("Số lượng file trong batch không hợp lệ.")
    if len(files) > max_files:
        if company_media:
            raise upload_error(
                "presign_batch_file_count_exceeded",
                f"Batch có {len(files)} tệp, tối đa {max_files} tệp.",
                details={"actual_files": len(files), "max_files": max_files},
            )
        raise StorageValidationError("Số lượng file trong batch không hợp lệ.")
    declared_total = sum(_safe_size(item.get("size")) for item in files if isinstance(item, dict))
    max_batch_bytes = limits["max_batch_bytes"] if company_media else int(_config("STORAGE_MAX_BATCH_SIZE_MB")) * 1024 * 1024
    if declared_total > max_batch_bytes:
        if company_media:
            raise upload_error(
                "presign_batch_bytes_exceeded",
                "Dung lượng batch vượt quá giới hạn.",
                details={"actual_bytes": declared_total, "max_bytes": max_batch_bytes},
            )
        raise StorageValidationError("Tổng dung lượng batch vượt quá giới hạn.")
    max_file_bytes = limits["max_file_bytes"] if company_media else int(_config("UPLOAD_SINGLE_FILE_MAX_BYTES"))
    oversize_item = next((item for item in files if isinstance(item, dict) and _safe_size(item.get("size")) > max_file_bytes), None)
    if oversize_item is not None:
        if company_media:
            raise file_size_error(
                client_file_id=str(oversize_item.get("client_file_id", "")),
                filename=str(oversize_item.get("filename", "")),
                actual_bytes=_safe_size(oversize_item.get("size")),
                max_bytes=max_file_bytes,
            )
        raise StorageValidationError("Một tệp vượt quá giới hạn 300 MB.")
    selection = _selection_session(user, selection_session_id, module_type, target_type, target_id) if selection_session_id else None
    if company_media and selection is not None:
        return _create_company_media_selection_presign(
            user=user,
            target_type=target_type,
            target_id=target_id,
            files=files,
            selection_session_id=selection_session_id,
            provider=provider,
            limits=limits,
        )
    from app.storage.quota import ensure_storage_capacity
    if company_media:
        client_ids = [str(item.get("client_file_id", "")) for item in files if isinstance(item, dict)]
        if len(client_ids) != len(files) or len(set(client_ids)) != len(client_ids) or any(not value for value in client_ids):
            raise StorageValidationError("client_file_id phải duy nhất và không được để trống.")
        prepared = []
        for item in files:
            try:
                meta = validate_file_metadata(
                    item.get("filename"), item.get("mime_type"), item.get("size"), item.get("checksum_sha256"),
                    module_type=module_type, limits=limits, client_file_id=str(item["client_file_id"]),
                )
                prepared.append((item, meta, None))
            except StorageValidationError as exc:
                prepared.append((item, None, exc))
        accepted_total = sum(meta["file_size"] for _, meta, error in prepared if meta is not None and error is None)
        accepted_count = sum(meta is not None and error is None for _, meta, error in prepared)
        if selection and selection.presigned_files + accepted_count > selection.declared_files:
            raise upload_error(
                "selection_declared_file_quota_exceeded",
                "Số tệp trong batch vượt số lượng đã khai báo cho phiên tải.",
                details={"declared_files": selection.declared_files, "used_files": selection.presigned_files,
                         "incoming_files": accepted_count, "resulting_files": selection.presigned_files + accepted_count},
                status_code=409,
            )
        if selection and selection.presigned_size_bytes + accepted_total > selection.declared_size_bytes:
            raise upload_error(
                "selection_declared_byte_quota_exceeded",
                "Dung lượng batch vượt dung lượng đã khai báo cho phiên tải.",
                details={"declared_bytes": selection.declared_size_bytes, "used_bytes": selection.presigned_size_bytes,
                         "incoming_bytes": accepted_total, "resulting_bytes": selection.presigned_size_bytes + accepted_total},
                status_code=409,
            )
        try: ensure_storage_capacity(accepted_total)
        except ValueError as exc: raise StorageValidationError(str(exc))
    else:
        if selection and (selection.presigned_files + len(files) > selection.declared_files or selection.presigned_size_bytes + declared_total > selection.declared_size_bytes):
            raise StorageValidationError("Batch vượt số lượng hoặc dung lượng đã khai báo.")
        try: ensure_storage_capacity(declared_total)
        except ValueError as exc: raise StorageValidationError(str(exc))
        client_ids = [str(item.get("client_file_id", "")) for item in files if isinstance(item, dict)]
        if len(set(client_ids)) != len(client_ids) or any(not value for value in client_ids):
            raise StorageValidationError("client_file_id phải duy nhất và không được để trống.")
        prepared = [(item, None, None) for item in files]

    provider = provider or get_storage_provider()
    storage_module = normalize_storage_module(module_type)
    batch = UploadBatch(module_type=module_type, target_type=target_type, target_id=int(target_id), created_by_id=user.id, selection_session_id=selection.id if selection else None, total_files=len(files))
    _add(batch)
    db.session.flush()
    response_items = []
    for item, meta, validation_error in prepared:
        client_file_id = str(item["client_file_id"])
        try:
            if validation_error is not None:
                raise validation_error
            if meta is None:
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
            upload = provider.create_presigned_upload(
                storage_object.bucket,
                storage_object.object_key,
                storage_object.mime_type,
                storage_object.file_size,
                _config("STORAGE_UPLOAD_URL_TTL_SECONDS"),
                max_file_size=max_file_size_for_category(meta["category"]),
                metadata={"sha256": storage_object.checksum_sha256} if storage_object.checksum_sha256 else None,
            )
            batch.accepted_files += 1
            response_items.append({"client_file_id": client_file_id, "accepted": True, "upload_batch_item_id": batch_item.id, "storage_object_id": storage_object.id, **upload})
        except StorageValidationError as exc:
            rejected = UploadBatchItem(upload_batch_id=batch.id, client_file_id=client_file_id, original_filename=str(item.get("filename", ""))[:255], mime_type=str(item.get("mime_type", ""))[:255], file_size=_safe_size(item.get("size")), status="rejected", error_message=str(exc))
            _add(rejected)
            batch.failed_files += 1
            if company_media and isinstance(exc, StorageUploadContractError):
                response_items.append(item_error(client_file_id, exc))
            else:
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
    if not session or session.created_by_id != user.id or session.module_type != module_type or session.target_type != target_type or session.target_id != int(target_id):
        if module_type == "company_media":
            raise upload_error("selection_session_target_mismatch", "Phiên tải không hợp lệ.", status_code=403)
        raise StorageAuthorizationError("Upload selection không hợp lệ.")
    if module_type == "company_media" and session.status == "cancelled":
        raise upload_error("upload_session_cancelled", "Phiên tải đã được hủy.", status_code=409)
    if session.status != "pending" or session.expires_at <= now:
        if session.status == "pending": session.status = "expired"; db.session.commit()
        if module_type == "company_media":
            raise upload_error("selection_session_expired", "Phiên tải đã hết hạn hoặc đã hoàn tất.", status_code=410)
        raise StorageValidationError("Upload selection đã hết hạn hoặc hoàn tất.")
    return session


def _canonical_client_file_id(value):
    """Validate the browser-generated key before it reaches logs or the DB."""
    if not isinstance(value, str):
        raise StorageValidationError("client_file_id phải là chuỗi hợp lệ.")
    value = value.strip()
    if not value or len(value) > 255:
        raise StorageValidationError("client_file_id phải có từ 1 đến 255 ký tự.")
    if not all(character.isascii() and (character.isalnum() or character in "._:-") for character in value):
        raise StorageValidationError("client_file_id không hợp lệ.")
    return value


def _company_media_upload_log(event, *, user, selection_session_id, upload_item_id=None, outcome=None):
    """Structured, non-sensitive lifecycle telemetry for the upload audit trail."""
    from flask import current_app
    current_app.logger.info(
        "company_media_upload event=%s actor_id=%s selection_session_id=%s upload_item_id=%s outcome=%s",
        event, getattr(user, "id", None), selection_session_id, upload_item_id, outcome,
    )


def _canonical_company_media_metadata(item, limits):
    meta = validate_file_metadata(
        item.get("filename"), item.get("mime_type"), item.get("size"), item.get("checksum_sha256"),
        module_type="company_media", limits=limits, client_file_id=item.get("client_file_id"),
    )
    # The validation policy already canonicalizes MIME aliases and extensions.
    # Store/compare the filename at that same normalization stage.
    stem, separator, _extension = meta["filename"].rpartition(".")
    meta["filename"] = f"{stem}{separator}{meta['file_ext']}" if separator else meta["filename"]
    return meta


def _company_media_metadata_matches(item, meta):
    return (
        item.original_filename == meta["filename"]
        and item.mime_type == meta["mime_type"]
        and item.file_size == meta["file_size"]
    )


def _company_media_item_query(selection_id, client_file_id):
    return select(UploadBatchItem).where(
        UploadBatchItem.selection_session_id == selection_id,
        UploadBatchItem.client_file_id == client_file_id,
    )


def _locked_company_media_selection(user, selection_session_id, target_type, target_id):
    if not selection_session_id:
        raise StorageValidationError("selection_session_id là bắt buộc.")
    session = db.session.scalar(
        select(UploadSelectionSession).where(UploadSelectionSession.id == selection_session_id).with_for_update()
    )
    if (
        session is None
        or session.created_by_id != user.id
        or session.module_type != "company_media"
        or session.target_type != target_type
        or session.target_id != int(target_id)
    ):
        raise upload_error("selection_session_target_mismatch", "Phiên tải không hợp lệ.", status_code=403)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if session.status != "pending" or session.expires_at <= now:
        if session.status == "pending":
            session.status = "expired"
            db.session.commit()
        raise upload_error("selection_session_expired", "Phiên tải đã hết hạn hoặc đã hoàn tất.", status_code=410)
    return session


def _new_company_media_batch(user, target_type, target_id, selection):
    batch = UploadBatch(
        module_type="company_media", target_type=target_type, target_id=int(target_id),
        created_by_id=user.id, selection_session_id=selection.id, total_files=0, status="pending",
    )
    _add(batch)
    db.session.flush()
    return batch


def _company_media_response_item(item, *, replay, provider, limits):
    payload = {
        "client_file_id": item.client_file_id,
        "accepted": True,
        "upload_batch_item_id": item.id,
        "storage_object_id": item.storage_object_id,
        "status": item.status,
        "idempotent_replay": replay,
    }
    if item.status in {"accepted", "uploading"}:
        storage_object = item.storage_object
        upload = provider.create_presigned_upload(
            storage_object.bucket, storage_object.object_key, storage_object.mime_type,
            storage_object.file_size, _config("STORAGE_UPLOAD_URL_TTL_SECONDS"),
            max_file_size=max_file_size_for_category(
                "image" if storage_object.mime_type.startswith("image/") else "video",
                module_type="company_media", limits=limits,
            ),
            metadata={"sha256": storage_object.checksum_sha256} if storage_object.checksum_sha256 else None,
        )
        payload.update(upload)
    return payload


def _create_company_media_selection_presign(*, user, target_type, target_id, files, selection_session_id, provider, limits):
    """Persist a canonical Company Media item before signing it.

    The direct session FK plus its DB unique constraint remains the final race
    guard.  The session lock is only for quota/counter serialization.
    """
    normalized = []
    client_ids = []
    for raw_item in files:
        if not isinstance(raw_item, dict):
            raise StorageValidationError("Thông tin tệp không hợp lệ.")
        client_file_id = _canonical_client_file_id(raw_item.get("client_file_id"))
        client_ids.append(client_file_id)
        normalized.append(({**raw_item, "client_file_id": client_file_id}, None, None))
    if len(set(client_ids)) != len(client_ids):
        raise StorageValidationError("client_file_id phải duy nhất và không được để trống.")

    for index, (raw_item, _meta, _error) in enumerate(normalized):
        try:
            normalized[index] = (raw_item, _canonical_company_media_metadata(raw_item, limits), None)
        except StorageValidationError as exc:
            normalized[index] = (raw_item, None, exc)

    # `_selection_session` has already authenticated/scope-checked before this
    # call. Re-read it under lock so counters and expiry are decided atomically.
    selection = _locked_company_media_selection(user, selection_session_id, target_type, target_id)
    existing = {
        item.client_file_id: item
        for item in db.session.scalars(
            select(UploadBatchItem).where(UploadBatchItem.selection_session_id == selection.id)
        ).all()
    }

    candidates = []
    rejected_candidates = []
    response_by_id = {}
    for raw_item, meta, validation_error in normalized:
        client_file_id = raw_item["client_file_id"]
        if validation_error is not None:
            if existing.get(client_file_id) is None:
                rejected_candidates.append((raw_item, validation_error))
            response_by_id[client_file_id] = item_error(client_file_id, validation_error) if isinstance(validation_error, StorageUploadContractError) else {
                "client_file_id": client_file_id, "accepted": False, "error": str(validation_error),
            }
            continue
        prior = existing.get(client_file_id)
        if prior is None:
            candidates.append((raw_item, meta))
            continue
        if not _company_media_metadata_matches(prior, meta):
            _company_media_upload_log(
                "CM-PRESIGN-IDEMPOTENCY", user=user, selection_session_id=selection.id,
                upload_item_id=prior.id, outcome="conflict",
            )
            raise upload_error(
                "idempotency_conflict", "Mã tệp đã được sử dụng cho một tệp khác.",
                details={}, retryable=False, status_code=409,
            )
        if prior.status == "failed":
            response_by_id[client_file_id] = item_error(client_file_id, upload_error(
                "upload_item_not_retryable", "Tệp này không thể thử lại. Vui lòng bắt đầu lựa chọn mới.",
                retryable=False,
            ))
            continue
        response_by_id[client_file_id] = prior

    new_total = sum(meta["file_size"] for _raw_item, meta in candidates)
    if selection.presigned_files + len(candidates) > selection.declared_files:
        raise upload_error(
            "selection_declared_file_quota_exceeded", "Số tệp trong batch vượt số lượng đã khai báo cho phiên tải.",
            details={"declared_files": selection.declared_files, "used_files": selection.presigned_files,
                     "incoming_files": len(candidates), "resulting_files": selection.presigned_files + len(candidates)},
            status_code=409,
        )
    if selection.presigned_size_bytes + new_total > selection.declared_size_bytes:
        raise upload_error(
            "selection_declared_byte_quota_exceeded", "Dung lượng batch vượt dung lượng đã khai báo cho phiên tải.",
            details={"declared_bytes": selection.declared_size_bytes, "used_bytes": selection.presigned_size_bytes,
                     "incoming_bytes": new_total, "resulting_bytes": selection.presigned_size_bytes + new_total},
            status_code=409,
        )
    if candidates:
        from app.storage.quota import ensure_storage_capacity
        try:
            ensure_storage_capacity(new_total)
        except ValueError as exc:
            raise StorageValidationError(str(exc)) from None

    storage_module = normalize_storage_module("company_media")
    created_batch = None
    created_item_ids = set()
    created_count = 0
    created_size = 0
    for raw_item, validation_error in rejected_candidates:
        if created_batch is None:
            created_batch = _new_company_media_batch(user, target_type, target_id, selection)
        rejected = UploadBatchItem(
            upload_batch_id=created_batch.id, selection_session_id=selection.id,
            client_file_id=raw_item["client_file_id"],
            original_filename=str(raw_item.get("filename", ""))[:255],
            mime_type=str(raw_item.get("mime_type", ""))[:255], file_size=_safe_size(raw_item.get("size")),
            status="rejected", error_message=str(validation_error),
        )
        _add(rejected)
        db.session.flush()
        created_batch.total_files += 1
        created_batch.failed_files += 1
    for raw_item, meta in candidates:
        client_file_id = raw_item["client_file_id"]
        try:
            with db.session.begin_nested():
                batch = created_batch or _new_company_media_batch(user, target_type, target_id, selection)
                object_key = build_original_key(storage_module, uuid4().hex, meta["filename"], _config("STORAGE_PREFIX"))
                storage_object = StorageObject(
                    bucket=_config("STORAGE_BUCKET"), object_key=object_key, storage_module=storage_module,
                    original_filename=meta["filename"], mime_type=meta["mime_type"], file_ext=meta["file_ext"],
                    file_size=meta["file_size"], checksum_sha256=meta["checksum_sha256"], uploaded_by_id=user.id,
                )
                _add(storage_object)
                db.session.flush()
                batch_item = UploadBatchItem(
                    upload_batch_id=batch.id, selection_session_id=selection.id, storage_object_id=storage_object.id,
                    client_file_id=client_file_id, original_filename=meta["filename"], mime_type=meta["mime_type"],
                    file_size=meta["file_size"], status="accepted",
                )
                _add(batch_item)
                db.session.flush()
                batch.total_files += 1
                batch.accepted_files += 1
            created_batch = batch
            created_count += 1
            created_size += meta["file_size"]
            created_item_ids.add(batch_item.id)
            response_by_id[client_file_id] = batch_item
        except IntegrityError:
            # Only the savepoint is rolled back. A concurrent winner is now the
            # canonical row and its object; never sign the rolled-back object.
            winner = db.session.scalar(_company_media_item_query(selection.id, client_file_id))
            if winner is None:
                raise
            if not _company_media_metadata_matches(winner, meta):
                _company_media_upload_log(
                    "CM-PRESIGN-IDEMPOTENCY", user=user, selection_session_id=selection.id,
                    upload_item_id=winner.id, outcome="conflict",
                )
                raise upload_error(
                    "idempotency_conflict", "Mã tệp đã được sử dụng cho một tệp khác.",
                    details={}, retryable=False, status_code=409,
                )
            response_by_id[client_file_id] = winner
            _company_media_upload_log(
                "CM-PRESIGN-IDEMPOTENCY", user=user, selection_session_id=selection.id,
                upload_item_id=winner.id, outcome="race-loser-replay",
            )

    if created_batch is not None:
        created_batch.status = "uploading" if created_batch.accepted_files else "failed"
    selection.presigned_files += created_count
    selection.presigned_size_bytes += created_size
    db.session.commit()

    provider = provider or get_storage_provider()
    response_items = []
    for raw_item, meta, validation_error in normalized:
        outcome = response_by_id[raw_item["client_file_id"]]
        if isinstance(outcome, UploadBatchItem):
            response_items.append(_company_media_response_item(
                outcome, replay=outcome.id not in created_item_ids, provider=provider, limits=limits,
            ))
        else:
            response_items.append(outcome)
    # Determine replay after persistence rather than from a request-specific
    # batch: canonical items can legitimately belong to an older batch.
    batch_id = created_batch.id if created_batch is not None else next(
        (entry["upload_batch_item_id"] for entry in response_items if entry.get("accepted")), None
    )
    _company_media_upload_log(
        "CM-PRESIGN-IDEMPOTENCY", user=user, selection_session_id=selection.id,
        outcome="created" if created_count else "replay",
    )
    return {"upload_batch_id": batch_id, "status": "uploading", "items": response_items}


def _selection_items(session_id):
    return db.session.scalars(
        select(UploadBatchItem).where(UploadBatchItem.selection_session_id == session_id)
    ).all()


def _finalize_company_media_selection_session(*, user, selection_session_id, target_type, target_id,
                                              failed_upload_batch_item_ids):
    """Finalize once, while permitting already-issued items to finish on expiry."""
    if not selection_session_id:
        raise StorageValidationError("selection_session_id là bắt buộc.")
    session = db.session.scalar(
        select(UploadSelectionSession).where(UploadSelectionSession.id == selection_session_id).with_for_update()
    )
    if (
        session is None or session.created_by_id != user.id or session.module_type != "company_media"
        or session.target_type != target_type or session.target_id != int(target_id)
    ):
        raise upload_error("selection_session_target_mismatch", "Phiên tải không hợp lệ.", status_code=403)
    items = _selection_items(session.id)
    if session.status == "completed":
        _company_media_upload_log(
            "CM-FINALIZE-IDEMPOTENCY", user=user, selection_session_id=session.id, outcome="finalized-replay",
        )
        return _selection_finalize_response(session, items, idempotent_replay=True)
    if session.status == "cancelled":
        raise upload_error("upload_session_cancelled", "Phiên tải đã được hủy.", status_code=409)
    if session.status == "finalized":
        raise upload_error("selection_session_expired", "Phiên tải đã hết hạn hoặc đã hoàn tất.", status_code=410)

    failed_ids = _normalize_failed_item_ids(failed_upload_batch_item_ids)
    known = {item.id: item for item in items}
    retryable = {item.id: item for item in items if item.status in {"accepted", "uploading"}}
    failed_or_retryable = {item.id for item in items if item.status in {"accepted", "uploading", "failed"}}
    if set(failed_ids) - failed_or_retryable:
        raise StorageValidationError("Danh sách tệp lỗi không hợp lệ.")
    for item_id in failed_ids:
        if item_id in retryable:
            _mark_item_failed(retryable[item_id], terminal=True)

    unfinished = [item for item in known.values() if item.status not in {"completed", "failed", "rejected", "cancelled"}]
    expired = session.expires_at <= datetime.now(timezone.utc).replace(tzinfo=None) or session.status == "expired"
    if unfinished:
        if expired:
            session.status = "expired"
            db.session.commit()
            raise upload_error("selection_session_expired", "Phiên tải đã hết hạn. Vui lòng chọn lại tệp.", status_code=410)
        raise StorageValidationError("Một số tệp chưa hoàn tất tải lên.")
    session.status = "completed"
    if session.completed_at is None:
        session.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.session.commit()
    _company_media_upload_log(
        "CM-FINALIZE-IDEMPOTENCY", user=user, selection_session_id=session.id, outcome="finalized",
    )
    return _selection_finalize_response(session, items, idempotent_replay=False)


def _selection_finalize_response(session, items, *, idempotent_replay):
    return {
        "selection_session_id": session.id,
        "status": session.status,
        "succeeded_files": sum(item.status == "completed" for item in items),
        "failed_files": sum(item.status in {"failed", "rejected", "cancelled"} for item in items),
        "idempotent_replay": idempotent_replay,
    }


def complete_upload_item(*, user, upload_batch_item_id, reported_etag=None, checksum_sha256=None, provider=None,
                         completion_handler=None):
    _require_active_user(user)
    item = db.session.scalar(
        select(UploadBatchItem).where(UploadBatchItem.id == upload_batch_item_id)
        .execution_options(populate_existing=True).with_for_update()
    )
    if item is None or item.storage_object is None:
        raise StorageNotFoundError("Upload item không tồn tại.")
    _check_item_owner_or_admin(user, item)
    storage_object = db.session.scalar(
        select(StorageObject).where(StorageObject.id == item.storage_object_id)
        .execution_options(populate_existing=True).with_for_update()
    )
    if storage_object is None:
        raise StorageNotFoundError("Upload item không tồn tại.")
    item.storage_object = storage_object
    idempotent = storage_object.upload_status == "active" and item.status == "completed"
    if not idempotent and (storage_object.upload_status != "pending" or item.status not in {"accepted", "uploading"}):
        raise StorageValidationError("Upload item không ở trạng thái có thể hoàn tất.")
    if not idempotent:
        provider = provider or get_storage_provider()
        try:
            head = provider.head_object(storage_object.bucket, storage_object.object_key)
            _validate_head(storage_object, head, checksum_sha256)
        except (StorageNotFoundError, StorageValidationError) as exc:
            _mark_item_failed(item, terminal=True)
            db.session.commit()
            if item.upload_batch.module_type == "company_media":
                raise upload_error(
                    "head_verification_failed",
                    "Không thể xác minh tệp đã tải lên. Bạn có thể tải lại tệp.",
                    retryable=True,
                ) from None
            raise
        storage_object.upload_status = "active"
        storage_object.completed_at = datetime.now(timezone.utc)
        item.status = "completed"
        item.error_message = None
        _refresh_batch(item.upload_batch)
    completion = completion_handler(item, idempotent) if completion_handler else None
    db.session.commit()
    response = _complete_response(item, idempotent=idempotent)
    if completion is not None:
        response["completion"] = completion
    return response


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


def _declared_positive_integer(value, kind):
    """Validate JSON selection declarations without coercing malformed values."""
    field = "actual_files" if kind == "files" else "actual_bytes"
    code = "invalid_selection_file_count" if kind == "files" else "invalid_selection_total_bytes"
    details = {field: value if isinstance(value, (int, float, str, bool)) or value is None else None}
    if kind == "files":
        details["min_files"] = 1
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        message = "Số lượng tệp đã chọn không hợp lệ." if kind == "files" else "Tổng dung lượng đã chọn không hợp lệ."
        raise upload_error(code, message, details=details)
    return value


def _normalize_failed_item_ids(value):
    if value is None:
        return []
    if not isinstance(value, list):
        raise StorageValidationError("Danh sách tệp lỗi không hợp lệ.")
    ids = []
    for item_id in value:
        if isinstance(item_id, bool):
            raise StorageValidationError("Danh sách tệp lỗi không hợp lệ.")
        try:
            normalized = int(item_id)
        except (TypeError, ValueError) as exc:
            raise StorageValidationError("Danh sách tệp lỗi không hợp lệ.") from exc
        if normalized < 1:
            raise StorageValidationError("Danh sách tệp lỗi không hợp lệ.")
        ids.append(normalized)
    if len(ids) != len(set(ids)):
        raise StorageValidationError("Danh sách tệp lỗi không hợp lệ.")
    return ids


def _config(name):
    from flask import current_app
    return current_app.config[name]


def _add(instance):
    if instance.id is None and db.engine.name == "sqlite":
        max_id = db.session.query(func.max(type(instance).id)).scalar() or 0
        instance.id = max_id + 1
    db.session.add(instance)


def _complete_response(item, idempotent=False):
    return {"upload_batch_item_id": item.id, "storage_object_id": item.storage_object_id, "status": item.status, "upload_status": item.storage_object.upload_status, "idempotent": idempotent, "idempotent_replay": idempotent}
