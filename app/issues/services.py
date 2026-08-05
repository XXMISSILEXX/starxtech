from datetime import date, datetime
from types import SimpleNamespace

from flask_login import current_user

from app.admin.services import add_with_sqlite_id, audit
from app.date_utils import local_today, parse_iso_date
from app.extensions import db
from app.models import (
    IssueSeverity,
    IssueStatus,
    PersistentIssue,
    PersistentIssueSection,
    Project,
    ProjectUser,
    User,
)
from app.project_memberships import accessible_project_ids


class IssueValidationError(ValueError):
    def __init__(self, message, errors=None):
        super().__init__(message)
        self.errors = errors or {}


def recalculate_issue_rollup(issue):
    """Recalculate the stored rollup fields from active issue sections.

    The caller owns the surrounding transaction and commits it when appropriate.
    PostgreSQL locks the issue row so concurrent edits to separate sections do not
    overwrite each other's rollup calculation.
    """
    if db.engine.dialect.name == "postgresql":
        issue = PersistentIssue.query.filter_by(id=issue.id).with_for_update().one()

    sections = (
        PersistentIssueSection.query.filter(
            PersistentIssueSection.persistent_issue_id == issue.id,
            PersistentIssueSection.deleted_at.is_(None),
        )
        .order_by(PersistentIssueSection.sort_order, PersistentIssueSection.id)
        .all()
    )
    statuses = {section.status for section in sections}
    completed_statuses = {IssueStatus.RESOLVED.value, IssueStatus.CLOSED.value}
    open_statuses = {IssueStatus.OPEN.value, IssueStatus.PROCESSING.value}

    if not sections:
        issue.status = IssueStatus.OPEN.value
    elif statuses <= completed_statuses:
        issue.status = IssueStatus.CLOSED.value
    elif IssueStatus.PROCESSING.value in statuses:
        issue.status = IssueStatus.PROCESSING.value
    else:
        issue.status = IssueStatus.OPEN.value

    due_dates = [
        section.due_date
        for section in sections
        if section.status in open_statuses and section.due_date is not None
    ]
    issue.due_date = min(due_dates) if due_dates else None

    if issue.status == IssueStatus.CLOSED.value:
        if issue.closed_date is None:
            issue.closed_date = local_today()
    else:
        issue.closed_date = None

    return issue


def project_issues_query(project_id):
    return PersistentIssue.query.filter(
        PersistentIssue.project_id == project_id,
        PersistentIssue.deleted_at.is_(None),
    ).order_by(PersistentIssue.opened_date.desc(), PersistentIssue.id.desc())


def issue_viewable_projects_query(actor=None):
    """Active project scope for the global issue index and its filters."""
    actor = actor or current_user
    query = Project.query.filter(Project.deleted_at.is_(None), Project.status == "active")
    project_ids = accessible_project_ids(actor, ("can_view_issues",))
    if project_ids is not None:
        query = query.filter(Project.id.in_(project_ids or [0]))
    return query


def owner_choices(project_id):
    return (
        User.query.join(ProjectUser, ProjectUser.user_id == User.id)
        .filter(
            ProjectUser.project_id == project_id,
            ProjectUser.is_active.is_(True),
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
        .order_by(User.full_name.asc())
        .all()
    )


def create_issue(project, form):
    validate_issue_form(form)
    issue = PersistentIssue(project_id=project.id, created_by_user_id=current_user.id)
    _assign_issue_fields(issue, form, project.id)
    add_with_sqlite_id(issue)
    db.session.commit()
    return issue


def update_issue(issue, form):
    validate_issue_form(form)
    old_values = issue_snapshot(issue)
    _assign_issue_fields(issue, form, issue.project_id)
    if issue.status in {IssueStatus.CLOSED.value, IssueStatus.RESOLVED.value} and not issue.closed_date:
        issue.closed_date = local_today()
    if issue.status in {IssueStatus.OPEN.value, IssueStatus.PROCESSING.value}:
        issue.closed_date = None
    audit("issue.update", "PersistentIssue", issue.id, old_values, issue_snapshot(issue))
    db.session.commit()
    return issue


def close_issue(issue):
    old_values = issue_snapshot(issue)
    issue.status = IssueStatus.CLOSED.value
    issue.closed_date = local_today()
    audit("issue.close", "PersistentIssue", issue.id, old_values, issue_snapshot(issue))
    db.session.commit()


def reopen_issue(issue):
    old_values = issue_snapshot(issue)
    issue.status = IssueStatus.OPEN.value
    issue.closed_date = None
    audit("issue.reopen", "PersistentIssue", issue.id, old_values, issue_snapshot(issue))
    db.session.commit()


def delete_issue(issue):
    old_values = issue_snapshot(issue)
    issue.deleted_at = db.func.now()
    audit("issue.delete", "PersistentIssue", issue.id, old_values, {"deleted_at": True})
    db.session.commit()


def issue_snapshot(issue):
    return {
        "project_id": issue.project_id,
        "title": issue.title,
        "description": issue.description,
        "severity": issue.severity,
        "status": issue.status,
        "opened_date": issue.opened_date.isoformat() if issue.opened_date else None,
        "due_date": issue.due_date.isoformat() if issue.due_date else None,
        "closed_date": issue.closed_date.isoformat() if issue.closed_date else None,
        "owner_user_id": issue.owner_user_id,
    }


def _assign_issue_fields(issue, form, project_id):
    title = form.get("title", "").strip()
    severity = form.get("severity", "").strip()
    status = form.get("status", "").strip()
    opened_date = _parse_required_date(form.get("opened_date", "").strip(), "Ngày mở")
    due_date = _parse_optional_date(form.get("due_date", "").strip(), "Hạn xử lý")
    owner_user_id = _parse_owner(form.get("owner_user_id", "").strip(), project_id)

    if not title:
        raise IssueValidationError("Vui lòng nhập tiêu đề.", {"title": "Vui lòng nhập tiêu đề."})
    if severity not in [item.value for item in IssueSeverity]:
        raise IssueValidationError("Vui lòng chọn mức độ.", {"severity": "Vui lòng chọn mức độ."})
    if status not in [item.value for item in IssueStatus]:
        raise IssueValidationError("Vui lòng chọn trạng thái.", {"status": "Vui lòng chọn trạng thái."})
    if due_date and due_date < opened_date:
        raise IssueValidationError("Ngày hạn xử lý không được trước ngày mở.", {"due_date": "Ngày hạn xử lý không được trước ngày mở."})

    issue.title = title
    issue.description = form.get("description", "").strip() or None
    issue.severity = severity
    issue.status = status
    issue.opened_date = opened_date
    issue.due_date = due_date
    issue.owner_user_id = owner_user_id


def _parse_required_date(value, label):
    if not value:
        raise IssueValidationError(f"Vui lòng chọn {label.lower()}.", {"opened_date": f"Vui lòng chọn {label.lower()}."})
    return _parse_date(value, label)


def _parse_optional_date(value, label):
    if not value:
        return None
    return _parse_date(value, label)


def _parse_date(value, label):
    try:
        return parse_iso_date(value, field_label=label, allow_empty=False)
    except ValueError as exc:
        raise IssueValidationError(str(exc)) from exc


def _parse_owner(value, project_id):
    if not value:
        return None
    try:
        owner_user_id = int(value)
    except ValueError as exc:
        raise IssueValidationError("Người phụ trách không hợp lệ.") from exc

    valid_owner = (
        ProjectUser.query.join(User, User.id == ProjectUser.user_id)
        .filter(
            ProjectUser.project_id == project_id,
            ProjectUser.user_id == owner_user_id,
            ProjectUser.is_active.is_(True),
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
        .first()
    )
    if not valid_owner:
        raise IssueValidationError("Người phụ trách phải đang hoạt động và được gán vào dự án này.")
    return owner_user_id


def validate_issue_form(form):
    errors = {}
    title = form.get("title", "").strip()
    severity = form.get("severity", "").strip()
    status = form.get("status", "").strip()
    opened_date_raw = form.get("opened_date", "").strip()
    due_date_raw = form.get("due_date", "").strip()

    if not title:
        errors["title"] = "Vui lòng nhập tiêu đề."
    if severity not in [item.value for item in IssueSeverity]:
        errors["severity"] = "Vui lòng chọn mức độ."
    if status not in [item.value for item in IssueStatus]:
        errors["status"] = "Vui lòng chọn trạng thái."

    opened_date = None
    due_date = None
    if not opened_date_raw:
        errors["opened_date"] = "Vui lòng chọn ngày mở."
    else:
        try:
            opened_date = parse_iso_date(opened_date_raw, field_label="Ngày mở", allow_empty=False)
        except ValueError as exc:
            errors["opened_date"] = str(exc)

    if due_date_raw:
        try:
            due_date = parse_iso_date(due_date_raw, field_label="Hạn xử lý", allow_empty=False)
        except ValueError as exc:
            errors["due_date"] = str(exc)

    if opened_date and due_date and due_date < opened_date:
        errors["due_date"] = "Ngày hạn xử lý không được trước ngày mở."

    if errors:
        first_message = next(iter(errors.values()))
        raise IssueValidationError(first_message, errors)


def build_issue_form_data(form, project_id=None):
    return SimpleNamespace(
        id=None,
        project_id=project_id,
        title=form.get("title", ""),
        description=form.get("description", ""),
        severity=form.get("severity", ""),
        status=form.get("status", ""),
        opened_date=form.get("opened_date", ""),
        due_date=form.get("due_date", ""),
        owner_user_id=int(form.get("owner_user_id")) if form.get("owner_user_id", "").isdigit() else None,
    )
