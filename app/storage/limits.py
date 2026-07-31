"""Resolved upload limits for modules that intentionally diverge from storage defaults."""

from collections.abc import Mapping

from flask import current_app


_MIB = 1024 * 1024


def _positive_integer(config: Mapping, key: str) -> int:
    value = config.get(key)
    if isinstance(value, bool):
        raise ValueError(f"{key} must be a positive integer")
    try:
        value = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be a positive integer") from exc
    if value <= 0:
        raise ValueError(f"{key} must be a positive integer")
    return value


def _override_or_fallback(config: Mapping, override_key: str, fallback: int) -> int:
    override = config.get(override_key)
    if override is None or override == "":
        return fallback
    return _positive_integer(config, override_key)


def get_company_media_upload_limits(config: Mapping | None = None) -> dict[str, int]:
    """Return the public, server-authoritative Company Media upload limits.

    New settings are optional to preserve existing deployments.  Once present,
    each setting must be a positive integer; zero, negative, and malformed
    values are rejected instead of quietly reducing (or increasing) capacity.
    """
    config = current_app.config if config is None else config
    max_file_bytes = _override_or_fallback(
        config, "COMPANY_MEDIA_MAX_FILE_BYTES", _positive_integer(config, "UPLOAD_SINGLE_FILE_MAX_BYTES")
    )
    max_image_bytes = min(max_file_bytes, _override_or_fallback(
        config, "COMPANY_MEDIA_MAX_IMAGE_BYTES", _positive_integer(config, "STORAGE_MAX_IMAGE_SIZE_MB") * _MIB
    ))
    max_video_bytes = min(max_file_bytes, _override_or_fallback(
        config,
        "COMPANY_MEDIA_MAX_VIDEO_BYTES",
        min(_positive_integer(config, "STORAGE_MAX_VIDEO_SIZE_MB") * _MIB, max_file_bytes),
    ))
    return {
        "max_selection_files": _override_or_fallback(
            config, "COMPANY_MEDIA_MAX_SELECTION_FILES", _positive_integer(config, "UPLOAD_SELECTION_MAX_FILES")
        ),
        "max_selection_bytes": _override_or_fallback(
            config, "COMPANY_MEDIA_MAX_SELECTION_BYTES", _positive_integer(config, "UPLOAD_SELECTION_MAX_BYTES")
        ),
        "max_files_per_batch": _override_or_fallback(
            config, "COMPANY_MEDIA_MAX_FILES_PER_BATCH", _positive_integer(config, "STORAGE_MAX_FILES_PER_BATCH")
        ),
        "max_batch_bytes": _override_or_fallback(
            config,
            "COMPANY_MEDIA_MAX_PRESIGN_BATCH_BYTES",
            _positive_integer(config, "STORAGE_MAX_BATCH_SIZE_MB") * _MIB,
        ),
        "max_file_bytes": max_file_bytes,
        "max_image_bytes": max_image_bytes,
        "max_video_bytes": max_video_bytes,
        "upload_concurrency": _override_or_fallback(config, "COMPANY_MEDIA_UPLOAD_CONCURRENCY", 3),
        "session_ttl_seconds": _override_or_fallback(
            config, "COMPANY_MEDIA_UPLOAD_SESSION_TTL_SECONDS", _positive_integer(config, "UPLOAD_SELECTION_TTL_SECONDS")
        ),
    }
