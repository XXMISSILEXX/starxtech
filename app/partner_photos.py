"""Private, authorised photo delivery for Partners and Companies."""
from pathlib import Path

from flask import Response, stream_with_context
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models import StorageDerivative
from app.storage.providers import get_storage_provider
from app.storage.quota import ensure_bandwidth, record_download
from app.display_images import (DisplayImageCleanupError, DisplayImageError,
                                finalize_display_image_change, remove_display_image,
                                replace_display_image)

PHOTO_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "heic", "heif"}
MAX_PHOTO_BYTES = 10 * 1024 * 1024


PartnerPhotoError = DisplayImageError


def replace_photo(record, upload, *, kind, user):
    scope = "partner-avatars" if kind == "profile_photo" else "company-logos"
    change = replace_display_image(record, upload, attribute=f"{kind}_storage_object", scope=scope, user=user)
    db.session.commit()
    try:
        finalize_display_image_change(change)
    except DisplayImageCleanupError:
        db.session.rollback()
        return {"object": change.object, "cleanup_pending": True}
    return {"object": change.object, "cleanup_pending": False}


def delete_photo(record, *, kind):
    change = remove_display_image(record, attribute=f"{kind}_storage_object")
    db.session.commit()
    try:
        finalize_display_image_change(change)
    except DisplayImageCleanupError:
        db.session.rollback()
        return {"cleanup_pending": True}
    return {"cleanup_pending": False}


def preview_response(record, *, kind, user):
    """Deliver a validated display image from the authorised same-origin URL."""
    obj = getattr(record, f"{kind}_storage_object")
    if not obj or obj.deleted_at is not None or obj.upload_status != "active":
        raise PartnerPhotoError("Ảnh chưa sẵn sàng.")
    derivative = StorageDerivative.query.filter(StorageDerivative.storage_object_id == obj.id,
        StorageDerivative.derivative_type.in_(("thumbnail", "preview")), StorageDerivative.deleted_at.is_(None)).order_by(
        StorageDerivative.derivative_type.asc()).first()
    target = derivative or obj
    if target.mime_type != "image/webp" or target.file_ext != "webp" or target.file_size < 0:
        raise PartnerPhotoError("Ảnh không sẵn sàng.")
    stored_name = secure_filename(obj.original_filename or "")
    if not stored_name:
        raise PartnerPhotoError("Ảnh không sẵn sàng.")
    filename = f"{Path(stored_name).stem or 'photo'}.webp"
    ensure_bandwidth(user, target.file_size, preview=True)
    record_download(user, kind="thumbnail" if derivative and derivative.derivative_type == "thumbnail" else "preview",
        source_type="thumbnail" if derivative and derivative.derivative_type == "thumbnail" else ("preview" if derivative else "original"),
        module="partner-management", estimated_bytes=target.file_size,
        storage_object_id=None if derivative else obj.id, derivative_id=derivative.id if derivative else None,
        estimated_storage_egress_bytes=target.file_size, estimated_client_egress_bytes=target.file_size)
    db.session.commit()
    try:
        stream = get_storage_provider().open_object(target.bucket, target.object_key)
    except Exception as exc:
        raise PartnerPhotoError("Ảnh chưa sẵn sàng.") from exc
    response = Response(stream_with_context(_stream_chunks(stream)), mimetype="image/webp")
    response.headers["Content-Length"] = str(int(target.file_size))
    response.headers["Content-Disposition"] = f'inline; filename="{filename}"'
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def _stream_chunks(stream, chunk_size=64 * 1024):
    try:
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                break
            yield chunk
    finally:
        close = getattr(stream, "close", None)
        if close:
            close()
