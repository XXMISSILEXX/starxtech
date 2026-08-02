from datetime import date, timedelta
from decimal import Decimal

from app.extensions import db
from app.date_utils import local_today
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


def test_entry_http_validation_and_idempotency(client, app):
    with app.app_context(): item_id = _item()
    _login(client)
    payload = {"report_date": "2026-01-01", "quantity": "2", "note": "ghi chú"}
    created = client.post(f"/projects/1/progress/items/{item_id}/entries", data=payload)
    assert created.status_code == 302
    assert "application/json" not in created.headers.get("Content-Type", "")
    assert "Đã tạo phiếu cập nhật tiến độ." in client.post(f"/projects/1/progress/items/{item_id}/entries", data={"report_date": "2026-01-03", "quantity": "1"}, follow_redirects=True).get_data(as_text=True)
    duplicate = client.post(f"/projects/1/progress/items/{item_id}/entries", data=payload, follow_redirects=True)
    assert "đã có phiếu" in duplicate.get_data(as_text=True)
    with app.app_context():
        assert ProgressEntry.query.filter_by(progress_item_id=item_id, report_date=date(2026, 1, 1)).count() == 1
    with app.app_context():
        future_date = local_today() + timedelta(days=1)
    future = client.post(f"/projects/1/progress/items/{item_id}/entries", data={"report_date": future_date.isoformat(), "quantity": "2"}, follow_redirects=True)
    assert "ngày trong tương lai" in future.get_data(as_text=True)
    with app.app_context():
        assert ProgressEntry.query.filter_by(progress_item_id=item_id, report_date=future_date).count() == 0
    for quantity in ("0", "-5"):
        response = client.post(f"/projects/1/progress/items/{item_id}/entries", data={"report_date": "2026-01-02", "quantity": quantity}, follow_redirects=True)
        assert "lớn hơn 0" in response.get_data(as_text=True)
        with app.app_context():
            assert ProgressEntry.query.filter_by(progress_item_id=item_id, report_date=date(2026, 1, 2)).count() == 0


def test_entry_http_create_update_delete_recalculates_and_audits(client, app):
    with app.app_context(): item_id = _item()
    _login(client)
    assert client.post(f"/projects/1/progress/items/{item_id}/entries", data={"report_date": "2026-01-01", "quantity": "14", "note": "mới"}).status_code == 302
    with app.app_context():
        item = db.session.get(ProgressItem, item_id)
        entry = ProgressEntry.query.filter_by(progress_item_id=item_id).one()
        assert item.completed_quantity == 14
        assert item_percent(item) == 140
        assert group_percent(item.progress_group, "quantity") == 140
        assert type_percent(item.progress_group.progress_type) == 140
        entry_id = entry.id
        create = AuditLog.query.filter_by(action="construction_progress.entry.create").one()
        assert create.new_values_json["report_date"] == "2026-01-01"
        assert Decimal(create.new_values_json["quantity"]) == Decimal("14")
        assert create.new_values_json["note"] == "mới"
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
