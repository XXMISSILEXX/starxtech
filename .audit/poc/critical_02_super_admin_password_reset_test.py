"""Secure regression: an ADMIN must not reset a SUPER_ADMIN password."""

pytest_plugins = ("tests.conftest",)

from app.extensions import db
from app.models import User


def _login(client, username):
    # The shared TestConfig disables CSRF, which is the repository's normal test convention.
    return client.post("/login", data={"username_or_email": username, "password": "password123"})


def test_admin_cannot_reset_super_admin_password_or_receive_temp_secret(client, app):
    with app.app_context():
        super_admin = User.query.filter_by(username="super").one()
        super_admin_id, password_hash_before = super_admin.id, super_admin.password_hash

    assert _login(client, "admin").status_code == 302
    response = client.post(
        f"/admin/users/{super_admin_id}/reset-password",
        follow_redirects=True,
    )

    with app.app_context():
        db.session.expire_all()
        password_hash_after = db.session.get(User, super_admin_id).password_hash

    temp_password_disclosed = "Mật khẩu tạm" in response.get_data(as_text=True)
    secure = (
        response.status_code in {400, 403, 404, 422}
        and password_hash_after == password_hash_before
        and not temp_password_disclosed
    )
    assert secure, (
        "secure behavior must reject a lower-admin reset, retain the SUPER_ADMIN hash, "
        "and not disclose a temporary password; "
        f"got HTTP {response.status_code}, hash_changed={password_hash_after != password_hash_before}, "
        f"temporary-password marker present={temp_password_disclosed}"
    )
