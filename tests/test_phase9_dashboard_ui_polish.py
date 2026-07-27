from pathlib import Path

from app.date_utils import local_today


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def login(client, username_or_email, password="password123"):
    return client.post("/login", data={"username_or_email": username_or_email, "password": password})


def _assert_in_order(markup, labels):
    positions = [markup.index(label) for label in labels]
    assert positions == sorted(positions)


def test_project_update_form_has_native_max_and_static_future_date_guard(client):
    login(client, "super")

    response = client.get("/projects/1/updates/new")

    assert response.status_code == 200
    assert f'type="date" name="update_date" max="{local_today().isoformat()}"'.encode() in response.data
    assert b"data-project-update-form" in response.data
    assert b"data-project-update-date" in response.data

    script = (PROJECT_ROOT / "app/static/js/app.js").read_text()
    assert "initProjectUpdateDateValidation" in script
    assert "field.value > field.max" in script
    assert "Ngày cập nhật không được lớn hơn ngày hôm nay." in script


def test_reports_navigation_is_dashboard_first_on_desktop_and_mobile(client):
    login(client, "super")
    response = client.get("/reports/dashboard/system")

    assert response.status_code == 200
    markup = response.data.decode()
    desktop = markup[markup.index("<aside"):markup.index('<div class="offcanvas')]
    mobile_start = markup.index('<div class="offcanvas')
    mobile = markup[mobile_start:markup.index('<div class="app-content">', mobile_start)]
    labels = [
        "<span>Dashboard quản trị</span>",
        "<span>Hôm nay</span>",
        "<span>Quản lý dự án &amp; đối tác</span>",
        "<span>Cấu hình</span>",
    ]

    _assert_in_order(desktop, labels)
    _assert_in_order(mobile, labels)


def test_system_dashboard_tab_order_and_coverage_chart_contract(client):
    login(client, "super")
    response = client.get("/reports/dashboard/system")

    assert response.status_code == 200
    markup = response.data.decode()
    tabs = markup[markup.index('id="scopedDashboardTabs"'):markup.index("</ul>", markup.index('id="scopedDashboardTabs"'))]
    _assert_in_order(tabs, ["Tổng quan", "Phân tích hệ thống", "Báo cáo", "Vấn đề tồn đọng", "Đối tác"])
    assert "system-analytics-grid" in markup
    assert "system-analytics-chart-wrap" in markup

    script = (PROJECT_ROOT / "app/static/js/scoped-dashboard-charts.js").read_text()
    assert "contractorCoverageBars(coverage.labels, coverage.values)" in script
    assert "coverage.percentages" not in script
    assert "CONTRACTOR_COVERAGE_COLORS" in script
    assert "legend: { display: false }" in script
    assert "Số dự án đang hoạt động" in script
    assert "maintainAspectRatio = false" in script
    assert "closest('.card-body')" in script
    assert "undefined" not in script

    styles = (PROJECT_ROOT / "app/static/css/app.css").read_text()
    assert ".system-analytics-card" in styles
    assert ".system-analytics-chart-wrap" in styles


def test_system_dashboard_activity_doughnut_markup_and_project_configuration_shell(client):
    login(client, "super")
    dashboard = client.get("/reports/dashboard/system")
    assert dashboard.status_code == 200
    markup = dashboard.data.decode()
    assert "Vấn đề tồn đọng theo dự án" in markup
    assert "Vấn đề hiện hành" not in markup
    assert markup.count('id="system-current-issues"') == 1
    assert markup.count('id="system-daily-report-activity"') == 1
    assert "data-activity-chart" in markup and "data-chart-empty" in markup

    configuration = client.get("/reports/config")
    assert configuration.status_code == 200
    assert "Vai trò &amp; phân quyền" not in configuration.data.decode()
    assert "Nhà thầu/Đối tác dự án" in configuration.data.decode()

    project_page = client.get("/admin/projects")
    assert project_page.status_code == 200
    project_markup = project_page.data.decode()
    assert "StarX · Quản lý dự án" in project_markup
    assert 'href="/reports/config"' in project_markup
    assert '<span>Cấu hình</span>' in project_markup

    roles_page = client.get("/admin/roles")
    assert roles_page.status_code == 200
    roles_markup = roles_page.data.decode()
    assert "StarX · Quản trị hệ thống" in roles_markup
    assert '<span>Quản lý dự án</span>' not in roles_markup


def test_project_domain_configuration_routes_keep_reports_shell_and_configuration_active(client):
    login(client, "super")
    for route in ("/admin/projects", "/admin/projects/1/categories", "/admin/projects/1/memberships", "/customers", "/project-operations/contractors"):
        response = client.get(route)
        assert response.status_code == 200, route
        markup = response.data.decode()
        assert "StarX · Quản lý dự án" in markup
        assert 'href="/reports/config"' in markup
        assert 'bi-gear"></i><span>Cấu hình</span>' in markup
