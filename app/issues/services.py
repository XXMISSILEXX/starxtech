from datetime import date, datetime

from flask_login import current_user

from app.admin.services import add_with_sqlite_id, audit
from app.extensions import db
from app.models import IssueSeverity, IssueStatus, PersistentIssue, ProjectUser, User, UserRole


class IssueValidationError(ValueError):
    pass


def project_issues_query(project_id):
    return PersistentIssue.query.filter(
        PersistentIssue.project_id == project_id,
        PersistentIssue.deleted_at.is_(None),
    ).order_by(PersistentIssue.opened_date.desc(), PersistentIssue.id.desc())


def owner_choices(project_id):
    return (
        User.query.join(ProjectUser, ProjectUser.user_id == User.id)
        .filter(
            ProjectUser.project_id == project_id,
            User.role.in_([UserRole.REPORTER.value, UserRole.PROJECT_MANAGER.value]),
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
        .order_by(User.full_name.asc())
        .all()
    )


def create_issue(project, form):
    issue = PersistentIssue(project_id=project.id, created_by_user_id=current_user.id)
    _assign_issue_fields(issue, form, project.id)
    add_with_sqlite_id(issue)
    audit("issue.create", "PersistentIssue", issue.id, new_values=issue_snapshot(issue))
    db.session.commit()
    return issue


def update_issue(issue, form):
    old_values = issue_snapshot(issue)
    _assign_issue_fields(issue, form, issue.project_id)
    if issue.status in {IssueStatus.CLOSED.value, IssueStatus.RESOLVED.value} and not issue.closed_date:
        issue.closed_date = date.today()
    if issue.status in {IssueStatus.OPEN.value, IssueStatus.PROCESSING.value}:
        issue.closed_date = None
    audit("issue.update", "PersistentIssue", issue.id, old_values, issue_snapshot(issue))
    db.session.commit()
    return issue


def close_issue(issue):
    old_values = issue_snapshot(issue)
    issue.status = IssueStatus.CLOSED.value
    issue.closed_date = date.today()
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
        raise IssueValidationError("Tiêu đề là bắt buộc.")
    if severity not in [item.value for item in IssueSeverity]:
        raise IssueValidationError("Mức độ vấn đề không hợp lệ.")
    if status not in [item.value for item in IssueStatus]:
        raise IssueValidationError("Trạng thái vấn đề không hợp lệ.")
    if due_date and due_date < opened_date:
        raise IssueValidationError("Ngày hạn xử lý không được trước ngày mở.")

    issue.title = title
    issue.description = form.get("description", "").strip() or None
    issue.severity = severity
    issue.status = status
    issue.opened_date = opened_date
    issue.due_date = due_date
    issue.owner_user_id = owner_user_id


def _parse_required_date(value, label):
    if not value:
        raise IssueValidationError(f"{label} là bắt buộc.")
    return _parse_date(value, label)


def _parse_optional_date(value, label):
    if not value:
        return None
    return _parse_date(value, label)


def _parse_date(value, label):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise IssueValidationError(f"{label} phải đúng định dạng YYYY-MM-DD.") from exc


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
            User.role.in_([UserRole.REPORTER.value, UserRole.PROJECT_MANAGER.value]),
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
        .first()
    )
    if not valid_owner:
        raise IssueValidationError("Người phụ trách phải đang hoạt động và được gán vào dự án này.")
    return owner_user_id
