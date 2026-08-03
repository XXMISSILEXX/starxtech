from app.extensions import db
from datetime import date

from app.models import ProgressEntry, ProgressGroup, ProgressItem, ProgressType
from pathlib import Path


def _login(client, username):
    client.post("/login", data={"username_or_email": username, "password": "password123"})


def test_progress_templates_hide_structure_actions_and_escape_item_name(client, app):
    with app.app_context():
        progress_type = ProgressType(project_id=1, name="Tiến độ", created_by_id=1)
        db.session.add(progress_type); db.session.flush()
        group = ProgressGroup(project_id=1, progress_type_id=progress_type.id, name="Khu vực", created_by_id=1)
        db.session.add(group); db.session.flush()
        item = ProgressItem(project_id=1, progress_group_id=group.id, name="<script>alert(1)</script>", unit="m", planned_quantity=10, created_by_id=1)
        db.session.add(item); db.session.commit()
        type_id, item_id = progress_type.id, item.id

    _login(client, "reporter")
    page = client.get(f"/projects/1/progress/types/{type_id}")
    assert page.status_code == 200
    assert b'name="planned_quantity"' not in page.data
    detail = client.get(f"/projects/1/progress/items/{item_id}")
    assert b"&lt;script&gt;alert(1)&lt;/script&gt;" in detail.data

    client.post("/logout")
    _login(client, "pm")
    assert b'name="items-0-planned_quantity"' in client.get(f"/projects/1/progress/types/{type_id}").data


def test_progress_tree_and_workspace_card_render_expected_content(client, app):
    with app.app_context():
        progress_type = ProgressType(project_id=1, name="Tiến độ chính", created_by_id=1)
        db.session.add(progress_type); db.session.flush()
        group = ProgressGroup(project_id=1, progress_type_id=progress_type.id, name="Tòa C1", created_by_id=1)
        db.session.add(group); db.session.flush()
        item = ProgressItem(project_id=1, progress_group_id=group.id, name="Đi ống", unit="mét", planned_quantity=10, completed_quantity=5, created_by_id=1)
        unplanned = ProgressItem(project_id=1, progress_group_id=group.id, name="Chưa kế hoạch", unit="cái", planned_quantity=0, created_by_id=1)
        db.session.add_all((item, unplanned)); db.session.commit()
        type_id, unplanned_id = progress_type.id, unplanned.id

    _login(client, "admin")
    tree = client.get(f"/projects/1/progress/types/{type_id}")
    tree_text = tree.get_data(as_text=True)
    assert "Tòa C1" in tree_text
    assert "Đi ống" in tree_text
    assert "mét" in tree_text
    assert "50,0%" in tree_text
    assert "<strong>50,0%</strong>" in tree_text
    assert "<strong>50.0%</strong>" not in tree_text
    assert "Quản lý tiến độ thi công" in client.get("/projects/1/workspace").get_data(as_text=True)
    assert "—" in client.get(f"/projects/1/progress/items/{unplanned_id}").get_data(as_text=True)

    client.post("/logout")
    _login(client, "reporter")
    assert "Quản lý tiến độ thi công" not in client.get("/projects/1/workspace").get_data(as_text=True)


def test_type_detail_polish_marks_unplanned_and_over_plan_items(client, app):
    with app.app_context():
        progress_type = ProgressType(project_id=1, name="Tiến độ hiển thị", created_by_id=1)
        db.session.add(progress_type); db.session.flush()
        group = ProgressGroup(project_id=1, progress_type_id=progress_type.id, name="Khu gập mở", created_by_id=1)
        db.session.add(group); db.session.flush()
        db.session.add_all((
            ProgressItem(project_id=1, progress_group_id=group.id, name="Chưa khai kế hoạch", unit="m", planned_quantity=0, created_by_id=1),
            ProgressItem(project_id=1, progress_group_id=group.id, name="Vượt kế hoạch", unit="m", planned_quantity=10, completed_quantity=15, created_by_id=1),
        ))
        db.session.commit()
        type_id = progress_type.id

    _login(client, "admin")
    page = client.get(f"/projects/1/progress/types/{type_id}").get_data(as_text=True)
    assert 'data-bs-toggle="collapse"' in page
    assert "chưa có kế hoạch" in page
    assert "vượt kế hoạch +50,0%" in page
    assert "width: 100%" in page
    assert "<th class=\"text-end\">Kế hoạch</th>" in page


def test_progress_templates_use_placeholders_and_no_longer_call_opening_quantity_mang_sang():
    template_dir = Path("app/templates/construction_progress")
    templates = list(template_dir.rglob("*.html"))
    assert templates
    content = "\n".join(template.read_text(encoding="utf-8") for template in templates)
    assert "Mang sang" not in content
    assert "Đã làm trước đó" in content
    assert 'align-items-end' not in content
    assert 'placeholder="Ví dụ: {{ number_example(decimal_places) }}"' in content
    assert 'placeholder="Ví dụ: 1.280,34"' in content
    assert '<div class="form-text">Ví dụ:' not in content


def test_progress_item_overlay_uses_two_subrows_for_nine_fields():
    template = Path("app/templates/construction_progress/type_detail.html").read_text(encoding="utf-8")
    assert 'data-item-quantity-row' in template
    assert 'data-item-timeline-row' in template
    assert 'name="items-{{ index }}-planned_start_date"' in template
    assert 'name="items-{{ index }}-planned_end_date"' in template
    assert 'name="items-{{ index }}-actual_start_date"' in template
    assert template.count('data-delete-item') == 1
    assert template.count('data-remove-item-row') == 1


def test_gantt_tab_renders_server_side_bars_and_required_disclosures(client, app):
    with app.app_context():
        progress_type = ProgressType(project_id=1, name="Tiến độ Gantt", created_by_id=1)
        db.session.add(progress_type)
        db.session.flush()
        shown_group = ProgressGroup(project_id=1, progress_type_id=progress_type.id, name="Khu vực hiển thị", created_by_id=1)
        empty_group = ProgressGroup(project_id=1, progress_type_id=progress_type.id, name="Khu vực không có ngày", created_by_id=1)
        db.session.add_all((shown_group, empty_group))
        db.session.flush()
        overdue = ProgressItem(project_id=1, progress_group_id=shown_group.id, name="Hạng mục quá hạn", unit="m", planned_quantity=10, completed_quantity=5, planned_start_date=date(2020, 1, 1), planned_end_date=date(2020, 1, 10), created_by_id=1)
        complete = ProgressItem(project_id=1, progress_group_id=shown_group.id, name="Hạng mục hoàn thành", unit="m", planned_quantity=10, completed_quantity=10, planned_start_date=date(2020, 1, 1), planned_end_date=date(2020, 1, 10), created_by_id=1)
        opening_without_actual = ProgressItem(project_id=1, progress_group_id=shown_group.id, name="Hạng mục thiếu mốc thực tế", unit="m", planned_quantity=10, opening_quantity=2, completed_quantity=2, planned_start_date=date(2030, 1, 1), planned_end_date=date(2030, 1, 10), created_by_id=1)
        manual_point = ProgressItem(project_id=1, progress_group_id=shown_group.id, name="Hạng mục điểm thực tế", unit="m", planned_quantity=10, opening_quantity=2, planned_start_date=date(2030, 1, 1), planned_end_date=date(2030, 1, 10), actual_start_date=date(2020, 1, 2), created_by_id=1)
        excluded = ProgressItem(project_id=1, progress_group_id=shown_group.id, name="Hạng mục chưa khai ngày", unit="m", planned_quantity=10, created_by_id=1)
        empty_group_item = ProgressItem(project_id=1, progress_group_id=empty_group.id, name="Hạng mục chưa khai ngày", unit="m", planned_quantity=10, created_by_id=1)
        db.session.add_all((overdue, complete, opening_without_actual, manual_point, excluded, empty_group_item))
        db.session.flush()
        db.session.add_all((
            ProgressEntry(project_id=1, progress_item_id=overdue.id, report_date=date(2020, 1, 2), quantity=1, created_by_id=1),
            ProgressEntry(project_id=1, progress_item_id=overdue.id, report_date=date(2020, 1, 4), quantity=1, created_by_id=1),
        ))
        db.session.commit()
        type_id, no_actual_id, manual_point_id, empty_group_id = progress_type.id, opening_without_actual.id, manual_point.id, empty_group.id

    _login(client, "admin")
    response = client.get(f"/projects/1/progress/types/{type_id}?tab=gantt")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'href="/projects/1/progress/types/' in page
    assert "Biểu đồ Gantt" in page
    assert '<nav class="nav nav-tabs mb-3"><a class="nav-link "' in page
    assert f'<a class="nav-link active" href="/projects/1/progress/types/{type_id}?tab=gantt">Biểu đồ Gantt</a>' in page
    assert "data-gantt-chart" in page
    assert 'data-gantt-today-line role="img" aria-label="Vạch hôm nay" title="Hôm nay"' in page
    assert "gantt-today-label" not in page
    assert "data-gantt-excluded-items" in page
    assert "Khu vực hiển thị — Hạng mục chưa khai ngày" in page
    assert "Khu vực không có ngày — Hạng mục chưa khai ngày" in page
    assert "Khu vực hiển thị" in page
    assert f'data-gantt-group-id="{empty_group_id}"' not in page
    assert page.count("data-gantt-overdue") == 1
    assert "quá hạn" in page
    assert "data-gantt-opening-reminder" in page
    no_actual_html = page.split(f'data-gantt-item-id="{no_actual_id}"', 1)[1].split('data-gantt-item-id=', 1)[0]
    manual_point_html = page.split(f'data-gantt-item-id="{manual_point_id}"', 1)[1].split('data-gantt-item-id=', 1)[0]
    assert "data-gantt-actual-bar" not in no_actual_html
    assert "data-gantt-opening-reminder" in no_actual_html
    assert "data-gantt-actual-point" in manual_point_html
    assert "data-gantt-opening-reminder" not in manual_point_html
    gantt_html = page.split("data-gantt-chart", 1)[1].split('id="createGroup"', 1)[0]
    assert "<canvas" not in gantt_html


def test_gantt_tab_empty_state_and_invalid_tab_follow_the_tab_contract(client, app):
    with app.app_context():
        progress_type = ProgressType(project_id=1, name="Tiến độ trống", created_by_id=1)
        db.session.add(progress_type)
        db.session.flush()
        group = ProgressGroup(project_id=1, progress_type_id=progress_type.id, name="Khu vực trống", created_by_id=1)
        db.session.add(group)
        db.session.flush()
        db.session.add(ProgressItem(project_id=1, progress_group_id=group.id, name="Chưa có ngày", unit="m", planned_quantity=10, created_by_id=1))
        db.session.commit()
        type_id = progress_type.id

    _login(client, "admin")
    empty = client.get(f"/projects/1/progress/types/{type_id}?tab=gantt")

    assert empty.status_code == 200
    assert "data-gantt-empty" in empty.get_data(as_text=True)
    assert client.get(f"/projects/1/progress/types/{type_id}?tab=khong-hop-le").status_code == 400
