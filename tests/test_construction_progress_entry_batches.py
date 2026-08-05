from datetime import date, timedelta
from decimal import Decimal

from app.construction_progress.services import group_percent, type_percent
from app.date_utils import local_today
from app.extensions import db
from app.models import AuditLog, ProgressEntry, ProgressGroup, ProgressItem, ProgressType


def _login(client):
    client.post("/login", data={"username_or_email": "reporter", "password": "password123"})


def _structure():
    progress_type = ProgressType(project_id=1, name="Loại phiếu batch", created_by_id=1)
    other_type = ProgressType(project_id=1, name="Loại khác", created_by_id=1)
    db.session.add_all((progress_type, other_type)); db.session.flush()
    group = ProgressGroup(project_id=1, progress_type_id=progress_type.id, name="Khu A", created_by_id=1)
    other_group = ProgressGroup(project_id=1, progress_type_id=other_type.id, name="Khu bí mật", created_by_id=1)
    db.session.add_all((group, other_group)); db.session.flush()
    first = ProgressItem(project_id=1, progress_group_id=group.id, name="Hạng mục A", unit="m", decimal_places=1, planned_quantity=Decimal("10.0"), created_by_id=1)
    second = ProgressItem(project_id=1, progress_group_id=group.id, name="Hạng mục B", unit="m", decimal_places=0, planned_quantity=Decimal("30"), created_by_id=1)
    outside = ProgressItem(project_id=1, progress_group_id=other_group.id, name="Hạng mục không được lộ", unit="m", decimal_places=0, planned_quantity=Decimal("10"), created_by_id=1)
    db.session.add_all((first, second, outside)); db.session.commit()
    return progress_type.id, group.id, first.id, second.id, outside.id


def test_entry_batch_creates_multiple_entries_without_audit_and_recalculates_each_item(client, app):
    with app.app_context():
        type_id, group_id, first_id, second_id, _ = _structure()
        before_audits = AuditLog.query.count()
    _login(client)
    response = client.post(
        f"/projects/1/progress/types/{type_id}/entries/batch",
        data={
            "report_date": "2026-01-03",
            "entries-0-group_id": str(group_id), "entries-0-item_id": str(first_id), "entries-0-quantity": "2.5", "entries-0-note": "lắp xong",
            "entries-1-group_id": str(group_id), "entries-1-item_id": str(second_id), "entries-1-quantity": "3", "entries-1-note": "đổ bê tông",
            "entries-2-group_id": "", "entries-2-item_id": "", "entries-2-quantity": "", "entries-2-note": "",
        },
    )
    assert response.status_code == 302
    with app.app_context():
        first, second = db.session.get(ProgressItem, first_id), db.session.get(ProgressItem, second_id)
        assert first.completed_quantity == Decimal("2.5")
        assert second.completed_quantity == Decimal("3")
        assert ProgressEntry.query.filter_by(project_id=1, report_date=date(2026, 1, 3)).count() == 2
        assert AuditLog.query.count() == before_audits
        assert group_percent(first.progress_group, "quantity") == Decimal("17.5")
        assert type_percent(first.progress_group.progress_type) == Decimal("17.5")


def test_entry_batch_invalid_row_rolls_back_everything_and_preserves_overlay_input(client, app):
    with app.app_context():
        type_id, group_id, first_id, second_id, _ = _structure()
    _login(client)
    response = client.post(
        f"/projects/1/progress/types/{type_id}/entries/batch",
        data={
            "report_date": "2026-01-04",
            "entries-0-group_id": str(group_id), "entries-0-item_id": str(first_id), "entries-0-quantity": "2.5", "entries-0-note": "dòng hợp lệ nhưng không được lưu",
            "entries-1-group_id": str(group_id), "entries-1-item_id": str(second_id), "entries-1-quantity": "1.5", "entries-1-note": "dòng sai độ chính xác",
        },
    )
    page = response.get_data(as_text=True)
    assert response.status_code == 400
    assert "Khối lượng chỉ được có tối đa 0 chữ số thập phân." in page
    assert 'name="entries-1-quantity"' in page
    assert "is-invalid" in page
    assert 'data-open-progress-modal="createEntries"' in page
    assert page.index('data-open-progress-modal') < page.index('construction-progress-overlays.js')
    assert 'data-overlay-error-summary>Không thể lưu. Hãy kiểm tra các ô được đánh dấu.</p>' in page
    page_flash = page.split('<main class="main-content">', 1)[1].split('data-open-progress-modal', 1)[0]
    assert "Không thể lưu" not in page_flash
    assert "dòng hợp lệ nhưng không được lưu" in page
    assert "dòng sai độ chính xác" in page
    with app.app_context():
        assert ProgressEntry.query.filter_by(project_id=1, report_date=date(2026, 1, 4)).count() == 0
        assert db.session.get(ProgressItem, first_id).completed_quantity == 0
        assert db.session.get(ProgressItem, second_id).completed_quantity == 0
        assert AuditLog.query.filter_by(action="construction_progress.entry.create").count() == 0


def test_entry_batch_rejects_duplicate_and_existing_daily_entries_without_writing(client, app):
    with app.app_context():
        type_id, group_id, first_id, _, _ = _structure()
    _login(client)
    duplicate = client.post(
        f"/projects/1/progress/types/{type_id}/entries/batch",
        data={
            "report_date": "2026-01-05",
            "entries-0-group_id": str(group_id), "entries-0-item_id": str(first_id), "entries-0-quantity": "1.0",
            "entries-1-group_id": str(group_id), "entries-1-item_id": str(first_id), "entries-1-quantity": "2.0",
        },
    )
    assert duplicate.status_code == 400
    assert "bị trùng trong lượt tạo phiếu" in duplicate.get_data(as_text=True)
    with app.app_context():
        assert ProgressEntry.query.filter_by(progress_item_id=first_id).count() == 0
        db.session.add(ProgressEntry(project_id=1, progress_item_id=first_id, report_date=date(2026, 1, 5), quantity=Decimal("1.0"), created_by_id=3))
        db.session.commit()
    existing = client.post(
        f"/projects/1/progress/types/{type_id}/entries/batch",
        data={"report_date": "2026-01-05", "entries-0-group_id": str(group_id), "entries-0-item_id": str(first_id), "entries-0-quantity": "2.0"},
    )
    assert existing.status_code == 400
    assert "đã có phiếu ngày 05/01/2026" in existing.get_data(as_text=True)
    with app.app_context():
        assert ProgressEntry.query.filter_by(progress_item_id=first_id, report_date=date(2026, 1, 5)).count() == 1


def test_entry_batch_hides_out_of_scope_item_and_rejects_future_date_without_writing(client, app):
    with app.app_context():
        type_id, group_id, first_id, _, outside_id = _structure()
        future = local_today() + timedelta(days=1)
    _login(client)
    outside = client.post(
        f"/projects/1/progress/types/{type_id}/entries/batch",
        data={"report_date": "2026-01-06", "entries-0-group_id": str(group_id), "entries-0-item_id": str(outside_id), "entries-0-quantity": "1"},
    )
    assert outside.status_code == 404
    assert "Hạng mục không được lộ" not in outside.get_data(as_text=True)
    future_response = client.post(
        f"/projects/1/progress/types/{type_id}/entries/batch",
        data={"report_date": future.isoformat(), "entries-0-group_id": str(group_id), "entries-0-item_id": str(first_id), "entries-0-quantity": "1.0"},
    )
    assert future_response.status_code == 400
    assert "ngày trong tương lai" in future_response.get_data(as_text=True)
    with app.app_context():
        assert ProgressEntry.query.filter_by(progress_item_id=first_id).count() == 0
