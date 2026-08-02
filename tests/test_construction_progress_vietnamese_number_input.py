from datetime import date
from decimal import Decimal

import pytest

from app.construction_progress.services import InvalidNumberFormatError, parse_vietnamese_number
from app.extensions import db
from app.models import ProgressEntry, ProgressGroup, ProgressItem, ProgressType


@pytest.mark.parametrize(
    ("raw", "decimal_places", "expected"),
    [
        ("1280,34", 2, "1280.34"), ("1280.34", 2, "1280.34"),
        ("1.280,34", 2, "1280.34"), ("1,280.34", 2, "1280.34"),
        ("1.000", 2, "1000"), ("1,000", 2, "1000"),
        ("1.000", 0, "1000"), ("1,000", 0, "1000"),
        ("0,5", 1, "0.5"), ("1 234,5", 1, "1234.5"),
        ("1.234.567", 0, "1234567"), ("277", 0, "277"), ("1.5", 1, "1.5"),
    ],
)
def test_parse_vietnamese_number_handles_unambiguous_input(raw, decimal_places, expected):
    assert parse_vietnamese_number(raw, decimal_places) == Decimal(expected)


@pytest.mark.parametrize("raw", ("1.000", "1,000"))
def test_parse_vietnamese_number_rejects_ambiguous_three_decimal_input(raw):
    with pytest.raises(InvalidNumberFormatError, match="có thể là 1000 hoặc 1,000"):
        parse_vietnamese_number(raw, 3)


def test_parse_vietnamese_number_accepts_nonbreaking_space():
    assert parse_vietnamese_number("1\u00a0234,5", 1) == Decimal("1234.5")


def _login(client, username):
    client.post("/login", data={"username_or_email": username, "password": "password123"})


def _structure():
    progress_type = ProgressType(project_id=1, name="Loại nhập Việt", created_by_id=1)
    db.session.add(progress_type); db.session.flush()
    group = ProgressGroup(project_id=1, progress_type_id=progress_type.id, name="Khu nhập Việt", created_by_id=1)
    db.session.add(group); db.session.flush()
    item = ProgressItem(project_id=1, progress_group_id=group.id, name="Hạng mục gốc", unit="m", decimal_places=2, planned_quantity=Decimal("100.00"), created_by_id=1)
    db.session.add(item); db.session.commit()
    return progress_type.id, group.id, item.id


def test_all_remaining_six_number_write_routes_accept_vietnamese_commas(client, app):
    with app.app_context():
        type_id, group_id, item_id = _structure()
    _login(client, "pm")
    created_item = client.post(f"/projects/1/progress/groups/{group_id}/items", data={"name": "Tạo lẻ", "unit": "m", "decimal_places": "2", "planned_quantity": "1280,34", "opening_quantity": "345,32"})
    assert created_item.status_code == 302
    with app.app_context():
        single_item = ProgressItem.query.filter_by(progress_group_id=group_id, name="Tạo lẻ").one()
        assert single_item.planned_quantity == Decimal("1280.34")
        assert single_item.opening_quantity == Decimal("345.32")
    edited_item = client.post(f"/projects/1/progress/items/{item_id}/edit", data={"name": "Hạng mục gốc", "unit": "m", "decimal_places": "2", "planned_quantity": "10,50", "opening_quantity": "0,25"})
    assert edited_item.status_code == 302
    created_group = client.post(f"/projects/1/progress/types/{type_id}/groups/batch", data={"name": "Khu batch", "items-0-name": "Hạng mục batch", "items-0-unit": "m", "items-0-decimal_places": "2", "items-0-planned_quantity": "1280,34", "items-0-opening_quantity": "345,32"})
    assert created_group.status_code == 302
    with app.app_context():
        batch_group = ProgressGroup.query.filter_by(progress_type_id=type_id, name="Khu batch").one()
        batch_item = ProgressItem.query.filter_by(progress_group_id=batch_group.id).one()
        assert batch_item.planned_quantity == Decimal("1280.34")
        assert batch_item.opening_quantity == Decimal("345.32")
        batch_group_id, batch_item_id = batch_group.id, batch_item.id
    updated_group = client.post(f"/projects/1/progress/groups/{batch_group_id}/batch", data={"name": "Khu batch", "items-0-id": str(batch_item_id), "items-0-name": "Hạng mục batch", "items-0-unit": "m", "items-0-decimal_places": "2", "items-0-planned_quantity": "20,50", "items-0-opening_quantity": "1,25"})
    assert updated_group.status_code == 302
    client.post("/logout"); _login(client, "reporter")
    batch_entries = client.post(f"/projects/1/progress/types/{type_id}/entries/batch", data={"report_date": "2026-02-01", "entries-0-group_id": str(batch_group_id), "entries-0-item_id": str(batch_item_id), "entries-0-quantity": "2,5"})
    assert batch_entries.status_code == 302
    with app.app_context():
        entry = ProgressEntry.query.filter_by(progress_item_id=batch_item_id, report_date=date(2026, 2, 1)).one()
        entry_id = entry.id
    updated_entry = client.post(f"/projects/1/progress/entries/{entry_id}/edit", data={"report_date": "2026-02-01", "quantity": "1,75"})
    assert updated_entry.status_code == 302
    with app.app_context():
        assert db.session.get(ProgressItem, item_id).planned_quantity == Decimal("10.50")
        assert db.session.get(ProgressItem, item_id).opening_quantity == Decimal("0.25")
        assert db.session.get(ProgressItem, item_id).completed_quantity == Decimal("0.25")
        assert db.session.get(ProgressItem, batch_item_id).completed_quantity == Decimal("3.00")


def test_integer_precision_still_rejects_comma_decimal_input(client, app):
    with app.app_context():
        _, group_id, _ = _structure()
    _login(client, "pm")
    response = client.post(
        f"/projects/1/progress/groups/{group_id}/items",
        data={"name": "Không được tạo", "unit": "m", "decimal_places": "0", "planned_quantity": "12,5", "opening_quantity": "0"},
        follow_redirects=True,
    )
    assert "Khối lượng kế hoạch chỉ được có tối đa 0 chữ số thập phân." in response.get_data(as_text=True)
    with app.app_context():
        assert ProgressItem.query.filter_by(progress_group_id=group_id, name="Không được tạo").count() == 0


def test_unreadable_number_reports_format_instead_of_zero_message(client, app):
    with app.app_context():
        _, group_id, _ = _structure()
    _login(client, "pm")
    response = client.post(
        f"/projects/1/progress/groups/{group_id}/items",
        data={"name": "Sai định dạng", "unit": "m", "decimal_places": "2", "planned_quantity": "abc", "opening_quantity": "0"},
        follow_redirects=True,
    )
    page = response.get_data(as_text=True)
    assert "Định dạng số không hợp lệ" in page
    assert "Ví dụ với độ chính xác này: 1.280,34" in page
    assert "phải lớn hơn 0" not in page


def test_item_detail_and_group_overlay_use_vietnamese_number_format(client, app):
    with app.app_context():
        type_id, _, item_id = _structure()
        item = db.session.get(ProgressItem, item_id)
        item.planned_quantity, item.opening_quantity = Decimal("1280.34"), Decimal("345.32")
        db.session.add(ProgressEntry(project_id=1, progress_item_id=item_id, report_date=date(2026, 1, 1), quantity=Decimal("1.50"), created_by_id=3))
        db.session.commit()
    _login(client, "pm")
    type_page = client.get(f"/projects/1/progress/types/{type_id}").get_data(as_text=True)
    item_page = client.get(f"/projects/1/progress/items/{item_id}").get_data(as_text=True)
    assert 'value="1.280,34"' in type_page
    assert 'value="345,32"' in type_page
    assert "1,50 m" in item_page
    assert "Ví dụ: 1.280,34" in type_page
