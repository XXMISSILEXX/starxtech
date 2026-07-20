from datetime import date

from app.extensions import db
from app.models import AuditLog, DailyReport, Permission, PersistentIssue, ReportCategory, RolePermission, User


def login(client, username_or_email, password="password123"):
    return client.post(
        "/login",
        data={
            "username_or_email": username_or_email,
            "password": password,
        },
    )


def issue_form(title="PM issue", owner_user_id="5"):
    return {
        "title": title,
        "description": "Theo dõi xử lý.",
        "severity": "CRITICAL",
        "status": "OPEN",
        "opened_date": "2026-07-08",
        "due_date": "2026-07-15",
        "owner_user_id": owner_user_id,
    }


def grant_pm(app, code):
    with app.app_context():
        user = User.query.filter_by(username="pm").one()
        permission = Permission.query.filter_by(code=code).one()
        db.session.add(RolePermission(role_id=user.role_id, permission_id=permission.id))
        db.session.commit()


def test_project_manager_accesses_only_assigned_projects(client):
    login(client, "pm")

    assert client.get("/projects/1/dashboard").status_code == 200
    assert client.get("/projects/2/dashboard").status_code == 403
    assert client.get("/projects/1/reports").status_code == 200
    assert client.get("/projects/2/reports").status_code == 403
    assert client.get("/admin/users").status_code == 403


def test_project_manager_can_manage_categories_only_for_assigned_project(client, app):
    grant_pm(app, "categories.manage")
    login(client, "pm")

    created = client.post(
        "/admin/projects/1/categories",
        data={
            "name": "An toàn",
            "icon": "shield-check",
            "sort_order": "3",
            "is_active": "on",
        },
    )
    assert created.status_code == 302

    blocked = client.post(
        "/admin/projects/2/categories",
        data={"name": "Blocked", "sort_order": "1", "is_active": "on"},
    )
    assert blocked.status_code == 403

    with app.app_context():
        category = ReportCategory.query.filter_by(project_id=1, name="An toàn").one()
        category_id = category.id

    deleted = client.post(f"/admin/projects/1/categories/{category_id}/delete")
    assert deleted.status_code == 302
    with app.app_context():
        category = db.session.get(ReportCategory, category_id)
        assert category.deleted_at is not None
        assert AuditLog.query.filter_by(action="category.delete", entity_id=category_id).count() == 1


def test_project_manager_can_delete_reports_only_for_assigned_project(client, app):
    with app.app_context():
        db.session.add_all(
            [
                DailyReport(
                    id=501,
                    project_id=1,
                    report_date=date(2026, 7, 10),
                    overall_status="GOOD",
                    highlight="Assigned PM report",
                    created_by_user_id=5,
                ),
                DailyReport(
                    id=502,
                    project_id=2,
                    report_date=date(2026, 7, 10),
                    overall_status="GOOD",
                    highlight="Unassigned PM report",
                    created_by_user_id=1,
                ),
            ]
        )
        db.session.commit()

    grant_pm(app, "reports.delete")
    login(client, "pm")
    assert client.post("/reports/501/delete").status_code == 302
    assert client.post("/reports/502/delete").status_code == 403


def test_project_manager_can_manage_issues_only_for_assigned_project(client, app):
    grant_pm(app, "issues.delete")
    login(client, "pm")

    created = client.post("/projects/1/issues/create", data=issue_form())
    assert created.status_code == 302
    blocked = client.post("/projects/2/issues/create", data=issue_form(owner_user_id=""))
    assert blocked.status_code == 403

    with app.app_context():
        issue = PersistentIssue.query.filter_by(title="PM issue").one()
        issue_id = issue.id

    edited = client.post(f"/issues/{issue_id}/edit", data=issue_form("PM issue updated"))
    assert edited.status_code == 302
    deleted = client.post(f"/issues/{issue_id}/delete")
    assert deleted.status_code == 302

    with app.app_context():
        issue = db.session.get(PersistentIssue, issue_id)
        assert issue.deleted_at is not None
        assert AuditLog.query.filter_by(action="issue.delete", entity_id=issue_id).count() == 1


def test_reporter_cannot_delete_persistent_issue(client, app):
    with app.app_context():
        issue = PersistentIssue(
            id=601,
            project_id=1,
            title="Reporter cannot delete",
            severity="HIGH",
            status="OPEN",
            opened_date=date(2026, 7, 8),
            created_by_user_id=3,
            owner_user_id=3,
        )
        db.session.add(issue)
        db.session.commit()

    login(client, "reporter")
    assert client.post("/issues/601/delete").status_code == 403
