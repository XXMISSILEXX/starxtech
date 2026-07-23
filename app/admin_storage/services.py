"""Read-only metadata aggregates for the storage dashboard.

These queries deliberately never list an object-storage bucket.  They are an
operational estimate based solely on metadata persisted by the application.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from flask import current_app
from sqlalchemy import case, func, select

from app.extensions import db
from app.models import BulkDownloadJob, DownloadEvent, StorageDerivative, StorageObject, User

UNKNOWN = "Không xác định / legacy"


class StorageDashboardFilterError(ValueError):
    pass


def now_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def parse_filters(args):
    period = args.get("period", "current_month")
    if period not in {"current_month", "last_7_days", "last_30_days", "custom"}:
        raise StorageDashboardFilterError("Khoảng thời gian không hợp lệ.")
    today = now_utc().date()
    if period == "current_month":
        start, end = today.replace(day=1), today
    elif period == "last_7_days":
        start, end = today - timedelta(days=6), today
    elif period == "last_30_days":
        start, end = today - timedelta(days=29), today
    else:
        try:
            start = datetime.strptime(args.get("from", ""), "%Y-%m-%d").date()
            end = datetime.strptime(args.get("to", ""), "%Y-%m-%d").date()
        except ValueError as exc:
            raise StorageDashboardFilterError("Nhập ngày theo định dạng YYYY-MM-DD.") from exc
        if start > end:
            raise StorageDashboardFilterError("Ngày bắt đầu phải trước hoặc bằng ngày kết thúc.")
    return {
        "period": period, "from": start, "to": end,
        "module": (args.get("module") or "").strip() or None,
        "source_type": (args.get("source_type") or "").strip() or None,
    }


def format_bytes(value):
    value = max(0, int(value or 0))
    units = ("B", "KB", "MB", "GB", "TB", "PB")
    number = float(value)
    for unit in units:
        if number < 1024 or unit == units[-1]:
            return f"{number:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".") + f" {unit}"
        number /= 1024


def quota_status(used, limit, prefix):
    ratio = (int(used or 0) / int(limit)) if limit else 0
    warn = float(current_app.config[f"{prefix}_WARN_RATIO"])
    soft = float(current_app.config[f"{prefix}_SOFT_RATIO"])
    hard = float(current_app.config[f"{prefix}_HARD_RATIO"])
    status = "hard" if ratio >= hard else "soft" if ratio >= soft else "warn" if ratio >= warn else "normal"
    return {"used": int(used or 0), "limit": int(limit or 0), "ratio": ratio, "percent": min(100, round(ratio * 100, 1)), "status": status}


def _event_query(filters):
    query = select(DownloadEvent).where(
        DownloadEvent.created_at >= datetime.combine(filters["from"], datetime.min.time()),
        DownloadEvent.created_at < datetime.combine(filters["to"] + timedelta(days=1), datetime.min.time()),
    )
    if filters["module"]:
        query = query.where(DownloadEvent.module == filters["module"])
    if filters["source_type"]:
        query = query.where(DownloadEvent.source_type == filters["source_type"])
    return query


MODULE_LABELS = {
    "document-library": "Hồ sơ tài liệu",
    "project_documents": "Hồ sơ tài liệu",
    "company-media": "Thư viện ảnh/video công ty",
    "company_media": "Thư viện ảnh/video công ty",
}
SOURCE_TYPE_LABELS = {
    "original": "Tải file gốc",
    "preview": "Xem trước",
    "thumbnail": "Ảnh thu nhỏ",
    "zip_stream": "Tải ZIP",
}


def normalize_module_label(value):
    return MODULE_LABELS.get(value, value or UNKNOWN)


def normalize_source_type_label(value):
    return SOURCE_TYPE_LABELS.get(value, value or UNKNOWN)


def _sum(column):
    return func.coalesce(func.sum(func.coalesce(column, 0)), 0)


def _egress(column, event_table):
    """Use the old single estimate for events written before egress split."""
    return case(
        (event_table.c.estimated_storage_egress_bytes.is_(None) & event_table.c.estimated_client_egress_bytes.is_(None), event_table.c.estimated_bytes),
        else_=func.coalesce(column, 0),
    )


def _breakdown_rows(rows, normalizer):
    return [SimpleNamespace(label=normalizer(row.label), bytes=int(getattr(row, "bytes", 0) or 0),
                            storage_bytes=int(getattr(row, "storage_bytes", 0) or 0),
                            client_bytes=int(getattr(row, "client_bytes", 0) or 0), count=int(row.count or 0))
            for row in rows]


def dashboard_context(filters):
    original_bytes = _sum(StorageObject.file_size).label("bytes")
    original_by_module = db.session.execute(
        select(StorageObject.storage_module.label("label"), original_bytes, func.count(StorageObject.id).label("count"))
        .where(StorageObject.upload_status == "active", StorageObject.deleted_at.is_(None))
        .group_by(StorageObject.storage_module).order_by(original_bytes.desc())
    ).all()
    original_by_module = _breakdown_rows(original_by_module, normalize_module_label)
    derivative_bytes = _sum(StorageDerivative.file_size).label("bytes")
    derivative_by_module = db.session.execute(
        select(StorageObject.storage_module.label("label"), derivative_bytes, func.count(StorageDerivative.id).label("count"))
        .join(StorageObject, StorageObject.id == StorageDerivative.storage_object_id)
        .where(StorageDerivative.deleted_at.is_(None)).group_by(StorageObject.storage_module).order_by(derivative_bytes.desc())
    ).all()
    derivative_by_module = _breakdown_rows(derivative_by_module, normalize_module_label)
    originals = sum(int(row.bytes or 0) for row in original_by_module)
    derivatives = sum(int(row.bytes or 0) for row in derivative_by_module)
    zips = int(db.session.scalar(select(_sum(BulkDownloadJob.zip_size_bytes)).where(
        BulkDownloadJob.status == "succeeded", BulkDownloadJob.expires_at > now_utc(), BulkDownloadJob.zip_size_bytes.is_not(None)
    )) or 0)

    event_query = _event_query(filters).subquery()
    storage_egress = _egress(event_query.c.estimated_storage_egress_bytes, event_query)
    client_egress = _egress(event_query.c.estimated_client_egress_bytes, event_query)
    storage_bytes = int(db.session.scalar(select(_sum(storage_egress))) or 0)
    client_bytes = int(db.session.scalar(select(_sum(client_egress))) or 0)

    module_storage_bytes = _sum(storage_egress).label("storage_bytes")
    module_client_bytes = _sum(client_egress).label("client_bytes")
    module_breakdown = db.session.execute(
        select(event_query.c.module.label("label"), module_storage_bytes, module_client_bytes, func.count().label("count"))
        .group_by(event_query.c.module).order_by((module_storage_bytes + module_client_bytes).desc())
    ).all()
    module_breakdown = _breakdown_rows(module_breakdown, normalize_module_label)
    source_storage_bytes = _sum(storage_egress).label("storage_bytes")
    source_client_bytes = _sum(client_egress).label("client_bytes")
    source_breakdown = db.session.execute(
        select(event_query.c.source_type.label("label"), source_storage_bytes, source_client_bytes, func.count().label("count"))
        .group_by(event_query.c.source_type).order_by((source_storage_bytes + source_client_bytes).desc())
    ).all()
    source_breakdown = _breakdown_rows(source_breakdown, normalize_source_type_label)
    user_bytes = _sum(client_egress).label("bytes")
    top_users = db.session.execute(
        select(User.full_name, User.username, user_bytes, func.count().label("count"))
        .join(User, User.id == event_query.c.user_id).group_by(User.id, User.full_name, User.username)
        .order_by(user_bytes.desc()).limit(10)
    ).all()
    object_bytes = _sum(client_egress).label("bytes")
    top_objects = db.session.execute(
        select(func.coalesce(event_query.c.storage_object_id, StorageDerivative.storage_object_id).label("storage_object_id"), StorageObject.original_filename, StorageObject.storage_module.label("module"), object_bytes, func.count().label("count"))
        .outerjoin(StorageDerivative, StorageDerivative.id == event_query.c.derivative_id)
        .outerjoin(StorageObject, StorageObject.id == func.coalesce(event_query.c.storage_object_id, StorageDerivative.storage_object_id))
        .group_by(event_query.c.storage_object_id, StorageDerivative.storage_object_id, StorageObject.original_filename, StorageObject.storage_module)
        .order_by(object_bytes.desc()).limit(10)
    ).all()
    top_objects = [SimpleNamespace(storage_object_id=row.storage_object_id, original_filename=row.original_filename,
                                   module=normalize_module_label(row.module), bytes=int(row.bytes or 0), count=int(row.count or 0))
                   for row in top_objects]
    events = db.session.execute(
        select(DownloadEvent, User.full_name, User.username, StorageObject.original_filename)
        .join(User, User.id == DownloadEvent.user_id).outerjoin(StorageDerivative, StorageDerivative.id == DownloadEvent.derivative_id)
        .outerjoin(StorageObject, StorageObject.id == func.coalesce(DownloadEvent.storage_object_id, StorageDerivative.storage_object_id))
        .where(DownloadEvent.id.in_(select(event_query.c.id))).order_by(DownloadEvent.created_at.desc()).limit(50)
    ).all()

    usage_by_module = {}
    for rows in (original_by_module, derivative_by_module):
        for row in rows:
            item = usage_by_module.setdefault(row.label, {"label": row.label, "originals": 0, "derivatives": 0})
            item["originals" if rows is original_by_module else "derivatives"] += int(row.bytes or 0)
    for item in usage_by_module.values(): item["total"] = item["originals"] + item["derivatives"]
    return {
        "filters": filters, "storage": quota_status(originals + derivatives + zips, current_app.config["STORAGE_QUOTA_BYTES"], "STORAGE"),
        "bandwidth": quota_status(client_bytes, current_app.config["DOWNLOAD_MONTHLY_QUOTA_BYTES"], "DOWNLOAD"),
        "originals": originals, "derivatives": derivatives, "zips": zips, "storage_egress": storage_bytes, "client_egress": client_bytes,
        "usage_by_module": sorted(usage_by_module.values(), key=lambda x: x["total"], reverse=True),
        "module_breakdown": module_breakdown, "source_breakdown": source_breakdown, "top_users": top_users, "top_objects": top_objects, "events": events,
    }
