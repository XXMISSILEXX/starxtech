"""Small, private image pipeline for display-only records.

Unlike report attachments these objects are never downloadable originals: they
are normalised to WebP before they leave the application process.
"""
import hashlib
import io
import tempfile
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import delete, select, update
from flask import current_app
from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import (Company, CompanyMediaFile, DownloadEvent, MediaProcessingJob,
                        Partner, ProjectDocumentFile, ReportAttachment,
                        StorageDerivative, StorageObject, SystemSetting, UploadBatchItem,
                        User)
from app.storage.exceptions import StorageNotFoundError, StorageValidationError
from app.storage.keys import build_display_image_key
from app.storage.providers import get_storage_provider
from app.storage.quota import ensure_storage_capacity

try:  # pillow-heif is an explicit project dependency, but keep CLI usable if absent.
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:  # pragma: no cover - deployment configuration error
    pass

IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "heic", "heif"}
MAX_DISPLAY_IMAGE_BYTES = 10 * 1024 * 1024


class DisplayImageError(ValueError):
    pass


class DisplayImageCleanupError(DisplayImageError):
    """The new reference is durable, but stale provider bytes need a retry."""


@dataclass(frozen=True)
class DisplayImageChange:
    object: StorageObject | None
    superseded_object: StorageObject | None


def replace_display_image(record, upload, *, attribute, scope, user):
    if upload is None or not upload.filename:
        raise DisplayImageError("Vui lòng chọn ảnh.")
    original_filename = secure_filename(upload.filename) or "image"
    extension = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else ""
    if extension not in IMAGE_EXTENSIONS:
        raise DisplayImageError("Chỉ cho phép ảnh JPG, JPEG, PNG, WebP, HEIC hoặc HEIF.")
    raw = upload.read()
    if not raw or len(raw) > MAX_DISPLAY_IMAGE_BYTES:
        raise DisplayImageError("Ảnh phải có dung lượng từ 1 byte đến 10 MB.")
    try:
        with Image.open(io.BytesIO(raw)) as source:
            source.verify()
        with Image.open(io.BytesIO(raw)) as source:
            image = ImageOps.exif_transpose(source)
            image.load()
            if image.width < 1 or image.height < 1:
                raise OSError("empty image")
            image.thumbnail((768, 768), Image.Resampling.LANCZOS)
            if image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
            output = io.BytesIO()
            image.save(output, "WEBP", quality=88, method=4)
            encoded = output.getvalue()
            width, height = image.size
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        if extension in {"heic", "heif"}:
            raise DisplayImageError("Không thể xử lý ảnh này. Vui lòng chuyển ảnh sang JPG/PNG/WebP rồi tải lại.") from exc
        raise DisplayImageError("Tệp tải lên không phải ảnh hợp lệ.") from exc
    try:
        ensure_storage_capacity(len(encoded))
        key = build_display_image_key(scope, current_app.config["STORAGE_PREFIX"])
        obj = StorageObject(bucket=current_app.config["STORAGE_BUCKET"], object_key=key,
            storage_module="partner-management" if scope in {"partner-avatars", "company-logos"} else scope,
            original_filename=original_filename, mime_type="image/webp", file_ext="webp", file_size=len(encoded),
            checksum_sha256=hashlib.sha256(encoded).hexdigest(), width=width, height=height,
            uploaded_by_id=user.id, upload_status="active", processing_status="none")
        db.session.add(obj); db.session.flush()
        with tempfile.NamedTemporaryFile(suffix=".webp") as temp:
            temp.write(encoded); temp.flush()
            get_storage_provider().upload_object(obj.bucket, obj.object_key, temp.name, "image/webp", {"sha256": obj.checksum_sha256})
    except StorageValidationError as exc:
        raise DisplayImageError(str(exc)) from exc
    old = getattr(record, attribute)
    setattr(record, f"{attribute}_id", obj.id)
    # Do not hide the old object from quota before its provider bytes are
    # removed.  The caller commits this new reference first, then performs the
    # bounded cleanup below.  A failed provider delete therefore remains
    # visible and quota-accounted instead of becoming an invisible orphan.
    return DisplayImageChange(object=obj, superseded_object=old)


def remove_display_image(record, *, attribute):
    old = getattr(record, attribute)
    setattr(record, f"{attribute}_id", None)
    return DisplayImageChange(object=None, superseded_object=old)


def finalize_display_image_change(change, *, provider=None):
    """Delete an unreferenced superseded image after its new reference commits.

    This deliberately does no broad scan in a request.  Provider failures make
    no metadata change, leaving the active, unreferenced object quota-accounted
    and eligible for the trusted reconciliation helper.
    """
    old = change.superseded_object if change else None
    if not old:
        return {"cleaned": 0, "skipped": False, "retryable": False}
    old = db.session.get(StorageObject, old.id)
    if old is None:
        return {"cleaned": 0, "skipped": False, "retryable": False}
    if storage_object_has_live_reference(old.id):
        return {"cleaned": 0, "skipped": bool(old), "retryable": False}
    _delete_display_storage_object(old, provider=provider)
    db.session.commit()
    return {"cleaned": 1, "skipped": False, "retryable": False}


def cleanup_unreferenced_display_images(*, dry_run=True, provider=None, batch_size=100):
    """Trusted, bounded reconciliation for display-image cleanup retries."""
    try:
        batch_size = max(1, int(batch_size))
    except (TypeError, ValueError) as exc:
        raise ValueError("batch_size must be a positive integer") from exc
    objects = StorageObject.query.filter(
        StorageObject.storage_module.in_(("account-profiles", "partner-management", "branding")),
        StorageObject.upload_status == "active",
        StorageObject.deleted_at.is_(None),
    ).order_by(StorageObject.id.asc()).limit(batch_size).all()
    candidates = [obj for obj in objects if not storage_object_has_live_reference(obj.id)]
    result = {"matched": len(candidates), "cleaned": 0, "failed": 0, "dry_run": dry_run}
    if dry_run:
        return result
    for obj in candidates:
        try:
            _delete_display_storage_object(obj, provider=provider)
            db.session.commit()
            result["cleaned"] += 1
        except DisplayImageCleanupError:
            db.session.rollback()
            result["failed"] += 1
    return result


def storage_object_has_live_reference(storage_object_id):
    """Conservative canonical reference guard shared by display cleanup paths."""
    storage_object_id = int(storage_object_id)
    checks = (
        select(User.id).where(User.avatar_storage_object_id == storage_object_id),
        select(Company.id).where(Company.company_photo_storage_object_id == storage_object_id),
        select(Partner.id).where(Partner.profile_photo_storage_object_id == storage_object_id),
        select(SystemSetting.key).where(SystemSetting.brand_logo_storage_object_id == storage_object_id),
        select(UploadBatchItem.id).where(UploadBatchItem.storage_object_id == storage_object_id),
        select(ReportAttachment.id).where(ReportAttachment.storage_object_id == storage_object_id),
        select(ProjectDocumentFile.id).where(ProjectDocumentFile.storage_object_id == storage_object_id),
        select(CompanyMediaFile.id).where(CompanyMediaFile.storage_object_id == storage_object_id),
    )
    return any(db.session.scalar(check.limit(1)) is not None for check in checks)


def _delete_display_storage_object(storage_object, *, provider=None):
    if storage_object_has_live_reference(storage_object.id):
        return False
    derivatives = StorageDerivative.query.filter_by(storage_object_id=storage_object.id).all()
    provider = provider or get_storage_provider()
    try:
        for item in [*derivatives, storage_object]:
            try:
                provider.delete_object(item.bucket, item.object_key)
            except StorageNotFoundError:
                continue
    except Exception as exc:
        raise DisplayImageCleanupError("Không thể dọn dẹp ảnh cũ; hệ thống sẽ thử lại.") from exc

    derivative_ids = [item.id for item in derivatives]
    if derivative_ids:
        db.session.execute(update(DownloadEvent).where(
            DownloadEvent.derivative_id.in_(derivative_ids)
        ).values(derivative_id=None))
        db.session.execute(delete(StorageDerivative).where(
            StorageDerivative.id.in_(derivative_ids)
        ))
    db.session.execute(delete(MediaProcessingJob).where(
        MediaProcessingJob.storage_object_id == storage_object.id
    ))
    db.session.execute(update(DownloadEvent).where(
        DownloadEvent.storage_object_id == storage_object.id
    ).values(storage_object_id=None))
    db.session.delete(storage_object)
    db.session.flush()
    return True
