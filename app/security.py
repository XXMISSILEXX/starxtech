"""Small, shared security helpers for passwords and deployment settings."""

import re
from urllib.parse import urlparse


MIN_PASSWORD_LENGTH = 12


def storage_connect_source(config) -> str | None:
    """Return only a safe S3 endpoint origin for CSP connect-src."""
    if str(config.get("STORAGE_PROVIDER", "disabled")).lower() != "s3":
        return None
    parsed = urlparse(str(config.get("STORAGE_ENDPOINT_URL", "")).strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def password_policy_errors(password: str) -> list[str]:
    """Return Vietnamese validation errors without ever retaining the password."""
    errors = []
    if len(password or "") < MIN_PASSWORD_LENGTH:
        errors.append(f"Mật khẩu phải có ít nhất {MIN_PASSWORD_LENGTH} ký tự.")

    groups = sum(
        bool(pattern.search(password or ""))
        for pattern in (
            re.compile(r"[A-Z]"),
            re.compile(r"[a-z]"),
            re.compile(r"\d"),
            re.compile(r"[^A-Za-z0-9]"),
        )
    )
    if groups < 3:
        errors.append("Mật khẩu phải có ít nhất 3 trong 4 nhóm: chữ hoa, chữ thường, số, ký tự đặc biệt.")
    return errors


def validate_password(password: str) -> None:
    errors = password_policy_errors(password)
    if errors:
        raise ValueError(" ".join(errors))


def is_default_secret_key(secret_key: str | None) -> bool:
    value = (secret_key or "").strip()
    return not value or value in {"dev-secret-key", "change-me", "change-this-to-a-long-random-secret"} or len(value) < 32


def is_unsafe_production_database_url(database_url: str | None) -> bool:
    """Reject missing, sample, and in-memory database URLs in production."""
    value = (database_url or "").strip()
    return (
        not value
        or value == "postgresql+psycopg://starx:starx@127.0.0.1:5432/starx_daily_report"
        or value.startswith("sqlite:")
    )


def production_configuration_errors(config) -> list[str]:
    if config.get("APP_ENV") != "production":
        return []

    errors = []
    if is_default_secret_key(config.get("SECRET_KEY")):
        errors.append("SECRET_KEY production is missing, default, or too short")
    if is_unsafe_production_database_url(config.get("SQLALCHEMY_DATABASE_URI")):
        errors.append("DATABASE_URL production is missing, sample, or uses SQLite")
    if config.get("DEBUG"):
        errors.append("DEBUG must be disabled in production")
    if not config.get("SESSION_COOKIE_SECURE"):
        errors.append("SESSION_COOKIE_SECURE must be enabled in production")
    if not config.get("SESSION_COOKIE_HTTPONLY"):
        errors.append("SESSION_COOKIE_HTTPONLY must be enabled in production")
    if str(config.get("SESSION_COOKIE_SAMESITE", "")).lower() not in {"lax", "strict"}:
        errors.append("SESSION_COOKIE_SAMESITE must be Lax or Strict in production")
    provider = str(config.get("STORAGE_PROVIDER", "disabled")).lower()
    if provider == "fake":
        errors.append("STORAGE_PROVIDER=fake is not allowed in production")
    if provider == "s3" and (not config.get("STORAGE_BUCKET") or not config.get("STORAGE_ACCESS_KEY_ID") or not config.get("STORAGE_SECRET_ACCESS_KEY")):
        errors.append("S3 storage requires bucket and credentials in production")
    return errors
