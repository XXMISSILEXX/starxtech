import importlib
import os
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import itsdangerous.timed
import pytest
from flask import jsonify, session
from flask_login import current_user
from werkzeug.security import check_password_hash
from app.date_utils import local_today

from app import create_app
from app.extensions import db
from app.models import DailyReport, UploadSelectionSession, User
from conftest import TestConfig, seed_test_data


class CsrfEnabledConfig(TestConfig):
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)
    REMEMBER_COOKIE_DURATION = timedelta(days=14)
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = False
    SESSION_REFRESH_EACH_REQUEST = True


@pytest.fixture
def csrf_app():
    app = create_app(CsrfEnabledConfig)

    @app.get("/test/session-state")
    def session_state():
        return jsonify(authenticated=current_user.is_authenticated, session_modified=session.modified)

    with app.app_context():
        db.create_all()
        seed_test_data()
        from app.permissions.sync import sync_registry
        sync_registry(apply_defaults=True)

    yield app

    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def csrf_client(csrf_app):
    return csrf_app.test_client()


@pytest.fixture
def short_csrf_app():
    class ShortCsrfConfig(CsrfEnabledConfig):
        WTF_CSRF_TIME_LIMIT = 1

    app = create_app(ShortCsrfConfig)
    with app.app_context():
        db.create_all()
        seed_test_data()
        from app.permissions.sync import sync_registry
        sync_registry(apply_defaults=True)

    yield app

    with app.app_context():
        db.session.remove()
        db.drop_all()


def _csrf_token(response):
    match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', response.get_data(as_text=True))
    assert match, "Expected a CSRF token in the form"
    return match.group(1)


def _login(client, username="reporter", *, remember=False):
    token = _csrf_token(client.get("/login"))
    data = {"username_or_email": username, "password": "password123", "csrf_token": token}
    if remember:
        data["remember"] = "y"
    response = client.post("/login", data=data)
    assert response.status_code == 302
    return response


def _session_cookie_header(response, app):
    cookie_name = app.config["SESSION_COOKIE_NAME"]
    return next((value for value in response.headers.getlist("Set-Cookie") if value.startswith(f"{cookie_name}=")), None)


def _cookie_expiry(header):
    expiry = re.search(r"Expires=([^;]+)", header)
    assert expiry, f"Expected a persistent cookie: {header}"
    return parsedate_to_datetime(expiry.group(1))


def test_guest_session_cookie_is_not_permanent(csrf_client, csrf_app):
    response = csrf_client.get("/login")

    session_cookie = _session_cookie_header(response, csrf_app)
    assert session_cookie is not None  # rendering the form stores its CSRF value in the session
    assert "Expires=" not in session_cookie


def test_authenticated_session_becomes_permanent_once(csrf_client, csrf_app):
    _login(csrf_client)

    first_authenticated_response = csrf_client.get("/test/session-state")

    assert first_authenticated_response.get_json()["authenticated"] is True
    session_cookie = _session_cookie_header(first_authenticated_response, csrf_app)
    assert session_cookie is not None
    assert "Expires=" in session_cookie
    with csrf_client.session_transaction() as client_session:
        assert client_session["_permanent"] is True


def test_authenticated_session_expiry_slides_on_activity(csrf_client, csrf_app, monkeypatch):
    _login(csrf_client)
    initial_time = datetime(2030, 1, 1, 8, 0, tzinfo=timezone.utc)

    class FrozenDateTime(datetime):
        current = initial_time

        @classmethod
        def now(cls, tz=None):
            return cls.current if tz is not None else cls.current.replace(tzinfo=None)

    monkeypatch.setattr("flask.sessions.datetime", FrozenDateTime)
    first = csrf_client.get("/test/session-state")
    first_expiry = _cookie_expiry(_session_cookie_header(first, csrf_app))

    FrozenDateTime.current = initial_time + timedelta(minutes=30)
    second = csrf_client.get("/test/session-state")
    second_expiry = _cookie_expiry(_session_cookie_header(second, csrf_app))

    assert second_expiry - first_expiry == timedelta(minutes=30)


def test_session_lifetime_hook_does_not_modify_an_already_permanent_session(csrf_client, csrf_app):
    _login(csrf_client)
    csrf_client.get("/test/session-state")  # the hook marks this newly logged-in session permanent

    response = csrf_client.get("/test/session-state")

    assert response.get_json()["session_modified"] is False
    # Flask still emits this cookie because SESSION_REFRESH_EACH_REQUEST=True
    # refreshes the sliding expiry.  The hook itself did not dirty the session.
    assert _session_cookie_header(response, csrf_app) is not None


def test_session_expiry_logs_out_user_without_remember_cookie(csrf_client, monkeypatch):
    _login(csrf_client)
    csrf_client.get("/test/session-state")
    original_time = itsdangerous.timed.time.time
    monkeypatch.setattr(itsdangerous.timed.time, "time", lambda: original_time() + 12 * 60 * 60 + 1)

    response = csrf_client.get("/")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
    with csrf_client.session_transaction() as client_session:
        assert "_user_id" not in client_session


def test_remember_cookie_restores_user_after_session_expiry(csrf_client, monkeypatch):
    _login(csrf_client, remember=True)
    original_time = itsdangerous.timed.time.time
    monkeypatch.setattr(itsdangerous.timed.time, "time", lambda: original_time() + 12 * 60 * 60 + 1)

    response = csrf_client.get("/")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/modules/")
    with csrf_client.session_transaction() as client_session:
        assert client_session["_user_id"] == "3"


def test_remember_cookie_defaults_and_secure_setting_follow_session_cookie(monkeypatch):
    import app.config as config_module

    original_getenv = os.getenv
    try:
        for secure_value, expected_secure in (("false", False), ("true", True)):
            monkeypatch.setenv("SESSION_COOKIE_SECURE", secure_value)
            config_module = importlib.reload(config_module)
            assert config_module.Config.REMEMBER_COOKIE_SECURE is expected_secure
            assert config_module.Config.REMEMBER_COOKIE_DURATION == timedelta(days=14)
            assert config_module.Config.REMEMBER_COOKIE_SAMESITE == "Lax"
    finally:
        monkeypatch.setattr(os, "getenv", original_getenv)
        importlib.reload(config_module)


def test_csrf_valid_logout_logs_the_user_out(csrf_client):
    _login(csrf_client)
    token = _csrf_token(csrf_client.get("/change-password"))

    response = csrf_client.post("/logout", data={"csrf_token": token})

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
    with csrf_client.session_transaction() as client_session:
        assert "_user_id" not in client_session


def test_csrf_missing_logout_token_has_no_side_effect(csrf_client):
    _login(csrf_client)

    response = csrf_client.post("/logout", data={})

    assert response.status_code == 400
    with csrf_client.session_transaction() as client_session:
        assert client_session["_user_id"] == "3"


def test_csrf_missing_json_logout_returns_json_without_side_effect(csrf_client):
    _login(csrf_client)

    response = csrf_client.post("/logout", json={})

    assert response.status_code == 400
    assert response.is_json
    payload = response.get_json()
    assert "Phiên đã hết hiệu lực" in payload["message"]
    assert "chưa được thực hiện" in payload["message"]
    assert "tải lại trang rồi thực hiện lại" in payload["message"]
    assert payload["error"]["message"] == payload["message"]
    assert "CSRF" not in payload["message"]
    assert "token" not in payload["message"].lower()
    assert response.headers["Cache-Control"] == "no-store"
    with csrf_client.session_transaction() as client_session:
        assert client_session["_user_id"] == "3"


def test_csrf_json_daily_report_finalize_returns_json_without_upload_side_effect(csrf_client, csrf_app):
    _login(csrf_client)
    with csrf_app.app_context():
        upload_session = UploadSelectionSession(
            module_type="daily_reports",
            target_type="project",
            target_id=1,
            created_by_id=3,
            declared_files=0,
            declared_size_bytes=0,
            status="ready",
            expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1),
        )
        db.session.add(upload_session)
        db.session.commit()
        upload_session_id = upload_session.id
        report_count = DailyReport.query.count()
        upload_session_count = UploadSelectionSession.query.count()

    response = csrf_client.post(
        "/api/projects/1/daily-reports/finalize",
        json={
            "client_request_id": "7cf6d3c9-75e9-4bbd-9328-c1314a2aebef",
            "report_date": local_today().isoformat(),
            "overall_status": "UPDATED",
            "highlight": "Báo cáo không được tạo khi phiên đã hết hạn.",
            "summary_note": "",
            "upload_session_id": upload_session_id,
            "attachments": [],
            "sections": [{
                "client_section_id": "ef5a91fe-a329-4ea4-8213-73c15e8d58ec",
                "report_category_id": 1,
                "status": "GOOD",
                "content": "Không được lưu.",
                "sort_order": 0,
            }],
        },
    )

    assert response.status_code == 400
    assert response.is_json
    assert "Phiên đã hết hiệu lực" in response.get_json()["message"]
    with csrf_app.app_context():
        assert DailyReport.query.count() == report_count
        assert UploadSelectionSession.query.count() == upload_session_count
        assert db.session.get(UploadSelectionSession, upload_session_id).status == "ready"


def test_csrf_missing_form_logout_keeps_the_vietnamese_html_error_page(csrf_client):
    _login(csrf_client)

    response = csrf_client.post("/logout", data={})

    assert response.status_code == 400
    assert response.mimetype == "text/html"
    assert "Phiên đã hết hiệu lực nên yêu cầu vừa rồi chưa được thực hiện".encode() in response.data
    assert "Vui lòng tải lại trang rồi thực hiện lại thao tác.".encode() in response.data
    assert b"CSRF" not in response.data
    assert response.headers["Cache-Control"] == "no-store"


def test_csrf_token_from_another_session_has_no_logout_side_effect(csrf_app):
    first_client = csrf_app.test_client()
    second_client = csrf_app.test_client()
    _login(first_client)
    _login(second_client)
    token_from_first_session = _csrf_token(first_client.get("/change-password"))

    response = second_client.post("/logout", data={"csrf_token": token_from_first_session})

    assert response.status_code == 400
    with second_client.session_transaction() as client_session:
        assert client_session["_user_id"] == "3"


def test_expired_csrf_token_shows_the_vietnamese_error_page(short_csrf_app, monkeypatch):
    client = short_csrf_app.test_client()
    _login(client)
    token = _csrf_token(client.get("/change-password"))
    original_time = itsdangerous.timed.time.time
    monkeypatch.setattr(itsdangerous.timed.time, "time", lambda: original_time() + 2)

    response = client.post("/logout", data={"csrf_token": token})

    assert response.status_code == 400
    assert "Phiên đã hết hiệu lực nên yêu cầu vừa rồi chưa được thực hiện".encode() in response.data
    assert "Vui lòng tải lại trang rồi thực hiện lại thao tác.".encode() in response.data
    assert "Về trang chính".encode() in response.data
    assert b"CSRF" not in response.data
    assert response.headers["Cache-Control"] == "no-store"


def test_csrf_protects_change_password_form_too(csrf_client, csrf_app):
    _login(csrf_client)
    token = _csrf_token(csrf_client.get("/change-password"))

    response = csrf_client.post(
        "/change-password",
        data={
            "csrf_token": token,
            "current_password": "password123",
            "new_password": "ReplacementPassword123!",
            "confirm_password": "ReplacementPassword123!",
        },
    )

    assert response.status_code == 302
    with csrf_app.app_context():
        assert check_password_hash(db.session.get(User, 3).password_hash, "ReplacementPassword123!")


def test_production_defaults_apply_when_compose_does_not_supply_session_or_csrf_settings(monkeypatch):
    import app.config as config_module

    # Compose does not pass these settings.  Without PERMANENT_SESSION_LIFETIME,
    # WTF_CSRF_TIME_LIMIT=None would leave CSRF tokens valid without an expiry bound.
    setting_names = (
        "PERMANENT_SESSION_LIFETIME",
        "REMEMBER_COOKIE_DURATION",
        "REMEMBER_COOKIE_SAMESITE",
        "REMEMBER_COOKIE_SECURE",
        "WTF_CSRF_TIME_LIMIT",
    )
    original_getenv = os.getenv

    def getenv_without_production_overrides(name, default=None):
        if name in setting_names:
            return default
        return original_getenv(name, default)

    try:
        monkeypatch.setattr(os, "getenv", getenv_without_production_overrides)
        config_module = importlib.reload(config_module)

        class ProductionDefaultsTestConfig(config_module.Config):
            APP_ENV = "testing"
            TESTING = True
            SECRET_KEY = "test-secret"
            SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

        app = create_app(ProductionDefaultsTestConfig)
        assert app.config["PERMANENT_SESSION_LIFETIME"] == timedelta(hours=12)
        assert app.config["REMEMBER_COOKIE_DURATION"] == timedelta(days=14)
        assert app.config["REMEMBER_COOKIE_SAMESITE"] == "Lax"
        assert app.config["WTF_CSRF_TIME_LIMIT"] is None
    finally:
        monkeypatch.setattr(os, "getenv", original_getenv)
        importlib.reload(config_module)
