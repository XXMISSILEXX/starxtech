"""Strict, module-aware file metadata policy for direct uploads."""

DOCUMENT_LIBRARY_TYPES = {
    "jpg": ("image/jpeg", "image"), "jpeg": ("image/jpeg", "image"), "png": ("image/png", "image"),
    "webp": ("image/webp", "image"), "gif": ("image/gif", "image"), "heic": ("image/heic", "image"), "heif": ("image/heif", "image"),
    "pdf": ("application/pdf", "document"), "doc": ("application/msword", "document"),
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "document"),
    "xls": ("application/vnd.ms-excel", "document"), "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "document"),
    "ppt": ("application/vnd.ms-powerpoint", "document"), "pptx": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", "document"), "txt": ("text/plain", "document"),
    "mp4": ("video/mp4", "video"), "webm": ("video/webm", "video"), "mov": ("video/quicktime", "video"), "m4v": ("video/x-m4v", "video"),
    "zip": ("application/zip", "archive"),
}

# Media deliberately excludes documents, audio and archives.
COMPANY_MEDIA_TYPES = {key: value for key, value in DOCUMENT_LIBRARY_TYPES.items() if value[1] in {"image", "video"}}
POLICIES = {"project_documents": DOCUMENT_LIBRARY_TYPES, "document-library": DOCUMENT_LIBRARY_TYPES,
            "company_media": COMPANY_MEDIA_TYPES, "company-media": COMPANY_MEDIA_TYPES,
            "daily_reports": {key: value for key, value in DOCUMENT_LIBRARY_TYPES.items() if key in {"jpg", "jpeg", "png", "webp"}},
            "daily-reports": {key: value for key, value in DOCUMENT_LIBRARY_TYPES.items() if key in {"jpg", "jpeg", "png", "webp"}},
            "partner_management": {key: value for key, value in DOCUMENT_LIBRARY_TYPES.items() if key in {"jpg", "jpeg", "png", "webp", "heic", "heif"}},
            "partner-management": {key: value for key, value in DOCUMENT_LIBRARY_TYPES.items() if key in {"jpg", "jpeg", "png", "webp", "heic", "heif"}}}
MIME_ALIASES = {"image/jpg": "image/jpeg", "image/x-heic": "image/heic", "image/x-heif": "image/heif",
                "video/m4v": "video/x-m4v", "application/x-zip-compressed": "application/zip"}
HEIF_EXTENSIONS = {"heic", "heif"}
HEIF_MIME_TYPES = {"image/heic", "image/heif", "image/heic-sequence", "image/heif-sequence"}
HEIF_BROWSER_FALLBACK_MIME_TYPES = {"", "application/octet-stream"}
BLOCKED_EXTENSIONS = {"exe", "msi", "bat", "cmd", "com", "sh", "bash", "ps1", "py", "js", "jar", "php", "svg", "html", "htm", "xml"}

def canonical_mime(value):
    return MIME_ALIASES.get((value or "").strip().lower(), (value or "").strip().lower())
