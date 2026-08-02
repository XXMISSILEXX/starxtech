from datetime import date
from decimal import Decimal

from app.extensions import db
from app.models import ProgressEntry, ProgressGroup, ProgressItem, ProgressType


def _login(client):
    client.post("/login", data={"username_or_email": "pm", "password": "password123"})


def _structure(*, with_second_item=False, with_entries=False):
    progress_type = ProgressType(project_id=1, name="Tiến độ batch", created_by_id=1)
    db.session.add(progress_type); db.session.flush()
    group = ProgressGroup(project_id=1, progress_type_id=progress_type.id, name="Khu vực gốc", created_by_id=1)
    db.session.add(group); db.session.flush()
    item = ProgressItem(project_id=1, progress_group_id=group.id, name="Hạng mục mịn", unit="m", decimal_places=1, planned_quantity=Decimal("200.0"), created_by_id=1)
    db.session.add(item); db.session.flush()
    second = None
    if with_second_item:
        second = ProgressItem(project_id=1, progress_group_id=group.id, name="Hạng mục hợp lệ", unit="m", decimal_places=0, planned_quantity=Decimal("10"), created_by_id=1)
        db.session.add(second); db.session.flush()
    if with_entries:
        db.session.add_all([
            ProgressEntry(project_id=1, progress_item_id=item.id, report_date=date(2026, 1, 1), quantity=Decimal("151.5"), created_by_id=3),
            ProgressEntry(project_id=1, progress_item_id=item.id, report_date=date(2026, 1, 2), quantity=Decimal("2.0"), created_by_id=3),
        ])
    db.session.commit()
    return progress_type.id, group.id, item.id, None if second is None else second.id


def test_create_group_batch_rejects_duplicate_names_in_payload_and_keeps_form_values(client, app):
    with app.app_context():
        progress_type = ProgressType(project_id=1, name="Tiến độ mới", created_by_id=1)
        db.session.add(progress_type); db.session.commit()
        type_id = progress_type.id
    _login(client)
    response = client.post(
        f"/projects/1/progress/types/{type_id}/groups/batch",
        data={
            "name": "Khu vực người dùng vừa nhập",
            "items-0-name": "Ống cấp nước", "items-0-unit": "m", "items-0-decimal_places": "1", "items-0-planned_quantity": "10.0", "items-0-opening_quantity": "0",
            "items-1-name": "ống cấp nước", "items-1-unit": "m", "items-1-decimal_places": "1", "items-1-planned_quantity": "12.0", "items-1-opening_quantity": "0",
        },
    )
    page = response.get_data(as_text=True)
    assert response.status_code == 400
    assert "bị trùng trong khu vực" in page
    assert "Khu vực người dùng vừa nhập" in page
    assert "Ống cấp nước" in page
    with app.app_context():
        assert ProgressGroup.query.filter_by(progress_type_id=type_id).count() == 0
        assert ProgressItem.query.count() == 0


def test_edit_group_batch_rejects_lower_precision_and_rolls_back_every_row(client, app):
    with app.app_context():
        type_id, group_id, precise_item_id, legal_item_id = _structure(with_second_item=True, with_entries=True)
    _login(client)
    response = client.post(
        f"/projects/1/progress/groups/{group_id}/batch",
        data={
            "name": "Khu vực đã sửa nhưng phải rollback",
            "items-0-id": str(precise_item_id), "items-0-name": "Hạng mục mịn", "items-0-unit": "m", "items-0-decimal_places": "0", "items-0-planned_quantity": "200", "items-0-opening_quantity": "0",
            "items-1-id": str(legal_item_id), "items-1-name": "Hạng mục hợp lệ đã sửa", "items-1-unit": "m", "items-1-decimal_places": "0", "items-1-planned_quantity": "99", "items-1-opening_quantity": "0",
            "items-2-name": "Hạng mục lẽ ra được tạo", "items-2-unit": "m", "items-2-decimal_places": "0", "items-2-planned_quantity": "5", "items-2-opening_quantity": "0",
        },
    )
    page = response.get_data(as_text=True)
    assert response.status_code == 400
    assert "Không thể hạ xuống 0 chữ số thập phân" in page
    assert "151,5" in page
    assert "Khu vực đã sửa nhưng phải rollback" in page
    assert "Hạng mục hợp lệ đã sửa" in page
    with app.app_context():
        group = db.session.get(ProgressGroup, group_id)
        precise = db.session.get(ProgressItem, precise_item_id)
        legal = db.session.get(ProgressItem, legal_item_id)
        assert group.name == "Khu vực gốc"
        assert precise.decimal_places == 1
        assert legal.name == "Hạng mục hợp lệ"
        assert legal.planned_quantity == Decimal("10")
        assert ProgressItem.query.filter_by(progress_group_id=group_id).count() == 2
        assert ProgressEntry.query.filter_by(progress_item_id=precise_item_id).count() == 2
        assert ProgressType.query.filter_by(id=type_id).count() == 1


def test_edit_group_overlay_shows_real_entry_count_before_item_deletion(client, app):
    with app.app_context():
        type_id, _, _, _ = _structure(with_entries=True)
    _login(client)
    page = client.get(f"/projects/1/progress/types/{type_id}").get_data(as_text=True)
    assert "sẽ xoá 2 phiếu" in page


def test_group_batches_create_and_apply_edit_delete_in_one_save(client, app):
    with app.app_context():
        progress_type = ProgressType(project_id=1, name="Tiến độ thao tác", created_by_id=1)
        db.session.add(progress_type); db.session.commit()
        type_id = progress_type.id
    _login(client)
    created = client.post(
        f"/projects/1/progress/types/{type_id}/groups/batch",
        data={"name": "Khu mới", "items-0-name": "Hạng mục mới", "items-0-unit": "m", "items-0-decimal_places": "1", "items-0-planned_quantity": "12.5", "items-0-opening_quantity": "1.0"},
    )
    assert created.status_code == 302
    with app.app_context():
        group = ProgressGroup.query.filter_by(progress_type_id=type_id, name="Khu mới").one()
        item = ProgressItem.query.filter_by(progress_group_id=group.id).one()
        group_id, item_id = group.id, item.id
        db.session.add(ProgressEntry(project_id=1, progress_item_id=item_id, report_date=date(2026, 1, 1), quantity=Decimal("1.0"), created_by_id=3))
        db.session.commit()
    edited = client.post(
        f"/projects/1/progress/groups/{group_id}/batch",
        data={
            "name": "Khu đã sửa", "confirm_deletions": "on",
            "items-0-id": str(item_id), "items-0-name": "Hạng mục mới", "items-0-unit": "m", "items-0-decimal_places": "1", "items-0-planned_quantity": "12.5", "items-0-opening_quantity": "1.0", "items-0-delete": "on",
            "items-1-name": "Hạng mục thêm", "items-1-unit": "cái", "items-1-decimal_places": "0", "items-1-planned_quantity": "3", "items-1-opening_quantity": "0",
        },
    )
    assert edited.status_code == 302
    with app.app_context():
        db.session.expire_all()
        group = db.session.get(ProgressGroup, group_id)
        assert group.name == "Khu đã sửa"
        assert [item.name for item in group.items] == ["Hạng mục thêm"]
        assert ProgressEntry.query.filter_by(progress_item_id=item_id).count() == 0
