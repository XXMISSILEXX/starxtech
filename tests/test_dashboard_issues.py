from datetime import date

from app.extensions import db
from app.models import AuditLog, DailyReport, IssueStatus, PersistentIssue


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
    assert counts["Nghiêm trọng"] == 0


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

    chart = client.get("/api/reports/dashboard/status-chart")
    counts = dict(zip(chart.get_json()["labels"], chart.get_json()["counts"]))
    assert counts["Tốt"] == 1
    assert counts["Đang xử lý"] == 1
    assert counts["Nghiêm trọng"] == 1

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
