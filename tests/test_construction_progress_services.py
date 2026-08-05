"""SQLite tests do not prove PostgreSQL concurrency or FOR UPDATE behavior."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.extensions import db
from app.models import AuditLog, ProgressEntry, ProgressItem, Project
from app.construction_progress.services import (
    DuplicateEntryError, FutureDateError, InvalidQuantityError, create_entry,
    create_group, create_item, create_type, delete_entry, group_percent,
    gantt_axis_for_dates, gantt_chart_for_type, gantt_timeline_for_type,
    group_gantt_timeline, item_gantt_timeline,
    item_percent, type_percent, type_progress_summary, update_entry, update_item,
    InvalidDecimalPlacesError,
)


def _tree(money=False, planned="100", opening="0"):
    project = db.session.get(Project, 1)
    progress_type = create_type(project=project, name="Dự toán" if money else "Khối lượng", value_mode="money" if money else "quantity", actor_id=1)
    group = create_group(progress_type=progress_type, name="Tòa C1", actor_id=1)
    item = create_item(group=group, name="Đi ống", unit="VNĐ" if money else "m", planned_quantity=planned, opening_quantity=opening, decimal_places=0 if money else 1, actor_id=1)
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
        assert Decimal(audit.old_values_json["quantity"]) == Decimal("3.5")
        assert audit.old_values_json["created_at"]


def test_decimal_precision_validation_and_lowering_protection(app):
    with app.app_context():
        _, _, item = _tree()
        report_date = date.today() - timedelta(days=1)

        with pytest.raises(InvalidDecimalPlacesError, match="tối đa 1 chữ số thập phân"):
            create_entry(item=item, report_date=report_date, quantity="1.25", actor_id=3)
        assert ProgressEntry.query.filter_by(progress_item_id=item.id).count() == 0

        create_entry(item=item, report_date=report_date, quantity="151.5", actor_id=3)
        db.session.commit()

        with pytest.raises(InvalidDecimalPlacesError, match=r"phiếu ngày .*151,5"):
            update_item(item, name=item.name, unit=item.unit, planned_quantity=item.planned_quantity,
                        opening_quantity=item.opening_quantity, decimal_places=0, actor_id=1)
        assert item.decimal_places == 1
        assert ProgressEntry.query.filter_by(progress_item_id=item.id).one().quantity == Decimal("151.500")

        update_item(item, name=item.name, unit=item.unit, planned_quantity=item.planned_quantity,
                    opening_quantity=item.opening_quantity, decimal_places=2, actor_id=1)
        assert item.decimal_places == 2


@pytest.mark.parametrize(
    ("planned_quantity", "opening_quantity", "message"),
    [
        ("1.25", "0", "Khối lượng kế hoạch"),
        ("1", "0.25", "Khối lượng mang sang"),
    ],
)
def test_item_rejects_quantities_more_precise_than_declared(app, planned_quantity, opening_quantity, message):
    with app.app_context():
        _, group, _ = _tree()
        before = ProgressItem.query.filter_by(progress_group_id=group.id).count()

        with pytest.raises(InvalidDecimalPlacesError, match=message):
            create_item(
                group=group,
                name="Sai độ chính xác",
                unit="m",
                planned_quantity=planned_quantity,
                opening_quantity=opening_quantity,
                decimal_places=1,
                actor_id=1,
            )

        assert ProgressItem.query.filter_by(progress_group_id=group.id).count() == before


def test_item_update_without_date_fields_preserves_existing_schedule_dates(app):
    with app.app_context():
        _, _, item = _tree()
        item.planned_start_date = date(2026, 8, 1)
        item.planned_end_date = date(2026, 8, 31)
        item.actual_start_date = date(2026, 8, 2)
        db.session.commit()

        update_item(
            item,
            name=item.name,
            unit=item.unit,
            planned_quantity=item.planned_quantity,
            opening_quantity=item.opening_quantity,
            decimal_places=item.decimal_places,
            actor_id=1,
        )

        assert item.planned_start_date == date(2026, 8, 1)
        assert item.planned_end_date == date(2026, 8, 31)
        assert item.actual_start_date == date(2026, 8, 2)


def _gantt_item(name, *, planned_start=None, planned_end=None, actual_start=None, opening=0, completed=0):
    return type(
        "GanttItem",
        (),
        {
            "id": name,
            "name": name,
            "planned_start_date": planned_start,
            "planned_end_date": planned_end,
            "actual_start_date": actual_start,
            "opening_quantity": Decimal(opening),
            "planned_quantity": Decimal("100"),
            "completed_quantity": Decimal(completed),
        },
    )()


def _gantt_group(name, *items):
    return type("GanttGroup", (), {"name": name, "items": list(items)})()


def _gantt_type(*groups):
    return type("GanttType", (), {"groups": list(groups), "value_mode": "quantity"})()


def test_type_progress_summary_leaves_dates_and_days_none_without_scheduled_groups():
    undated = _gantt_item("Chưa khai ngày", completed=50)

    summary = type_progress_summary(_gantt_type(_gantt_group("Khu trống", undated)), today=date(2026, 8, 10))

    assert summary["planned_start"] is None
    assert summary["planned_end"] is None
    assert summary["days"] is None
    assert summary["status"] == "not_started"
    assert summary["undated_items"] == 1


def test_type_progress_summary_uses_scheduled_group_bounds_and_ignores_undated_items():
    early = _gantt_item("Sớm", planned_start=date(2026, 8, 2), planned_end=date(2026, 8, 4), completed=20)
    late = _gantt_item("Muộn", planned_start=date(2026, 8, 10), planned_end=date(2026, 8, 20), completed=20)
    undated = _gantt_item("Chưa khai", completed=99)

    summary = type_progress_summary(
        _gantt_type(_gantt_group("Khu A", late, undated), _gantt_group("Khu B", early)),
        today=date(2026, 8, 10),
    )

    assert summary["planned_start"] == date(2026, 8, 2)
    assert summary["planned_end"] == date(2026, 8, 20)
    assert summary["days"] == 19
    assert summary["undated_items"] == 1


def test_type_progress_summary_counts_single_planned_day_inclusively():
    item = _gantt_item("Một ngày", planned_start=date(2026, 8, 1), planned_end=date(2026, 8, 1), completed=20)

    summary = type_progress_summary(_gantt_type(_gantt_group("Khu A", item)), today=date(2026, 8, 1))

    assert summary["days"] == 1


def test_type_progress_summary_marks_not_started_before_planned_start():
    item = _gantt_item("Sắp làm", planned_start=date(2026, 8, 12), planned_end=date(2026, 8, 20), completed=20)

    summary = type_progress_summary(_gantt_type(_gantt_group("Khu A", item)), today=date(2026, 8, 10))

    assert summary["status"] == "not_started"


def test_type_progress_summary_marks_in_progress_during_planned_range():
    item = _gantt_item("Đang làm", planned_start=date(2026, 8, 1), planned_end=date(2026, 8, 20), completed=20)

    summary = type_progress_summary(_gantt_type(_gantt_group("Khu A", item)), today=date(2026, 8, 10))

    assert summary["status"] == "in_progress"


def test_type_progress_summary_marks_overdue_when_incomplete_after_planned_end():
    item = _gantt_item("Chậm", planned_start=date(2026, 8, 1), planned_end=date(2026, 8, 5), completed=99)

    summary = type_progress_summary(_gantt_type(_gantt_group("Khu A", item)), today=date(2026, 8, 10))

    assert summary["status"] == "overdue"


def test_type_progress_summary_marks_done_before_overdue_when_complete():
    item = _gantt_item("Đã xong", planned_start=date(2026, 8, 1), planned_end=date(2026, 8, 5), completed=100)

    summary = type_progress_summary(_gantt_type(_gantt_group("Khu A", item)), today=date(2026, 8, 10))

    assert summary["status"] == "done"


def test_type_progress_summary_counts_only_scheduled_incomplete_items_as_overdue():
    overdue = _gantt_item("Quá hạn", planned_start=date(2026, 8, 1), planned_end=date(2026, 8, 5), completed=50)
    complete = _gantt_item("Đã xong", planned_start=date(2026, 8, 1), planned_end=date(2026, 8, 5), completed=100)
    undated = _gantt_item("Chưa khai ngày", completed=0)
    progress_type = _gantt_type(_gantt_group("Khu A", overdue, complete, undated))

    summary = type_progress_summary(
        progress_type,
        {overdue.id: [date(2026, 8, 2)], undated.id: [date(2026, 8, 12)]},
        today=date(2026, 8, 10),
    )

    assert summary["overdue_items"] == 1
    assert summary["undated_items"] == len(gantt_timeline_for_type(progress_type)["excluded_items"]) == 1
    assert summary["last_entry_date"] == date(2026, 8, 12)


def test_item_gantt_timeline_derives_planned_and_entry_based_actual_ranges():
    item = _gantt_item("Đi ống", planned_start=date(2026, 8, 1), planned_end=date(2026, 8, 31))

    timeline = item_gantt_timeline(item, (date(2026, 8, 3), date(2026, 8, 10), date(2026, 8, 7)))

    assert timeline["planned_start"] == date(2026, 8, 1)
    assert timeline["planned_end"] == date(2026, 8, 31)
    assert timeline["actual_start"] == date(2026, 8, 3)
    assert timeline["actual_end"] == date(2026, 8, 10)
    assert timeline["actual_is_point"] is False


@pytest.mark.parametrize(
    ("actual_start", "entry_dates", "expected_start"),
    (
        (date(2026, 8, 1), (date(2026, 8, 3),), date(2026, 8, 1)),
        (date(2026, 8, 5), (date(2026, 8, 3),), date(2026, 8, 3)),
    ),
)
def test_item_gantt_timeline_uses_earliest_actual_evidence(actual_start, entry_dates, expected_start):
    item = _gantt_item("Đi dây", planned_start=date(2026, 8, 1), planned_end=date(2026, 8, 31), actual_start=actual_start)

    timeline = item_gantt_timeline(item, entry_dates)

    assert timeline["actual_start"] == expected_start
    assert timeline["actual_end"] == date(2026, 8, 3)


def test_item_gantt_timeline_marks_manual_actual_start_without_entries_as_point():
    item = _gantt_item("Lắp tủ", planned_start=date(2026, 8, 1), planned_end=date(2026, 8, 31), actual_start=date(2026, 8, 4))

    timeline = item_gantt_timeline(item)

    assert timeline["actual_start"] == date(2026, 8, 4)
    assert timeline["actual_end"] == date(2026, 8, 4)
    assert timeline["actual_is_point"] is True


def test_item_gantt_timeline_has_no_actual_bar_without_start_or_entries():
    item = _gantt_item("Nghiệm thu", planned_start=date(2026, 8, 1), planned_end=date(2026, 8, 31), opening=10)

    timeline = item_gantt_timeline(item)

    assert timeline["actual_start"] is None
    assert timeline["actual_end"] is None
    assert timeline["actual_is_point"] is False
    assert timeline["has_opening_actual_start_reminder"] is True


def test_group_gantt_timeline_uses_only_scheduled_items_and_excludes_empty_group():
    scheduled_early = _gantt_item("A", planned_start=date(2026, 8, 1), planned_end=date(2026, 8, 5), actual_start=date(2026, 8, 2))
    scheduled_late = _gantt_item("B", planned_start=date(2026, 8, 10), planned_end=date(2026, 8, 20))
    excluded = _gantt_item("Không có ngày", actual_start=date(2026, 7, 20))
    group = _gantt_group("Khu C1", scheduled_late, excluded, scheduled_early)

    timeline = group_gantt_timeline(group, [item_gantt_timeline(item) for item in group.items])

    assert timeline["planned_start"] == date(2026, 8, 1)
    assert timeline["planned_end"] == date(2026, 8, 20)
    assert timeline["actual_start"] == date(2026, 8, 2)
    assert timeline["actual_end"] == date(2026, 8, 2)
    assert [row["item"].name for row in timeline["items"]] == ["A", "B"]
    assert group_gantt_timeline(_gantt_group("Khu trống", excluded), [item_gantt_timeline(excluded)]) is None


def test_gantt_timeline_for_type_counts_excluded_items_and_omits_empty_groups():
    shown = _gantt_item("Có kế hoạch", planned_start=date(2026, 8, 3), planned_end=date(2026, 8, 8))
    excluded_one = _gantt_item("Chưa khai một")
    excluded_two = _gantt_item("Chưa khai hai", actual_start=date(2026, 8, 1))
    first_group = _gantt_group("Khu xuất hiện", shown, excluded_one)
    empty_group = _gantt_group("Khu không xuất hiện", excluded_two)
    progress_type = type("GanttType", (), {"groups": [empty_group, first_group]})()

    timeline = gantt_timeline_for_type(progress_type)

    assert [group["group"].name for group in timeline["groups"]] == ["Khu xuất hiện"]
    assert [item.name for item in timeline["excluded_items"]] == ["Chưa khai hai", "Chưa khai một"]


@pytest.mark.parametrize(
    ("last_date", "expected_unit"),
    (
        (date(2026, 1, 31), "day"),
        (date(2026, 2, 1), "week"),
        (date(2026, 7, 1), "week"),
        (date(2026, 7, 2), "month"),
    ),
)
def test_gantt_axis_selects_daily_weekly_and_monthly_ticks_at_thresholds(last_date, expected_unit):
    axis = gantt_axis_for_dates(date(2026, 1, 1), last_date, today=date(2026, 1, 1))

    assert axis["unit"] == expected_unit
    assert axis["ticks"]


def test_gantt_chart_axis_expands_to_today_without_extending_actual_bar_to_today():
    item = _gantt_item("Công việc dừng", planned_start=date(2026, 1, 1), planned_end=date(2026, 1, 10))
    group = _gantt_group("Khu A", item)
    progress_type = type("GanttType", (), {"groups": [group]})()

    chart = gantt_chart_for_type(progress_type, {item.id: [date(2026, 1, 2), date(2026, 1, 4)]}, today=date(2026, 2, 1))

    line = chart["groups"][0]["items"][0]
    assert chart["axis"]["end"] == date(2026, 2, 1)
    assert line["actual_bar"]["end"] == date(2026, 1, 4)
