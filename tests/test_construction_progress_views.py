from app.extensions import db
from app.models import ProgressGroup, ProgressItem, ProgressType


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
