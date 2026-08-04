from datetime import date
from decimal import Decimal

from app.extensions import db
from app.models import AuditLog, ProgressEntry, ProgressGroup, ProgressItem, ProgressType
from app.construction_progress.services import group_percent, item_percent, type_percent


def _login(client, username="reporter"):
    client.post("/login", data={"username_or_email": username, "password": "password123"})


def _item():
    progress_type = ProgressType(project_id=1, name="Tiến độ", created_by_id=1)
    db.session.add(progress_type); db.session.flush()
    group = ProgressGroup(project_id=1, progress_type_id=progress_type.id, name="Khu vực", created_by_id=1)
    db.session.add(group); db.session.flush()
    item = ProgressItem(project_id=1, progress_group_id=group.id, name="Hạng mục", unit="m", planned_quantity=10, created_by_id=1)
    db.session.add(item); db.session.commit()
    return item.id


def test_item_detail_shows_history_without_create_form_and_removed_create_route_is_404(client, app):
    with app.app_context():
        item_id = _item()
        item = db.session.get(ProgressItem, item_id)
        item.decimal_places = 2
        item.opening_quantity = Decimal("1.00")
        item.completed_quantity = Decimal("14.84")
        db.session.add_all((
            ProgressEntry(project_id=1, progress_item_id=item_id, report_date=date(2026, 1, 1), quantity=Decimal("1.50"), note="Phiếu cũ", created_by_id=3),
            ProgressEntry(project_id=1, progress_item_id=item_id, report_date=date(2026, 1, 3), quantity=Decimal("12.34"), note="Phiếu mới", created_by_id=5),
        ))
        db.session.commit()
    _login(client)
    removed_route = client.post(f"/projects/1/progress/items/{item_id}/entries", data={"report_date": "2026-01-04", "quantity": "1"})
    assert removed_route.status_code == 404
    with app.app_context():
        assert ProgressEntry.query.filter_by(progress_item_id=item_id).count() == 2
    page = client.get(f"/projects/1/progress/items/{item_id}").get_data(as_text=True)
    assert 'name="report_date"' not in page
    assert "Tạo phiếu" not in page
    assert "Kế hoạch" in page
    assert "Đã làm" in page
    assert "Còn lại" in page
    assert "Hoàn thành" in page
    assert "Lịch sử cập nhật" in page
    assert page.index("03/01/2026") < page.index("01/01/2026")
    assert "12,34 m" in page
    assert "1,50 m" in page
    assert "Pm" in page
    assert "Reporter" in page
    assert "Đã làm trước đó" in page
    assert "1,00 m" in page
    assert "data-entry-edit" in page
    assert "data-entry-delete" in page


def test_entry_http_update_delete_recalculates_and_audits(client, app):
    with app.app_context():
        item_id = _item()
        item = db.session.get(ProgressItem, item_id)
        item.completed_quantity = Decimal("14")
        entry = ProgressEntry(project_id=1, progress_item_id=item_id, report_date=date(2026, 1, 1), quantity=Decimal("14"), note="mới", created_by_id=3)
        db.session.add(entry)
        db.session.commit()
        entry_id = entry.id
    _login(client)
    with app.app_context():
        item = db.session.get(ProgressItem, item_id)
        assert item.completed_quantity == 14
        assert item_percent(item) == 140
        assert group_percent(item.progress_group, "quantity") == 140
        assert type_percent(item.progress_group.progress_type) == 140
    assert client.post(f"/projects/1/progress/entries/{entry_id}/edit", data={"report_date": "2026-01-01", "quantity": "20", "note": "sửa"}).status_code == 302
    with app.app_context():
        item = db.session.get(ProgressItem, item_id)
        assert item.completed_quantity == 20
        assert item_percent(item) == 200
        update = AuditLog.query.filter_by(action="construction_progress.entry.update").one()
        assert Decimal(update.old_values_json["quantity"]) == Decimal("14")
        assert Decimal(update.new_values_json["quantity"]) == Decimal("20")
    assert client.post(f"/projects/1/progress/entries/{entry_id}/delete").status_code == 302
    with app.app_context():
        item = db.session.get(ProgressItem, item_id)
        assert item.completed_quantity == 0
        assert item_percent(item) == 0
        assert group_percent(item.progress_group, "quantity") == 0
        assert type_percent(item.progress_group.progress_type) == 0
        deleted = AuditLog.query.filter_by(action="construction_progress.entry.delete").one()
        assert Decimal(deleted.old_values_json["quantity"]) == Decimal("20")


def test_item_http_rejects_lower_decimal_places_that_would_round_existing_entries(client, app):
    with app.app_context():
        item_id = _item()
        item = db.session.get(ProgressItem, item_id)
        item.decimal_places = 1
        entry = ProgressEntry(
            project_id=1,
            progress_item_id=item_id,
            report_date=date(2026, 1, 1),
            quantity=Decimal("151.5"),
            created_by_id=3,
        )
        db.session.add(entry)
        db.session.commit()

    _login(client, "pm")
    response = client.post(
        f"/projects/1/progress/items/{item_id}/edit",
        data={"name": "Hạng mục", "unit": "m", "planned_quantity": "10", "opening_quantity": "0", "decimal_places": "0"},
        follow_redirects=True,
    )
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Không thể hạ xuống 0 chữ số thập phân" in page
    assert "151,5" in page
    with app.app_context():
        assert db.session.get(ProgressItem, item_id).decimal_places == 1
        assert ProgressEntry.query.filter_by(progress_item_id=item_id).count() == 1
