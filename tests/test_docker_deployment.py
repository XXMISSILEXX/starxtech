import importlib
from pathlib import Path

import pytest

from app.config import read_secret
from app.security import configuration_errors


def _production_config(**overrides):
    values = {
        "APP_ENV": "production",
        "SECRET_KEY": "a" * 48,
        "SQLALCHEMY_DATABASE_URI": "postgresql+psycopg://starx:password@db.example.invalid:5432/starx",
        "DEBUG": False,
        "TESTING": False,
        "SESSION_COOKIE_SECURE": True,
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "STORAGE_PROVIDER": "s3",
        "STORAGE_ENDPOINT_URL": "https://objects.example.invalid",
        "STORAGE_BUCKET": "starx-private",
        "STORAGE_REGION": "ap-southeast-1",
        "STORAGE_ACCESS_KEY_ID": "access-key",
        "STORAGE_SECRET_ACCESS_KEY": "secret-key",
        "RATELIMIT_STORAGE_URI": "redis://:password@redis:6379/2",
        "CELERY_BROKER_URL": "redis://:password@redis:6379/0",
        "CELERY_RESULT_BACKEND": "redis://:password@redis:6379/1",
        "CELERY_TASK_ALWAYS_EAGER": False,
        "TRUST_PROXY_HOPS": 1,
        "TRUSTED_HOSTS": ("report.example.invalid",),
    }
    values.update(overrides)
    return values


def _config_class(values):
    return type("StartupConfig", (), values)


def test_read_secret_prefers_file_over_environment(monkeypatch, tmp_path):
    secret_file = tmp_path / "secret.txt"
    secret_file.write_text("from-file\n", encoding="utf-8")
    monkeypatch.setenv("STARX_TEST_SECRET", "from-environment")
    assert read_secret("STARX_TEST_SECRET") == "from-environment"

    monkeypatch.setenv("STARX_TEST_SECRET_FILE", str(secret_file))
    assert read_secret("STARX_TEST_SECRET") == "from-file"


def test_config_reads_secret_files_and_upload_environment(monkeypatch, tmp_path):
    import app.config as config_module

    key_file = tmp_path / "secret_key.txt"
    database_file = tmp_path / "database_url.txt"
    key_file.write_text("a" * 32, encoding="utf-8")
    database_file.write_text("postgresql+psycopg://user:pass@db:5432/starx", encoding="utf-8")
    monkeypatch.setenv("SECRET_KEY_FILE", str(key_file))
    monkeypatch.setenv("DATABASE_URL_FILE", str(database_file))
    monkeypatch.setenv("UPLOAD_ROOT", "/app/storage/uploads")

    reloaded = importlib.reload(config_module)
    assert reloaded.Config.SECRET_KEY == "a" * 32
    assert reloaded.Config.SQLALCHEMY_DATABASE_URI == "postgresql+psycopg://user:pass@db:5432/starx"
    assert reloaded.Config.UPLOAD_ROOT == "/app/storage/uploads"

    monkeypatch.undo()
    importlib.reload(config_module)


def test_exact_production_configuration_starts():
    from app import create_app

    app = create_app(_config_class(_production_config()))
    assert app.config["APP_ENV"] == "production"
    assert configuration_errors(app.config) == []


@pytest.mark.parametrize("app_env", [None, "", "prod", "production ", "Production"])
def test_unknown_or_misspelled_app_env_fails_startup(app_env):
    from app import create_app

    with pytest.raises(RuntimeError, match="APP_ENV"):
        create_app(_config_class(_production_config(APP_ENV=app_env)))


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"SECRET_KEY": "dev-secret-key"}, "SECRET_KEY"),
        ({"STORAGE_PROVIDER": "fake"}, "STORAGE_PROVIDER"),
        ({"SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"}, "DATABASE_URL"),
        ({"CELERY_BROKER_URL": None}, "Celery broker"),
        ({"RATELIMIT_STORAGE_URI": "memory://"}, "RATELIMIT_STORAGE_URI"),
        ({"CELERY_TASK_ALWAYS_EAGER": True}, "CELERY_TASK_ALWAYS_EAGER"),
        ({"SESSION_COOKIE_SECURE": False}, "SESSION_COOKIE_SECURE"),
    ],
)
def test_production_startup_rejects_unsafe_required_settings(overrides, expected):
    from app import create_app

    with pytest.raises(RuntimeError, match=expected):
        create_app(_config_class(_production_config(**overrides)))


@pytest.mark.parametrize("app_env", ["local", "development", "testing"])
def test_explicit_nonproduction_modes_remain_supported(app_env):
    from app import create_app

    app = create_app(_config_class({
        "APP_ENV": app_env,
        "TESTING": app_env == "testing",
        "SECRET_KEY": "local-secret",
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    }))
    assert app.config["APP_ENV"] == app_env


def test_healthz_is_public_and_returns_ok(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_security_audit_accepts_isolated_memory_rate_limit_storage_for_tests(app):
    result = app.test_cli_runner().invoke(args=["security-audit"])
    assert "PASS rate-limit-storage: isolated in-memory storage configured for tests" in result.output
    assert "WARN rate-limit-storage" not in result.output


def test_compose_defines_the_production_service_gate_without_cloudflared():
    content = Path("docker-compose.yml").read_text(encoding="utf-8")
    for service in ("migrate:", "web:", "worker:", "scheduler:", "redis:"):
        assert service in content
    assert "service_completed_successfully" in content
    assert "cloudflared" not in content.lower()
    assert "127.0.0.1:${HOST_WEB_PORT:-6655}:6655" in content
    assert "redis_password" in content
    assert "storage_access_key_id" in content
    assert "MEDIA_CACHE_DELIVERY_MODE: ${MEDIA_CACHE_DELIVERY_MODE:-send_file}" in content
    assert "/app/docker-entrypoint.sh celery -A app.celery_worker:celery_app inspect ping" in content
    assert "for cmdline in /proc/[0-9]*/cmdline" in content
    assert "celery.*beat" in content


def test_dockerfile_is_python_312_non_root_gunicorn_image():
    content = Path("Dockerfile").read_text(encoding="utf-8")
    assert "FROM python:3.12-slim" in content
    assert "USER appuser" in content
    assert "HEALTHCHECK" in content
    assert 'ENTRYPOINT ["/app/docker-entrypoint.sh"]' in content
    assert 'CMD ["gunicorn"' in content


def test_dockerignore_excludes_deployment_secrets_audits_and_backups():
    content = Path(".dockerignore").read_text(encoding="utf-8")
    for ignored in [".git", ".audit/", ".env*", "secrets/", "backups/", "deploy_backup_*/", "claude-partial-audit-backup/"]:
        assert ignored in content
