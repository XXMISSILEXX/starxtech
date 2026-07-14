import importlib
from pathlib import Path

from app.config import read_secret
from app.security import production_configuration_errors


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


def test_healthz_is_public_and_returns_ok(client):
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_security_audit_warns_when_memory_rate_limit_storage_is_used(app):
    result = app.test_cli_runner().invoke(args=["security-audit"])

    assert "WARN rate-limit-storage: memory:// is per worker and resets when the application restarts" in result.output


def test_docker_deployment_files_and_gitignore_are_safe():
    for filename in [
        "Dockerfile",
        "docker-compose.yml",
        "docker-entrypoint.sh",
        "gunicorn.conf.py",
        ".dockerignore",
        ".env.docker.example",
        "DOCKER_DEPLOY.md",
        "secrets/README.md",
    ]:
        assert Path(filename).exists()

    gitignore = Path(".gitignore").read_text(encoding="utf-8")
    assert ".env.docker" in gitignore
    assert "secrets/*" in gitignore

    docker_env = Path(".env.docker.example").read_text(encoding="utf-8")
    assert "SECRET_KEY=change" not in docker_env
    assert "DATABASE_URL=postgresql" not in docker_env
    assert "cloudflared_tunnel_token=" not in docker_env.lower()


def test_compose_uses_internal_web_service_socket_postgres_and_secret_files():
    content = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "web:" in content
    assert '"6655"' in content
    assert "/run/secrets/app_secret_key" in content
    assert "/run/secrets/database_url" in content
    assert "/srv/construction_relation_management/uploads:/app/storage/uploads" in content
    assert "/var/run/postgresql:/var/run/postgresql:ro" in content
    assert "TUNNEL_TOKEN_FILE: /run/secrets/cloudflare_tunnel_token" in content
    assert "http://web:6655" in Path("DOCKER_DEPLOY.md").read_text(encoding="utf-8")
    assert "appnet" in content
    assert "ports:" not in content.replace("# ports:", "")


def test_dockerfile_runs_non_root_gunicorn_without_copying_secrets():
    content = Path("Dockerfile").read_text(encoding="utf-8")

    assert "USER appuser" in content
    assert "EXPOSE 6655" in content
    assert 'ENTRYPOINT ["/app/docker-entrypoint.sh"]' in content
    assert 'CMD ["gunicorn"' in content
    assert "COPY secrets" not in content


def test_dockerignore_excludes_all_secrets_and_runtime_artifacts():
    content = Path(".dockerignore").read_text(encoding="utf-8")

    for ignored in [".env*", ".venv", "secrets/", "uploads/", "tmp/", "backups/", "docker_backup_*/"]:
        assert ignored in content


def test_production_configuration_rejects_sqlite_and_sample_database_urls():
    base_config = {
        "APP_ENV": "production",
        "SECRET_KEY": "a" * 32,
        "DEBUG": False,
        "SESSION_COOKIE_SECURE": True,
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
    }

    sqlite_errors = production_configuration_errors({**base_config, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    sample_errors = production_configuration_errors(
        {**base_config, "SQLALCHEMY_DATABASE_URI": "postgresql+psycopg://starx:starx@127.0.0.1:5432/starx_daily_report"}
    )

    assert any("DATABASE_URL" in error for error in sqlite_errors)
    assert any("DATABASE_URL" in error for error in sample_errors)
