from app.extensions import db
from app.models import AuditLog, Project, ProjectStatus, ProjectUser, ReportCategory, Role, User, UserRole


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
        assert AuditLog.query.filter_by(action="project.archive", entity_id=project.id).count() == 1


def test_super_admin_assigns_and_removes_project_reporters(client, app):
    login(client, "super")

    assigned = client.post("/admin/projects/2/reporters", data={"reporter_ids": ["3"]})

    assert assigned.status_code == 302
    with app.app_context():
        assert ProjectUser.query.filter_by(project_id=2, user_id=3).count() == 1
        assert AuditLog.query.filter_by(action="project_user.assign").count() == 1

    removed = client.post("/admin/projects/2/reporters", data={})

    assert removed.status_code == 302
    with app.app_context():
        assert ProjectUser.query.filter_by(project_id=2, user_id=3).count() == 0
        assert AuditLog.query.filter_by(action="project_user.remove").count() == 1


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
