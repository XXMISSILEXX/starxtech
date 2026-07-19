import pytest
from werkzeug.security import check_password_hash

from app import create_app
from app.attachments.routes import _resolve_attachment_path
from app.extensions import db
from app.models import Role, User, UserRole
from app.security import password_policy_errors


def test_password_policy_requires_length_and_character_groups():
    assert password_policy_errors("short")
    assert password_policy_errors("alllowercase12")
    assert not password_policy_errors("StrongPass123!")


def test_response_security_headers_are_present(client):
    response = client.get("/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


def test_attachment_path_must_stay_inside_upload_root(app, tmp_path):
    app.config["UPLOAD_ROOT"] = str(tmp_path / "uploads")
    with app.app_context():
        assert _resolve_attachment_path("project_1/image.jpg") == (tmp_path / "uploads/project_1/image.jpg").resolve()
        with pytest.raises(Exception) as absolute:
            _resolve_attachment_path("/etc/passwd")
        assert getattr(absolute.value, "code", None) == 404
        with pytest.raises(Exception) as traversal:
            _resolve_attachment_path("../secret.jpg")
        assert getattr(traversal.value, "code", None) == 404


def test_production_configuration_refuses_unsafe_settings():
    class UnsafeProductionConfig:
        TESTING = True
        APP_ENV = "production"
        SECRET_KEY = "dev-secret-key"
        DEBUG = True
        SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
        SESSION_COOKIE_SECURE = False
        SESSION_COOKIE_HTTPONLY = False
        SESSION_COOKIE_SAMESITE = "None"

    with pytest.raises(RuntimeError, match="Unsafe production configuration"):
        create_app(UnsafeProductionConfig)


def test_seed_admin_updates_requested_account_and_never_echoes_password(app):
    runner = app.test_cli_runner()
    password = "StrongPass123!"
    result = runner.invoke(args=["seed-admin", "--username", "newadmin", "--password", password, "--email", "newadmin@example.com", "--full-name", "New Admin"])
    assert result.exit_code == 0
    assert password not in result.output
    with app.app_context():
        user = User.query.filter_by(username="newadmin").one()
        assert user.role_code == UserRole.SUPER_ADMIN.value
        assert user.is_active is True
        assert check_password_hash(user.password_hash, password)


def test_reset_database_refuses_wrong_confirmation(app):
    result = app.test_cli_runner().invoke(args=["reset-database", "--confirm", "no"])
    assert result.exit_code != 0
    assert "Refusing destructive action" in result.output


def test_reset_local_dev_runs_migrations_and_seeds_admin(tmp_path):
    class ResetConfig:
        TESTING = True
        APP_ENV = "local"
        SECRET_KEY = "a-test-secret-that-is-long-enough-for-this-case"
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path / 'reset.sqlite'}"
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        WTF_CSRF_ENABLED = False
        UPLOAD_ROOT = str(tmp_path / "uploads")
        SESSION_COOKIE_HTTPONLY = True
        SESSION_COOKIE_SAMESITE = "Lax"
        SESSION_COOKIE_SECURE = False

    reset_app = create_app(ResetConfig)
    result = reset_app.test_cli_runner().invoke(
        args=["reset-local-dev", "--confirm", "RESET DATABASE", "--admin-password", "StrongPass123!"]
    )
    assert result.exit_code == 0, result.output
    with reset_app.app_context():
        assert User.query.join(Role).filter(User.username == "admin", Role.code == UserRole.SUPER_ADMIN.value).count() == 1
    audit = reset_app.test_cli_runner().invoke(args=["security-audit"])
    assert audit.exit_code == 0, audit.output


def test_security_audit_runs_and_warns_for_local_default_secret(app):
    result = app.test_cli_runner().invoke(args=["security-audit"])
    assert result.exit_code != 0  # test fixture deliberately has no migration version table
    assert "WARN secret-key" in result.output
    assert "PASS security-headers" in result.output
