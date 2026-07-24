"""Canonical, safe object-key construction for S3-backed modules."""
from datetime import datetime, timezone
from pathlib import PurePosixPath
import re
from uuid import uuid4

STORAGE_MODULE_DOCUMENT_LIBRARY = "document-library"
STORAGE_MODULE_COMPANY_MEDIA = "company-media"
STORAGE_MODULE_DAILY_REPORTS = "daily-reports"
STORAGE_MODULE_PARTNER_MANAGEMENT = "partner-management"

_MODULE_ALIASES = {
    "project_documents": STORAGE_MODULE_DOCUMENT_LIBRARY,
    "document-library": STORAGE_MODULE_DOCUMENT_LIBRARY,
    "company_media": STORAGE_MODULE_COMPANY_MEDIA,
    "company-media": STORAGE_MODULE_COMPANY_MEDIA,
    "daily_reports": STORAGE_MODULE_DAILY_REPORTS,
    "daily-reports": STORAGE_MODULE_DAILY_REPORTS,
    "partner_management": STORAGE_MODULE_PARTNER_MANAGEMENT,
    "partner-management": STORAGE_MODULE_PARTNER_MANAGEMENT,
}
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._() -]+")


def normalize_storage_module(module):
    try:
        return _MODULE_ALIASES[str(module).strip().lower()]
    except KeyError as exc:
        raise ValueError("Storage module không hợp lệ.") from exc


def safe_storage_filename(filename, fallback="file"):
    """Return a filename safe for object keys and ZIP entries, never a path."""
    value = PurePosixPath(str(filename or "").replace("\\", "/")).name
    value = _SAFE_NAME.sub("-", value).strip(" .-")
    if value in {"", ".", ".."}:
        value = fallback
    return value[:180]


def _prefix(prefix):
    return str(prefix or "").strip("/")


def _join(prefix, *parts):
    values = [value.strip("/") for value in (_prefix(prefix), *map(str, parts)) if value]
    return "/".join(values)


def build_original_key(module, object_id_or_uuid, filename, prefix="", now=None):
    now = now or datetime.now(timezone.utc)
    storage_module = normalize_storage_module(module)
    token = safe_storage_filename(str(object_id_or_uuid or uuid4().hex), fallback=uuid4().hex)
    # Original display names live in database metadata. Keep object paths
    # opaque so user input (including traversal attempts) is never exposed in
    # S3 keys.
    extension = safe_storage_filename(filename, fallback="file").rsplit(".", 1)[-1].lower()
    extension = extension if extension and extension != "file" else "bin"
    name = safe_storage_filename(filename, fallback=f"file.{extension}")
    # Daily reports and partner photos deliberately retain a safe display name
    # in their opaque object namespace; other modules retain legacy behaviour.
    if storage_module in {STORAGE_MODULE_DAILY_REPORTS, STORAGE_MODULE_PARTNER_MANAGEMENT}:
        return _join(prefix, storage_module, "originals", f"{now:%Y}", f"{now:%m}", token, name)
    return _join(prefix, storage_module, "originals", f"{now:%Y}", f"{now:%m}", token, f"{uuid4().hex}.{extension}")


def build_derivative_key(module, original_object_id, derivative_type, extension="webp", prefix="", now=None):
    now = now or datetime.now(timezone.utc)
    storage_module = normalize_storage_module(module)
    token = safe_storage_filename(str(original_object_id), fallback=uuid4().hex)
    kind = safe_storage_filename(derivative_type, fallback="preview").replace(".", "-")
    ext = safe_storage_filename(extension, fallback="webp").lstrip(".") or "webp"
    return _join(prefix, storage_module, "derivatives", f"{now:%Y}", f"{now:%m}", token, f"{kind}.{ext}")


def build_partner_photo_key(record_type, filename, prefix="", now=None):
    """Partner/Company originals have an explicit non-user-controlled scope."""
    now = now or datetime.now(timezone.utc)
    if record_type not in {"partners", "companies"}:
        raise ValueError("Loại ảnh đối tác không hợp lệ.")
    return _join(prefix, STORAGE_MODULE_PARTNER_MANAGEMENT, "originals", record_type,
                 f"{now:%Y}", f"{now:%m}", uuid4().hex,
                 safe_storage_filename(filename, fallback="photo.webp"))


def build_display_image_key(scope, prefix="", now=None):
    """Opaque WebP key for normalised UI images."""
    now = now or datetime.now(timezone.utc)
    allowed = {"partner-avatars", "company-logos", "account-profiles", "branding"}
    if scope not in allowed:
        raise ValueError("Phạm vi ảnh hiển thị không hợp lệ.")
    return _join(prefix, "display-images", scope, f"{now:%Y}", f"{now:%m}", f"{uuid4().hex}.webp")


def build_bulk_zip_key(module, job_id, filename, prefix="", now=None):
    now = now or datetime.now(timezone.utc)
    storage_module = normalize_storage_module(module)
    name = safe_storage_filename(filename, fallback="bulk-download.zip")
    if not name.lower().endswith(".zip"):
        name = f"{name}.zip"
    return _join(prefix, storage_module, "bulk-downloads", f"{now:%Y}", f"{now:%m}", safe_storage_filename(str(job_id), fallback=uuid4().hex), name)


# Compatibility helper retained for legacy callers. New module code must use
# the builders above rather than string replacement.
def generate_original_key(file_ext, prefix="", now=None):
    return _join(prefix, "originals", f"{(now or datetime.now(timezone.utc)):%Y}", f"{(now or datetime.now(timezone.utc)):%m}", f"{uuid4().hex}.{safe_storage_filename(file_ext, 'bin').lstrip('.')}")
