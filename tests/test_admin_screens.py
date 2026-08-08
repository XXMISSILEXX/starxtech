from datetime import datetime

from app.extensions import db
from app.models import AuditLog, Customer, Project, ProjectStatus, ProjectUser, ReportCategory, Role, User, UserRole


def login(client, username_or_email, password="password123"):
    return client.post(
        "/login",
        data={
            "username_or_email": username_or_email,
            "password": password,
        },
    )


def test_viewer_admin_can_read_admin_pages_but_cannot_post(client):
    login(client, "viewer")

    assert client.get("/admin/users").status_code == 200
    assert client.get("/admin/projects").status_code == 200
    assert client.get("/admin/projects/1/reporters").status_code == 200
    assert client.get("/admin/projects/1/categories").status_code == 200

    response = client.post(
        "/admin/users/new",
        data={
            "full_name": "Blocked User",
            "username": "blocked",
            "email": "blocked@example.com",
            "role": "REPORTER",
            "password": "Password123!",
            "is_active": "on",
        },
    )

    assert response.status_code == 403


def test_users_view_is_read_only_and_users_manage_allows_admin_mutations(client, app):
    login(client, "viewer")
    assert client.get("/admin/users").status_code == 200
    assert client.get("/admin/users/new").status_code == 200
    assert b"/admin/users/new" not in client.get("/admin/users").data
    assert client.post("/admin/users/3/deactivate").status_code == 403

    client.post("/logout")
    login(client, "admin")
    with app.app_context():
        reporter_role = Role.query.filter_by(code=UserRole.REPORTER.value).one()

    response = client.post(
        "/admin/users/new",
        data={
            "full_name": "Managed User",
            "username": "managed-user",
            "email": "managed-user@example.com",
            "role_id": str(reporter_role.id),
            "password": "Password123!",
            "is_active": "on",
        },
    )

    assert response.status_code == 302
    with app.app_context():
        assert User.query.filter_by(username="managed-user").one().is_active is True


def test_users_list_displays_last_login_in_vietnam_time_and_dash_for_never_logged_in(client, app):
    login(client, "super")
    with app.app_context():
        reporter = User.query.filter_by(username="reporter").one()
        reporter.last_login_at = datetime(2026, 8, 6, 14, 38)
        db.session.commit()

    response = client.get("/admin/users")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Đăng nhập cuối" in page
    assert "06/08/2026 lúc 21:38" in page
    inactive_row_start = page.index("Inactive")
    inactive_row = page[inactive_row_start:page.index("</tr>", inactive_row_start)]
    assert ">—</td>" in inactive_row


def test_super_admin_creates_role_with_audit(client, app):
    login(client, "super")
    with app.app_context():
        before_audits = AuditLog.query.count()

    response = client.post(
        "/admin/roles/new",
        data={"code": "AUDIT_ROLE", "name": "Audit role", "description": "Audit retention test"},
    )

    assert response.status_code == 302
    with app.app_context():
        role = Role.query.filter_by(code="AUDIT_ROLE").one()
        assert AuditLog.query.count() == before_audits + 1
        assert AuditLog.query.filter_by(action="role.create", entity_id=role.id).count() == 1


def test_last_active_super_admin_cannot_be_deactivated_or_reassigned(client, app):
    login(client, "super")
    with app.app_context():
        super_user = User.query.filter_by(username="super").one()
        reporter_role = Role.query.filter_by(code=UserRole.REPORTER.value).one()

    assert client.post(f"/admin/users/{super_user.id}/deactivate").status_code == 400
    reassigned = client.post(
        f"/admin/users/{super_user.id}/edit",
        data={
            "full_name": super_user.full_name,
            "username": super_user.username,
            "email": super_user.email,
            "role_id": str(reporter_role.id),
            "is_active": "on",
        },
    )
    assert reassigned.status_code == 400

    with app.app_context():
        super_user = db.session.get(User, super_user.id)
        assert super_user.is_active is True
        assert super_user.role_code == UserRole.SUPER_ADMIN.value


def test_reporter_cannot_access_admin_routes(client):
    login(client, "reporter")

    assert client.get("/admin/users").status_code == 403
    assert client.post("/admin/projects/1/categories", data={"name": "Blocked"}).status_code == 403


def test_super_admin_creates_user_and_duplicate_validation_fails(client, app):
    login(client, "super")

    created = client.post(
        "/admin/users/new",
        data={
            "full_name": "New Reporter",
            "username": "newreporter",
            "email": "newreporter@example.com",
            "role": "REPORTER",
            "password": "Password123!",
            "is_active": "on",
        },
    )

    assert created.status_code == 302
    with app.app_context():
        user = User.query.filter_by(username="newreporter").one()
        assert user.email == "newreporter@example.com"
        assert AuditLog.query.filter_by(action="user.create", entity_id=user.id).count() == 1

    duplicate = client.post(
        "/admin/users/new",
        data={
            "full_name": "Duplicate Reporter",
            "username": "newreporter",
            "email": "newreporter@example.com",
            "role": "REPORTER",
            "password": "Password123!",
            "is_active": "on",
        },
    )

    assert duplicate.status_code == 400
    assert "Tên đăng nhập đã tồn tại".encode() in duplicate.data
    assert "Email đã tồn tại".encode() in duplicate.data


def test_super_admin_creates_and_archives_project(client, app):
    with app.app_context():
        customer = Customer(id=9905, name="Snapshot Customer", normalized_name="snapshot customer")
        db.session.add(customer)
        db.session.commit()
        customer_id = customer.id

    login(client, "super")

    created = client.post(
        "/admin/projects/new",
        data={
            "code": "P003",
            "name": "New Project",
            "description": "Daily reports",
            "status": ProjectStatus.ACTIVE.value,
            "start_date": "2026-07-01",
            "expected_end_date": "2026-08-01",
            "customer_id": str(customer_id),
        },
    )

    assert created.status_code == 302
    with app.app_context():
        project = Project.query.filter_by(code="P003").one()
        assert project.name == "New Project"

    archived = client.post(f"/admin/projects/{project.id}/archive")

    assert archived.status_code == 302
    with app.app_context():
        archived_project = db.session.get(Project, project.id)
        assert archived_project.status == ProjectStatus.ARCHIVED.value
        audit = AuditLog.query.filter_by(action="project.archive", entity_id=project.id).one()
        assert audit.old_values_json["code"] == "P003"
        assert audit.old_values_json["name"] == "New Project"
        assert audit.old_values_json["customer"] == {"id": customer_id, "name": "Snapshot Customer"}
        assert audit.old_values_json["created_by_id"] is None
        assert audit.old_values_json["created_at"]


def test_super_admin_assigns_and_removes_project_reporters(client, app):
    login(client, "super")

    assigned = client.post("/admin/projects/2/memberships", data={"user_id": "3", "project_role_code": "PROJECT_VIEWER", "can_view_project": "1"})

    assert assigned.status_code == 302
    with app.app_context():
        assert ProjectUser.query.filter_by(project_id=2, user_id=3).count() == 1
        assert AuditLog.query.filter_by(action="project_membership.assign").count() == 1

    with app.app_context():
        membership_id = ProjectUser.query.filter_by(project_id=2, user_id=3).one().id
    removed = client.post(f"/admin/projects/2/memberships/{membership_id}/deactivate")

    assert removed.status_code == 302
    with app.app_context():
        membership = ProjectUser.query.filter_by(project_id=2, user_id=3).one()
        assert membership.is_active is False
        assert AuditLog.query.filter_by(action="project_membership.deactivate").count() == 1


def test_super_admin_creates_category_duplicate_fails_and_deactivate_toggles(client, app):
    login(client, "super")

    created = client.post(
        "/admin/projects/1/categories",
        data={
            "name": "Safety",
            "description": "Safety notes",
            "sort_order": "10",
            "is_active": "on",
            "is_required": "on",
        },
    )

    assert created.status_code == 302
    with app.app_context():
        category = ReportCategory.query.filter_by(project_id=1, name="Safety").one()
        assert category.is_required is True
        assert AuditLog.query.filter_by(action="category.create", entity_id=category.id).count() == 1

    duplicate = client.post(
        "/admin/projects/1/categories",
        data={
            "name": "Safety",
            "sort_order": "20",
            "is_active": "on",
        },
    )

    assert duplicate.status_code == 400
    assert "Tên hạng mục đã tồn tại".encode() in duplicate.data

    deactivated = client.post(f"/admin/projects/1/categories/{category.id}/deactivate")

    assert deactivated.status_code == 302
    with app.app_context():
        category = db.session.get(ReportCategory, category.id)
        assert category.is_active is False
        assert AuditLog.query.filter_by(action="category.deactivate", entity_id=category.id).count() == 1
