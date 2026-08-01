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
