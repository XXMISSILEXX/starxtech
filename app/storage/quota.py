from datetime import datetime, timezone
from sqlalchemy import func
from app.extensions import db
from app.models import BulkDownloadJob, DownloadEvent, StorageDerivative, StorageObject

def storage_usage_bytes():
    originals = db.session.query(func.coalesce(func.sum(StorageObject.file_size), 0)).filter(StorageObject.upload_status == "active", StorageObject.deleted_at.is_(None)).scalar()
    derivatives = db.session.query(func.coalesce(func.sum(StorageDerivative.file_size), 0)).filter(StorageDerivative.deleted_at.is_(None)).scalar()
    zips = db.session.query(func.coalesce(func.sum(BulkDownloadJob.zip_size_bytes), 0)).filter(BulkDownloadJob.status == "succeeded", BulkDownloadJob.expires_at > _now()).scalar()
    return int(originals or 0) + int(derivatives or 0) + int(zips or 0)

def monthly_bandwidth_bytes():
    now = _now(); start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return int(db.session.query(func.coalesce(func.sum(DownloadEvent.estimated_bytes), 0)).filter(DownloadEvent.created_at >= start).scalar() or 0)

def level(used, limit):
    ratio = (used / limit) if limit else 0
    return "hard" if ratio >= .95 else "soft" if ratio >= .85 else "warning" if ratio >= .70 else "ok"

def ensure_storage_capacity(incoming):
    from flask import current_app
    used = storage_usage_bytes(); limit = int(current_app.config["STORAGE_QUOTA_BYTES"])
    if used + int(incoming) > limit: raise ValueError("Đã vượt quota lưu trữ.")
    return {"used_bytes": used, "limit_bytes": limit, "level": level(used + int(incoming), limit)}

def ensure_bandwidth(user, amount, *, preview=False):
    from flask import current_app
    used = monthly_bandwidth_bytes(); limit = int(current_app.config["DOWNLOAD_MONTHLY_QUOTA_BYTES"])
    if not preview and used + int(amount) > int(limit * .95): raise ValueError("Đã đạt giới hạn băng thông tháng.")

def record_download(user, *, kind, estimated_bytes, storage_object_id=None, derivative_id=None,
                    source_type=None, module=None, estimated_storage_egress_bytes=None,
                    estimated_client_egress_bytes=None):
    db.session.add(DownloadEvent(user_id=user.id, kind=kind, source_type=source_type, module=module,
        estimated_bytes=max(0, int(estimated_bytes)), storage_object_id=storage_object_id,
        derivative_id=derivative_id, estimated_storage_egress_bytes=estimated_storage_egress_bytes,
        estimated_client_egress_bytes=estimated_client_egress_bytes))

def _now(): return datetime.now(timezone.utc).replace(tzinfo=None)
