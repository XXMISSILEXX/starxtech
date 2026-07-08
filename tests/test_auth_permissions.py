from werkzeug.security import check_password_hash

from app.extensions import db
from app.models import User


def login(client, username_or_email, password="password123"):
    return client.post(
        "/login",
        data={
            "username_or_email": username_or_email,
            "password": password,
        },
    )


def test_login_by_username_updates_last_login(client, app):
    response = login(client, "reporter")

    assert response.status_code == 302
    with app.app_context():
        user = db.session.get(User, 3)
        assert user.last_login_at is not None


def test_login_by_email_updates_last_login(client, app):
    response = login(client, "reporter@example.com")

    assert response.status_code == 302
    with app.app_context():
        user = db.session.get(User, 3)
        assert user.last_login_at is not None


def test_wrong_password_does_not_authenticate(client):
    response = login(client, "reporter", "wrong-password")

    assert response.status_code == 401
    with client.session_transaction() as session:
        assert "_user_id" not in session


def test_inactive_user_cannot_login(client):
    response = login(client, "inactive")

    assert response.status_code == 401
    with client.session_transaction() as session:
        assert "_user_id" not in session


def test_protected_routes_redirect_anonymous_to_login(client):
    response = client.get("/projects/")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login?next=/projects/")


def test_viewer_admin_is_blocked_from_project_write_route(client):
    login(client, "viewer")

    response = client.post("/test/projects/1/write")

    assert response.status_code == 403


def test_reporter_can_read_assigned_project(client):
    login(client, "reporter")

    response = client.get("/test/projects/1/read")

    assert response.status_code == 200
    assert response.get_json() == {"project_id": 1}


def test_reporter_cannot_read_unassigned_project(client):
    login(client, "reporter")

    response = client.get("/test/projects/2/read")

    assert response.status_code == 403


def test_change_password_requires_current_password_and_allows_new_login(client, app):
    login(client, "reporter")

    wrong_current = client.post(
        "/change-password",
        data={
            "current_password": "wrong-password",
            "new_password": "new-password-123",
            "confirm_password": "new-password-123",
        },
    )
    assert wrong_current.status_code == 400

    changed = client.post(
        "/change-password",
        data={
            "current_password": "password123",
            "new_password": "new-password-123",
            "confirm_password": "new-password-123",
        },
    )
    assert changed.status_code == 302

    with app.app_context():
        user = db.session.get(User, 3)
        assert check_password_hash(user.password_hash, "new-password-123")

    client.post("/logout")
    old_login = login(client, "reporter", "password123")
    assert old_login.status_code == 401

    new_login = login(client, "reporter", "new-password-123")
    assert new_login.status_code == 302
