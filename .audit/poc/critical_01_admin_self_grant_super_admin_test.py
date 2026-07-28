"""Secure regression: an ADMIN must not be able to promote their own account."""

pytest_plugins = ("tests.conftest",)

from app.extensions import db
from app.models import Role, User, UserRole


def _login(client, username):
    # The shared TestConfig disables CSRF, which is the repository's normal test convention.
    return client.post("/login", data={"username_or_email": username, "password": "password123"})


def test_admin_cannot_promote_self_to_super_admin(client, app):
    with app.app_context():
        admin = User.query.filter_by(username="admin").one()
        super_admin = Role.query.filter_by(code=UserRole.SUPER_ADMIN.value).one()
        admin_id, super_admin_role_id = admin.id, super_admin.id

    assert _login(client, "admin").status_code == 302
    response = client.post(
        f"/admin/users/{admin_id}/edit",
        data={
            "full_name": "Admin",
            "username": "admin",
            "email": "admin@example.com",
            "role_id": str(super_admin_role_id),
            "is_active": "on",
        },
    )

    with app.app_context():
        db.session.expire_all()
        persisted_role = db.session.get(User, admin_id).role_code

    secure = response.status_code in {400, 403, 404, 422} and persisted_role == UserRole.ADMIN.value
    assert secure, (
        "secure behavior must reject self-promotion and retain ADMIN; "
        f"got HTTP {response.status_code}, persisted role={persisted_role!r}"
    )
