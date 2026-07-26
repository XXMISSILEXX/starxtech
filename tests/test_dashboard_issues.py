from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import event

from app.extensions import db
from app.models import AuditLog, DailyReport, DailyReportSection, IssueStatus, PersistentIssue, Permission, Project, ProjectContractor, ProjectContractorAssignment, ProjectUpdate, RolePermission, User
from app.dashboard.services import project_section_status_payload


def login(client, username_or_email, password="password123"):
    return client.post(
        "/login",
        data={
            "username_or_email": username_or_email,
            "password": password,
        },
    )


def seed_dashboard_data():
    db.session.add_all(
        [
            DailyReport(
                id=101,
                project_id=1,
                report_date=date(2026, 7, 1),
                overall_status="GOOD",
                highlight="Assigned good report",
                created_by_user_id=3,
            ),
            DailyReport(
                id=102,
                project_id=1,
                report_date=date(2026, 7, 2),
                overall_status="PROCESSING",
                highlight="Assigned processing report",
                created_by_user_id=3,
            ),
            DailyReport(
                id=103,
                project_id=2,
                report_date=date(2026, 7, 3),
                overall_status="CRITICAL",
                highlight="Unassigned critical report",
                created_by_user_id=1,
            ),
            PersistentIssue(
                id=201,
                project_id=1,
                title="Assigned open issue",
                severity="HIGH",
                status="OPEN",
                opened_date=date(2026, 7, 1),
                created_by_user_id=3,
                owner_user_id=3,
            ),
            PersistentIssue(
                id=202,
                project_id=1,
                title="Assigned closed issue",
                severity="LOW",
                status="CLOSED",
                opened_date=date(2026, 7, 1),
                closed_date=date(2026, 7, 2),
                created_by_user_id=3,
            ),
            PersistentIssue(
                id=203,
                project_id=2,
                title="Unassigned open issue",
                severity="CRITICAL",
                status="OPEN",
                opened_date=date(2026, 7, 3),
                created_by_user_id=1,
            ),
        ]
    )
    db.session.commit()


def issue_form(title="New persistent issue", status="OPEN"):
    return {
        "title": title,
        "description": "Needs follow-up.",
        "severity": "MEDIUM",
        "status": status,
        "opened_date": "2026-07-08",
        "due_date": "2026-07-15",
        "owner_user_id": "3",
    }


def test_reporter_dashboard_does_not_leak_unassigned_project_data(client, app):
    with app.app_context():
        seed_dashboard_data()

    login(client, "reporter")
    response = client.get("/reports/dashboard")

    assert response.status_code == 200
    assert b"Assigned good report" in response.data
    assert b"Unassigned critical report" not in response.data
    assert b"Assigned open issue" in response.data
    assert b"Unassigned open issue" not in response.data

    chart = client.get("/api/reports/dashboard/status-chart")
    assert chart.status_code == 200
    payload = chart.get_json()
    counts = dict(zip(payload["labels"], payload["counts"]))
    assert counts["Tốt"] == 1
    assert counts["Đang xử lý"] == 1
    assert counts["Khẩn cấp"] == 0
    assert "Nghiêm trọng" not in counts


def test_viewer_admin_sees_all_but_no_write_buttons(client, app):
    with app.app_context():
        seed_dashboard_data()

    login(client, "viewer")
    dashboard = client.get("/reports/dashboard")
    assert dashboard.status_code == 200
    assert b"Unassigned critical report" in dashboard.data
    assert b"Unassigned open issue" in dashboard.data

    project_dashboard = client.get("/reports/projects/1/dashboard")
    assert project_dashboard.status_code == 200
    assert b"Add report" not in project_dashboard.data

    issues = client.get("/reports/projects/1/issues")
    assert issues.status_code == 200
    assert b"Create issue" not in issues.data

    blocked = client.post("/reports/projects/1/issues/create", data=issue_form())
    assert blocked.status_code == 403


def test_dashboard_counts_are_correct_for_seed_data(client, app):
    with app.app_context():
        seed_dashboard_data()

    login(client, "super")
    response = client.get("/reports/dashboard")

    assert response.status_code == 200
    assert "Tổng báo cáo".encode() in response.data
    assert "Vấn đề đang mở".encode() in response.data
    assert "Khẩn cấp".encode() in response.data
    assert b'data-status-icon-key="x-octagon-fill"' in response.data

    chart = client.get("/api/reports/dashboard/status-chart")
    counts = dict(zip(chart.get_json()["labels"], chart.get_json()["counts"]))
    assert counts["Tốt"] == 1
    assert counts["Đang xử lý"] == 1
    assert counts["Khẩn cấp"] == 1
    assert "Nghiêm trọng" not in counts

    count_chart = client.get("/api/reports/dashboard/report-count-chart?from_date=2026-07-01&to_date=2026-07-31")
    assert count_chart.status_code == 200
    assert count_chart.get_json()["counts"] == [1, 1, 1]


def test_reporter_cannot_mutate_persistent_issues_by_default(client, app):
    login(client, "reporter")

    created = client.post("/reports/projects/1/issues/create", data=issue_form())
    assert created.status_code == 403

    with app.app_context():
        assert PersistentIssue.query.count() == 0


def test_reporter_cannot_access_unassigned_project_issues(client, app):
    with app.app_context():
        seed_dashboard_data()

    login(client, "reporter")
    assert client.get("/reports/projects/2/issues").status_code == 403
    assert client.get("/reports/issues/203/edit").status_code == 403
    assert client.post("/reports/issues/203/close").status_code == 403


def test_project_section_status_api_is_additive_scoped_and_keeps_five_statuses(client, app):
    with app.app_context():
        report = DailyReport(id=301, project_id=1, report_date=date.today(), overall_status="GOOD", highlight="Section status", created_by_user_id=3)
        db.session.add(report); db.session.flush()
        db.session.add_all([
            DailyReportSection(id=301, daily_report_id=report.id, report_category_id=1, status="INFO", content="Info"),
            DailyReportSection(id=302, daily_report_id=report.id, report_category_id=2, status="CRITICAL", content="Critical"),
        ])
        user = User.query.filter_by(username="reporter").one()
        permission = Permission.query.filter_by(code="dashboards.project.view").one()
        db.session.add(RolePermission(role_id=user.role_id, permission_id=permission.id)); db.session.commit()
    login(client, "reporter")
    response = client.get("/api/reports/dashboard/projects/1/section-status")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["section_status"]["keys"] == ["INFO", "GOOD", "PROCESSING", "ATTENTION", "CRITICAL"]
    assert payload["section_status"]["values"] == [1, 0, 0, 0, 1]
    assert payload["section_status"]["total"] == 2
    assert len(payload["trend"]["days"]) == 7
    assert all(len(values) == 7 for values in payload["trend"]["series"].values())
    assert client.get("/api/reports/dashboard/projects/2/section-status").status_code == 403


def _payload_query_count(app, extra_rows):
    with app.app_context():
        offset = (db.session.query(db.func.max(DailyReport.id)).scalar() or 0) + 1
        start_date = date(2026, 6, 1) + timedelta(days=30 if DailyReport.query.count() else 0)
        for index in range(extra_rows):
            row_id = offset + index
            report = DailyReport(id=row_id, project_id=1, report_date=start_date + timedelta(days=index), overall_status="GOOD", highlight="aggregate", created_by_user_id=3)
            contractor = ProjectContractor(name=f"Contractor {row_id}", normalized_name=f"contractor {row_id}")
            db.session.add_all([report, contractor]); db.session.flush()
            db.session.add(DailyReportSection(id=row_id, daily_report_id=report.id, report_category_id=1, status="INFO" if index % 2 else "CRITICAL", content="aggregate"))
            db.session.add(ProjectContractorAssignment(id=row_id, project_id=1, contractor_id=contractor.id, role="CONSTRUCTION" if index % 2 else "SOLUTION", status="ACTIVE"))
            db.session.add(ProjectUpdate(id=row_id, project_id=1, update_type="NOTE", title="Update", content="aggregate", update_date=date(2026, 6, 1), created_by_id=3))
            db.session.add(PersistentIssue(id=row_id, project_id=1, title="Issue", severity="LOW", status="OPEN", opened_date=date(2026, 6, 1), created_by_user_id=3))
        db.session.commit()
        count = 0
        def before(*_args):
            nonlocal count; count += 1
        event.listen(db.engine, "before_cursor_execute", before)
        try:
            project_section_status_payload(db.session.get(Project, 1), selected_date=date(2026, 6, 1))
        finally:
            event.remove(db.engine, "before_cursor_execute", before)
        return count


def test_project_dashboard_payload_query_count_is_not_linear(app):
    small = _payload_query_count(app, 1)
    # Fresh app fixture state is not needed: the second call adds rows, which is
    # precisely the regression condition—more assignments/issues/updates must
    # not add per-row statements.
    large = _payload_query_count(app, 20)
    assert large == small


def test_project_dashboard_uses_external_csp_safe_chart_script(client, app):
    login(client, "viewer")
    page = client.get("/reports/projects/1/dashboard")
    assert page.status_code == 200
    assert b"project-dashboard-charts.js" in page.data
    assert b"data-section-status-api=" in page.data
    assert b'id="project-section-pie"' in page.data and b'id="project-section-trend"' in page.data
    assert "Tóm tắt năm trạng thái section".encode() in page.data
    assert b"new Chart(" not in page.data
    # The crop-preview template embeds markup containing script-like text, so
    # use the final rendered script tag rather than the first byte occurrence.
    assert page.data.index(b'<script src="https://cdn.jsdelivr.net/npm/chart.js') < page.data.rindex(b'<script src="/static/js/project-dashboard-charts.js')

    script = Path(app.static_folder, "js", "project-dashboard-charts.js").read_text()
    assert "fetch(root.dataset.sectionStatusApi" in script
    assert "data.section_status" in script and "status.keys.length === STATUS_COUNT" in script
    assert "data.trend" in script and "trend.days.length === 7" in script
    assert "data-chart-empty" in script and "data-chart-error" in script
