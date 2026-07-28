"""Secure regression: role managers must not expand their own effective grants."""

pytest_plugins = ("tests.conftest",)

from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import Permission, Role, RolePermission, User


def _login(client, username):
    # The shared TestConfig disables CSRF, which is the repository's normal test convention.
    return client.post("/login", data={"username_or_email": username, "password": "password123"})


def test_role_manager_cannot_add_dangerous_permission_to_own_role(client, app):
    with app.app_context():
        role = Role(id=9001, code="AUDIT_ROLE_MANAGER", name="Audit role manager", is_system=False)
        actor = User(
            id=9001,
            full_name="Audit Role Manager",
            username="audit-role-manager",
            email="audit-role-manager@example.com",
            password_hash=generate_password_hash("password123"),
            role=role,
            legacy_role=role.code,
        )
        db.session.add_all([role, actor])
        db.session.flush()
        permissions = {
            item.code: item
            for item in Permission.query.filter(
                Permission.code.in_({"roles.view", "roles.manage", "system.settings"})
            ).all()
        }
        db.session.add_all(
            RolePermission(role_id=role.id, permission_id=permissions[code].id)
            for code in ("roles.view", "roles.manage")
        )
        role_view_permission_id = permissions["roles.view"].id
        role_manage_permission_id = permissions["roles.manage"].id
        dangerous_permission_id = permissions["system.settings"].id
        role_id = role.id
        db.session.commit()

    assert _login(client, "audit-role-manager").status_code == 302
    response = client.post(
        f"/admin/roles/{role_id}/permissions",
        data={"permission_ids": [str(item) for item in (role_view_permission_id, role_manage_permission_id, dangerous_permission_id)]},
    )

    with app.app_context():
        db.session.expire_all()
        dangerous_grant_exists = RolePermission.query.filter_by(
            role_id=role_id, permission_id=dangerous_permission_id
        ).first() is not None

    secure = response.status_code in {400, 403, 404, 422} and not dangerous_grant_exists
    assert secure, (
        "secure behavior must reject a manager changing their own role's grants; "
        f"got HTTP {response.status_code}, system.settings grant created={dangerous_grant_exists}"
    )
