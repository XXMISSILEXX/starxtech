import inspect
from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import select
from werkzeug.security import check_password_hash

from app import create_app
from app.extensions import db
from app.models import AuditLog, DownloadEvent, ReportAttachment, Role, StorageDerivative, User, UserRole
from app.security import password_policy_errors
from tests.helpers.daily_report_create_v2 import DailyReportV2UploadFile, submit_daily_report_create_v2


def test_password_policy_requires_length_and_character_groups():
    assert password_policy_errors("short")
    assert password_policy_errors("alllowercase12")
    assert not password_policy_errors("StrongPass123!")


def test_response_security_headers_are_present(client):
    response = client.get("/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


def test_csp_allows_only_valid_configured_s3_endpoint_origin(client, app):
    def directives(value):
        return {
            part.split()[0]: set(part.split()[1:])
            for part in value.rstrip(";").split("; ")
            if part
        }

    app.config.update(STORAGE_PROVIDER="s3", STORAGE_ENDPOINT_URL="http://127.0.0.1:9000/starx-local")
    csp = directives(client.get("/health").headers["Content-Security-Policy"])
    origin = "http://127.0.0.1:9000"
    assert {"'self'", origin}.issubset(csp["connect-src"])
    assert {"'self'", "data:", "blob:", origin}.issubset(csp["img-src"])
    assert {"'self'", "blob:", origin}.issubset(csp["media-src"])
    assert "starx-local" not in " ".join(sum((list(v) for v in csp.values()), []))
    assert "*" not in set().union(*csp.values())
    assert not ({"data:", "javascript:"} & csp["connect-src"])
    app.config.update(STORAGE_PROVIDER="fake", STORAGE_ENDPOINT_URL="https://fake-storage.invalid")
    csp = directives(client.get("/health").headers["Content-Security-Policy"])
    assert csp["connect-src"] == {"'self'"}
    assert csp["img-src"] == {"'self'", "data:", "blob:"}
    assert csp["media-src"] == {"'self'", "blob:"}
    assert csp["worker-src"] == {"'self'", "blob:"}
    assert "blob:" not in csp["script-src"]
    assert "'unsafe-eval'" not in csp["script-src"]
    assert "fake-storage.invalid" not in csp


def _login(client, username):
    return client.post("/login", data={"username_or_email": username, "password": "password123"})


def _report_attachment(client, app, project_id=1):
    stream = BytesIO(); Image.new("RGB", (16, 16), "navy").save(stream, "JPEG")
    result = submit_daily_report_create_v2(client, app, project_id=project_id, report={
        "report_date": "2026-07-23", "overall_status": "UPDATED", "highlight": "Secure storage",
    }, sections=[{"report_category_id": 1 if project_id == 1 else 3, "status": "GOOD", "content": "Attachment"}],
       files=[DailyReportV2UploadFile(stream.getvalue(), filename="safe.jpg")])
    assert result["finalize_response"].status_code == 200
    assert result["finalize_json"]["report_id"]
    assert len(result["attachment_ids"]) == 1
    return result["attachment_ids"][0]


def test_attachment_preview_is_authorized_signed_redirect_without_local_runtime(client, app):
    _login(client, "reporter")
    attachment_id = _report_attachment(client, app)
    with app.app_context():
        attachment = db.session.get(ReportAttachment, attachment_id)
        object_key = attachment.storage_object.object_key
        report_id = attachment.section.daily_report_id
        derivative = StorageDerivative(storage_object_id=attachment.storage_object_id, derivative_type="preview",
            bucket=attachment.storage_object.bucket, object_key="daily-reports/derivatives/security-preview.webp",
            mime_type="image/webp", file_ext="webp", file_size=4)
        db.session.add(derivative); db.session.commit()
        app.extensions["storage_provider"].put_bytes(derivative.bucket, derivative.object_key, b"webp", derivative.mime_type)
        derivative_key = derivative.object_key
    response = client.get(f"/attachments/{attachment_id}")
    assert response.status_code == 302
    assert "fake-storage.invalid" in response.headers["Location"]
    assert derivative_key in response.headers["Location"]  # derivative URL, not rendered HTML
    assert object_key not in response.headers["Location"]
    detail = client.get(f"/reports/{report_id}")
    assert object_key.encode() not in detail.data
    import app.attachments.routes as routes
    source = inspect.getsource(routes)
    forbidden = ("send" + "_file", "UPLOAD" + "_ROOT", "_resolve" + "_attachment_path")
    assert all(value not in source for value in forbidden)


def test_attachment_original_download_is_signed_and_audited(client, app):
    _login(client, "reporter")
    attachment_id = _report_attachment(client, app)
    with app.app_context():
        before_audits = AuditLog.query.count()
        before_events = DownloadEvent.query.count()
    response = client.get(f"/attachments/{attachment_id}/download")
    assert response.status_code == 302 and "fake-storage.invalid" in response.headers["Location"]
    with app.app_context():
        event = DownloadEvent.query.filter_by(module="daily-reports", source_type="original").one()
        assert event.storage_object_id == db.session.get(ReportAttachment, attachment_id).storage_object_id
        audit = AuditLog.query.filter_by(action="attachment.download", entity_id=attachment_id).one()
        assert AuditLog.query.count() == before_audits + 1
        assert DownloadEvent.query.count() == before_events + 1
        assert audit.new_values_json["file_name"] == "safe.jpg"
        assert audit.new_values_json["storage_object_id"] == event.storage_object_id


def test_attachment_preview_and_thumbnail_do_not_record_disclosure_audit(client, app):
    _login(client, "reporter")
    attachment_id = _report_attachment(client, app)
    with app.app_context():
        attachment = db.session.get(ReportAttachment, attachment_id)
        derivative = StorageDerivative(storage_object_id=attachment.storage_object_id, derivative_type="preview",
            bucket=attachment.storage_object.bucket, object_key="daily-reports/derivatives/audit-preview.webp",
            mime_type="image/webp", file_ext="webp", file_size=4)
        thumbnail = StorageDerivative(storage_object_id=attachment.storage_object_id, derivative_type="thumbnail",
            bucket=attachment.storage_object.bucket, object_key="daily-reports/derivatives/audit-thumbnail.webp",
            mime_type="image/webp", file_ext="webp", file_size=2)
        db.session.add_all((derivative, thumbnail)); db.session.commit()
        app.extensions["storage_provider"].put_bytes(derivative.bucket, derivative.object_key, b"webp", derivative.mime_type)
        app.extensions["storage_provider"].put_bytes(thumbnail.bucket, thumbnail.object_key, b"webp", thumbnail.mime_type)
        before_audits = AuditLog.query.count()

    assert client.get(f"/attachments/{attachment_id}").status_code == 302
    response = client.get(f"/attachments/{attachment_id}/thumbnail")
    assert response.status_code == 302
    response.close()
    with app.app_context():
        assert AuditLog.query.count() == before_audits


def test_attachment_does_not_issue_signed_url_to_unauthorized_user(client, app):
    _login(client, "super")
    attachment_id = _report_attachment(client, app, project_id=2)
    client.post("/logout"); _login(client, "reporter")
    response = client.get(f"/attachments/{attachment_id}")
    assert response.status_code == 403
    assert "fake-storage.invalid" not in response.headers.get("Location", "")


def test_attachment_missing_storage_object_is_safe_error_without_fallback(client, app):
    _login(client, "reporter")
    attachment_id = _report_attachment(client, app)
    with app.app_context():
        attachment = db.session.get(ReportAttachment, attachment_id)
        attachment.storage_object_id = None
        db.session.commit()
    response = client.get(f"/attachments/{attachment_id}")
    assert response.status_code == 410
    assert "S3" in response.get_data(as_text=True)


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


def test_security_audit_reports_local_default_secret_without_warning(app):
    result = app.test_cli_runner().invoke(args=["security-audit"])
    assert result.exit_code != 0  # test fixture deliberately has no migration version table
    assert "PASS secret-key: local default accepted" in result.output
    assert "WARN " not in result.output
    assert "PASS security-headers" in result.output
