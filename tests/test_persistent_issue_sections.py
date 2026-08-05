from datetime import date, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import PersistentIssue, PersistentIssueSection


def make_issue(issue_id, project_id=1):
    return PersistentIssue(
        id=issue_id,
        project_id=project_id,
        title=f"Issue {issue_id}",
        severity="MEDIUM",
        status="OPEN",
        opened_date=date(2026, 8, 5),
        created_by_user_id=3,
    )


def make_section(issue_id, category_id, sort_order=0):
    return PersistentIssueSection(
        persistent_issue_id=issue_id,
        report_category_id=category_id,
        severity="MEDIUM",
        status="OPEN",
        sort_order=sort_order,
        created_by_id=3,
    )


def test_issue_accepts_sections_for_distinct_categories(app):
    with app.app_context():
        issue = make_issue(1001)
        db.session.add(issue)
        db.session.add_all([make_section(issue.id, 1), make_section(issue.id, 2)])
        db.session.commit()

        assert [section.report_category_id for section in issue.sections] == [1, 2]


def test_issue_rejects_duplicate_category_at_database_layer(app):
    with app.app_context():
        issue = make_issue(1002)
        db.session.add(issue)
        db.session.add_all([make_section(issue.id, 1), make_section(issue.id, 1, sort_order=1)])

        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_different_issues_may_use_the_same_category(app):
    with app.app_context():
        db.session.add_all([make_issue(1003), make_issue(1004)])
        db.session.add_all([make_section(1003, 1), make_section(1004, 1)])
        db.session.commit()

        assert PersistentIssueSection.query.filter_by(report_category_id=1).count() == 2


def test_issue_sections_are_ordered_by_sort_order_then_id_after_update(app):
    with app.app_context():
        issue = make_issue(1005)
        db.session.add(issue)
        db.session.flush()
        first = make_section(issue.id, 1, sort_order=1)
        second = make_section(issue.id, 2, sort_order=1)
        db.session.add_all([first, second])
        db.session.commit()

        second.sort_order = 0
        db.session.commit()
        db.session.expire(issue, ["sections"])

        assert [section.id for section in issue.sections] == [second.id, first.id]


def test_soft_deleted_section_is_hidden_from_active_issue_sections(app):
    with app.app_context():
        issue = make_issue(1006)
        db.session.add(issue)
        db.session.flush()
        active = make_section(issue.id, 1)
        deleted = make_section(issue.id, 2, sort_order=1)
        db.session.add_all([active, deleted])
        db.session.commit()

        deleted.deleted_at = datetime.utcnow()
        db.session.commit()
        db.session.expire(issue, ["sections"])

        assert [section.id for section in issue.sections] == [active.id]
        assert db.session.get(PersistentIssueSection, deleted.id).deleted_at is not None
