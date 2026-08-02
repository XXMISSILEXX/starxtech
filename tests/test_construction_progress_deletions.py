from datetime import date

from app.construction_progress.services import progress_tree
from app.extensions import db
from app.models import AuditLog, ProgressEntry, ProgressGroup, ProgressItem, ProgressType, Project


def _login(client, username):
    client.post("/login", data={"username_or_email": username, "password": "password123"})


def _counts():
    return (
        ProgressType.query.count(),
        ProgressGroup.query.count(),
        ProgressItem.query.count(),
        ProgressEntry.query.count(),
    )


def _tree(*, inactive=False):
    progress_type = ProgressType(project_id=1, name="Loại cần xoá", is_active=not inactive, created_by_id=1)
    db.session.add(progress_type)
    db.session.flush()
    first_group = ProgressGroup(project_id=1, progress_type_id=progress_type.id, name="Tầng hầm", is_active=not inactive, created_by_id=1)
    second_group = ProgressGroup(project_id=1, progress_type_id=progress_type.id, name="Tầng mái", created_by_id=1)
    db.session.add_all((first_group, second_group))
    db.session.flush()
    first_item = ProgressItem(project_id=1, progress_group_id=first_group.id, name="Đi ống", unit="mét", is_active=not inactive, planned_quantity=100, created_by_id=1)
    second_item = ProgressItem(project_id=1, progress_group_id=first_group.id, name="Kéo dây", unit="mét", planned_quantity=100, created_by_id=1)
    third_item = ProgressItem(project_id=1, progress_group_id=second_group.id, name="Lắp tủ", unit="cái", planned_quantity=10, created_by_id=1)
    db.session.add_all((first_item, second_item, third_item))
    db.session.flush()
    entries = [
        ProgressEntry(project_id=1, progress_item_id=first_item.id, report_date=date(2026, 1, 1), quantity=10, note="Ghi chú phiếu 1", created_by_id=3),
        ProgressEntry(project_id=1, progress_item_id=first_item.id, report_date=date(2026, 1, 2), quantity=20, note="Ghi chú phiếu 2", created_by_id=1),
        ProgressEntry(project_id=1, progress_item_id=second_item.id, report_date=date(2026, 1, 3), quantity=30, note="Ghi chú phiếu 3", created_by_id=3),
    ]
    db.session.add_all(entries)
    db.session.commit()
    return progress_type.id, first_group.id, first_item.id


def test_type_delete_requires_exact_name_preserves_all_children_and_audits_full_snapshot(client, app):
    with app.app_context():
        type_id, _group_id, _item_id = _tree()
        assert _counts() == (1, 2, 3, 3)

    _login(client, "pm")
    rejected = client.post(
        f"/projects/1/progress/types/{type_id}/delete",
        data={"confirm_name": "Tên sai"},
    )
    assert rejected.status_code == 400
    assert "Tên xác nhận không khớp" in rejected.get_data(as_text=True)
    with app.app_context():
        assert _counts() == (1, 2, 3, 3)
        assert AuditLog.query.filter_by(action="construction_progress.type.delete").count() == 0

    deleted = client.post(
        f"/projects/1/progress/types/{type_id}/delete",
        data={"confirm_name": "Loại cần xoá"},
    )
    assert deleted.status_code == 302
    with app.app_context():
        assert _counts() == (0, 0, 0, 0)
        audit = AuditLog.query.filter_by(action="construction_progress.type.delete").one()
        old_values = audit.old_values_json
        first_entry = old_values["groups"][0]["items"][0]["entries"][0]
        assert old_values["progress_type"]["name"] == "Loại cần xoá"
        assert old_values["groups"][0]["name"] == "Tầng hầm"
        assert old_values["groups"][0]["items"][0]["name"] == "Đi ống"
        assert first_entry["id"] is not None
        assert {key: first_entry[key] for key in ("report_date", "quantity", "note", "created_by")} == {
            "report_date": "2026-01-01",
            "quantity": "10.000",
            "note": "Ghi chú phiếu 1",
            "created_by": {"id": 3, "username": "reporter", "full_name": "Reporter"},
        }


def test_group_delete_removes_only_its_descendants(client, app):
    with app.app_context():
        _type_id, group_id, _item_id = _tree()

    _login(client, "pm")
    group_deleted = client.post(
        f"/projects/1/progress/groups/{group_id}/delete",
        data={"confirm_name": "Tầng hầm"},
    )
    assert group_deleted.status_code == 302
    with app.app_context():
        assert _counts() == (1, 1, 1, 0)
        group_audit = AuditLog.query.filter_by(action="construction_progress.group.delete").one()
        assert group_audit.old_values_json["counts"] == {"groups": 1, "items": 2, "entries": 3}
        assert group_audit.old_values_json["groups"][0]["items"][1]["entries"][0]["report_date"] == "2026-01-03"
        assert group_audit.old_values_json["groups"][0]["items"][1]["entries"][0]["quantity"] == "30.000"
        assert group_audit.old_values_json["groups"][0]["items"][1]["entries"][0]["created_by"]["username"] == "reporter"


def test_item_delete_removes_only_its_entries(client, app):
    with app.app_context():
        _type_id, _group_id, item_id = _tree()

    _login(client, "pm")
    item_deleted = client.post(
        f"/projects/1/progress/items/{item_id}/delete",
        data={"confirm_name": "Đi ống"},
    )
    assert item_deleted.status_code == 302
    with app.app_context():
        assert _counts() == (1, 2, 2, 1)
        item_audit = AuditLog.query.filter_by(action="construction_progress.item.delete").one()
        assert item_audit.old_values_json["counts"] == {"groups": 0, "items": 1, "entries": 2}
        item_entry = item_audit.old_values_json["groups"][0]["items"][0]["entries"][1]
        assert {key: item_entry[key] for key in ("report_date", "quantity", "note", "created_by")} == {
            "report_date": "2026-01-02",
            "quantity": "20.000",
            "note": "Ghi chú phiếu 2",
            "created_by": {"id": 1, "username": "super", "full_name": "Super"},
        }


def test_structure_delete_without_capability_is_forbidden_and_preserves_everything(client, app):
    with app.app_context():
        type_id, _group_id, _item_id = _tree()
        assert _counts() == (1, 2, 3, 3)

    _login(client, "reporter")
    denied = client.post(
        f"/projects/1/progress/types/{type_id}/delete",
        data={"confirm_name": "Loại cần xoá"},
    )
    assert denied.status_code == 403
    with app.app_context():
        assert _counts() == (1, 2, 3, 3)
        assert AuditLog.query.filter_by(action="construction_progress.type.delete").count() == 0


def test_inactive_progress_structure_is_visible_and_archive_actions_are_gone(client, app):
    with app.app_context():
        type_id, group_id, item_id = _tree(inactive=True)
        tree = progress_tree(db.session.get(Project, 1))
        assert len(tree) == 1
        assert len(tree[0]["groups"]) == 2
        assert len(tree[0]["groups"][0]["items"]) == 2

    _login(client, "pm")
    detail = client.get(f"/projects/1/progress/types/{type_id}")
    detail_text = detail.get_data(as_text=True)
    assert detail.status_code == 200
    assert detail_text.count("đang ẩn") >= 3
    assert "Ẩn loại" not in detail_text
    assert "/archive" not in detail_text
    assert client.post(f"/projects/1/progress/types/{type_id}/archive").status_code == 404
    assert client.post(f"/projects/1/progress/groups/{group_id}/archive").status_code == 404
    assert client.post(f"/projects/1/progress/items/{item_id}/archive").status_code == 404
    client.post("/logout")
    _login(client, "admin")
    workspace = client.get("/projects/1/workspace").get_data(as_text=True)
    assert "1 loại tiến độ" in workspace
