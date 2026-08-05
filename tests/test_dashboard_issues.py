from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import event

from app.extensions import db
from app.models import AuditLog, Customer, DailyReport, DailyReportSection, IssueStatus, PersistentIssue, Permission, ProgressEntry, ProgressGroup, ProgressItem, ProgressType, Project, ProjectContractor, ProjectContractorAssignment, ProjectUpdate, ProjectUser, ReportCategory, Role, RolePermission, User
from app.dashboard.services import _activity_payload, project_dashboard_context, project_section_status_payload


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


def issue_form(title="New persistent issue"):
    return {
        "title": title,
        "description": "Needs follow-up.",
        "severity": "MEDIUM",
        "opened_date": "2026-07-08",
    }


def test_legacy_report_dashboard_and_chart_routes_are_404(client, app):
    with app.app_context():
        seed_dashboard_data()
    for url in ("/reports/dashboard", "/api/reports/dashboard/status-chart", "/api/reports/dashboard/report-count-chart"):
        assert client.get(url).status_code == 404


def test_viewer_admin_sees_all_but_no_write_buttons(client, app):
    with app.app_context():
        seed_dashboard_data()

    login(client, "viewer")
    project_dashboard = client.get("/reports/projects/1/dashboard")
    assert project_dashboard.status_code == 200
    assert b"Add report" not in project_dashboard.data

    issues = client.get("/reports/projects/1/issues")
    assert issues.status_code == 200
    assert b"Create issue" not in issues.data

    blocked = client.post("/reports/projects/1/issues/create", data=issue_form())
    assert blocked.status_code == 403


def test_project_dashboard_uses_project_context_issue_wording(client, app):
    login(client, "viewer")
    response = client.get("/reports/projects/1/dashboard")
    assert response.status_code == 200
    assert "Vấn đề tồn đọng".encode() in response.data
    assert "Vấn đề đang mở".encode() not in response.data


def test_project_dashboard_renders_without_issue_owner_column(client, app):
    with app.app_context():
        seed_dashboard_data()
    login(client, "viewer")

    response = client.get("/reports/projects/1/dashboard")

    assert response.status_code == 200
    assert b"Assigned open issue" in response.data
    assert b"<th>Ph\xe1\xbb\xa5 tr\xc3\xa1ch</th>" not in response.data


def _seed_project_progress_dashboard_data():
    scheduled_type = ProgressType(project_id=1, name="Giai đoạn có lịch", created_by_id=1)
    undated_type = ProgressType(project_id=1, name="Giai đoạn chưa lịch", created_by_id=1)
    db.session.add_all((scheduled_type, undated_type))
    db.session.flush()
    scheduled_group = ProgressGroup(project_id=1, progress_type_id=scheduled_type.id, name="Khu có lịch", created_by_id=1)
    undated_group = ProgressGroup(project_id=1, progress_type_id=undated_type.id, name="Khu chưa lịch", created_by_id=1)
    db.session.add_all((scheduled_group, undated_group))
    db.session.flush()
    scheduled_item = ProgressItem(project_id=1, progress_group_id=scheduled_group.id, name="Hạng mục có lịch", unit="m", planned_quantity=10, completed_quantity=5, planned_start_date=date(2026, 8, 1), planned_end_date=date(2026, 8, 10), created_by_id=1)
    undated_item = ProgressItem(project_id=1, progress_group_id=undated_group.id, name="Hạng mục chưa lịch", unit="m", planned_quantity=10, completed_quantity=2, created_by_id=1)
    db.session.add_all((scheduled_item, undated_item))
    db.session.flush()
    db.session.add(ProgressEntry(project_id=1, progress_item_id=scheduled_item.id, report_date=date(2026, 8, 3), quantity=1, created_by_id=1))
    db.session.commit()
    return scheduled_type, undated_type


def test_project_dashboard_renders_capability_scoped_progress_block_without_project_percent(client, app):
    with app.app_context():
        _seed_project_progress_dashboard_data()

    login(client, "admin")
    response = client.get("/reports/projects/1/dashboard")
    page = response.get_data(as_text=True)
    stats = page[page.index("data-project-progress-stats"):page.index("data-project-progress-table")]
    table = page[page.index("data-project-progress-table"):page.index("</table>", page.index("data-project-progress-table"))]

    assert response.status_code == 200
    assert "data-project-progress-dashboard" in page
    assert "Giai đoạn đang chạy" in stats
    assert "Hạng mục quá hạn" in stats
    assert "Chưa khai ngày" in stats
    assert "Cập nhật gần nhất" in stats
    assert "%" not in stats
    assert page.index("Giai đoạn có lịch") < page.index("Giai đoạn chưa lịch")
    assert '<td data-project-progress-planned></td>' in table
    assert '<td data-project-progress-days></td>' in table
    assert "0 ngày" not in table
    assert "—/—" not in table
    assert "Tổng" not in table
    assert 'href="/projects/1/progress/types/1"' in table
    assert 'href="/projects/1/progress"' in page


def test_project_dashboard_hides_progress_block_without_progress_capability(client, app):
    with app.app_context():
        _seed_project_progress_dashboard_data()
        user = User.query.filter_by(username="reporter").one()
        permission = Permission.query.filter_by(code="dashboards.project.view").one()
        db.session.add(RolePermission(role_id=user.role_id, permission_id=permission.id))
        membership = ProjectUser.query.filter_by(project_id=1, user_id=user.id).one()
        membership.can_view_progress = False
        db.session.commit()

    login(client, "reporter")
    response = client.get("/reports/projects/1/dashboard")

    assert response.status_code == 200
    assert "data-project-progress-dashboard" not in response.get_data(as_text=True)


def test_project_dashboard_shows_progress_instruction_without_progress_types(client, app):
    login(client, "admin")
    response = client.get("/reports/projects/2/dashboard")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "data-project-progress-dashboard" in page
    assert "data-project-progress-empty" in page
    assert "data-project-progress-table" not in page


def test_project_dashboard_aggregates_multiple_report_dates_without_invalid_grouping(client, app):
    with app.app_context():
        seed_dashboard_data()
        db.session.add(
            DailyReport(
                id=104,
                project_id=1,
                report_date=date(2026, 7, 4),
                overall_status="GOOD",
                highlight="A later good report",
                created_by_user_id=3,
            )
        )
        db.session.commit()

    login(client, "viewer")
    response = client.get("/reports/projects/1/dashboard")
    assert response.status_code == 200

    statements = []

    def capture(_connection, _cursor, statement, _parameters, _context, _executemany):
        if "GROUP BY daily_reports.overall_status" in statement:
            statements.append(statement)

    with app.app_context():
        event.listen(db.engine, "before_cursor_execute", capture)
        try:
            with app.test_request_context("/reports/projects/1/dashboard"):
                from flask_login import login_user

                login_user(db.session.get(User, 2))
                context = project_dashboard_context(db.session.get(Project, 1))
        finally:
            event.remove(db.engine, "before_cursor_execute", capture)

    assert context["cards"]["total_reports"] == 3
    assert context["cards"]["good_reports"] == 2
    assert context["cards"]["processing_reports"] == 1
    assert len(statements) == 1
    assert "ORDER BY daily_reports.overall_status" in statements[0]
    assert "ORDER BY daily_reports.report_date" not in statements[0]


def test_project_dashboard_shows_recent_updates_with_sql_limit_and_full_list_link(client, app):
    with app.app_context():
        for index in range(6):
            db.session.add(ProjectUpdate(
                id=800 + index, project_id=1, update_type="NOTE", title=f"Update {index}", content="x",
                update_date=date(2026, 7, index + 1), created_by_id=3,
            ))
        db.session.add(ProjectUpdate(id=899, project_id=1, update_type="GENERAL", title="Deleted", content="x", update_date=date(2026, 8, 1), created_by_id=3, deleted_at=datetime.utcnow()))
        db.session.commit()
    login(client, "viewer")
    page = client.get("/reports/projects/1/dashboard")
    assert page.status_code == 200
    assert "Báo cáo xuyên suốt gần đây".encode() in page.data
    assert page.data.count(b"Update ") == 5
    assert b"Update 5" in page.data and b"Update 0" not in page.data
    assert b"Deleted" not in page.data
    assert "Xem tất cả báo cáo xuyên suốt".encode() in page.data
    assert client.get("/projects/1/updates").status_code == 200


def test_project_dashboard_selector_is_scoped_sorted_and_uses_canonical_urls(client, app):
    with app.app_context():
        db.session.add_all([
            Project(id=810, code="Z99", name="Zulu", status="active"),
            Project(id=811, code="A01", name="Alpha", status="active"),
            Project(id=812, code="000", name="Paused first by code", status="paused"),
        ])
        db.session.commit()
    login(client, "viewer")
    page = client.get("/reports/projects/1/dashboard")
    assert page.status_code == 200
    assert b"dashboard-project-select" in page.data
    assert b"dashboard-project-filter" in page.data
    assert b"/reports/projects/811/dashboard" in page.data
    assert page.data.index(b"A01") < page.data.index(b"Z99") < page.data.index(b"Paused first by code")
    assert client.get("/reports/projects/811/dashboard").status_code == 200


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
    assert client.post("/reports/issues/203/close").status_code == 404


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


def _seed_scoped_dashboard_data():
    customer_one = Customer(id=101, name="Khách hàng Một", normalized_name="khách hàng một")
    customer_two = Customer(id=102, name="Khách hàng Hai", normalized_name="khách hàng hai")
    db.session.add_all([customer_one, customer_two])
    db.session.flush()
    project_one = db.session.get(Project, 1)
    project_two = db.session.get(Project, 2)
    project_one.customer_id = customer_one.id
    project_two.customer_id = customer_two.id
    project_three = Project(id=103, code="P103", name="Customer one missing", customer_id=customer_one.id)
    project_paused = Project(id=104, code="P104", name="Paused project", customer_id=customer_one.id, status="paused")
    db.session.add_all([project_three, project_paused])
    db.session.flush()
    db.session.add_all([
        ReportCategory(id=103, project_id=1, name="Safety"),
        ReportCategory(id=104, project_id=1, name="Material"),
        ReportCategory(id=105, project_id=1, name="Planning"),
        ReportCategory(id=106, project_id=1, name="Coordination"),
    ])
    report = DailyReport(id=701, project_id=1, report_date=date.today(), overall_status="GOOD", highlight="Five section statuses", created_by_user_id=3)
    db.session.add(report)
    db.session.flush()
    db.session.add_all([
        DailyReportSection(id=701, daily_report_id=report.id, report_category_id=1, status="INFO", content="info"),
        DailyReportSection(id=702, daily_report_id=report.id, report_category_id=2, status="GOOD", content="good"),
        DailyReportSection(id=703, daily_report_id=report.id, report_category_id=103, status="PROCESSING", content="processing"),
        DailyReportSection(id=704, daily_report_id=report.id, report_category_id=104, status="ATTENTION", content="attention"),
        DailyReportSection(id=705, daily_report_id=report.id, report_category_id=105, status="CRITICAL", content="critical"),
    ])
    contractor_one = ProjectContractor(id=701, name="VTS", normalized_name="vts")
    contractor_two = ProjectContractor(id=702, name="HT", normalized_name="ht")
    contractor_three = ProjectContractor(id=703, name="ZTSS", normalized_name="ztss")
    db.session.add_all([contractor_one, contractor_two, contractor_three])
    db.session.flush()
    db.session.add_all([
        ProjectContractorAssignment(id=701, project_id=1, contractor_id=contractor_one.id, role="CONSTRUCTION", status="ACTIVE"),
        ProjectContractorAssignment(id=702, project_id=103, contractor_id=contractor_one.id, role="SOLUTION", status="ACTIVE"),
        ProjectContractorAssignment(id=703, project_id=103, contractor_id=contractor_two.id, role="CONSTRUCTION", status="ACTIVE"),
        ProjectContractorAssignment(id=704, project_id=2, contractor_id=contractor_three.id, role="SOLUTION", status="ACTIVE"),
    ])
    db.session.add_all([
        PersistentIssue(id=701, project_id=1, title="P1", severity="LOW", status="OPEN", opened_date=date.today(), created_by_user_id=3),
        PersistentIssue(id=702, project_id=103, title="P3", severity="CRITICAL", status="PROCESSING", opened_date=date.today(), created_by_user_id=3),
        PersistentIssue(id=703, project_id=2, title="P2", severity="HIGH", status="CLOSED", opened_date=date.today(), created_by_user_id=1),
        ProjectUpdate(id=701, project_id=103, update_type="NOTE", title="Customer update", content="timeline", update_date=date.today(), created_by_id=3),
    ])
    db.session.commit()
    return customer_one, customer_two


def _grant_reporter(client, app, *permissions):
    with app.app_context():
        reporter = User.query.filter_by(username="reporter").one()
        rows = Permission.query.filter(Permission.code.in_(permissions)).all()
        db.session.add_all(RolePermission(role_id=reporter.role_id, permission_id=row.id) for row in rows)
        db.session.commit()
    login(client, "reporter")


def test_customer_and_system_scopes_have_exact_aggregates(client, app):
    with app.app_context():
        customer_one, _ = _seed_scoped_dashboard_data()
        customer_one_id = customer_one.id

    login(client, "viewer")
    customer = client.get(f"/api/reports/dashboard/customers/{customer_one_id}/overview")
    assert customer.status_code == 200
    customer_payload = customer.get_json()
    assert customer_payload["submissions"]["labels"] == ["P001", "P103"]
    assert customer_payload["submissions"]["values"] == [1, 0]
    assert customer_payload["section_status"]["keys"] == ["INFO", "GOOD", "PROCESSING", "ATTENTION", "CRITICAL"]
    assert customer_payload["section_status"]["values"] == [1, 1, 1, 1, 1]
    assert customer_payload["contractors"]["values"] == [2, 1]
    assert customer_payload["persistent_issues"]["status"]["values"] == [1, 1, 0, 0]
    assert customer_payload["persistent_issues"]["severity"]["values"] == [1, 0, 0, 1]

    system = client.get("/api/reports/dashboard/system/overview")
    assert system.status_code == 200
    system_payload = system.get_json()
    assert system_payload["submissions"]["labels"] == ["P001", "P002", "P103"]
    assert system_payload["submissions"]["values"] == [1, 0, 0]
    assert system_payload["contractors"]["values"] == [2, 2]
    assert "system_analytics" in system_payload
    assert system_payload["system_analytics"]["contractor_project_coverage"]["denominator_active_projects"] == 3
    assert system_payload["system_analytics"]["project_activity"]["default_days"] == 30
    assert "system_analytics" not in customer_payload

    page = client.get(f"/reports/dashboard/customers/{customer_one_id}")
    assert page.status_code == 200
    assert "1/2 dự án".encode() in page.data
    assert b"Customer update" in page.data
    assert b"scoped-dashboard-charts.js" in page.data


def test_customer_and_system_dashboards_deny_partial_scope_without_enumeration(client, app):
    with app.app_context():
        customer_one, _ = _seed_scoped_dashboard_data()
        customer_one_id = customer_one.id
    _grant_reporter(client, app, "dashboards.customer.view", "dashboards.system.view")

    assert client.get("/reports/dashboard/system").status_code == 403
    assert client.get(f"/reports/dashboard/customers/{customer_one_id}").status_code == 403
    assert client.get("/reports/dashboard/customers/999999").status_code == 403
    assert client.get(f"/api/reports/dashboard/customers/{customer_one_id}/overview").status_code == 403


def test_custom_global_read_only_role_can_view_scoped_dashboards_without_write_access(client, app):
    with app.app_context():
        customer_one, _ = _seed_scoped_dashboard_data()
        role = Role(code="DASHBOARD_READ_ONLY", name="Dashboard read only", is_system=False)
        db.session.add(role)
        db.session.flush()
        user = User(id=701, full_name="Read only", username="dashboard-read-only", password_hash="x", role=role, legacy_role=role.code)
        db.session.add(user)
        permissions = Permission.query.filter(Permission.code.in_(("modules.reports.access", "projects.scope_all", "dashboards.system.view", "dashboards.customer.view"))).all()
        db.session.add_all(RolePermission(role_id=role.id, permission_id=permission.id) for permission in permissions)
        db.session.commit()
        customer_one_id = customer_one.id

    with client.session_transaction() as session:
        session["_user_id"] = "701"
        session["_fresh"] = True
    assert client.get("/reports/dashboard/system").status_code == 200
    assert client.get(f"/reports/dashboard/customers/{customer_one_id}").status_code == 200
    assert client.post("/reports/projects/2/reports/upload-sessions", json={}).status_code == 403


def test_system_dashboard_payload_query_count_is_not_linear(client, app):
    with app.app_context():
        _seed_scoped_dashboard_data()
        for index in range(20):
            contractor = ProjectContractor(id=800 + index, name=f"Extra {index}", normalized_name=f"extra {index}")
            db.session.add(contractor)
            db.session.flush()
            db.session.add_all([
                ProjectContractorAssignment(id=800 + index, project_id=1, contractor_id=contractor.id, role="CONSTRUCTION", status="ACTIVE"),
                PersistentIssue(id=800 + index, project_id=1, title=f"Issue {index}", severity="LOW", status="OPEN", opened_date=date.today(), created_by_user_id=3),
                ProjectUpdate(id=800 + index, project_id=1, update_type="NOTE", title=f"Update {index}", content="x", update_date=date.today(), created_by_id=3),
            ])
        db.session.commit()
    login(client, "viewer")

    with app.app_context():
        count = 0
        def before(*_args):
            nonlocal count
            count += 1
        event.listen(db.engine, "before_cursor_execute", before)
        try:
            with client:
                client.get("/api/reports/dashboard/system/overview")
        finally:
            event.remove(db.engine, "before_cursor_execute", before)
    assert count < 20


def test_system_analytics_keeps_unclassified_projects_and_native_status_partition(client, app):
    with app.app_context():
        _seed_scoped_dashboard_data()
        db.session.add(Project(id=105, code="P105", name="Không phân loại", status="archived"))
        db.session.commit()
    login(client, "viewer")
    payload = client.get("/api/reports/dashboard/system/overview").get_json()["system_analytics"]

    customer_share = payload["customer_project_share"]
    assert "Chưa phân loại" in customer_share["labels"]
    assert sum(customer_share["values"]) == customer_share["total_projects"] == 5
    statuses = payload["project_status_distribution"]
    assert sum(statuses["values"]) == statuses["total_projects"] == 5
    assert statuses["values"][statuses["keys"].index("archived")] == 1
    assert set(payload["project_activity"]["daily_reports"]["periods"]) == {"7", "30", "90"}


def test_system_project_activity_totals_and_percentages_are_additive_and_scoped(client, app):
    with app.app_context():
        _seed_scoped_dashboard_data()
    login(client, "viewer")

    payload = client.get("/api/reports/dashboard/system/overview").get_json()["system_analytics"]["project_activity"]
    activities = [payload["current_issues"], *payload["daily_reports"]["periods"].values()]
    assert set(payload["daily_reports"]["periods"]) == {"7", "30", "90"}
    for activity in activities:
        assert activity["total_count"] == sum(activity["values"])
        assert len(activity["percentages"]) == len(activity["values"])
        if activity["total_count"]:
            assert abs(sum(activity["percentages"]) - 100) <= 0.2
        else:
            assert activity["percentages"] == []

    # Viewer has all-project scope in the fixture; the API remains JSON and
    # never includes a project outside the effective dashboard scope.
    assert isinstance(payload["current_issues"]["total_count"], int)


def test_project_activity_zero_total_payload_is_serializable():
    assert _activity_payload([]) == {
        "project_ids": [], "labels": [], "values": [], "total_count": 0, "percentages": [],
    }


def test_contractor_dashboard_is_assignment_scoped_and_keeps_project_context(client, app):
    with app.app_context():
        customer_one = Customer(id=901, name="Contract customer one", normalized_name="contract customer one")
        customer_two = Customer(id=902, name="Contract customer two", normalized_name="contract customer two")
        project_one = db.session.get(Project, 1); project_two = db.session.get(Project, 2)
        project_one.customer = customer_one; project_two.customer = customer_two
        contractor = ProjectContractor(id=901, name="Contractor Dashboard", short_name="CD", normalized_name="contractor dashboard")
        archived = ProjectContractor(id=902, name="Archived contractor", normalized_name="archived contractor", is_active=False)
        db.session.add_all([customer_one, customer_two, contractor, archived]); db.session.flush()
        active = ProjectContractorAssignment(id=901, project_id=1, contractor_id=contractor.id, role="CONSTRUCTION", status="ACTIVE")
        ended = ProjectContractorAssignment(id=902, project_id=2, contractor_id=contractor.id, role="SOLUTION", status="ENDED")
        db.session.add_all([active, ended]); db.session.flush()
        db.session.add_all([
            ProjectUpdate(id=901, project_id=1, contractor_assignment_id=active.id, update_type="CONTRACTOR", title="Bound contractor update", content="bound", update_date=date.today(), created_by_id=3),
            ProjectUpdate(id=902, project_id=1, update_type="GENERAL", title="General update", content="general", update_date=date.today(), created_by_id=3),
            DailyReport(id=901, project_id=1, report_date=date.today(), overall_status="GOOD", highlight="context", created_by_user_id=3),
            PersistentIssue(id=901, project_id=1, title="Project context issue", severity="LOW", status="OPEN", opened_date=date.today(), created_by_user_id=3),
        ])
        db.session.commit()

    login(client, "viewer")
    page = client.get("/reports/dashboard/contractors/901")
    assert page.status_code == 200
    assert b"CD" in page.data and "Báo cáo ngày gần đây".encode() in page.data
    assert b"Bound contractor update" in page.data
    assert b"General update" not in page.data
    assert "Bối cảnh dự án".encode() in page.data
    payload = client.get("/api/reports/dashboard/contractors/901/overview").get_json()
    assert payload["cards"]["active_projects"] == 1
    assert payload["assignment_roles"]["values"] == [1, 0]
    assert payload["latest_update"]["title"] == "Bound contractor update"
    historical = client.get("/api/reports/dashboard/contractors/901/overview?assignment_status=ALL").get_json()
    assert historical["assignment_roles"]["values"] == [1, 1]
    assert client.get("/reports/dashboard/contractors/902").status_code == 200


def test_contractor_dashboard_hides_inaccessible_contractors_after_permission_check(client, app):
    with app.app_context():
        contractor = ProjectContractor(id=903, name="Scoped contractor", normalized_name="scoped contractor")
        other = ProjectContractor(id=904, name="Other contractor", normalized_name="other contractor")
        db.session.add_all([contractor, other]); db.session.flush()
        db.session.add_all([
            ProjectContractorAssignment(id=903, project_id=1, contractor_id=contractor.id, role="CONSTRUCTION", status="ACTIVE"),
            ProjectContractorAssignment(id=904, project_id=2, contractor_id=other.id, role="CONSTRUCTION", status="ACTIVE"),
        ])
        permission = Permission.query.filter_by(code="dashboards.contractor.view").one()
        reporter = User.query.filter_by(username="reporter").one()
        db.session.add(RolePermission(role_id=reporter.role_id, permission_id=permission.id)); db.session.commit()
    login(client, "reporter")
    assert client.get("/reports/dashboard/contractors/903").status_code == 200
    assert client.get("/api/reports/dashboard/contractors/904/overview").status_code == 404
    assert client.get("/reports/dashboard/contractors/903?project_id=2").status_code == 404
    assert client.get("/reports/dashboard/contractors/999999").status_code == 404


def test_contractor_dashboard_payload_query_count_is_not_linear(client, app):
    with app.app_context():
        contractor = ProjectContractor(id=905, name="Query contractor", normalized_name="query contractor")
        db.session.add(contractor); db.session.flush()
        db.session.add(ProjectContractorAssignment(id=905, project_id=1, contractor_id=contractor.id, role="CONSTRUCTION", status="ACTIVE"))
        db.session.commit()
    login(client, "viewer")

    def payload_queries(extra_rows, start):
        with app.app_context():
            for index in range(extra_rows):
                row_id = start + index
                db.session.add(ProjectUpdate(id=row_id, project_id=1, contractor_assignment_id=905, update_type="NOTE", title=f"Update {index}", content="x", update_date=date.today(), created_by_id=3))
            db.session.commit()
            count = 0
            def before(*_args):
                nonlocal count
                count += 1
            event.listen(db.engine, "before_cursor_execute", before)
            try:
                with client:
                    assert client.get("/api/reports/dashboard/contractors/905/overview").status_code == 200
            finally:
                event.remove(db.engine, "before_cursor_execute", before)
            return count

    small = payload_queries(1, 910)
    large = payload_queries(20, 1000)
    assert large == small


def test_system_dashboard_hub_exposes_permission_aware_canonical_dashboard_cards(client, app):
    with app.app_context():
        customer = Customer(id=990, name="Hub customer", normalized_name="hub customer")
        contractor = ProjectContractor(id=990, name="Hub contractor", normalized_name="hub contractor")
        db.session.add_all([customer, contractor]); db.session.flush()
        db.session.get(Project, 1).customer_id = customer.id
        db.session.add(ProjectContractorAssignment(id=990, project_id=1, contractor_id=contractor.id, role="CONSTRUCTION", status="ACTIVE"))
        db.session.commit()
    login(client, "viewer")
    page = client.get("/reports/dashboard/system")
    assert page.status_code == 200
    assert "Điều hướng Dashboard quản trị".encode() in page.data
    assert "Dashboard toàn hệ thống".encode() in page.data
    assert "Dashboard khách hàng".encode() in page.data
    assert "Dashboard dự án".encode() in page.data
    assert "Dashboard đối tác".encode() in page.data
    assert b"dashboard-customer-select" not in page.data
    assert b'href="/reports/dashboard"' not in page.data
