from datetime import date
from types import SimpleNamespace

from flask_login import current_user
from sqlalchemy import exists
from sqlalchemy.orm import joinedload

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
    ReportCategory,
    User,
)
from app.project_memberships import accessible_project_ids
from app.ui import issue_severity_label, issue_status_label


class IssueValidationError(ValueError):
    def __init__(self, message, errors=None):
        super().__init__(message)
        self.errors = errors or {}


ISSUE_LIST_PER_PAGE = 20
OPEN_SECTION_STATUSES = (IssueStatus.OPEN.value, IssueStatus.PROCESSING.value)


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
    elif statuses <= {IssueStatus.CLOSED.value}:
        issue.status = IssueStatus.CLOSED.value
    elif statuses <= completed_statuses:
        issue.status = IssueStatus.RESOLVED.value
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


def issue_list_state(project_ids, source=None):
    """Parse URL-backed issue filters and choices scoped to visible projects."""
    source = source or {}
    project_ids = list(project_ids)
    state = {
        "severity": source.get("severity", ""),
        "status": source.get("status", ""),
        "date_from": source.get("date_from", ""),
        "date_to": source.get("date_to", ""),
        "category_id": source.get("category_id", ""),
        "owner_user_id": source.get("owner_user_id", ""),
        "show_closed": source.get("show_closed", "0") == "1",
        "page": source.get("page", 1),
        "errors": [],
        "severities": [severity.value for severity in IssueSeverity],
        "statuses": [status.value for status in IssueStatus],
    }
    state["categories"] = _issue_filter_categories(project_ids)
    state["owners"] = _issue_filter_owners(project_ids)

    if state["severity"] and state["severity"] not in state["severities"]:
        state["errors"].append("Mức độ không hợp lệ.")
        state["severity_value"] = None
    else:
        state["severity_value"] = state["severity"] or None
    if state["status"] and state["status"] not in state["statuses"]:
        state["errors"].append("Trạng thái không hợp lệ.")
        state["status_value"] = None
    else:
        state["status_value"] = state["status"] or None

    try:
        state["date_from_value"] = parse_iso_date(state["date_from"], field_label="Từ ngày")
        state["date_to_value"] = parse_iso_date(state["date_to"], field_label="Đến ngày")
    except ValueError as exc:
        state["errors"].append(str(exc))
        state["date_from_value"] = state["date_to_value"] = None
    if state["date_from_value"] and state["date_to_value"] and state["date_from_value"] > state["date_to_value"]:
        state["errors"].append("Từ ngày không được lớn hơn đến ngày.")

    state["category_id_value"] = _filter_choice_id(
        state["category_id"],
        {category.id for category, _project in state["categories"]},
        "Loại hạng mục không hợp lệ.",
        state["errors"],
    )
    state["owner_user_id_value"] = _filter_choice_id(
        state["owner_user_id"],
        {owner.id for owner in state["owners"]},
        "Người phụ trách hạng mục không hợp lệ.",
        state["errors"],
    )
    try:
        state["page"] = max(1, int(state["page"]))
    except ValueError:
        state["page"] = 1
    state["has_explicit_filters"] = any(
        state[key]
        for key in ("severity", "status", "date_from", "date_to", "category_id", "owner_user_id")
    )
    return state


def apply_issue_filters(query, state, *, include_closed=False):
    """Apply one AND-combined filter set without joining issue sections."""
    if state["severity_value"]:
        query = query.filter(PersistentIssue.severity == state["severity_value"])
    if state["status_value"]:
        query = query.filter(PersistentIssue.status == state["status_value"])
    if state["date_from_value"]:
        query = query.filter(PersistentIssue.opened_date >= state["date_from_value"])
    if state["date_to_value"]:
        query = query.filter(PersistentIssue.opened_date <= state["date_to_value"])
    if state["category_id_value"] is not None or state["owner_user_id_value"] is not None:
        section_query = exists().where(
            PersistentIssueSection.persistent_issue_id == PersistentIssue.id,
            PersistentIssueSection.deleted_at.is_(None),
            PersistentIssueSection.status.in_(OPEN_SECTION_STATUSES),
        )
        if state["category_id_value"] is not None:
            section_query = section_query.where(
                PersistentIssueSection.report_category_id == state["category_id_value"]
            )
        if state["owner_user_id_value"] is not None:
            section_query = section_query.where(
                PersistentIssueSection.owner_user_id == state["owner_user_id_value"]
            )
        query = query.filter(section_query)
    if not include_closed and not state["show_closed"]:
        query = query.filter(PersistentIssue.status != IssueStatus.CLOSED.value)
    return query


def issue_list_page(query, page, per_page=ISSUE_LIST_PER_PAGE):
    """Count and fetch a stable, project-loaded page of persistent issues."""
    total = query.order_by(None).count()
    issues = query.options(joinedload(PersistentIssue.project)).order_by(None).order_by(
        PersistentIssue.opened_date.desc(),
        PersistentIssue.id.desc(),
    ).offset((page - 1) * per_page).limit(per_page).all()
    return issues, total


def filtered_issue_list(query, state):
    """Return one filtered page and the number of closed rows hidden from it."""
    if state["errors"]:
        return [], 0, 0

    query_with_closed = apply_issue_filters(query, state, include_closed=True)
    hidden_closed_total = 0
    if not state["show_closed"]:
        hidden_closed_total = query_with_closed.filter(
            PersistentIssue.status == IssueStatus.CLOSED.value
        ).order_by(None).count()
    visible_query = apply_issue_filters(query, state)
    issues, total = issue_list_page(visible_query, state["page"])
    return issues, total, hidden_closed_total


def _issue_filter_categories(project_ids):
    if not project_ids:
        return []
    return (
        db.session.query(ReportCategory, Project)
        .join(Project, Project.id == ReportCategory.project_id)
        .filter(
            ReportCategory.project_id.in_(project_ids),
            ReportCategory.deleted_at.is_(None),
        )
        .order_by(Project.code.asc(), ReportCategory.sort_order.asc(), ReportCategory.id.asc())
        .all()
    )


def _issue_filter_owners(project_ids):
    if not project_ids:
        return []
    return (
        User.query.join(PersistentIssueSection, PersistentIssueSection.owner_user_id == User.id)
        .join(PersistentIssue, PersistentIssue.id == PersistentIssueSection.persistent_issue_id)
        .filter(
            PersistentIssue.project_id.in_(project_ids),
            PersistentIssue.deleted_at.is_(None),
            PersistentIssueSection.deleted_at.is_(None),
        )
        .distinct()
        .order_by(User.full_name.asc(), User.id.asc())
        .all()
    )


def _filter_choice_id(raw_value, valid_ids, error_message, errors):
    if not raw_value:
        return None
    try:
        value = int(raw_value)
    except ValueError:
        errors.append(error_message)
        return None
    if value not in valid_ids:
        errors.append(error_message)
        return None
    return value


def issue_list_context(issues, *, project, can_create, create_url, actor=None):
    """Build shared list-template context without per-issue section queries."""
    from app.auth.permissions import (
        can_delete_persistent_issue,
        can_edit_persistent_issue,
    )

    actor = actor or current_user
    issue_ids = [issue.id for issue in issues]
    section_counts = {}
    if issue_ids:
        section_counts = dict(
            db.session.query(
                PersistentIssueSection.persistent_issue_id,
                db.func.count(PersistentIssueSection.id),
            )
            .filter(
                PersistentIssueSection.persistent_issue_id.in_(issue_ids),
                PersistentIssueSection.deleted_at.is_(None),
            )
            .group_by(PersistentIssueSection.persistent_issue_id)
            .all()
        )
    for issue in issues:
        issue.section_count = section_counts.get(issue.id, 0)

    return {
        "issues": issues,
        "project": project,
        "can_write": False,
        "can_delete": False,
        "can_create": can_create,
        "create_url": create_url,
        "can_edit_by_issue": {issue.id: can_edit_persistent_issue(issue, actor) for issue in issues},
        "can_delete_by_issue": {issue.id: can_delete_persistent_issue(issue, actor) for issue in issues},
    }


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


def issue_form_context(project_id, issue=None, submitted_sections=None):
    """Context shared by both persistent-issue form entry points."""
    used_ids = set()
    if issue is not None and issue.id is not None:
        used_ids.update(
            section.report_category_id
            for section in issue_sections(issue)
        )
    for section in submitted_sections or []:
        if section.report_category_id is not None:
            used_ids.add(section.report_category_id)

    categories = ReportCategory.query.filter(
        ReportCategory.project_id == project_id,
        ReportCategory.deleted_at.is_(None),
        (ReportCategory.is_active.is_(True)) | (ReportCategory.id.in_(used_ids or [0])),
    ).order_by(ReportCategory.sort_order.asc(), ReportCategory.id.asc()).all()
    active_categories = [category for category in categories if category.is_active]
    return {
        "categories": categories,
        "active_categories": active_categories,
        "owners": owner_choices(project_id),
        "severities": [severity.value for severity in IssueSeverity],
        "section_statuses": [status.value for status in IssueStatus],
        "section_severity_options": [
            {"value": severity.value, "label": issue_severity_label(severity.value)}
            for severity in IssueSeverity
        ],
        "section_status_options": [
            {"value": status.value, "label": issue_status_label(status.value)}
            for status in IssueStatus
        ],
    }


def issue_sections(issue):
    if issue.id is None:
        return []
    return (
        PersistentIssueSection.query.filter(
            PersistentIssueSection.persistent_issue_id == issue.id,
            PersistentIssueSection.deleted_at.is_(None),
        )
        .order_by(PersistentIssueSection.sort_order, PersistentIssueSection.id)
        .all()
    )


def create_issue(project, form):
    validate_issue_form(form)
    section_inputs = parse_issue_sections(form, project.id)
    issue = PersistentIssue(project_id=project.id, created_by_user_id=current_user.id)
    _assign_issue_fields(issue, form, project.id)
    add_with_sqlite_id(issue)
    db.session.flush()
    replace_issue_sections(issue, section_inputs)
    recalculate_issue_rollup(issue)
    db.session.commit()
    return issue


def update_issue(issue, form):
    validate_issue_form(form)
    section_inputs = parse_issue_sections(form, issue.project_id)
    old_values = issue_snapshot(issue)
    _assign_issue_fields(issue, form, issue.project_id)
    replace_issue_sections(issue, section_inputs)
    issue = recalculate_issue_rollup(issue)
    new_values = issue_snapshot(issue)
    if _issue_editable_values_changed(old_values, new_values):
        audit("issue.update", "PersistentIssue", issue.id, old_values, new_values)
    db.session.commit()
    return issue


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
    }


def issue_section_snapshot(section):
    return {
        "report_category_id": section.report_category_id,
        "severity": section.severity,
        "status": section.status,
        "due_date": section.due_date.isoformat() if section.due_date else None,
        "owner_user_id": section.owner_user_id,
        "description": section.description,
        "proposed_solution": section.proposed_solution,
        "created_at": section.created_at.isoformat() if section.created_at else None,
        "created_by_id": section.created_by_id,
    }


def _issue_editable_values_changed(old_values, new_values):
    return any(
        old_values[field] != new_values[field]
        for field in ("title", "description", "severity", "opened_date")
    )


def _assign_issue_fields(issue, form, project_id):
    title = form.get("title", "").strip()
    severity = form.get("severity", "").strip()
    opened_date = _parse_required_date(form.get("opened_date", "").strip(), "Ngày mở")

    if not title:
        raise IssueValidationError("Vui lòng nhập tiêu đề.", {"title": "Vui lòng nhập tiêu đề."})
    if severity not in [item.value for item in IssueSeverity]:
        raise IssueValidationError("Vui lòng chọn mức độ.", {"severity": "Vui lòng chọn mức độ."})

    issue.title = title
    issue.description = form.get("description", "").strip() or None
    issue.severity = severity
    issue.opened_date = opened_date


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


def _parse_section_owner(value, project_id, field):
    if not value:
        return None
    try:
        owner_user_id = int(value)
    except ValueError as exc:
        raise IssueValidationError("Người phụ trách không hợp lệ.", {field: "Người phụ trách không hợp lệ."}) from exc

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
        raise IssueValidationError(
            "Người phụ trách phải đang hoạt động và được gán vào dự án này.",
            {field: "Người phụ trách phải đang hoạt động và được gán vào dự án này."},
        )
    return owner_user_id


def validate_issue_form(form):
    errors = {}
    title = form.get("title", "").strip()
    severity = form.get("severity", "").strip()
    opened_date_raw = form.get("opened_date", "").strip()

    if not title:
        errors["title"] = "Vui lòng nhập tiêu đề."
    if severity not in [item.value for item in IssueSeverity]:
        errors["severity"] = "Vui lòng chọn mức độ."

    opened_date = None
    if not opened_date_raw:
        errors["opened_date"] = "Vui lòng chọn ngày mở."
    else:
        try:
            opened_date = parse_iso_date(opened_date_raw, field_label="Ngày mở", allow_empty=False)
        except ValueError as exc:
            errors["opened_date"] = str(exc)

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
        opened_date=form.get("opened_date", ""),
        sections=_submitted_issue_sections(form),
    )


def parse_issue_sections(form, project_id):
    sections = []
    seen_categories = set()
    for index in _issue_section_indexes(form):
        category_raw = form.get(f"sections-{index}-category_id", "").strip()
        severity = form.get(f"sections-{index}-severity", "").strip()
        status = form.get(f"sections-{index}-status", "").strip()
        due_date_raw = form.get(f"sections-{index}-due_date", "").strip()
        owner_raw = form.get(f"sections-{index}-owner_user_id", "").strip()
        description = form.get(f"sections-{index}-description", "").strip()
        proposed_solution = form.get(f"sections-{index}-proposed_solution", "").strip()
        if not any((category_raw, severity, status, due_date_raw, owner_raw, description, proposed_solution)):
            continue
        category_field = f"sections-{index}-category_id"
        if not category_raw:
            raise IssueValidationError("Vui lòng chọn hạng mục.", {category_field: "Vui lòng chọn hạng mục."})
        try:
            category_id = int(category_raw)
        except ValueError as exc:
            raise IssueValidationError("Hạng mục không hợp lệ.", {category_field: "Hạng mục không hợp lệ."}) from exc
        if category_id in seen_categories:
            raise IssueValidationError(
                "Hạng mục không được trùng trong cùng vấn đề.",
                {category_field: "Hạng mục không được trùng trong cùng vấn đề."},
            )
        if severity not in [item.value for item in IssueSeverity]:
            raise IssueValidationError("Vui lòng chọn mức độ hạng mục.", {f"sections-{index}-severity": "Vui lòng chọn mức độ hạng mục."})
        if status not in [item.value for item in IssueStatus]:
            raise IssueValidationError("Vui lòng chọn trạng thái hạng mục.", {f"sections-{index}-status": "Vui lòng chọn trạng thái hạng mục."})
        seen_categories.add(category_id)
        sections.append(
            {
                "index": index,
                "section_id": _parse_optional_section_id(form.get(f"sections-{index}-section-id", ""), index),
                "report_category_id": category_id,
                "severity": severity,
                "status": status,
                "due_date": _parse_optional_date(due_date_raw, "Hạn xử lý"),
                "owner_user_id": _parse_section_owner(owner_raw, project_id, f"sections-{index}-owner_user_id"),
                "description": description or None,
                "proposed_solution": proposed_solution or None,
                "sort_order": len(sections),
            }
        )
    return sections


def replace_issue_sections(issue, section_inputs):
    existing_sections = {section.id: section for section in issue_sections(issue)}
    submitted_ids = [section["section_id"] for section in section_inputs if section["section_id"] is not None]
    if len(submitted_ids) != len(set(submitted_ids)):
        raise IssueValidationError("Một hạng mục được gửi nhiều lần.")
    unknown_ids = set(submitted_ids) - set(existing_sections)
    if unknown_ids:
        raise IssueValidationError("Hạng mục không thuộc vấn đề này.")
    _validate_section_close_reopen_permission(issue, section_inputs, existing_sections)
    _validate_issue_section_categories(issue, section_inputs, existing_sections)

    submitted_id_set = set(submitted_ids)
    for section in existing_sections.values():
        if section.id not in submitted_id_set:
            old_values = issue_section_snapshot(section)
            section.deleted_at = db.func.now()
            section.updated_by_id = current_user.id
            audit(
                "issue.section.delete",
                "PersistentIssueSection",
                section.id,
                old_values,
                {"deleted_at": True},
            )

    for section_input in section_inputs:
        section = existing_sections.get(section_input["section_id"])
        if section is None:
            section = PersistentIssueSection(
                persistent_issue_id=issue.id,
                created_by_id=current_user.id,
            )
            db.session.add(section)
        else:
            old_values = issue_section_snapshot(section)
            old_sort_order = section.sort_order
            section.updated_by_id = current_user.id
        section.deleted_at = None
        section.report_category_id = section_input["report_category_id"]
        section.severity = section_input["severity"]
        section.status = section_input["status"]
        section.due_date = section_input["due_date"]
        section.owner_user_id = section_input["owner_user_id"]
        section.description = section_input["description"]
        section.proposed_solution = section_input["proposed_solution"]
        section.sort_order = section_input["sort_order"]
        if section_input["section_id"] is not None:
            new_values = issue_section_snapshot(section)
            if old_values != new_values or old_sort_order != section.sort_order:
                audit(
                    _section_audit_action(old_values["status"], new_values["status"]),
                    "PersistentIssueSection",
                    section.id,
                    old_values,
                    new_values,
                )


def _validate_section_close_reopen_permission(issue, section_inputs, existing_sections):
    from app.auth.permissions import can_close_persistent_issue

    requires_close_reopen_permission = False
    for section_input in section_inputs:
        section_id = section_input["section_id"]
        old_status = existing_sections[section_id].status if section_id is not None else None
        if (old_status == IssueStatus.CLOSED.value) != (section_input["status"] == IssueStatus.CLOSED.value):
            requires_close_reopen_permission = True
            break
    if requires_close_reopen_permission and not can_close_persistent_issue(issue):
        raise IssueValidationError(
            "Bạn không có quyền đóng hoặc mở lại hạng mục.",
            {"sections": "Bạn không có quyền đóng hoặc mở lại hạng mục."},
        )


def _section_audit_action(old_status, new_status):
    if old_status != IssueStatus.CLOSED.value and new_status == IssueStatus.CLOSED.value:
        return "issue.section.close"
    if old_status == IssueStatus.CLOSED.value and new_status != IssueStatus.CLOSED.value:
        return "issue.section.reopen"
    return "issue.section.update"


def _validate_issue_section_categories(issue, section_inputs, existing_sections):
    category_ids = {section["report_category_id"] for section in section_inputs}
    if not category_ids:
        return
    categories = {
        category.id: category
        for category in ReportCategory.query.filter(
            ReportCategory.project_id == issue.project_id,
            ReportCategory.id.in_(category_ids),
            ReportCategory.deleted_at.is_(None),
        ).all()
    }
    if len(categories) != len(category_ids):
        raise IssueValidationError("Tất cả hạng mục phải thuộc dự án này.")
    existing_category_ids = {section.report_category_id for section in existing_sections.values()}
    for section_input in section_inputs:
        category = categories[section_input["report_category_id"]]
        if not category.is_active and section_input["report_category_id"] not in existing_category_ids:
            raise IssueValidationError(
                "Hạng mục đã ngừng hoạt động, không thể chọn mới.",
                {f"sections-{section_input['index']}-category_id": "Hạng mục đã ngừng hoạt động, không thể chọn mới."},
            )


def _parse_optional_section_id(value, index):
    value = str(value or "").strip()
    if not value:
        return None
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise IssueValidationError("Mã hạng mục không hợp lệ.", {f"sections-{index}-section-id": "Mã hạng mục không hợp lệ."}) from exc
    if result < 1:
        raise IssueValidationError("Mã hạng mục không hợp lệ.", {f"sections-{index}-section-id": "Mã hạng mục không hợp lệ."})
    return result


def _submitted_issue_sections(form):
    sections = []
    for sort_order, index in enumerate(_issue_section_indexes(form)):
        category_raw = form.get(f"sections-{index}-category_id", "").strip()
        section_id_raw = form.get(f"sections-{index}-section-id", "").strip()
        sections.append(
            SimpleNamespace(
                id=int(section_id_raw) if section_id_raw.isdigit() and int(section_id_raw) > 0 else None,
                form_index=index,
                report_category_id=int(category_raw) if category_raw.isdigit() else None,
                severity=form.get(f"sections-{index}-severity", ""),
                status=form.get(f"sections-{index}-status", ""),
                due_date=form.get(f"sections-{index}-due_date", ""),
                owner_user_id=int(form.get(f"sections-{index}-owner_user_id", "")) if form.get(f"sections-{index}-owner_user_id", "").isdigit() else None,
                description=form.get(f"sections-{index}-description", ""),
                proposed_solution=form.get(f"sections-{index}-proposed_solution", ""),
                sort_order=sort_order,
                deleted_at=None,
            )
        )
    return sections


def _issue_section_indexes(form):
    indexes = set()
    for key in form.keys():
        if key.startswith("sections-"):
            parts = key.split("-")
            if len(parts) >= 3 and parts[1].isdigit():
                indexes.add(int(parts[1]))
    return sorted(indexes)
