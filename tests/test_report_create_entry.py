from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import ProjectUser, Role, User
from app.project_memberships import preset_flags


def login(client, username_or_email, password="password123"):
    return client.post(
        "/login",
        data={
            "username_or_email": username_or_email,
            "password": password,
        },
    )


def test_reports_page_contains_create_report_entry_for_admin(client):
    login(client, "super")

    response = client.get("/reports")

    assert response.status_code == 200
    assert "Tạo báo cáo".encode() in response.data
    assert b"create_report=1" in response.data


def test_projects_create_report_query_shows_flash_message(client):
    login(client, "super")

    response = client.get("/reports/projects?create_report=1")

    assert response.status_code == 200
    assert "Chọn dự án để tạo báo cáo mới".encode() in response.data


def test_reporter_with_assigned_project_sees_create_report_entry(client):
    login(client, "reporter")

    response = client.get("/reports")

    assert response.status_code == 200
    assert "Tạo báo cáo".encode() in response.data
    assert b"create_report=1" in response.data


def test_reporter_without_project_access_does_not_see_create_report_entry(client, app):
    with app.app_context():
        db.session.add(
            User(
                id=901,
                username="no_project",
                email="no_project@example.com",
                full_name="No Project",
                password_hash=generate_password_hash("password123"),
                role=Role.query.filter_by(code="REPORTER").one(),
                legacy_role="REPORTER",
                is_active=True,
            )
        )
        db.session.commit()

    login(client, "no_project")

    response = client.get("/reports")

    assert response.status_code == 403


def test_report_view_membership_without_create_capability_hides_create_entry(client, app):
    with app.app_context():
        role = Role.query.filter_by(code="REPORTER").one()
        user = User(id=902, username="report_viewer", email="report_viewer@example.com", full_name="Report Viewer",
                    password_hash=generate_password_hash("password123"), role=role, legacy_role=role.code, is_active=True)
        db.session.add(user); db.session.flush()
        db.session.add(ProjectUser(id=902, project_id=1, user_id=user.id, project_role_code="PROJECT_VIEWER", **preset_flags("PROJECT_VIEWER")))
        db.session.commit()

    login(client, "report_viewer")
    response = client.get("/reports")

    assert response.status_code == 200
    assert "Tạo báo cáo".encode() not in response.data
    assert b"create_report=1" not in response.data
