"""SQLite in-memory constraint tests; they do not prove PostgreSQL concurrency behavior."""

from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import ProgressEntry, ProgressGroup, ProgressItem, ProgressType


def _progress_tree():
    progress_type = ProgressType(project_id=1, name="Khối lượng", created_by_id=1)
    db.session.add(progress_type)
    db.session.flush()
    group = ProgressGroup(project_id=1, progress_type_id=progress_type.id, name="Tòa C1", created_by_id=1)
    db.session.add(group)
    db.session.flush()
    item = ProgressItem(
        project_id=1,
        progress_group_id=group.id,
        name="Đi ống nổi",
        unit="mét",
        planned_quantity=100,
        created_by_id=1,
    )
    db.session.add(item)
    db.session.commit()
    return progress_type, group, item


def test_progress_entry_is_unique_per_item_and_report_date(app):
    with app.app_context():
        _, _, item = _progress_tree()
        db.session.add_all(
            [
                ProgressEntry(project_id=1, progress_item_id=item.id, report_date=date(2026, 8, 1), quantity=1, created_by_id=1),
                ProgressEntry(project_id=1, progress_item_id=item.id, report_date=date(2026, 8, 1), quantity=2, created_by_id=1),
            ]
        )

        with pytest.raises(IntegrityError):
            db.session.commit()


def test_progress_names_are_unique_within_their_parent(app):
    with app.app_context():
        progress_type, group, _ = _progress_tree()
        db.session.add(ProgressType(project_id=1, name=progress_type.name, created_by_id=1))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()

        db.session.add(ProgressGroup(project_id=1, progress_type_id=progress_type.id, name=group.name, created_by_id=1))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()

        db.session.add(
            ProgressItem(
                project_id=1,
                progress_group_id=group.id,
                name="Đi ống nổi",
                unit="mét",
                created_by_id=1,
            )
        )
        with pytest.raises(IntegrityError):
            db.session.commit()


@pytest.mark.parametrize(
    ("planned_quantity", "opening_quantity"),
    [(-1, 0), (0, -1)],
)
def test_progress_item_rejects_negative_planned_or_opening_quantity(app, planned_quantity, opening_quantity):
    with app.app_context():
        _, group, _ = _progress_tree()
        db.session.add(
            ProgressItem(
                project_id=1,
                progress_group_id=group.id,
                name="Hạng mục khác",
                unit="cái",
                planned_quantity=planned_quantity,
                opening_quantity=opening_quantity,
                created_by_id=1,
            )
        )
        with pytest.raises(IntegrityError):
            db.session.commit()


def test_progress_type_value_mode_only_accepts_quantity_or_money(app):
    with app.app_context():
        db.session.add(ProgressType(project_id=1, name="Không hợp lệ", value_mode="hours", created_by_id=1))

        with pytest.raises(IntegrityError):
            db.session.commit()


def test_progress_structure_models_have_no_archive_state():
    assert "is_active" not in ProgressType.__table__.columns
    assert "is_active" not in ProgressGroup.__table__.columns
    assert "is_active" not in ProgressItem.__table__.columns


def test_existing_zero_order_items_keep_creation_order_after_an_update(app):
    """SQLite cannot reproduce PostgreSQL heap order, so assert the ORM ordering contract."""
    with app.app_context():
        _, group, first_item = _progress_tree()
        second_item = ProgressItem(
            project_id=1,
            progress_group_id=group.id,
            name="Hạng mục thứ hai",
            unit="mét",
            created_by_id=1,
        )
        third_item = ProgressItem(
            project_id=1,
            progress_group_id=group.id,
            name="Hạng mục thứ ba",
            unit="mét",
            created_by_id=1,
        )
        db.session.add_all((second_item, third_item))
        db.session.commit()
        expected_ids = [first_item.id, second_item.id, third_item.id]

        assert [item.display_order for item in group.items] == [0, 0, 0]
        assert [item.id for item in group.items] == expected_ids

        second_item.planned_quantity = 200
        db.session.commit()
        db.session.expire_all()

        reloaded_group = db.session.get(ProgressGroup, group.id)
        assert [item.id for item in reloaded_group.items] == expected_ids


def test_existing_zero_order_groups_keep_creation_order_after_an_update(app):
    with app.app_context():
        progress_type, first_group, _ = _progress_tree()
        second_group = ProgressGroup(
            project_id=1,
            progress_type_id=progress_type.id,
            name="Khu vực thứ hai",
            created_by_id=1,
        )
        third_group = ProgressGroup(
            project_id=1,
            progress_type_id=progress_type.id,
            name="Khu vực thứ ba",
            created_by_id=1,
        )
        db.session.add_all((second_group, third_group))
        db.session.commit()
        expected_ids = [first_group.id, second_group.id, third_group.id]

        assert [group.display_order for group in progress_type.groups] == [0, 0, 0]
        assert [group.id for group in progress_type.groups] == expected_ids

        second_group.note = "Đã cập nhật"
        db.session.commit()
        db.session.expire_all()

        reloaded_type = db.session.get(ProgressType, progress_type.id)
        assert [group.id for group in reloaded_type.groups] == expected_ids


@pytest.mark.parametrize("decimal_places", [-1, 4])
def test_progress_item_decimal_places_must_be_between_zero_and_three(app, decimal_places):
    with app.app_context():
        _, group, _ = _progress_tree()
        db.session.add(
            ProgressItem(
                project_id=1,
                progress_group_id=group.id,
                name=f"Hạng mục {decimal_places}",
                unit="mét",
                decimal_places=decimal_places,
                created_by_id=1,
            )
        )
        with pytest.raises(IntegrityError):
            db.session.commit()


@pytest.mark.parametrize(
    ("planned_start_date", "planned_end_date"),
    [
        (date(2026, 8, 1), None),
        (None, date(2026, 8, 2)),
    ],
)
def test_progress_item_database_rejects_unpaired_planned_dates(app, planned_start_date, planned_end_date):
    with app.app_context():
        _, group, _ = _progress_tree()
        db.session.add(
            ProgressItem(
                project_id=1,
                progress_group_id=group.id,
                name="Hạng mục khai ngày lẻ",
                unit="mét",
                planned_start_date=planned_start_date,
                planned_end_date=planned_end_date,
                created_by_id=1,
            )
        )

        with pytest.raises(IntegrityError):
            db.session.commit()


def test_progress_item_database_rejects_reversed_planned_dates(app):
    with app.app_context():
        _, group, _ = _progress_tree()
        db.session.add(
            ProgressItem(
                project_id=1,
                progress_group_id=group.id,
                name="Hạng mục đảo ngày",
                unit="mét",
                planned_start_date=date(2026, 8, 2),
                planned_end_date=date(2026, 8, 1),
                created_by_id=1,
            )
        )

        with pytest.raises(IntegrityError):
            db.session.commit()


def test_progress_item_database_allows_valid_planned_dates(app):
    with app.app_context():
        _, group, _ = _progress_tree()
        item = ProgressItem(
            project_id=1,
            progress_group_id=group.id,
            name="Hạng mục khai ngày hợp lệ",
            unit="mét",
            planned_start_date=date(2026, 8, 1),
            planned_end_date=date(2026, 8, 31),
            actual_start_date=date(2026, 8, 2),
            created_by_id=1,
        )
        db.session.add(item)
        db.session.commit()

        assert item.planned_start_date == date(2026, 8, 1)
        assert item.planned_end_date == date(2026, 8, 31)
        assert item.actual_start_date == date(2026, 8, 2)


def test_progress_item_database_allows_all_gantt_dates_empty(app):
    with app.app_context():
        _, group, _ = _progress_tree()
        item = ProgressItem(
            project_id=1,
            progress_group_id=group.id,
            name="Hạng mục chưa khai ngày",
            unit="mét",
            created_by_id=1,
        )
        db.session.add(item)
        db.session.commit()

        assert item.planned_start_date is None
        assert item.planned_end_date is None
        assert item.actual_start_date is None
