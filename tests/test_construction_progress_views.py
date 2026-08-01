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
    assert b'name="planned_quantity"' in client.get(f"/projects/1/progress/types/{type_id}").data


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
    assert b"T\xc3\xb2a C1" in tree.data
    assert b"\xc4\x90i \xe1\xbb\x91ng" in tree.data
    assert b"m\xc3\xa9t" in tree.data
    assert b"50.0%" in tree.data
    assert b"Qu\xe1\xba\xa3n l\xc3\xbd ti\xe1\xba\xbfn \xc4\x91\xe1\xbb\x99 thi c\xc3\xb4ng" in client.get("/projects/1/workspace").data
    assert b"\xe2\x80\x94" in client.get(f"/projects/1/progress/items/{unplanned_id}").data

    client.post("/logout")
    _login(client, "reporter")
    assert b"Qu\xe1\xba\xa3n l\xc3\xbd ti\xe1\xba\xbfn \xc4\x91\xe1\bb\x99 thi c\xc3\xb4ng" not in client.get("/projects/1/workspace").data
