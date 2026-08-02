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
