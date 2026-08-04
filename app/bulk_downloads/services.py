import shutil
import tempfile
import zipfile
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import current_app, send_file

from app.audit import audit
from app.extensions import db
from app.models import BulkDownloadJob, CompanyMediaAlbum, CompanyMediaFile, ProjectDocumentFile, ProjectDocumentFolder, User
from app.storage.keys import (STORAGE_MODULE_COMPANY_MEDIA, STORAGE_MODULE_DOCUMENT_LIBRARY,
                              build_bulk_zip_key, safe_storage_filename)
from app.storage.providers import get_storage_provider


class BulkDownloadError(ValueError):
    pass


# Keep bounded disclosure snapshots consistent with project document archives.
AUDIT_SNAPSHOT_CHILD_LIMIT = 50


def parse_file_ids(request):
    """Read bulk file IDs from the JSON API or a native HTML form."""
    if request.is_json:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or not isinstance(payload.get("file_ids"), list):
            raise BulkDownloadError("Danh sách tệp không hợp lệ.")
        return payload["file_ids"]

    if "file_ids_json" in request.form:
        try:
            values = json.loads(request.form["file_ids_json"])
        except (TypeError, ValueError) as exc:
            raise BulkDownloadError("Danh sách tệp không hợp lệ.") from exc
        if not isinstance(values, list):
            raise BulkDownloadError("Danh sách tệp không hợp lệ.")
        return values

    values = request.form.getlist("file_ids[]")
    if values:
        return values
    return []


def preflight_document_download(user, folder, file_ids):
    files = _select_document_files(user, folder, file_ids)
    _ensure_objects_exist(files)
    return {"kind": "direct" if len(files) == 1 else "zip"}


def preflight_media_download(user, album, file_ids):
    files = _select_media_files(user, album, file_ids)
    _ensure_objects_exist(files)
    return {"kind": "direct" if len(files) == 1 else "zip"}


def request_document_download(user, folder, file_ids):
    from app.project_documents.services import create_file_download_url
    files = _select_document_files(user, folder, file_ids)
    if len(files) == 1:
        return {"kind": "direct", "download": create_file_download_url(user, files[0])}
    return {
        "kind": "zip", "files": files, "filename": f"ho-so-tai-lieu-{_now():%Y%m%d-%H%M}.zip",
        "module": STORAGE_MODULE_DOCUMENT_LIBRARY, "entity_type": "ProjectDocumentFolder",
        "entity_id": folder.id, "object_type": "ProjectDocumentFile",
    }


def request_media_download(user, album, file_ids):
    from app.company_media.services import signed_download
    files = _select_media_files(user, album, file_ids)
    if len(files) == 1:
        return {"kind": "direct", "download": signed_download(files[0], user)}
    return {
        "kind": "zip", "files": files, "filename": f"album-{safe_storage_filename(album.name, 'media')}-{_now():%Y%m%d-%H%M}.zip",
        "module": STORAGE_MODULE_COMPANY_MEDIA, "entity_type": "CompanyMediaAlbum",
        "entity_id": album.id, "object_type": "CompanyMediaFile",
    }


def _bulk_download_audit_snapshot(selection, files, total_size):
    visible_files = files[:AUDIT_SNAPSHOT_CHILD_LIMIT]
    return {
        "module": selection["module"],
        "object_type": selection["object_type"],
        "file_count": len(files),
        "total_size_bytes": total_size,
        "file_ids": [item.id for item in visible_files],
        "truncated_file_count": len(files) - len(visible_files),
        "files": [
            {
                "id": item.id,
                "file_name": item.display_name,
                "storage_object_id": item.storage_object_id,
                "file_size": item.storage_object.file_size,
            }
            for item in visible_files
        ],
    }


def stream_zip_download(user, selection):
    """Create a request-local ZIP; legacy jobs remain the only S3 ZIP producers."""
    files = selection["files"]
    _ensure_objects_exist(files)
    provider = get_storage_provider()

    temp_root = Path(current_app.config["BULK_DOWNLOAD_TEMP_ROOT"])
    temp_root.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix="zip-stream-", dir=temp_root))
    zip_path = temp_dir / "download.zip"
    total_size = sum(int(item.storage_object.file_size or 0) for item in files)
    try:
        names = set()
        # This is a bundle, not a recompression service. Storing entries avoids
        # expensive/redundant compression of ZIP, Office, media, and archives.
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
            for index, item in enumerate(files, start=1):
                storage = item.storage_object
                source = temp_dir / f"source-{index}"
                provider.download_object(storage.bucket, storage.object_key, source)
                archive.write(source, arcname=_unique_zip_name(item.display_name, names))
                source.unlink(missing_ok=True)
        if not zip_path.is_file() or zip_path.stat().st_size <= 0:
            raise BulkDownloadError("Không thể tạo file ZIP. Vui lòng thử lại hoặc chọn ít tệp hơn.")
        from app.storage.quota import ensure_bandwidth, record_download
        try:
            ensure_bandwidth(user, total_size)
        except ValueError as exc:
            raise BulkDownloadError(str(exc))
        zip_size = zip_path.stat().st_size
        record_download(user, kind="zip_stream", source_type="zip_stream", module=selection["module"],
            estimated_bytes=total_size, estimated_storage_egress_bytes=total_size,
            estimated_client_egress_bytes=zip_size)
        audit(
            "bulk_download.create",
            selection["entity_type"],
            selection["entity_id"],
            new_values=_bulk_download_audit_snapshot(selection, files, total_size),
        )
        db.session.commit()
        response = send_file(zip_path, mimetype="application/zip", as_attachment=True,
            download_name=selection["filename"], conditional=False, max_age=0)
        # send_file defaults to direct_passthrough. Disable it so the Flask
        # Response close lifecycle invokes call_on_close after body iteration.
        response.direct_passthrough = False
        response.call_on_close(lambda: shutil.rmtree(temp_dir, ignore_errors=True))
        return response
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def serialize_job(user, job):
    _check_job_access(user, job)
    result = {"id": job.id, "status": job.status, "file_count": job.file_count,
              "completed_file_count": job.completed_file_count, "error": job.error_message}
    if job.status == "succeeded" and job.zip_object_key and job.expires_at > _now():
        result["download"] = get_storage_provider().create_presigned_download(
            current_app.config["STORAGE_BUCKET"], job.zip_object_key,
            current_app.config["STORAGE_DOWNLOAD_URL_TTL_SECONDS"], "attachment", job.zip_filename)
    return result


def enqueue_job(job):
    # Tests call ``run_job`` explicitly; do not require a Redis process or let
    # the process-global Celery test task retain a previous Flask app context.
    if current_app.testing:
        return None
    from app.bulk_downloads.tasks import build_bulk_zip
    task = build_bulk_zip.delay(job.id)
    return task.id


def run_job(job_id):
    job = db.session.get(BulkDownloadJob, job_id)
    if not job or job.status in {"succeeded", "expired"}:
        return _task_result(job)
    if job.expires_at <= _now():
        job.status = "expired"; db.session.commit(); return _task_result(job)
    job.status = "running"; job.error_message = None; db.session.commit()
    temp_root = Path(current_app.config["BULK_DOWNLOAD_TEMP_ROOT"]); temp_root.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix=f"bulk-{job.id}-", dir=temp_root))
    try:
        requester = db.session.get(User, job.requested_by_id)
        if not requester or not requester.is_active:
            raise BulkDownloadError("Người yêu cầu không còn hoạt động.")
        files = _task_files(job)
        _validate_task_permissions(requester, job, files)
        zip_path = temp_dir / "download.zip"
        provider = get_storage_provider()
        names = set()
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
            for index, item in enumerate(files, start=1):
                storage = item.storage_object
                source = temp_dir / f"source-{index}"
                provider.download_object(storage.bucket, storage.object_key, source)
                entry = _unique_zip_name(item.display_name, names)
                archive.write(source, arcname=entry)
                job.completed_file_count = index
                db.session.commit()
        key = build_bulk_zip_key(job.module, job.id, job.zip_filename, current_app.config["STORAGE_PREFIX"])
        provider.upload_object(current_app.config["STORAGE_BUCKET"], key, zip_path, "application/zip")
        job.zip_object_key = key; job.status = "succeeded"; job.completed_at = _now(); job.error_message = None
        db.session.commit()
    except Exception as exc:
        job.status = "failed"; job.error_message = str(exc)[:300]; db.session.commit()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
    return _task_result(job)


def cleanup_expired_jobs():
    now = _now(); provider = get_storage_provider(); cleaned = 0
    jobs = BulkDownloadJob.query.filter(BulkDownloadJob.expires_at <= now, BulkDownloadJob.status != "expired").all()
    for job in jobs:
        if job.zip_object_key:
            provider.delete_object(current_app.config["STORAGE_BUCKET"], job.zip_object_key)
        job.status = "expired"; cleaned += 1
    db.session.commit()
    return {"matched": len(jobs), "cleaned": cleaned}


def _create_job(user, module, context_type, context_id, files, filename_prefix):
    job = BulkDownloadJob(module=module, requested_by_id=user.id, source_context_type=context_type,
                          source_context_id=context_id, requested_file_ids=[item.id for item in files],
                          file_count=len(files), total_size_bytes=sum(item.storage_object.file_size for item in files),
                          zip_filename=f"{filename_prefix}-{_now():%Y%m%d-%H%M}.zip",
                          expires_at=_now() + timedelta(seconds=int(current_app.config["BULK_DOWNLOAD_ZIP_TTL_SECONDS"])))
    db.session.add(job); db.session.commit()
    enqueue_job(job)
    return serialize_job(user, job)


def _validate_selected(files, requested_ids, permitted):
    ids = _normal_ids(requested_ids)
    if not ids or len(files) != len(ids):
        raise BulkDownloadError("Tệp đã chọn không thuộc vị trí hiện tại.")
    if len(files) > int(current_app.config["BULK_DOWNLOAD_MAX_FILES"]):
        raise BulkDownloadError("Bạn chỉ có thể tải xuống tối đa 100 tệp mỗi lần.")
    if sum(int(item.storage_object.file_size or 0) for item in files) > int(current_app.config["BULK_DOWNLOAD_MAX_TOTAL_BYTES"]):
        raise BulkDownloadError("Dung lượng tải xuống hàng loạt tối đa là 300 MB mỗi lần.")
    if any(not item.is_active or item.deleted_at or not permitted(item) for item in files):
        raise PermissionError("Không có quyền tải xuống một hoặc nhiều tệp đã chọn")


def _document_files(folder, ids):
    values = _normal_ids(ids)
    return ProjectDocumentFile.query.filter(ProjectDocumentFile.folder_id == folder.id, ProjectDocumentFile.id.in_(values)).all()


def _media_files(album, ids):
    values = _normal_ids(ids)
    return CompanyMediaFile.query.filter(CompanyMediaFile.album_id == album.id, CompanyMediaFile.id.in_(values)).all()


def _select_document_files(user, folder, file_ids):
    from app.project_documents.permissions import can_download_project_document_file
    files = _document_files(folder, file_ids)
    _validate_selected(files, file_ids, lambda item: can_download_project_document_file(user, item))
    return files


def _select_media_files(user, album, file_ids):
    from app.company_media.permissions import download_file
    files = _media_files(album, file_ids)
    _validate_selected(files, file_ids, lambda item: download_file(user, item))
    return files


def _ensure_objects_exist(files):
    provider = get_storage_provider()
    try:
        for item in files:
            storage = item.storage_object
            provider.head_object(storage.bucket, storage.object_key)
    except Exception as exc:
        raise BulkDownloadError("Không tìm thấy một hoặc nhiều tệp trên kho lưu trữ. Vui lòng kiểm tra lại hoặc liên hệ quản trị viên.") from exc


def _task_files(job):
    if job.module == STORAGE_MODULE_DOCUMENT_LIBRARY:
        folder = db.session.get(ProjectDocumentFolder, job.source_context_id)
        if not folder: raise BulkDownloadError("Thư mục nguồn không còn tồn tại.")
        return _document_files(folder, job.requested_file_ids)
    album = db.session.get(CompanyMediaAlbum, job.source_context_id)
    if not album: raise BulkDownloadError("Album nguồn không còn tồn tại.")
    return _media_files(album, job.requested_file_ids)


def _validate_task_permissions(user, job, files):
    if job.module == STORAGE_MODULE_DOCUMENT_LIBRARY:
        from app.project_documents.permissions import can_download_project_document_file
        _validate_selected(files, job.requested_file_ids, lambda item: can_download_project_document_file(user, item))
    else:
        from app.company_media.permissions import download_file
        _validate_selected(files, job.requested_file_ids, lambda item: download_file(user, item))


def _normal_ids(values):
    try: ids = [int(value) for value in (values or [])]
    except (TypeError, ValueError): raise BulkDownloadError("Danh sách tệp không hợp lệ.")
    return list(dict.fromkeys(ids))


def _unique_zip_name(filename, names):
    safe = safe_storage_filename(filename, "file")
    stem, dot, ext = safe.rpartition(".")
    stem = stem if dot else safe; suffix = f".{ext}" if dot else ""
    candidate = safe; number = 2
    while candidate.casefold() in names:
        candidate = f"{stem} ({number}){suffix}"; number += 1
    names.add(candidate.casefold()); return candidate


def _check_job_access(user, job):
    if not user or not user.is_active or (user.id != job.requested_by_id and not user.has_role("SUPER_ADMIN") and not user.has_role("ADMIN")):
        raise PermissionError("Bạn không có quyền xem tiến trình tải xuống này.")


def _task_result(job):
    return {"job_id": getattr(job, "id", None), "status": getattr(job, "status", "not_found"), "ok": bool(job and job.status == "succeeded")}


def _now(): return datetime.now(timezone.utc).replace(tzinfo=None)
