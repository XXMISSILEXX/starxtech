"""SQLite tests do not prove PostgreSQL concurrency or FOR UPDATE behavior."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.extensions import db
from app.models import AuditLog, Project
from app.construction_progress.services import (
    DuplicateEntryError, FutureDateError, InvalidQuantityError, create_entry,
    create_group, create_item, create_type, delete_entry, group_percent,
    item_percent, type_percent, update_entry,
)


def _tree(money=False, planned="100", opening="0"):
    project = db.session.get(Project, 1)
    progress_type = create_type(project=project, name="Dự toán" if money else "Khối lượng", value_mode="money" if money else "quantity", actor_id=1)
    group = create_group(progress_type=progress_type, name="Tòa C1", actor_id=1)
    item = create_item(group=group, name="Đi ống", unit="VNĐ" if money else "m", planned_quantity=planned, opening_quantity=opening, actor_id=1)
    db.session.commit()
    return progress_type, group, item


def test_quantity_percentages_skip_unplanned_and_empty_groups(app):
    with app.app_context():
        progress_type, group, item = _tree()
        item.completed_quantity = Decimal("150")
        empty = create_group(progress_type=progress_type, name="Chưa cấu hình", actor_id=1)
        unplanned = create_item(group=group, name="Chưa kế hoạch", unit="m", planned_quantity=0, actor_id=1)
        unplanned.completed_quantity = Decimal("99")

        assert item_percent(unplanned) is None
        assert group_percent(empty, "quantity") is None
        assert group_percent(group, "quantity") == Decimal("150")
        assert type_percent(progress_type) == Decimal("150")


def test_money_progress_uses_aggregated_values_and_decimal_precision(app):
    with app.app_context():
        progress_type, group, item = _tree(money=True, planned="3")
        item.completed_quantity = Decimal("1")
        other = create_item(group=group, name="Thiết bị", unit="VNĐ", planned_quantity="6", actor_id=1)
        other.completed_quantity = Decimal("2")

        assert group_percent(group, "money") == Decimal("33.33333333333333333333333333")
        assert type_percent(progress_type) == Decimal("33.33333333333333333333333333")


def test_entries_validate_dates_duplicate_and_recalculate(app):
    with app.app_context():
        _, _, item = _tree(opening="4")
        report_date = date.today() - timedelta(days=1)
        entry = create_entry(item=item, report_date=report_date, quantity="2.5", actor_id=3)
        db.session.commit()
        assert item.completed_quantity == Decimal("6.500")

        with pytest.raises(DuplicateEntryError):
            create_entry(item=item, report_date=report_date, quantity=1, actor_id=3)
        assert db.session.query(type(entry)).count() == 1
        with pytest.raises(FutureDateError):
            create_entry(item=item, report_date=date.today() + timedelta(days=1), quantity=1, actor_id=3)
        for value in (0, -1):
            with pytest.raises(InvalidQuantityError):
                create_entry(item=item, report_date=report_date - timedelta(days=1), quantity=value, actor_id=3)

        update_entry(entry, report_date=report_date, quantity="3.5", actor_id=3)
        db.session.commit()
        assert item.completed_quantity == Decimal("7.500")
        delete_entry(entry, actor_id=3)
        db.session.commit()
        assert item.completed_quantity == Decimal("4.000")
        audit = AuditLog.query.filter_by(action="construction_progress.entry.delete").one()
        assert audit.old_values_json["quantity"] == "3.500"
