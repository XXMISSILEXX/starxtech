from datetime import date, timedelta

import pytest
from sqlalchemy import event
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import Permission, ProgressEntry, ProgressGroup, ProgressItem, ProgressType, ProjectUser, Role, RolePermission, User
from app.permissions.registry import DEFAULTS, PERMISSIONS


PROGRESS_DASHBOARD_URL = "/reports/dashboard/progress"


def _login(client, username):
    return client.post("/login", data={"username_or_email": username, "password": "password123"})


def _dashboard_user(app, user_id, username, permissions=(), memberships=()):
    with app.app_context():
        role = Role(code=f"ROLE_{username.upper()}", name=username, is_system=False)
        user = User(
            id=user_id,
            username=username,
            email=f"{username}@example.com",
            full_name=username,
            password_hash=generate_password_hash("password123"),
            role=role,
            legacy_role=role.code,
        )
        db.session.add_all((role, user))
        db.session.flush()
        rows = Permission.query.filter(Permission.code.in_(permissions)).all()
        db.session.add_all(RolePermission(role_id=role.id, permission_id=row.id) for row in rows)
        for index, (project_id, flags) in enumerate(memberships, start=1):
            db.session.add(ProjectUser(id=user_id * 10 + index, project_id=project_id, user_id=user.id, is_active=True, **flags))
        db.session.commit()
    return username


def _add_progress_type(project_id, name, *, planned_start, planned_end, completed=5, planned=10, entry_date=None):
    progress_type = ProgressType(project_id=project_id, name=name, created_by_id=1)
    db.session.add(progress_type)
    db.session.flush()
    group = ProgressGroup(project_id=project_id, progress_type_id=progress_type.id, name=f"Khu {name}", created_by_id=1)
    db.session.add(group)
    db.session.flush()
    item = ProgressItem(
        project_id=project_id,
        progress_group_id=group.id,
        name=f"Hạng mục {name}",
        unit="m",
        planned_quantity=planned,
        completed_quantity=completed,
        planned_start_date=planned_start,
        planned_end_date=planned_end,
        created_by_id=1,
    )
    db.session.add(item)
    db.session.flush()
    if entry_date:
        db.session.add(ProgressEntry(project_id=project_id, progress_item_id=item.id, report_date=entry_date, quantity=1, created_by_id=1))
    return progress_type


def _add_progress_group(progress_type, name, items):
    group = ProgressGroup(project_id=progress_type.project_id, progress_type_id=progress_type.id, name=name, created_by_id=1)
    db.session.add(group)
    db.session.flush()
    for item_name, completed, planned in items:
        db.session.add(ProgressItem(
            project_id=progress_type.project_id,
            progress_group_id=group.id,
            name=item_name,
            unit="m",
            planned_quantity=planned,
            completed_quantity=completed,
            created_by_id=1,
        ))
    return group


def test_progress_dashboard_permission_defaults_are_read_only():
    permission_codes = {permission["code"] for permission in PERMISSIONS}

    assert "dashboards.progress.view" in permission_codes
    assert "dashboards.progress.view" in DEFAULTS["ADMIN"]
    assert "dashboards.progress.view" in DEFAULTS["VIEWER_ADMIN"]
    assert not {"construction_progress.create", "construction_progress.edit", "construction_progress.edit_all", "construction_progress.delete", "construction_progress.structure"} & DEFAULTS["VIEWER_ADMIN"]


@pytest.mark.parametrize("username, permissions, memberships, expected", [
    (None, (), (), 302),
    ("progress-no-module", (), (), 403),
    ("progress-no-permission", ("modules.reports.access",), (), 403),
    ("progress-empty", ("modules.reports.access", "dashboards.progress.view"), (), 200),
    ("progress-scoped", ("modules.reports.access", "dashboards.progress.view"), ((1, {"can_view_project": True, "can_view_progress": True}),), 200),
    ("viewer", (), (), 200),
    ("admin", (), (), 200),
    ("super", (), (), 200),
])
def test_progress_dashboard_route_matrix(client, app, username, permissions, memberships, expected):
    if username and username not in {"viewer", "admin", "super"}:
        _dashboard_user(app, 800 + len(username), username, permissions, memberships)
    if username:
        _login(client, username)

    assert client.get(PROGRESS_DASHBOARD_URL).status_code == expected


def test_progress_dashboard_scopes_rows_to_progress_capability_without_global_scope(client, app):
    with app.app_context():
        _add_progress_type(1, "Giai đoạn được xem", planned_start=date.today(), planned_end=date.today() + timedelta(days=2))
        _add_progress_type(2, "Giai đoạn bị ẩn", planned_start=date.today(), planned_end=date.today() + timedelta(days=2))
        db.session.commit()
    username = _dashboard_user(
        app,
        850,
        "progress-partial",
        ("modules.reports.access", "dashboards.progress.view"),
        (
            (1, {"can_view_project": True, "can_view_progress": True}),
            (2, {"can_view_project": True, "can_view_progress": False}),
        ),
    )

    _login(client, username)
    page = client.get(PROGRESS_DASHBOARD_URL).get_data(as_text=True)

    assert "Giai đoạn được xem" in page
    assert "Assigned Project" in page
    assert "Giai đoạn bị ẩn" not in page
    assert "Other Project" not in page


def test_progress_dashboard_navigation_card_respects_permission(client, app):
    without_permission = _dashboard_user(
        app,
        860,
        "progress-nav-hidden",
        ("modules.reports.access", "projects.scope_all", "dashboards.system.view"),
    )
    _login(client, without_permission)
    hidden_page = client.get("/reports/dashboard/system").get_data(as_text=True)
    client.post("/logout")
    with_permission = _dashboard_user(
        app,
        861,
        "progress-nav-visible",
        ("modules.reports.access", "projects.scope_all", "dashboards.system.view", "dashboards.progress.view"),
    )
    _login(client, with_permission)
    visible_page = client.get("/reports/dashboard/system").get_data(as_text=True)

    assert "Dashboard tiến độ thi công" not in hidden_page
    assert "Dashboard tiến độ thi công" in visible_page
    assert 'href="/reports/dashboard/progress"' in visible_page


def test_progress_dashboard_orders_statuses_and_uses_sql_pagination(client, app):
    today = date.today()
    with app.app_context():
        _add_progress_type(1, "Hoàn thành", planned_start=today - timedelta(days=5), planned_end=today - timedelta(days=2), completed=10)
        _add_progress_type(1, "Chưa bắt đầu", planned_start=today + timedelta(days=2), planned_end=today + timedelta(days=4))
        _add_progress_type(1, "Đang triển khai", planned_start=today - timedelta(days=1), planned_end=today + timedelta(days=3))
        _add_progress_type(1, "Quá hạn", planned_start=today - timedelta(days=5), planned_end=today - timedelta(days=1))
        for index in range(51):
            _add_progress_type(1, f"Phân trang {index:02d}", planned_start=today + timedelta(days=5), planned_end=today + timedelta(days=6))
        db.session.commit()

    _login(client, "admin")
    first_page = client.get(PROGRESS_DASHBOARD_URL).get_data(as_text=True)
    second_page = client.get(f"{PROGRESS_DASHBOARD_URL}?page=2").get_data(as_text=True)

    table = first_page[first_page.index("data-progress-dashboard-table"):first_page.index("</table>", first_page.index("data-progress-dashboard-table"))]
    assert table.index('data-progress-dashboard-status="overdue"') < table.index('data-progress-dashboard-status="in_progress"') < table.index('data-progress-dashboard-status="not_started"')
    assert 'data-progress-dashboard-status="done"' not in table
    assert 'data-progress-dashboard-status="done"' in second_page
    second_table = second_page[second_page.index("data-progress-dashboard-table"):second_page.index("</table>", second_page.index("data-progress-dashboard-table"))]
    assert "Phân trang 50" not in table
    assert "Phân trang 50" in second_table
    assert 'href="/reports/dashboard/progress?page=2&amp;type_id=' in first_page


def test_progress_dashboard_cards_include_projects_without_recent_entries(client, app):
    today = date.today()
    with app.app_context():
        _add_progress_type(1, "Không có phiếu", planned_start=today, planned_end=today + timedelta(days=1))
        _add_progress_type(2, "Phiếu cũ", planned_start=today, planned_end=today + timedelta(days=1), entry_date=today - timedelta(days=8))
        db.session.commit()

    _login(client, "admin")
    page = client.get(PROGRESS_DASHBOARD_URL).get_data(as_text=True)
    stats = page[page.index("data-progress-dashboard-stats"):page.index("data-progress-dashboard-table")]

    assert 'data-progress-dashboard-projects><div><div class="stat-label">Dự án có tiến độ</div><div class="stat-value">2</div>' in stats
    assert 'data-progress-dashboard-stale-projects><div><div class="stat-label">Không cập nhật quá 7 ngày</div><div class="stat-value">2</div>' in stats
    assert "%" not in stats
    assert "Tổng" not in stats


def test_progress_dashboard_query_count_is_not_linear(client, app):
    today = date.today()
    with app.app_context():
        _add_progress_type(1, "Mốc truy vấn", planned_start=today, planned_end=today + timedelta(days=1))
        db.session.commit()

    _login(client, "admin")

    def request_count():
        count = 0

        def before(*_args):
            nonlocal count
            count += 1

        with app.app_context():
            event.listen(db.engine, "before_cursor_execute", before)
            try:
                client.get(PROGRESS_DASHBOARD_URL)
            finally:
                event.remove(db.engine, "before_cursor_execute", before)
        return count

    small = request_count()
    with app.app_context():
        for index in range(20):
            _add_progress_type(1, f"Mốc truy vấn {index}", planned_start=today, planned_end=today + timedelta(days=1))
        db.session.commit()
    large = request_count()

    assert large == small


def test_progress_dashboard_chart_selector_scopes_pairs_and_defaults_to_first_problem(client, app):
    today = date.today()
    with app.app_context():
        default_type = _add_progress_type(1, "Giai đoạn quá hạn được chọn", planned_start=today - timedelta(days=3), planned_end=today - timedelta(days=1))
        _add_progress_type(2, "Giai đoạn ngoài phạm vi", planned_start=today - timedelta(days=3), planned_end=today - timedelta(days=1))
        db.session.commit()
        default_id = default_type.id
    username = _dashboard_user(
        app,
        870,
        "progress-chart-scoped",
        ("modules.reports.access", "dashboards.progress.view"),
        (
            (1, {"can_view_project": True, "can_view_progress": True}),
            (2, {"can_view_project": True, "can_view_progress": False}),
        ),
    )

    _login(client, username)
    page = client.get(PROGRESS_DASHBOARD_URL).get_data(as_text=True)
    selector = page[page.index("data-progress-dashboard-type-select"):page.index("</select>", page.index("data-progress-dashboard-type-select"))]

    assert "P001 · Assigned Project — Giai đoạn quá hạn được chọn" in selector
    assert "P002" not in selector
    assert "Giai đoạn ngoài phạm vi" not in page
    assert f'value="{default_id}" selected' in selector
    assert f'data-chart-url="/projects/1/progress/types/{default_id}/chart-data"' in page
    assert '<form method="get" data-progress-dashboard-filter-form>' in page
    assert 'onchange="this.form.submit()"' not in page
    assert 'name="item_name"' in page
    assert 'type="submit">Lọc</button>' in page
    assert 'style="height: 320px; position: relative;"' in page
    assert 'role="img" aria-label="Biểu đồ phần trăm hoàn thành theo khu vực' in page
    assert page.index("progress-dashboard-filter.js") < page.index("progress-dashboard-chart.js")
    assert page.index("data-progress-dashboard-chart-canvas") < page.index("progress-dashboard-chart.js")


def test_progress_dashboard_chart_out_of_scope_type_falls_back_without_disclosure(client, app):
    today = date.today()
    with app.app_context():
        visible_type = _add_progress_type(1, "Giai đoạn mặc định", planned_start=today, planned_end=today + timedelta(days=2))
        hidden_type = _add_progress_type(2, "Giai đoạn bí mật", planned_start=today, planned_end=today + timedelta(days=2))
        db.session.commit()
        visible_id, hidden_id = visible_type.id, hidden_type.id
    username = _dashboard_user(
        app,
        871,
        "progress-chart-outside",
        ("modules.reports.access", "dashboards.progress.view"),
        (
            (1, {"can_view_project": True, "can_view_progress": True}),
            (2, {"can_view_project": True, "can_view_progress": False}),
        ),
    )

    _login(client, username)
    response = client.get(f"{PROGRESS_DASHBOARD_URL}?type_id={hidden_id}")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert f'value="{visible_id}" selected' in page
    assert "Giai đoạn bí mật" not in page
    assert "Other Project" not in page


def test_progress_dashboard_chart_empty_states(client, app):
    empty_user = _dashboard_user(
        app,
        872,
        "progress-chart-empty",
        ("modules.reports.access", "dashboards.progress.view"),
    )
    _login(client, empty_user)
    empty_page = client.get(PROGRESS_DASHBOARD_URL).get_data(as_text=True)
    client.post("/logout")
    with app.app_context():
        no_group_type = ProgressType(project_id=1, name="Giai đoạn chưa có khu vực", created_by_id=1)
        db.session.add(no_group_type)
        db.session.commit()
        no_group_id = no_group_type.id
    _login(client, "admin")
    no_group_page = client.get(f"{PROGRESS_DASHBOARD_URL}?type_id={no_group_id}").get_data(as_text=True)

    assert "data-progress-dashboard-no-types" in empty_page
    assert "data-progress-dashboard-type-select" not in empty_page
    assert "data-progress-dashboard-chart-canvas" not in empty_page
    assert "data-progress-dashboard-table" not in empty_page
    assert "data-progress-dashboard-type-select" in no_group_page
    assert "Giai đoạn này chưa có khu vực nào." in no_group_page
    assert "data-progress-dashboard-chart-canvas" not in no_group_page


def test_progress_dashboard_item_selector_is_limited_to_selected_type_and_scope(client, app):
    today = date.today()
    with app.app_context():
        selected_type = _add_progress_type(1, "Giai đoạn được chọn", planned_start=today, planned_end=today + timedelta(days=1))
        _add_progress_group(selected_type, "C1", [("Điện", 25, 100), ("Nước", 50, 100), ("Ăn", 1, 1), ("Bê", 1, 1)])
        other_type = _add_progress_type(1, "Giai đoạn khác", planned_start=today, planned_end=today + timedelta(days=1))
        _add_progress_group(other_type, "C2", [("Chỉ thuộc giai đoạn khác", 1, 1)])
        hidden_type = _add_progress_type(2, "Giai đoạn dự án khác", planned_start=today, planned_end=today + timedelta(days=1))
        _add_progress_group(hidden_type, "C3", [("Bí mật dự án khác", 1, 1)])
        db.session.commit()
        selected_type_id = selected_type.id

    username = _dashboard_user(
        app,
        880,
        "progress-item-selector",
        ("modules.reports.access", "dashboards.progress.view"),
        ((1, {"can_view_project": True, "can_view_progress": True}),),
    )
    _login(client, username)
    page = client.get(PROGRESS_DASHBOARD_URL, query_string={"type_id": selected_type_id}).get_data(as_text=True)
    item_selector = page[page.index('id="progress-dashboard-item"'):page.index("</select>", page.index('id="progress-dashboard-item"'))]

    assert item_selector.index("Ăn") < item_selector.index("Bê") < item_selector.index("Điện") < item_selector.index("Nước")
    assert "Chỉ thuộc giai đoạn khác" not in item_selector
    assert "Bí mật dự án khác" not in page


def test_progress_chart_item_filter_returns_each_group_value_and_null_for_missing_item(client, app):
    today = date.today()
    with app.app_context():
        progress_type = _add_progress_type(1, "Lọc hạng mục", planned_start=today, planned_end=today + timedelta(days=1))
        _add_progress_group(progress_type, "C1", [("Điện", 25, 100)])
        _add_progress_group(progress_type, "C2", [("Điện", 100, 200)])
        _add_progress_group(progress_type, "C3", [("Nước", 90, 100)])
        _add_progress_group(progress_type, "C4", [("Dây điện", 90, 100)])
        db.session.commit()
        type_id = progress_type.id

    _login(client, "admin")
    response = client.get(f"/projects/1/progress/types/{type_id}/chart-data", query_string={"item_name": "Điện"})

    assert response.status_code == 200
    assert response.get_json() == {
        "item_name": "Điện",
        "labels": ["Khu Lọc hạng mục", "C1", "C2", "C3", "C4"],
        "overall_percent": 37.5,
        "percentages": [None, 25.0, 50.0, None, None],
    }


def test_progress_chart_item_filter_keeps_budget_weighted_total_for_money_types(client, app):
    today = date.today()
    with app.app_context():
        progress_type = _add_progress_type(1, "Chi phí", planned_start=today, planned_end=today + timedelta(days=1))
        progress_type.value_mode = "money"
        _add_progress_group(progress_type, "C1", [("Điện", 50, 100)])
        _add_progress_group(progress_type, "C2", [("Điện", 90, 300)])
        db.session.commit()
        type_id = progress_type.id

    _login(client, "admin")
    payload = client.get(f"/projects/1/progress/types/{type_id}/chart-data", query_string={"item_name": "Điện"}).get_json()

    assert payload["percentages"] == [None, 50.0, 30.0]
    assert payload["overall_percent"] == 35.0
    assert "completed" not in payload
    assert "remaining" not in payload


@pytest.mark.parametrize("item_name", ["", "Không tồn tại", "Chỉ thuộc giai đoạn khác"])
def test_progress_chart_invalid_or_other_type_item_name_safely_falls_back_to_unfiltered(client, app, item_name):
    today = date.today()
    with app.app_context():
        progress_type = _add_progress_type(1, "Giai đoạn hiện tại", planned_start=today, planned_end=today + timedelta(days=1), completed=2, planned=10)
        other_type = _add_progress_type(1, "Giai đoạn khác", planned_start=today, planned_end=today + timedelta(days=1))
        _add_progress_group(other_type, "C2", [("Chỉ thuộc giai đoạn khác", 1, 1)])
        db.session.commit()
        type_id = progress_type.id

    _login(client, "admin")
    response = client.get(f"/projects/1/progress/types/{type_id}/chart-data", query_string={"item_name": item_name})

    assert response.status_code == 200
    payload = response.get_json()
    assert "item_name" not in payload
    assert payload["labels"] == ["Khu Giai đoạn hiện tại"]
    assert payload["percentages"] == [20.0]
