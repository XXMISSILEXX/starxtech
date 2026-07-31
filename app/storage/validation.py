import re
from pathlib import PurePath

from flask import current_app
from app.storage.file_types import (HEIF_BROWSER_FALLBACK_MIME_TYPES, HEIF_EXTENSIONS,
                                    HEIF_MIME_TYPES, POLICIES, canonical_mime)

from app.storage.exceptions import StorageValidationError
from app.storage.company_media_errors import category_size_error, file_size_error
from app.storage.limits import get_company_media_upload_limits


ALLOWED_FILES = {
    "jpg": ("image/jpeg", "image"), "jpeg": ("image/jpeg", "image"), "png": ("image/png", "image"), "webp": ("image/webp", "image"),
    "pdf": ("application/pdf", "document"), "doc": ("application/msword", "document"),
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "document"),
    "xls": ("application/vnd.ms-excel", "document"), "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "document"),
    "ppt": ("application/vnd.ms-powerpoint", "document"), "pptx": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", "document"), "txt": ("text/plain", "document"),
    "mp4": ("video/mp4", "video"), "webm": ("video/webm", "video"), "mov": ("video/quicktime", "video"),
    "mp3": ("audio/mpeg", "audio"), "wav": ("audio/wav", "audio"), "m4a": ("audio/mp4", "audio"),
}
WAV_MIME_TYPES = {"audio/wav", "audio/x-wav"}
CHECKSUM_RE = re.compile(r"^[a-fA-F0-9]{64}$")


def validate_file_metadata(filename, mime_type, size, checksum_sha256=None, module_type="project_documents", limits=None,
                           client_file_id=None):
    filename = (filename or "").strip()
    mime_type = canonical_mime(mime_type)
    ext = PurePath(filename).suffix.lower().lstrip(".")
    policy = POLICIES.get(module_type)
    if not policy or not filename or not ext or ext not in policy:
        raise StorageValidationError("Loại file không được hỗ trợ.")
    expected_mime, category = policy[ext]
    if ext in HEIF_EXTENSIONS:
        if mime_type not in HEIF_MIME_TYPES | HEIF_BROWSER_FALLBACK_MIME_TYPES:
            raise StorageValidationError("Định dạng HEIC/HEIF không hợp lệ hoặc không được hỗ trợ.")
    elif not _mime_matches(expected_mime, mime_type, ext):
        raise StorageValidationError("MIME type không khớp với phần mở rộng file.")
    try:
        size = int(size)
    except (TypeError, ValueError):
        raise StorageValidationError("Kích thước file không hợp lệ.")
    if size <= 0:
        raise StorageValidationError("Kích thước file phải lớn hơn 0.")
    max_size = max_file_size_for_category(category, module_type=module_type, limits=limits)
    if size > max_size:
        if module_type == "company_media":
            limits = limits or get_company_media_upload_limits()
            if size > limits["max_file_bytes"]:
                raise file_size_error(
                    client_file_id=client_file_id,
                    filename=filename,
                    actual_bytes=size,
                    max_bytes=limits["max_file_bytes"],
                )
            if category in {"image", "video"}:
                raise category_size_error(
                    category=category,
                    client_file_id=client_file_id,
                    filename=filename,
                    actual_bytes=size,
                    max_bytes=limits[f"max_{category}_bytes"],
                )
        raise StorageValidationError("File vượt quá dung lượng cho phép.")
    if checksum_sha256 and not CHECKSUM_RE.fullmatch(str(checksum_sha256)):
        raise StorageValidationError("Checksum SHA-256 không hợp lệ.")
    return {"filename": filename, "mime_type": expected_mime, "file_ext": "jpg" if ext == "jpeg" else ext, "file_size": size, "checksum_sha256": checksum_sha256 or None, "category": category}


def _mime_matches(expected, actual, ext):
    return actual == expected or (ext == "wav" and actual in WAV_MIME_TYPES)


def _max_size_bytes(category):
    name = {"image": "STORAGE_MAX_IMAGE_SIZE_MB", "document": "STORAGE_MAX_DOCUMENT_SIZE_MB", "video": "STORAGE_MAX_VIDEO_SIZE_MB", "audio": "STORAGE_MAX_AUDIO_SIZE_MB", "archive": "STORAGE_MAX_DOCUMENT_SIZE_MB"}[category]
    return int(current_app.config[name]) * 1024 * 1024


def max_file_size_for_category(category, *, module_type="project_documents", limits=None):
    """Return the server-enforced byte cap used for a validated upload type."""
    if module_type == "company_media":
        limits = limits or get_company_media_upload_limits()
        if category == "image":
            return min(limits["max_image_bytes"], limits["max_file_bytes"])
        if category == "video":
            return min(limits["max_video_bytes"], limits["max_file_bytes"])
    return min(_max_size_bytes(category), int(current_app.config["UPLOAD_SINGLE_FILE_MAX_BYTES"]))
