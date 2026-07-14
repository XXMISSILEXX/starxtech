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


class Config:
    APP_ENV = os.getenv("APP_ENV", "local")
    DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true" and APP_ENV != "production"
    SECRET_KEY = read_secret("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_DATABASE_URI = read_secret(
        "DATABASE_URL",
        "postgresql+psycopg://starx:starx@127.0.0.1:5432/starx_daily_report",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_ROOT = os.getenv("UPLOAD_ROOT", str(BASE_DIR / "storage" / "uploads"))
    TMP_ROOT = os.getenv("TMP_ROOT", str(BASE_DIR / "tmp"))
    MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "10"))
    MAX_CONTENT_LENGTH = MAX_UPLOAD_MB * 1024 * 1024
    MAX_IMAGES_PER_SECTION = int(os.getenv("MAX_IMAGES_PER_SECTION", "3"))
    SESSION_COOKIE_HTTPONLY = os.getenv("SESSION_COOKIE_HTTPONLY", "true").lower() == "true"
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_LOGIN_LIMIT = os.getenv("RATELIMIT_LOGIN_LIMIT", "5 per minute")
    RATELIMIT_EXPORT_LIMIT = os.getenv("RATELIMIT_EXPORT_LIMIT", "10 per hour")
    TRUST_PROXY_HOPS = int(os.getenv("TRUST_PROXY_HOPS", "0"))
    TRUSTED_HOSTS = read_csv_setting("TRUSTED_HOSTS")
