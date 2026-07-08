from pathlib import Path

from flask_login import login_user

from app.audit import log_audit
from app.extensions import db
from app.models import AuditLog, User


def test_log_audit_records_actor_request_metadata_and_values(app):
    with app.test_request_context(
        "/audit-test",
        headers={"X-Forwarded-For": "203.0.113.10", "User-Agent": "pytest-agent"},
    ):
        user = db.session.get(User, 1)
        login_user(user)
        log = log_audit(
            "test.action",
            "Widget",
            123,
            old_values={"name": "old"},
            new_values={"name": "new"},
        )
        db.session.commit()

        saved = db.session.get(AuditLog, log.id)
        assert saved.actor_user_id == user.id
        assert saved.action == "test.action"
        assert saved.entity_type == "Widget"
        assert saved.entity_id == 123
        assert saved.old_values_json == {"name": "old"}
        assert saved.new_values_json == {"name": "new"}
        assert saved.ip_address == "203.0.113.10"
        assert saved.user_agent == "pytest-agent"
        assert saved.created_at is not None


def test_max_content_length_is_derived_from_upload_limit(app):
    assert app.config["MAX_CONTENT_LENGTH"] == app.config["MAX_UPLOAD_MB"] * 1024 * 1024


def test_env_example_has_production_security_keys_without_real_secret():
    content = Path(".env.example").read_text()

    assert "APP_ENV=" in content
    assert "FLASK_DEBUG=false" in content
    assert "SECRET_KEY=change-this-to-a-long-random-secret" in content
    assert "SESSION_COOKIE_SECURE=false" in content
    assert "SESSION_COOKIE_HTTPONLY=true" in content
    assert "SESSION_COOKIE_SAMESITE=Lax" in content
    assert "UPLOAD_ROOT=" in content
    assert "MAX_UPLOAD_MB=" in content
    assert "GENERATE_A_LONG_RANDOM_SECRET" not in content


def test_backup_scripts_exist_and_are_executable():
    for script_name in ["backup_db.sh", "backup_uploads.sh", "restore_db.sh"]:
        path = Path("scripts") / script_name
        assert path.exists()
        assert path.stat().st_mode & 0o111
