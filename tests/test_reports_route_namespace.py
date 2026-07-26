from flask import url_for
def _login(client, username="reporter"):
    return client.post("/login", data={"username_or_email": username, "password": "password123"})


def test_reports_endpoint_names_generate_the_new_namespace(app):
    with app.test_request_context():
        assert url_for("dashboard.system_dashboard") == "/reports/dashboard/system"
        assert url_for("dashboard_api.system_dashboard_payload") == "/api/reports/dashboard/system/overview"
        assert url_for("dashboard.contractor_dashboard", contractor_id=1) == "/reports/dashboard/contractors/1"
        assert url_for("dashboard_api.contractor_dashboard_payload_api", contractor_id=1) == "/api/reports/dashboard/contractors/1/overview"
        assert url_for("projects.index") == "/reports/projects"
        assert url_for("projects.dashboard", project_id=1) == "/reports/projects/1/dashboard"
        assert url_for("projects.reports", project_id=1) == "/reports/projects/1/reports"
        assert url_for("projects.reports_create", project_id=1) == "/reports/projects/1/reports/create"
        assert url_for("projects.issues", project_id=1) == "/reports/projects/1/issues"
        assert url_for("issues.index") == "/reports/issues"


def test_reports_static_routes_win_over_report_detail_and_legacy_routes_are_404(app, client):
    adapter = app.url_map.bind("localhost")
    for legacy in ("/reports/dashboard", "/api/reports/dashboard/status-chart", "/api/reports/dashboard/report-count-chart"):
        assert client.get(legacy).status_code == 404
    assert adapter.match("/reports/dashboard/system")[0] == "dashboard.system_dashboard"
    assert adapter.match("/reports/projects")[0] == "projects.index"
    assert adapter.match("/reports/issues")[0] == "issues.index"
    assert adapter.match("/reports/123")[0] == "reports.detail"
    for legacy in (
        "/dashboard", "/dashboard/", "/projects", "/projects/1/dashboard",
        "/projects/1/reports", "/projects/1/reports/create", "/projects/1/issues",
        "/issues", "/issues/new", "/api/dashboard/status-chart",
        "/api/dashboard/report-count-chart",
    ):
        assert client.get(legacy).status_code == 404
    assert client.get("/admin/projects").status_code != 404
    assert client.get("/project-documents/projects/1").status_code != 404


def test_reports_module_selector_and_new_routes_work(client):
    _login(client)
    selected = client.get("/modules/select/reports")
    assert selected.status_code == 302
    assert selected.headers["Location"].endswith("/reports/projects")
    assert client.get("/reports/projects").status_code == 200
