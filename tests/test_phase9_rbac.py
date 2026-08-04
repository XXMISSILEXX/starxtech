from app.auth.permissions import can_create_report, can_read_project
from app.extensions import db
from app.models import Permission, Role, RolePermission, User
from app.permissions.services import user_has_permission
from app.permissions.sync import sync_registry
from app.project_memberships import accessible_project_ids, user_has_project_capability


def _custom_user(app, *, role_code, username, permissions=()):
    with app.app_context():
        role = Role(code=role_code, name=role_code, is_system=False)
        db.session.add(role)
        db.session.flush()
        user = User(
            id=100,
            full_name=username.title(),
            username=username,
            password_hash="not-used-by-this-test",
            role=role,
            legacy_role=role_code,
        )
        db.session.add(user)
        db.session.flush()
        rows = Permission.query.filter(Permission.code.in_(permissions)).all()
        assert len(rows) == len(permissions)
        db.session.add_all(RolePermission(role_id=role.id, permission_id=row.id) for row in rows)
        db.session.commit()
        return user.id


def _login_as(client, user_id):
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def test_phase9_registry_sync_is_idempotent_and_preserves_custom_role_grants(app):
    user_id = _custom_user(app, role_code="PHASE9_CUSTOM", username="phase9-custom", permissions=("reports.view",))

    with app.app_context():
        first = sync_registry(apply_defaults=True)
        second = sync_registry(apply_defaults=True)
        user = db.session.get(User, user_id)

        assert first["permissions_created"] == 0
        assert second["permissions_created"] == 0
        assert user.can("reports.view")
        assert not user.can("customers.view")


def test_unknown_permission_is_denied_for_custom_role(app):
    user_id = _custom_user(app, role_code="PHASE9_DENY", username="phase9-deny")

    with app.app_context():
        assert not user_has_permission(db.session.get(User, user_id), "phase9.unknown")


def test_scope_all_grants_global_read_scope_but_not_project_mutation(client, app):
    user_id = _custom_user(
        app,
        role_code="PHASE9_GLOBAL_VIEWER",
        username="phase9-global-viewer",
        permissions=("modules.reports.access", "projects.scope_all"),
    )

    with app.app_context():
        user = db.session.get(User, user_id)
        assert accessible_project_ids(user) is None
        assert can_read_project(1, user)
        assert can_read_project(2, user)
        assert not user_has_project_capability(user, 1, "can_edit_all_reports")
        assert not can_create_report(user, 1)

    _login_as(client, user_id)
    assert client.get("/test/projects/2/read").status_code == 200
    assert client.post("/test/projects/2/write").status_code == 403


def test_project_dashboard_permission_does_not_bypass_project_scope(client, app):
    user_id = _custom_user(
        app,
        role_code="PHASE9_DASHBOARD_UNSCOPED",
        username="phase9-dashboard-unscoped",
        permissions=("modules.reports.access", "dashboards.project.view"),
    )

    _login_as(client, user_id)
    assert client.get("/reports/projects/1/dashboard").status_code == 403
    assert client.get("/api/reports/dashboard/projects/1/section-status").status_code == 403


def test_scope_all_does_not_grant_project_dashboard_permission(client, app):
    user_id = _custom_user(
        app,
        role_code="PHASE9_SCOPE_WITHOUT_DASHBOARD",
        username="phase9-scope-without-dashboard",
        permissions=("modules.reports.access", "projects.scope_all"),
    )

    _login_as(client, user_id)
    assert client.get("/reports/projects/1/dashboard").status_code == 403
    assert client.get("/api/reports/dashboard/projects/1/section-status").status_code == 403


def test_scope_all_and_dashboard_permission_allow_read_only_dashboard(client, app):
    user_id = _custom_user(
        app,
        role_code="PHASE9_GLOBAL_DASHBOARD",
        username="phase9-global-dashboard",
        permissions=("modules.reports.access", "projects.scope_all", "dashboards.project.view"),
    )

    _login_as(client, user_id)
    assert client.get("/reports/projects/2/dashboard").status_code == 200
    assert client.get("/api/reports/dashboard/projects/2/section-status").status_code == 200
    assert client.post("/reports/projects/2/reports/upload-sessions", json={}).status_code == 403


def test_action_permission_without_scope_or_membership_cannot_access_project(app):
    user_id = _custom_user(
        app,
        role_code="PHASE9_ACTION_ONLY",
        username="phase9-action-only",
        permissions=("modules.reports.access", "reports.create", "project_updates.create"),
    )

    with app.app_context():
        user = db.session.get(User, user_id)
        assert not can_read_project(1, user)
        assert not can_create_report(user, 1)
        assert accessible_project_ids(user) == []


def test_super_admin_scope_behavior_is_unchanged(app):
    with app.app_context():
        super_admin = User.query.filter_by(username="super").one()
        assert accessible_project_ids(super_admin) is None
        assert user_has_project_capability(super_admin, 2, "can_edit_all_reports")


def test_role_permission_ui_groups_phase9_catalogue(client):
    _login_as(client, 1)

    response = client.get("/admin/roles/1/permissions")

    assert response.status_code == 200
    for label in (
        "Điều hướng Reports",
        "Khách hàng",
        "Nhà thầu dự án",
        "Assignment",
        "Báo cáo xuyên suốt",
        "Dashboard",
    ):
        assert label.encode() in response.data


def test_super_admin_role_permissions_do_not_offer_dead_security_audit_permission(client):
    _login_as(client, 1)

    response = client.get("/admin/roles/1/permissions")

    assert response.status_code == 200
    assert b"security.audit" not in response.data
    assert "Xem nhật ký bảo mật".encode() not in response.data
