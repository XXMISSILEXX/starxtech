from datetime import date, timedelta
from decimal import Decimal

from app.extensions import db
from app.models import AuditLog, ProgressEntry, ProgressGroup, ProgressItem, ProgressType


def _login(client, username="reporter"):
    client.post("/login", data={"username_or_email": username, "password": "password123"})


def _entries():
    value = ProgressType(project_id=1, name="Danh sách phiếu", created_by_id=1)
    db.session.add(value); db.session.flush()
    first = ProgressGroup(project_id=1, progress_type_id=value.id, name="Khu A", created_by_id=1)
    second = ProgressGroup(project_id=1, progress_type_id=value.id, name="Khu B", created_by_id=1)
    db.session.add_all((first, second)); db.session.flush()
    item_a = ProgressItem(project_id=1, progress_group_id=first.id, name="Mục A", unit="m", decimal_places=1, created_by_id=1)
    item_b = ProgressItem(project_id=1, progress_group_id=second.id, name="Mục B", unit="cái", decimal_places=0, created_by_id=1)
    db.session.add_all((item_a, item_b)); db.session.flush()
    for day in range(1, 46):
        item = item_a if day % 2 else item_b
        db.session.add(ProgressEntry(project_id=1, progress_item_id=item.id, report_date=date(2026, 1, 1) + timedelta(days=day - 1), quantity=Decimal("1.5") if item is item_a else Decimal("2"), note=f"phiếu {day}", created_by_id=3))
    db.session.commit()
    return value.id, first.id, second.id


def test_entry_tab_uses_sql_page_filters_and_distinguishes_empty_states(client, app):
    with app.app_context(): type_id, first_group_id, _ = _entries()
    _login(client)
    first_page = client.get(f"/projects/1/progress/types/{type_id}?tab=entries&group_id={first_group_id}&date_from=2026-01-01")
    page = first_page.get_data(as_text=True)
    assert first_page.status_code == 200
    assert "Tổng quan" in page and "Cập nhật ngày" in page
    assert "phiếu 45" in page and "phiếu 5" not in page
    assert "group_id=" + str(first_group_id) in page
    second_page = client.get(f"/projects/1/progress/types/{type_id}?tab=entries&page=2&group_id={first_group_id}&date_from=2026-01-01")
    assert "phiếu 5" in second_page.get_data(as_text=True)
    filtered = client.get(f"/projects/1/progress/types/{type_id}?tab=entries&group_id={first_group_id}&date_from=2026-03-01")
    assert "Không có phiếu nào khớp bộ lọc." in filtered.get_data(as_text=True)
    no_entries_type = client.get(f"/projects/1/progress/types/{type_id}?tab=entries&date_from=bad")
    assert "Từ ngày phải theo định dạng YYYY-MM-DD." in no_entries_type.get_data(as_text=True)
    invalid_range = client.get(f"/projects/1/progress/types/{type_id}?tab=entries&date_from=2026-02-02&date_to=2026-01-01")
    assert "Từ ngày không được lớn hơn đến ngày." in invalid_range.get_data(as_text=True)
    assert client.get(f"/projects/1/progress/types/{type_id}?tab=bad").status_code == 400


def test_entry_list_edit_failure_and_delete_keep_list_state_and_audit(client, app):
    with app.app_context():
        type_id, group_id, _ = _entries()
        first = ProgressEntry.query.order_by(ProgressEntry.id).first()
        duplicate = ProgressEntry.query.filter(ProgressEntry.progress_item_id == first.progress_item_id, ProgressEntry.id != first.id).first()
        first_id, duplicate_date = first.id, duplicate.report_date
    _login(client)
    failed = client.post(
        f"/projects/1/progress/entries/{first_id}/edit",
        data={"return_tab": "entries", "page": "1", "group_id": str(group_id), "date_from": "2026-01-01", "report_date": duplicate_date.isoformat(), "quantity": "1,5", "note": "không đổi"},
    )
    page = failed.get_data(as_text=True)
    assert failed.status_code == 400
    assert f'data-open-progress-modal="editEntry-{first_id}"' in page
    assert "đã có phiếu" in page
    with app.app_context():
        assert db.session.get(ProgressEntry, first_id).report_date != duplicate_date
        before_audits = AuditLog.query.count()
    deleted = client.post(f"/projects/1/progress/entries/{first_id}/delete", data={"return_tab": "entries", "page": "1", "group_id": str(group_id), "date_from": "2026-01-01"})
    assert deleted.status_code == 302
    assert "tab=entries" in deleted.headers["Location"] and "page=1" in deleted.headers["Location"]
    with app.app_context():
        audit = AuditLog.query.filter_by(action="construction_progress.entry.delete").one()
        assert AuditLog.query.count() == before_audits + 1
        assert audit.old_values_json["report_date"]
        assert audit.old_values_json["quantity"]
        assert audit.old_values_json["created_by"]["username"] == "reporter"
