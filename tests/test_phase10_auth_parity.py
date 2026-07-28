"""Regression coverage for Phase 10 group 5 resource-specific scopes."""

from datetime import date, datetime

from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import (
    DailyReport,
    DailyReportSection,
    Permission,
    PersistentIssue,
    Project,
    ProjectContractor,
    ProjectContractorAssignment,
    ProjectUpdate,
    ProjectUser,
    Role,
    RolePermission,
    User,
)


def _login(client, username):
    return client.post("/login", data={"username_or_email": username, "password": "password123"})


def _actor(app, user_id, *, permissions=(), memberships=()):
    username = f"parity-{user_id}"
    with app.app_context():
        role = Role(id=user_id, code=f"PARITY_{user_id}", name=f"Parity {user_id}", is_system=False)
        user = User(
            id=user_id,
            username=username,
            email=f"{username}@example.test",
            full_name=username,
            password_hash=generate_password_hash("password123"),
            role=role,
            legacy_role=role.code,
        )
        db.session.add_all((role, user))
        db.session.flush()
        granted = Permission.query.filter(Permission.code.in_(permissions)).all()
        db.session.add_all(RolePermission(role_id=role.id, permission_id=item.id) for item in granted)
        for offset, (project_id, flags) in enumerate(memberships, start=1):
            db.session.add(ProjectUser(
                id=user_id * 10 + offset,
                user_id=user.id,
                project_id=project_id,
                project_role_code="CUSTOM",
                is_active=True,
                **flags,
            ))
        db.session.commit()
    return username


def _report(report_id, project_id, *, highlight):
    return DailyReport(
        id=report_id,
        project_id=project_id,
        report_date=date.today(),
        overall_status="GOOD",
        highlight=highlight,
        created_by_user_id=3,
    )


def test_report_list_and_today_use_report_scope_and_exclude_deleted_projects(client, app):
    username = _actor(
        app,
        2101,
        permissions=("modules.reports.access", "reports.today.view"),
        memberships=(
            (1, {"can_view_project": True}),
            (2, {"can_view_project": True, "can_view_reports": True}),
        ),
    )
    with app.app_context():
        hidden_project = Project(id=2103, code="P2103", name="Deleted report project", deleted_at=datetime.utcnow())
        db.session.add_all((
            _report(2101, 1, highlight="hidden report metadata"),
            _report(2102, 2, highlight="permitted report metadata"),
            hidden_project,
            _report(2103, 2103, highlight="deleted project report metadata"),
        ))
        db.session.add(ProjectUser(id=21013, user_id=2101, project_id=2103, project_role_code="CUSTOM", is_active=True,
                                   can_view_project=True, can_view_reports=True))
        db.session.commit()

    _login(client, username)
    listing = client.get("/reports")
    today = client.get("/reports/today")
    assert listing.status_code == today.status_code == 200
    assert b"permitted report metadata" in listing.data
    assert b"hidden report metadata" not in listing.data
    assert b"deleted project report metadata" not in listing.data
    assert b"Other Project" in today.data
    assert b"Deleted report project" not in today.data
    assert client.get("/reports/2101").status_code == 403
    assert client.get("/reports/2102").status_code == 200


def test_global_issue_list_uses_issue_scope_and_active_project_lifecycle(client, app):
    username = _actor(
        app,
        2102,
        permissions=("modules.reports.access",),
        memberships=(
            (1, {"can_view_project": True, "can_view_issues": True}),
            (2, {"can_view_project": True}),
        ),
    )
    with app.app_context():
        db.session.add_all((
            PersistentIssue(id=2201, project_id=1, title="allowed issue title", severity="HIGH", status="OPEN", opened_date=date.today(), created_by_user_id=3),
            PersistentIssue(id=2202, project_id=2, title="hidden issue title", severity="CRITICAL", status="OPEN", opened_date=date.today(), created_by_user_id=3),
        ))
        db.session.commit()

    _login(client, username)
    response = client.get("/reports/issues?status=CRITICAL")
    assert response.status_code == 200
    assert b"hidden issue title" not in response.data
    response = client.get("/reports/issues")
    assert b"allowed issue title" in response.data
    with app.app_context():
        db.session.get(Project, 1).status = "archived"
        db.session.commit()
    assert b"allowed issue title" not in client.get("/reports/issues").data


def test_archived_project_rejects_report_edit_and_upload_before_mutation(client, app):
    with app.app_context():
        db.session.add(_report(2301, 1, highlight="unchanged archive report"))
        db.session.get(Project, 1).status = "archived"
        db.session.commit()
    _login(client, "reporter")
    edit = client.post("/reports/2301/edit", data={"report_date": date.today().isoformat(), "overall_status": "GOOD", "highlight": "mutated"})
    session = client.post("/api/projects/1/daily-reports/upload-sessions", json={"file_count": 1, "total_size_bytes": 1})
    assert edit.status_code == session.status_code == 403
    with app.app_context():
        assert db.session.get(DailyReport, 2301).highlight == "unchanged archive report"


def test_project_dashboard_html_and_json_hide_each_resource_without_its_capability(client, app):
    username = _actor(
        app,
        2103,
        permissions=("modules.reports.access", "dashboards.project.view"),
        memberships=((1, {"can_view_project": True}),),
    )
    with app.app_context():
        report = _report(2401, 1, highlight="hidden dashboard report")
        db.session.add(report)
        db.session.flush()
        db.session.add_all((
            DailyReportSection(id=2401, daily_report_id=report.id, report_category_id=1, status="CRITICAL", content="hidden dashboard section"),
            PersistentIssue(id=2401, project_id=1, title="hidden dashboard issue", severity="CRITICAL", status="OPEN", opened_date=date.today(), created_by_user_id=3),
            ProjectUpdate(id=2401, project_id=1, update_type="NOTE", title="hidden dashboard update", content="hidden", update_date=date.today(), created_by_id=3),
        ))
        db.session.commit()

    _login(client, username)
    page = client.get("/reports/projects/1/dashboard")
    payload = client.get("/api/reports/dashboard/projects/1/section-status").get_json()
    assert page.status_code == 200
    assert b"hidden dashboard report" not in page.data
    assert b"hidden dashboard issue" not in page.data
    assert b"hidden dashboard update" not in page.data
    assert payload["submission"]["report_id"] is None
    assert payload["section_status"]["total"] == 0
    assert payload["persistent_issues"]["total"] == 0
    assert payload["latest_project_update"] is None


def test_system_dashboard_html_and_json_keep_resource_aggregates_empty_without_resource_capabilities(client, app):
    username = _actor(
        app,
        2105,
        permissions=(
            "modules.reports.access",
            "projects.scope_all",
            "dashboards.system.view",
            "dashboards.customer.view",
        ),
    )
    with app.app_context():
        db.session.add_all((
            _report(2451, 1, highlight="system hidden report"),
            PersistentIssue(id=2451, project_id=1, title="system hidden issue", severity="HIGH", status="OPEN", opened_date=date.today(), created_by_user_id=3),
            ProjectUpdate(id=2451, project_id=1, update_type="NOTE", title="system hidden update", content="hidden", update_date=date.today(), created_by_id=3),
        ))
        db.session.commit()

    _login(client, username)
    page = client.get("/reports/dashboard/system")
    payload = client.get("/api/reports/dashboard/system/overview").get_json()
    assert page.status_code == 200
    assert b"system hidden report" not in page.data
    assert b"system hidden issue" not in page.data
    assert b"system hidden update" not in page.data
    assert payload["submissions"]["labels"] == []
    assert payload["persistent_issues"]["by_project"]["labels"] == []
    assert payload["persistent_issues"]["status"]["values"] == [0, 0, 0, 0]
    assert payload["system_analytics"]["project_activity"]["current_issues"]["project_ids"] == []


def test_contractor_dashboard_does_not_turn_one_issue_capability_into_global_issue_access(client, app):
    username = _actor(
        app,
        2104,
        permissions=("modules.reports.access", "dashboards.contractor.view"),
        memberships=(
            (1, {"can_view_project": True, "can_view_issues": True}),
            (2, {"can_view_project": True}),
        ),
    )
    with app.app_context():
        contractor = ProjectContractor(id=2501, name="Parity contractor", normalized_name="parity contractor")
        db.session.add(contractor)
        db.session.flush()
        db.session.add_all((
            ProjectContractorAssignment(id=2501, project_id=1, contractor_id=contractor.id, role="CONSTRUCTION", status="ACTIVE"),
            ProjectContractorAssignment(id=2502, project_id=2, contractor_id=contractor.id, role="SOLUTION", status="ACTIVE"),
            PersistentIssue(id=2501, project_id=1, title="permitted contractor issue", severity="LOW", status="OPEN", opened_date=date.today(), created_by_user_id=3),
            PersistentIssue(id=2502, project_id=2, title="hidden contractor issue", severity="CRITICAL", status="OPEN", opened_date=date.today(), created_by_user_id=3),
        ))
        db.session.commit()

    _login(client, username)
    page = client.get("/reports/dashboard/contractors/2501")
    assert page.status_code == 200
    assert b"permitted contractor issue" in page.data
    assert b"hidden contractor issue" not in page.data
