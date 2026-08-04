import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def read_secret(name: str, default: str | None = None) -> str | None:
    """Read a setting from a Docker-style ``*_FILE`` secret or the environment.

    A file value takes precedence so a Compose secret cannot accidentally be
    overridden by an inherited environment variable.  Values are stripped only
    to remove the newline commonly present in secret files.
    """
    secret_file = os.getenv(f"{name}_FILE")
    if secret_file:
        try:
            value = Path(secret_file).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise RuntimeError(f"Unable to read {name}_FILE") from exc
        if not value:
            raise RuntimeError(f"{name}_FILE is empty")
        return value
    return os.getenv(name, default)


def read_csv_setting(name: str) -> tuple[str, ...]:
    return tuple(value.strip().lower() for value in os.getenv(name, "").split(",") if value.strip())


def read_optional_positive_int(name: str) -> int | None:
    """Read an optional positive integer without treating invalid input as unset."""
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return None
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a positive integer") from exc
    if value <= 0:
        raise RuntimeError(f"{name} must be a positive integer")
    return value


class Config:
    STATIC_ASSET_VERSION = os.getenv("STATIC_ASSET_VERSION", "20260730-8404")
    # Do not supply an implicit environment.  A typo here used to silently
    # retain the development signing key while skipping production checks.
    APP_ENV = os.getenv("APP_ENV")
    DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    SECRET_KEY = read_secret("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = read_secret(
        "DATABASE_URL",
        "postgresql+psycopg://starx:starx@127.0.0.1:5432/starx_daily_report",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_ROOT = os.getenv("UPLOAD_ROOT", str(BASE_DIR / "storage" / "uploads"))
    TMP_ROOT = os.getenv("TMP_ROOT", str(BASE_DIR / "tmp"))
    MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "10"))
    MAX_CONTENT_LENGTH = MAX_UPLOAD_MB * 1024 * 1024
    MAX_FORM_PARTS = int(os.getenv("MAX_FORM_PARTS", "1000"))
    DAILY_REPORT_DIRECT_UPLOAD_ENABLED = os.getenv("DAILY_REPORT_DIRECT_UPLOAD_ENABLED", "true").lower() == "true"
    DAILY_REPORT_MAX_FILES = int(os.getenv("DAILY_REPORT_MAX_FILES", "30"))
    # Deprecated: Daily Reports have a fixed product limit of 10 per section.
    DAILY_REPORT_MAX_FILES_PER_SECTION = 10
    DAILY_REPORT_MAX_FILE_BYTES = int(os.getenv("DAILY_REPORT_MAX_FILE_BYTES", str(25 * 1024 * 1024)))
    DAILY_REPORT_MAX_TOTAL_BYTES = int(os.getenv("DAILY_REPORT_MAX_TOTAL_BYTES", str(300 * 1024 * 1024)))
    DAILY_REPORT_UPLOAD_CONCURRENCY = int(os.getenv("DAILY_REPORT_UPLOAD_CONCURRENCY", "3"))
    DAILY_REPORT_PRESIGN_TTL_SECONDS = int(os.getenv("DAILY_REPORT_PRESIGN_TTL_SECONDS", "900"))
    DAILY_REPORT_SESSION_TTL_SECONDS = int(os.getenv("DAILY_REPORT_SESSION_TTL_SECONDS", "86400"))
    STORAGE_CORS_ALLOWED_ORIGINS = read_csv_setting("STORAGE_CORS_ALLOWED_ORIGINS") or ("http://192.168.1.159:5666",)
    SESSION_COOKIE_HTTPONLY = os.getenv("SESSION_COOKIE_HTTPONLY", "true").lower() == "true"
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_LOGIN_LIMIT = os.getenv("RATELIMIT_LOGIN_LIMIT", "5 per minute")
    RATELIMIT_EXPORT_LIMIT = os.getenv("RATELIMIT_EXPORT_LIMIT", "10 per hour")
    TRUST_PROXY_HOPS = int(os.getenv("TRUST_PROXY_HOPS", "0"))
    TRUSTED_HOSTS = read_csv_setting("TRUSTED_HOSTS")
    STORAGE_PROVIDER = os.getenv("STORAGE_PROVIDER", "fake")
    STORAGE_BUCKET = os.getenv("STORAGE_BUCKET", "starx-local")
    STORAGE_ENDPOINT_URL = os.getenv("STORAGE_ENDPOINT_URL")
    STORAGE_REGION = os.getenv("STORAGE_REGION")
    STORAGE_ACCESS_KEY_ID = read_secret("STORAGE_ACCESS_KEY_ID")
    STORAGE_SECRET_ACCESS_KEY = read_secret("STORAGE_SECRET_ACCESS_KEY")
    STORAGE_PREFIX = os.getenv("STORAGE_PREFIX", "").strip("/")
    STORAGE_UPLOAD_URL_TTL_SECONDS = int(os.getenv("STORAGE_UPLOAD_URL_TTL_SECONDS", "300"))
    STORAGE_DOWNLOAD_URL_TTL_SECONDS = int(os.getenv("STORAGE_DOWNLOAD_URL_TTL_SECONDS", "300"))
    # CloudFly evaluates a presigned POST content-length-range against the
    # complete multipart request, not only the file bytes.  Keep this bounded
    # allowance explicit; exact object size is verified with HEAD on complete.
    STORAGE_PRESIGNED_POST_MULTIPART_OVERHEAD_BYTES = int(
        os.getenv("STORAGE_PRESIGNED_POST_MULTIPART_OVERHEAD_BYTES", str(1024 * 1024))
    )
    STORAGE_MAX_IMAGE_SIZE_MB = int(os.getenv("STORAGE_MAX_IMAGE_SIZE_MB", "50"))
    STORAGE_MAX_DOCUMENT_SIZE_MB = int(os.getenv("STORAGE_MAX_DOCUMENT_SIZE_MB", "200"))
    STORAGE_MAX_VIDEO_SIZE_MB = int(os.getenv("STORAGE_MAX_VIDEO_SIZE_MB", "500"))
    STORAGE_MAX_AUDIO_SIZE_MB = int(os.getenv("STORAGE_MAX_AUDIO_SIZE_MB", "200"))
    STORAGE_MAX_FILES_PER_BATCH = int(os.getenv("STORAGE_MAX_FILES_PER_BATCH", "50"))
    STORAGE_MAX_BATCH_SIZE_MB = int(os.getenv("STORAGE_MAX_BATCH_SIZE_MB", "512"))
    UPLOAD_SELECTION_TTL_SECONDS = int(os.getenv("UPLOAD_SELECTION_TTL_SECONDS", "7200"))
    UPLOAD_SELECTION_MAX_FILES = int(os.getenv("UPLOAD_SELECTION_MAX_FILES", "500"))
    UPLOAD_SELECTION_MAX_BYTES = int(os.getenv("UPLOAD_SELECTION_MAX_BYTES", str(2 * 1024 * 1024 * 1024)))
    UPLOAD_SINGLE_FILE_MAX_BYTES = int(os.getenv("UPLOAD_SINGLE_FILE_MAX_BYTES", str(300 * 1024 * 1024)))
    # Company Media values intentionally remain optional here.  The resolver
    # applies the shared-setting fallback so existing deployments retain their
    # current effective capacity until they explicitly opt into an override.
    COMPANY_MEDIA_MAX_SELECTION_FILES = read_optional_positive_int("COMPANY_MEDIA_MAX_SELECTION_FILES")
    COMPANY_MEDIA_MAX_SELECTION_BYTES = read_optional_positive_int("COMPANY_MEDIA_MAX_SELECTION_BYTES")
    COMPANY_MEDIA_MAX_FILES_PER_BATCH = read_optional_positive_int("COMPANY_MEDIA_MAX_FILES_PER_BATCH")
    COMPANY_MEDIA_MAX_PRESIGN_BATCH_BYTES = read_optional_positive_int("COMPANY_MEDIA_MAX_PRESIGN_BATCH_BYTES")
    COMPANY_MEDIA_MAX_FILE_BYTES = read_optional_positive_int("COMPANY_MEDIA_MAX_FILE_BYTES")
    COMPANY_MEDIA_MAX_IMAGE_BYTES = read_optional_positive_int("COMPANY_MEDIA_MAX_IMAGE_BYTES")
    COMPANY_MEDIA_MAX_VIDEO_BYTES = read_optional_positive_int("COMPANY_MEDIA_MAX_VIDEO_BYTES")
    COMPANY_MEDIA_UPLOAD_CONCURRENCY = read_optional_positive_int("COMPANY_MEDIA_UPLOAD_CONCURRENCY")
    COMPANY_MEDIA_UPLOAD_SESSION_TTL_SECONDS = read_optional_positive_int("COMPANY_MEDIA_UPLOAD_SESSION_TTL_SECONDS")
    DOWNLOAD_SINGLE_FILE_MAX_BYTES = int(os.getenv("DOWNLOAD_SINGLE_FILE_MAX_BYTES", str(300 * 1024 * 1024)))
    STORAGE_QUOTA_BYTES = int(os.getenv("STORAGE_QUOTA_BYTES", str(500 * 1024 * 1024 * 1024)))
    DOWNLOAD_MONTHLY_QUOTA_BYTES = int(os.getenv("DOWNLOAD_MONTHLY_QUOTA_BYTES", str(1024 * 1024 * 1024 * 1024)))
    STORAGE_WARN_RATIO = float(os.getenv("STORAGE_WARN_RATIO", "0.70"))
    STORAGE_SOFT_RATIO = float(os.getenv("STORAGE_SOFT_RATIO", "0.85"))
    STORAGE_HARD_RATIO = float(os.getenv("STORAGE_HARD_RATIO", "0.95"))
    DOWNLOAD_WARN_RATIO = float(os.getenv("DOWNLOAD_WARN_RATIO", "0.70"))
    DOWNLOAD_SOFT_RATIO = float(os.getenv("DOWNLOAD_SOFT_RATIO", "0.85"))
    DOWNLOAD_HARD_RATIO = float(os.getenv("DOWNLOAD_HARD_RATIO", "0.95"))
    STORAGE_PENDING_UPLOAD_HOURS = int(os.getenv("STORAGE_PENDING_UPLOAD_HOURS", "24"))
    BULK_DOWNLOAD_MAX_FILES = int(os.getenv("BULK_DOWNLOAD_MAX_FILES", "100"))
    BULK_DOWNLOAD_MAX_TOTAL_BYTES = int(os.getenv("BULK_DOWNLOAD_MAX_TOTAL_BYTES", str(300 * 1024 * 1024)))
    BULK_DOWNLOAD_ZIP_TTL_SECONDS = int(os.getenv("BULK_DOWNLOAD_ZIP_TTL_SECONDS", "86400"))
    BULK_DOWNLOAD_TEMP_ROOT = os.getenv("BULK_DOWNLOAD_TEMP_ROOT", str(BASE_DIR / "tmp" / "bulk_downloads"))
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL")
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND")
    CELERY_TASK_ALWAYS_EAGER = os.getenv("CELERY_TASK_ALWAYS_EAGER", "false").lower() == "true"
    CELERY_TASK_EAGER_PROPAGATES = os.getenv("CELERY_TASK_EAGER_PROPAGATES", "true").lower() == "true"
    CELERY_RESULT_EXPIRES_SECONDS = int(os.getenv("CELERY_RESULT_EXPIRES_SECONDS", "3600"))
    CELERY_WORKER_PREFETCH_MULTIPLIER = 1
    CELERY_TASK_ACKS_LATE = True
    CELERY_TASK_TIME_LIMIT_IMAGE_SECONDS = int(os.getenv("CELERY_TASK_TIME_LIMIT_IMAGE_SECONDS", "120"))
    CELERY_TASK_SOFT_TIME_LIMIT_IMAGE_SECONDS = int(os.getenv("CELERY_TASK_SOFT_TIME_LIMIT_IMAGE_SECONDS", "90"))
    CELERY_TASK_TIME_LIMIT_VIDEO_SECONDS = int(os.getenv("CELERY_TASK_TIME_LIMIT_VIDEO_SECONDS", "300"))
    CELERY_TASK_SOFT_TIME_LIMIT_VIDEO_SECONDS = int(os.getenv("CELERY_TASK_SOFT_TIME_LIMIT_VIDEO_SECONDS", "240"))
    CELERY_TASK_TIME_LIMIT_BULK_DOWNLOAD_SECONDS = int(os.getenv("CELERY_TASK_TIME_LIMIT_BULK_DOWNLOAD_SECONDS", "1800"))
    REPORT_UPLOAD_CLEANUP_INTERVAL_SECONDS = int(os.getenv("REPORT_UPLOAD_CLEANUP_INTERVAL_SECONDS", "3600"))
    MEDIA_RECONCILIATION_INTERVAL_SECONDS = int(os.getenv("MEDIA_RECONCILIATION_INTERVAL_SECONDS", "900"))
    BULK_DOWNLOAD_CLEANUP_INTERVAL_SECONDS = int(os.getenv("BULK_DOWNLOAD_CLEANUP_INTERVAL_SECONDS", "3600"))
    MEDIA_PROCESSING_MAX_ATTEMPTS = int(os.getenv("MEDIA_PROCESSING_MAX_ATTEMPTS", "3"))
    MEDIA_IMAGE_THUMBNAIL_MAX_SIZE = int(os.getenv("MEDIA_IMAGE_THUMBNAIL_MAX_SIZE", "480"))
    MEDIA_IMAGE_PREVIEW_MAX_SIZE = int(os.getenv("MEDIA_IMAGE_PREVIEW_MAX_SIZE", "1600"))
    MEDIA_VIDEO_POSTER_MAX_SIZE = int(os.getenv("MEDIA_VIDEO_POSTER_MAX_SIZE", "720"))
    MEDIA_TEMP_ROOT = os.getenv("MEDIA_TEMP_ROOT", str(BASE_DIR / "tmp" / "media_processing"))
    MEDIA_ENABLE_PROCESSING = os.getenv("MEDIA_ENABLE_PROCESSING", "true").lower() == "true"
    MEDIA_CACHE_ENABLED = os.getenv("MEDIA_CACHE_ENABLED", "false").lower() == "true"
    MEDIA_CACHE_ROOT = os.getenv(
        "MEDIA_CACHE_ROOT",
        "/tmp/starx-media-cache" if os.getenv("APP_ENV") in {"local", "development", "testing"} else "/app/cache/media",
    )
    MEDIA_CACHE_DELIVERY_MODE = os.getenv("MEDIA_CACHE_DELIVERY_MODE", "send_file")
    MEDIA_CACHE_X_ACCEL_PREFIX = os.getenv("MEDIA_CACHE_X_ACCEL_PREFIX", "/_protected_media_cache/")
    MEDIA_CACHE_MAX_BYTES = int(os.getenv("MEDIA_CACHE_MAX_BYTES", str(5 * 1024 * 1024 * 1024)))
    MEDIA_CACHE_MAX_AGE_DAYS = int(os.getenv("MEDIA_CACHE_MAX_AGE_DAYS", "30"))
