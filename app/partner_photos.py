"""Compatibility facade for the shared private display-image pipeline."""
import hashlib
import tempfile
from pathlib import Path

from flask import current_app
from app.extensions import db
from app.models import StorageDerivative
from app.storage.providers import get_storage_provider
from app.storage.quota import ensure_bandwidth, ensure_storage_capacity, record_download
from app.display_images import DisplayImageError, remove_display_image, replace_display_image

PHOTO_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "heic", "heif"}
MAX_PHOTO_BYTES = 10 * 1024 * 1024


PartnerPhotoError = DisplayImageError


def replace_photo(record, upload, *, kind, user):
    scope = "partner-avatars" if kind == "profile_photo" else "company-logos"
    obj = replace_display_image(record, upload, attribute=f"{kind}_storage_object", scope=scope, user=user)
    db.session.commit()
    return obj


def delete_photo(record, *, kind):
    remove_display_image(record, attribute=f"{kind}_storage_object")
    db.session.commit()


def signed_preview(record, *, kind, user):
    obj = getattr(record, f"{kind}_storage_object")
    if not obj or obj.deleted_at is not None or obj.upload_status != "active":
        raise PartnerPhotoError("Ảnh chưa sẵn sàng.")
    derivative = StorageDerivative.query.filter(StorageDerivative.storage_object_id == obj.id,
        StorageDerivative.derivative_type.in_(("thumbnail", "preview")), StorageDerivative.deleted_at.is_(None)).order_by(
        StorageDerivative.derivative_type.asc()).first()
    target = derivative or obj
    ensure_bandwidth(user, target.file_size, preview=True)
    record_download(user, kind="thumbnail" if derivative and derivative.derivative_type == "thumbnail" else "preview",
        source_type="thumbnail" if derivative and derivative.derivative_type == "thumbnail" else ("preview" if derivative else "original"),
        module="partner-management", estimated_bytes=target.file_size,
        storage_object_id=None if derivative else obj.id, derivative_id=derivative.id if derivative else None,
        estimated_storage_egress_bytes=target.file_size, estimated_client_egress_bytes=target.file_size)
    db.session.commit()
    return get_storage_provider().create_presigned_download(target.bucket, target.object_key,
        current_app.config["STORAGE_DOWNLOAD_URL_TTL_SECONDS"], "inline", obj.original_filename)
