"""Small, private image pipeline for display-only records.

Unlike report attachments these objects are never downloadable originals: they
are normalised to WebP before they leave the application process.
"""
import hashlib
import io
import tempfile
from pathlib import Path

from flask import current_app
from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import StorageObject
from app.storage.exceptions import StorageValidationError
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
    if old:
        old.deleted_at = db.func.now(); old.upload_status = "deleted"
    return obj


def remove_display_image(record, *, attribute):
    old = getattr(record, attribute)
    if old:
        old.deleted_at = db.func.now(); old.upload_status = "deleted"
    setattr(record, f"{attribute}_id", None)
