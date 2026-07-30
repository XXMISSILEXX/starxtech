"""Safe Company Media upload error contract shared by route and storage layers."""

from app.storage.exceptions import StorageUploadContractError


_MIB = 1024 * 1024
_GIB = 1024 * _MIB


def _size_label(value: int) -> str:
    if value >= _GIB:
        return f"{value / _GIB:.2f}".replace(".", ",") + " GiB"
    return f"{value / _MIB:.0f}".replace(".", ",") + " MiB"


def upload_error(code: str, message: str, *, details=None, retryable=False, status_code=422):
    return StorageUploadContractError(
        code,
        message,
        details=details,
        retryable=retryable,
        status_code=status_code,
    )


def error_envelope(error: StorageUploadContractError) -> dict:
    return {
        "ok": False,
        "error": {
            "code": error.code,
            "message": error.message,
            "details": error.details,
            "retryable": error.retryable,
        },
    }


def item_error(client_file_id, error: StorageUploadContractError) -> dict:
    """Keep the old string message temporarily while callers adopt ``error``."""
    return {
        "client_file_id": client_file_id,
        "accepted": False,
        "error": error_envelope(error)["error"],
        # Deprecated compatibility field. Remove after all clients require the
        # structured ``error`` object.
        "error_message": error.message,
    }


def file_size_error(*, client_file_id, filename, actual_bytes, max_bytes):
    return upload_error(
        "file_size_exceeded",
        f"Tệp {filename or 'đã chọn'} có dung lượng {_size_label(actual_bytes)}, tối đa {_size_label(max_bytes)}.",
        details={"client_file_id": client_file_id, "filename": filename, "actual_bytes": actual_bytes, "max_bytes": max_bytes},
    )


def category_size_error(*, category, client_file_id, filename, actual_bytes, max_bytes):
    label = "Ảnh" if category == "image" else "Video"
    return upload_error(
        f"{category}_size_exceeded",
        f"{label} {filename or 'đã chọn'} có dung lượng {_size_label(actual_bytes)}, tối đa {_size_label(max_bytes)}.",
        details={"actual_bytes": actual_bytes, "max_bytes": max_bytes},
    )
