"""Safe, shared contracts for browser-initiated signed downloads."""

from collections.abc import Mapping

from flask import current_app


DOWNLOAD_ERROR_MESSAGE = "Không thể tạo liên kết tải xuống."


class SignedDownloadError(RuntimeError):
    """A client-safe failure while preparing a signed original download."""

    def __init__(self, code, message, *, retryable, status_code, category):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.status_code = status_code
        self.category = category


def unavailable_source_error():
    return SignedDownloadError(
        "download_source_unavailable",
        "Tệp nguồn để tải xuống không còn sẵn sàng.",
        retryable=False,
        status_code=404,
        category="source",
    )


def signing_unavailable_error(category="provider"):
    return SignedDownloadError(
        "signed_download_unavailable", DOWNLOAD_ERROR_MESSAGE,
        retryable=True, status_code=502, category=category,
    )


def _download_ttl_seconds():
    try:
        ttl = int(current_app.config["STORAGE_DOWNLOAD_URL_TTL_SECONDS"])
    except (KeyError, TypeError, ValueError) as exc:
        raise SignedDownloadError(
            "signed_download_unavailable", DOWNLOAD_ERROR_MESSAGE,
            retryable=True, status_code=503, category="configuration",
        ) from exc
    if not 1 <= ttl <= 86_400:
        raise SignedDownloadError(
            "signed_download_unavailable", DOWNLOAD_ERROR_MESSAGE,
            retryable=True, status_code=503, category="configuration",
        )
    return ttl


def create_attachment_download(provider, storage_object, filename):
    """Sign an active original and return the browser single-download contract."""
    ttl = _download_ttl_seconds()
    try:
        result = provider.create_presigned_download(
            storage_object.bucket, storage_object.object_key, ttl, "attachment", filename,
        )
    except Exception as exc:
        raise signing_unavailable_error() from exc
    if not isinstance(result, Mapping) or not isinstance(result.get("url"), str) or not result["url"].strip() or not result.get("expires_at"):
        raise SignedDownloadError(
            "signed_download_invalid_response", DOWNLOAD_ERROR_MESSAGE,
            retryable=True, status_code=502, category="provider_response",
        )
    return {
        "ok": True,
        "url": result["url"],
        "expires_at": result["expires_at"],
        "filename": filename,
        "disposition": "attachment",
    }


def error_payload(error):
    return {
        "ok": False,
        "error": {
            "code": error.code,
            "message": error.message,
            "retryable": error.retryable,
        },
    }
