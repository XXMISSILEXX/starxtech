from datetime import date

import pytest

from app.date_utils import local_today
from app.extensions import db
from app.issues import services
from app.models import PersistentIssue, PersistentIssueSection


def make_issue(*, status="OPEN", due_date=None, closed_date=None, severity="MEDIUM"):
    issue = PersistentIssue(
        id=2001,
        project_id=1,
        title="Rollup issue",
        severity=severity,
        status=status,
        opened_date=date(2026, 8, 5),
        due_date=due_date,
        closed_date=closed_date,
        created_by_user_id=3,
    )
    db.session.add(issue)
    db.session.commit()
    return issue


def add_sections(issue, values):
    for category_id, status, due_date in values:
        db.session.add(
            PersistentIssueSection(
                persistent_issue_id=issue.id,
                report_category_id=category_id,
                severity="CRITICAL",
                status=status,
                due_date=due_date,
                created_by_id=3,
            )
        )
    db.session.commit()


def recalculate_and_commit(issue):
    result = services.recalculate_issue_rollup(issue)
    db.session.commit()
    return result


def test_rollup_without_sections_is_open(app):
    with app.app_context():
        issue = make_issue(status="PROCESSING", due_date=date(2026, 8, 9), closed_date=date(2026, 8, 1))

        recalculate_and_commit(issue)

        assert (issue.status, issue.due_date, issue.closed_date) == ("OPEN", None, None)


def test_rollup_one_open_section_is_open(app):
    with app.app_context():
        issue = make_issue()
        add_sections(issue, [(1, "OPEN", None)])

        assert recalculate_and_commit(issue).status == "OPEN"


def test_rollup_one_processing_section_is_processing(app):
    with app.app_context():
        issue = make_issue()
        add_sections(issue, [(1, "PROCESSING", None)])

        assert recalculate_and_commit(issue).status == "PROCESSING"


def test_rollup_open_and_closed_sections_is_open(app):
    with app.app_context():
        issue = make_issue()
        add_sections(issue, [(1, "OPEN", None), (2, "CLOSED", None)])

        assert recalculate_and_commit(issue).status == "OPEN"


def test_rollup_processing_and_closed_sections_is_processing(app):
    with app.app_context():
        issue = make_issue()
        add_sections(issue, [(1, "PROCESSING", None), (2, "CLOSED", None)])

        assert recalculate_and_commit(issue).status == "PROCESSING"


def test_rollup_all_closed_sections_is_closed(app, monkeypatch):
    with app.app_context():
        monkeypatch.setattr(services, "local_today", lambda: date(2026, 8, 5))
        issue = make_issue()
        add_sections(issue, [(1, "CLOSED", None), (2, "CLOSED", None)])

        result = recalculate_and_commit(issue)

        assert (result.status, result.closed_date) == ("CLOSED", date(2026, 8, 5))


def test_rollup_all_resolved_sections_is_closed(app):
    with app.app_context():
        issue = make_issue()
        add_sections(issue, [(1, "RESOLVED", None), (2, "RESOLVED", None)])

        assert recalculate_and_commit(issue).status == "CLOSED"


def test_rollup_resolved_and_closed_sections_is_closed(app):
    with app.app_context():
        issue = make_issue()
        add_sections(issue, [(1, "RESOLVED", None), (2, "CLOSED", None)])

        assert recalculate_and_commit(issue).status == "CLOSED"


def test_rollup_uses_earliest_due_date_from_open_sections(app):
    with app.app_context():
        issue = make_issue()
        add_sections(
            issue,
            [
                (1, "OPEN", date(2026, 8, 20)),
                (2, "PROCESSING", date(2026, 8, 10)),
                (3, "OPEN", date(2026, 8, 15)),
            ],
        )

        assert recalculate_and_commit(issue).due_date == date(2026, 8, 10)


def test_rollup_ignores_due_date_of_closed_section(app):
    with app.app_context():
        issue = make_issue()
        add_sections(
            issue,
            [(1, "CLOSED", date(2026, 8, 1)), (2, "OPEN", date(2026, 8, 10))],
        )

        assert recalculate_and_commit(issue).due_date == date(2026, 8, 10)


def test_rollup_returns_no_due_date_when_open_sections_have_no_due_date(app):
    with app.app_context():
        issue = make_issue(due_date=date(2026, 8, 1))
        add_sections(issue, [(1, "OPEN", None), (2, "PROCESSING", None)])

        assert recalculate_and_commit(issue).due_date is None


def test_rollup_returns_no_due_date_when_all_sections_are_closed(app):
    with app.app_context():
        issue = make_issue(due_date=date(2026, 8, 1))
        add_sections(issue, [(1, "CLOSED", date(2026, 8, 2)), (2, "RESOLVED", date(2026, 8, 3))])

        assert recalculate_and_commit(issue).due_date is None


def test_rollup_sets_closed_date_when_last_section_closes(app, monkeypatch):
    with app.app_context():
        monkeypatch.setattr(services, "local_today", lambda: date(2026, 8, 5))
        issue = make_issue()
        add_sections(issue, [(1, "CLOSED", None)])

        assert recalculate_and_commit(issue).closed_date == date(2026, 8, 5)


def test_rollup_clears_closed_date_when_section_reopens(app):
    with app.app_context():
        issue = make_issue(status="CLOSED", closed_date=date(2026, 8, 1))
        add_sections(issue, [(1, "CLOSED", None)])
        section = PersistentIssueSection.query.filter_by(persistent_issue_id=issue.id).one()
        section.status = "OPEN"
        db.session.commit()

        assert recalculate_and_commit(issue).closed_date is None


def test_rollup_keeps_existing_closed_date(app):
    with app.app_context():
        closed_date = date(2026, 8, 1)
        issue = make_issue(status="CLOSED", closed_date=closed_date)
        add_sections(issue, [(1, "CLOSED", None)])

        assert recalculate_and_commit(issue).closed_date == closed_date


def test_rollup_ignores_soft_deleted_open_section(app):
    with app.app_context():
        issue = make_issue()
        add_sections(issue, [(1, "OPEN", None), (2, "CLOSED", None)])
        open_section = PersistentIssueSection.query.filter_by(
            persistent_issue_id=issue.id,
            report_category_id=1,
        ).one()
        open_section.deleted_at = db.func.now()
        db.session.commit()

        assert recalculate_and_commit(issue).status == "CLOSED"


def test_rollup_with_all_sections_soft_deleted_is_open(app):
    with app.app_context():
        issue = make_issue(status="PROCESSING")
        add_sections(issue, [(1, "OPEN", None), (2, "CLOSED", None)])
        for section in PersistentIssueSection.query.filter_by(persistent_issue_id=issue.id):
            section.deleted_at = db.func.now()
        db.session.commit()

        assert recalculate_and_commit(issue).status == "OPEN"


def test_rollup_never_changes_manual_issue_severity(app):
    with app.app_context():
        issue = make_issue(severity="LOW")
        add_sections(issue, [(1, "OPEN", None)])
        section = PersistentIssueSection.query.filter_by(persistent_issue_id=issue.id).one()

        for status in ("OPEN", "PROCESSING", "RESOLVED", "CLOSED"):
            section.status = status
            recalculate_and_commit(issue)
            assert issue.severity == "LOW"


def test_rollup_does_not_commit(app):
    with app.app_context():
        issue = make_issue(status="PROCESSING", due_date=date(2026, 8, 9))
        add_sections(issue, [(1, "OPEN", date(2026, 8, 10))])

        services.recalculate_issue_rollup(issue)
        db.session.rollback()
        db.session.expire_all()
        persisted_issue = db.session.get(PersistentIssue, issue.id)

        assert (persisted_issue.status, persisted_issue.due_date) == ("PROCESSING", date(2026, 8, 9))
