"""Small, shared security helpers for passwords and deployment settings."""

import re
from urllib.parse import urlparse


MIN_PASSWORD_LENGTH = 12
ALLOWED_APP_ENVS = frozenset({"local", "development", "testing", "production"})
_PLACEHOLDER_SECRETS = frozenset({
    "dev-secret-key", "change-me", "change-this-to-a-long-random-secret",
    "replace-with-a-generated-secret", "your-secret-key", "placeholder",
})


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
    return not value or value.lower() in _PLACEHOLDER_SECRETS or len(value) < 32


def is_unsafe_production_database_url(database_url: str | None) -> bool:
    """Reject non-PostgreSQL, missing, sample, and SQLite URLs in production."""
    value = (database_url or "").strip()
    parsed = urlparse(value)
    return (
        not value
        or value == "postgresql+psycopg://starx:starx@127.0.0.1:5432/starx_daily_report"
        or value.startswith("sqlite:")
        or not parsed.scheme.startswith("postgresql")
    )


def _is_valid_redis_url(value: str | None, *, allow_loopback: bool = False) -> bool:
    parsed = urlparse((value or "").strip())
    if parsed.scheme not in {"redis", "rediss"} or not parsed.hostname:
        return False
    return allow_loopback or parsed.hostname.lower() not in {"localhost", "127.0.0.1", "::1"}


def configuration_errors(config) -> list[str]:
    """Return canonical, secret-safe startup errors for every environment.

    This is intentionally shared by application startup and ``security-audit``
    so an audit result cannot disagree with the process that serves requests.
    """
    app_env = config.get("APP_ENV")
    errors = []
    if not isinstance(app_env, str) or app_env not in ALLOWED_APP_ENVS:
        errors.append("APP_ENV must be exactly one of: local, development, testing, production")
        return errors
    if app_env != "production":
        return errors

    if is_default_secret_key(config.get("SECRET_KEY")):
        errors.append("SECRET_KEY production is missing, default, or too short")
    if is_unsafe_production_database_url(config.get("SQLALCHEMY_DATABASE_URI")):
        errors.append("DATABASE_URL production is missing, sample, or uses SQLite")
    if config.get("DEBUG") or config.get("TESTING"):
        errors.append("DEBUG and TESTING must be disabled in production")
    if not config.get("SESSION_COOKIE_SECURE"):
        errors.append("SESSION_COOKIE_SECURE must be enabled in production")
    if not config.get("SESSION_COOKIE_HTTPONLY"):
        errors.append("SESSION_COOKIE_HTTPONLY must be enabled in production")
    if str(config.get("SESSION_COOKIE_SAMESITE", "")).lower() not in {"lax", "strict"}:
        errors.append("SESSION_COOKIE_SAMESITE must be Lax or Strict in production")
    provider = str(config.get("STORAGE_PROVIDER", "disabled")).lower()
    if provider != "s3":
        errors.append("STORAGE_PROVIDER must be s3 in production")
    endpoint = str(config.get("STORAGE_ENDPOINT_URL") or "").strip()
    parsed_endpoint = urlparse(endpoint)
    if not endpoint or parsed_endpoint.scheme not in {"http", "https"} or not parsed_endpoint.netloc:
        errors.append("S3 storage requires a valid endpoint in production")
    if not str(config.get("STORAGE_BUCKET") or "").strip() or not str(config.get("STORAGE_REGION") or "").strip():
        errors.append("S3 storage requires bucket and region in production")
    if not config.get("STORAGE_ACCESS_KEY_ID") or not config.get("STORAGE_SECRET_ACCESS_KEY"):
        errors.append("S3 storage requires credentials in production")
    if not _is_valid_redis_url(config.get("RATELIMIT_STORAGE_URI")):
        errors.append("RATELIMIT_STORAGE_URI must be a non-loopback Redis URL in production")
    if not _is_valid_redis_url(config.get("CELERY_BROKER_URL")) or not _is_valid_redis_url(config.get("CELERY_RESULT_BACKEND")):
        errors.append("Celery broker and result backend must be non-loopback Redis URLs in production")
    if config.get("CELERY_TASK_ALWAYS_EAGER"):
        errors.append("CELERY_TASK_ALWAYS_EAGER must be disabled in production")
    trusted_hosts = tuple(config.get("TRUSTED_HOSTS") or ())
    if int(config.get("TRUST_PROXY_HOPS", 0)) < 1 or not trusted_hosts:
        errors.append("TRUST_PROXY_HOPS and TRUSTED_HOSTS are required in production")
    elif any("/" in host or "://" in host or "*" in host for host in trusted_hosts):
        errors.append("TRUSTED_HOSTS contains an invalid host")
    return errors


# Compatibility name retained for callers/tests added before the full
# environment allow-list existed.  It now performs the complete canonical
# validation, including invalid non-production APP_ENV values.
def production_configuration_errors(config) -> list[str]:
    return configuration_errors(config)
