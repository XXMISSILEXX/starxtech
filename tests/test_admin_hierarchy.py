import json
import re

from app.extensions import db
from app.models import AuditLog, Permission, Role, RolePermission, User, UserRole


def _login(client, username):
    return client.post("/login", data={"username_or_email": username, "password": "password123"})


def _user_form(user, role):
    return {
        "full_name": user.full_name,
        "username": user.username,
        "email": user.email or "",
        "role_id": str(role.id),
        "is_active": "on" if user.is_active else "",
    }


def _permission_ids(role):
    return {
        item.permission_id
        for item in RolePermission.query.filter_by(role_id=role.id).all()
    }


def _role_manager(app):
    with app.app_context():
        permissions = {
            permission.code: permission
            for permission in Permission.query.filter(
                Permission.code.in_(("roles.view", "roles.manage", "reports.view"))
            ).all()
        }
        actor_role = Role(code="HIERARCHY_ROLE_MANAGER", name="Hierarchy role manager", is_system=False)
        target_role = Role(code="HIERARCHY_SUBORDINATE", name="Hierarchy subordinate", is_system=False)
        actor = User(
            id=9001,
            full_name="Hierarchy Role Manager",
            username="hierarchy-role-manager",
            email="hierarchy-role-manager@example.com",
            password_hash="",
            role=actor_role,
            legacy_role=actor_role.code,
        )
        from werkzeug.security import generate_password_hash

        actor.password_hash = generate_password_hash("password123")
        db.session.add_all((actor_role, target_role, actor))
        db.session.flush()
        db.session.add_all(
            RolePermission(role_id=actor_role.id, permission_id=permissions[code].id)
            for code in ("roles.view", "roles.manage", "reports.view")
        )
        db.session.add(RolePermission(role_id=target_role.id, permission_id=permissions["roles.view"].id))
        permission_ids = {code: permission.id for code, permission in permissions.items()}
        actor_id, actor_role_id, target_role_id = actor.id, actor_role.id, target_role.id
        db.session.commit()
        return actor_id, actor_role_id, target_role_id, permission_ids


def test_admin_cannot_assign_super_admin_and_rejection_retains_role(client, app):
    with app.app_context():
        admin = User.query.filter_by(username="admin").one()
        reporter = User.query.filter_by(username="reporter").one()
        super_role = Role.query.filter_by(code=UserRole.SUPER_ADMIN.value).one()
        admin_id, reporter_id = admin.id, reporter.id
        admin_form = _user_form(admin, super_role)
        reporter_form = _user_form(reporter, super_role)

    assert _login(client, "admin").status_code == 302
    assert client.post(f"/admin/users/{admin_id}/edit", data=admin_form).status_code in {400, 403}
    assert client.post(f"/admin/users/{reporter_id}/edit", data=reporter_form).status_code == 403

    with app.app_context():
        assert db.session.get(User, admin_id).role_code == UserRole.ADMIN.value
        assert db.session.get(User, reporter_id).role_code == UserRole.REPORTER.value


def test_super_admin_can_assign_subordinate_role(client, app):
    with app.app_context():
        reporter = User.query.filter_by(username="reporter").one()
        admin_role = Role.query.filter_by(code=UserRole.ADMIN.value).one()
        form = _user_form(reporter, admin_role)
        reporter_id = reporter.id

    assert _login(client, "super").status_code == 302
    assert client.post(f"/admin/users/{reporter_id}/edit", data=form).status_code == 302

    with app.app_context():
        assert db.session.get(User, reporter_id).role_code == UserRole.ADMIN.value


def test_password_reset_respects_super_admin_boundary_and_keeps_audit_secret_free(client, app):
    with app.app_context():
        super_admin = User.query.filter_by(username="super").one()
        super_admin_id, original_hash = super_admin.id, super_admin.password_hash
        reporter_id = User.query.filter_by(username="reporter").one().id

    assert _login(client, "admin").status_code == 302
    denied = client.post(f"/admin/users/{super_admin_id}/reset-password", follow_redirects=True)
    assert denied.status_code == 403
    assert "Mật khẩu tạm" not in denied.get_data(as_text=True)

    with app.app_context():
        assert db.session.get(User, super_admin_id).password_hash == original_hash

    allowed = client.post(f"/admin/users/{reporter_id}/reset-password")
    assert allowed.status_code == 302
    with client.session_transaction() as session:
        reset_message = next(message for category, message in session["_flashes"] if "Mật khẩu tạm" in message)
    secret = re.search(r": (.+)$", reset_message).group(1)

    with app.app_context():
        reset_audit = AuditLog.query.filter_by(action="user.reset_password", entity_id=reporter_id).one()
        assert secret not in json.dumps({"old": reset_audit.old_values_json, "new": reset_audit.new_values_json})


def test_role_permission_management_enforces_self_system_and_grant_ceiling(client, app):
    actor_id, actor_role_id, target_role_id, permissions = _role_manager(app)
    with app.app_context():
        system_role_id = Role.query.filter_by(code=UserRole.ADMIN.value).one().id
        system_settings_id = Permission.query.filter_by(code="system.settings").one().id
        actor_original = _permission_ids(db.session.get(Role, actor_role_id))
        target_original = _permission_ids(db.session.get(Role, target_role_id))
        system_original = _permission_ids(db.session.get(Role, system_role_id))

    assert _login(client, "hierarchy-role-manager").status_code == 302
    assert client.post(
        f"/admin/roles/{actor_role_id}/permissions",
        data={"permission_ids": [str(permissions["roles.view"]), str(system_settings_id)]},
    ).status_code == 403
    assert client.post(
        f"/admin/roles/{target_role_id}/permissions",
        data={"permission_ids": [str(system_settings_id)]},
    ).status_code == 403
    assert client.post(
        f"/admin/roles/{system_role_id}/permissions",
        data={"permission_ids": [str(permissions["roles.view"])]},
    ).status_code == 403

    permitted = client.post(
        f"/admin/roles/{target_role_id}/permissions",
        data={"permission_ids": [str(permissions["reports.view"])]},
    )
    assert permitted.status_code == 302

    with app.app_context():
        assert _permission_ids(db.session.get(Role, actor_role_id)) == actor_original
        assert _permission_ids(db.session.get(Role, system_role_id)) == system_original
        assert _permission_ids(db.session.get(Role, target_role_id)) == {permissions["reports.view"]}
        assert target_original == {permissions["roles.view"]}


def test_malformed_or_duplicate_permission_ids_reject_without_partial_update(client, app):
    _, _, target_role_id, permissions = _role_manager(app)
    with app.app_context():
        original = _permission_ids(db.session.get(Role, target_role_id))

    assert _login(client, "hierarchy-role-manager").status_code == 302
    malformed = client.post(
        f"/admin/roles/{target_role_id}/permissions",
        data={"permission_ids": [str(permissions["reports.view"]), "not-a-permission"]},
    )
    assert malformed.status_code == 400
    unknown = client.post(
        f"/admin/roles/{target_role_id}/permissions",
        data={"permission_ids": [str(permissions["reports.view"]), "999999"]},
    )
    assert unknown.status_code == 400
    duplicate = client.post(
        f"/admin/roles/{target_role_id}/permissions",
        data={"permission_ids": [str(permissions["reports.view"])] * 2},
    )
    assert duplicate.status_code == 400

    with app.app_context():
        assert _permission_ids(db.session.get(Role, target_role_id)) == original


def test_activation_deactivation_respects_hierarchy_self_and_last_super_admin(client, app):
    with app.app_context():
        admin = User.query.filter_by(username="admin").one()
        super_admin = User.query.filter_by(username="super").one()
        reporter = User.query.filter_by(username="reporter").one()
        admin_id, super_admin_id, reporter_id = admin.id, super_admin.id, reporter.id
        admin_role = admin.role
        self_deactivate_form = _user_form(admin, admin_role)
        self_deactivate_form.pop("is_active")

    assert _login(client, "admin").status_code == 302
    assert client.post(f"/admin/users/{super_admin_id}/deactivate").status_code == 403
    assert client.post(f"/admin/users/{admin_id}/deactivate").status_code == 400
    assert client.post(f"/admin/users/{admin_id}/edit", data=self_deactivate_form).status_code == 400
    assert client.post(f"/admin/users/{reporter_id}/deactivate").status_code == 302

    with app.app_context():
        assert db.session.get(User, super_admin_id).is_active is True
        assert db.session.get(User, admin_id).is_active is True
        assert db.session.get(User, reporter_id).is_active is False

    client.post("/logout")
    assert _login(client, "super").status_code == 302
    assert client.post(f"/admin/users/{super_admin_id}/deactivate").status_code == 400
