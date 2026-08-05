from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.auth.permissions import (
    can_create_persistent_issue,
    can_delete_persistent_issue,
    can_edit_persistent_issue,
    can_view_issue,
)
from app.extensions import db
from app.issues import bp
from app.issues.services import (
    ISSUE_LIST_PER_PAGE,
    IssueValidationError,
    filtered_issue_list,
    build_issue_form_data,
    create_issue,
    delete_issue,
    issue_form_context,
    issue_list_context,
    issue_list_state,
    issue_sections,
    issue_viewable_projects_query,
    update_issue,
)
from app.models import IssueSeverity, IssueStatus, PersistentIssue
from app.reports.services import accessible_projects_query
from app.project_memberships import has_any_project_capability


@bp.get("")
def index():
    if not has_any_project_capability(current_user, ("can_view_issues",)):
        abort(403)
    # Generic project visibility is not issue visibility.  Scope rows, filters
    # and every derived count from the same capability-aware project set.
    project_ids = [project.id for project in issue_viewable_projects_query().all()]
    query = PersistentIssue.query.filter(
        PersistentIssue.project_id.in_(project_ids),
        PersistentIssue.deleted_at.is_(None),
    )
    state = issue_list_state(project_ids, request.args)
    issues, total, hidden_closed_total = filtered_issue_list(query, state)
    can_create = can_create_persistent_issue()
    return render_template(
        "issues/index.html",
        **issue_list_context(
            issues,
            project=None,
            can_create=can_create,
            create_url=url_for("issues.new") if can_create else None,
        ),
        issue_filter_state=state,
        issue_total=total,
        issue_per_page=ISSUE_LIST_PER_PAGE,
        hidden_closed_total=hidden_closed_total,
    )


@bp.route("/new", methods=["GET", "POST"])
def new():
    if not has_any_project_capability(current_user, ("can_view_issues",)):
        abort(403)
    projects = [
        project
        for project in accessible_projects_query().all()
        if can_create_persistent_issue(project.id)
    ]
    if not projects:
        abort(403)

    selected_project = _selected_project_from_request(projects)
    issue = PersistentIssue(project_id=selected_project.id if selected_project else None)

    if request.method == "POST":
        if not selected_project or not can_create_persistent_issue(selected_project.id):
            flash("Vui lòng chọn dự án.", "danger")
            form_errors = {"project_id": "Vui lòng chọn dự án."}
            return _render_new_form(
                build_issue_form_data(request.form),
                projects,
                selected_project,
                form_errors=form_errors,
            ), 400
        try:
            create_issue(selected_project, request.form)
        except IssueValidationError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
            return _render_new_form(
                build_issue_form_data(request.form, selected_project.id),
                projects,
                selected_project,
                form_errors=exc.errors,
            ), 400
        flash("Đã thêm vấn đề tồn đọng.", "success")
        return redirect(url_for("issues.index"))

    return _render_new_form(issue, projects, selected_project)


@bp.route("/<int:issue_id>/edit", methods=["GET", "POST"])
def edit(issue_id):
    issue = _issue_or_404(issue_id)
    if not can_view_issue(current_user, issue):
        abort(403)

    if request.method == "POST":
        if not can_edit_persistent_issue(issue):
            abort(403)
        try:
            update_issue(issue, request.form)
        except IssueValidationError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
            form_issue = build_issue_form_data(request.form, issue.project_id)
            form_issue.id = issue.id
            form_issue.project = issue.project
            form_issue.status = issue.status
            form_issue.due_date = issue.due_date
            form_issue.closed_date = issue.closed_date
            return _render_form(form_issue, form_errors=exc.errors), 400
        flash("Đã lưu vấn đề tồn đọng.", "success")
        return redirect(url_for("projects.issues", project_id=issue.project_id))

    return _render_form(issue)


@bp.post("/<int:issue_id>/delete")
def delete(issue_id):
    issue = _issue_or_404(issue_id)
    if not can_delete_persistent_issue(issue):
        abort(403)
    project_id = issue.project_id
    delete_issue(issue)
    flash("Đã xóa vấn đề tồn đọng.", "success")
    return redirect(url_for("projects.issues", project_id=project_id))


def _render_form(issue, form_errors=None):
    sections = getattr(issue, "sections", None) if form_errors else None
    sections = sections if sections is not None else issue_sections(issue)
    return render_template(
        "issues/form.html",
        issue=issue,
        project=issue.project,
        sections=sections,
        can_write=can_edit_persistent_issue(issue),
        can_delete=can_delete_persistent_issue(issue),
        form_errors=form_errors or {},
        **issue_form_context(issue.project_id, issue, sections),
    )


def _render_new_form(issue, projects, selected_project, form_errors=None):
    sections = getattr(issue, "sections", [])
    return render_template(
        "issues/form.html",
        issue=issue,
        project=selected_project,
        projects=projects,
        sections=sections,
        can_write=bool(selected_project and can_create_persistent_issue(selected_project.id)),
        can_delete=False,
        form_errors=form_errors or {},
        **(issue_form_context(selected_project.id, issue, sections) if selected_project else {
            "categories": [], "active_categories": [], "owners": [], "severities": [severity.value for severity in IssueSeverity], "section_statuses": [status.value for status in IssueStatus],
        }),
    )


def _issue_or_404(issue_id):
    return PersistentIssue.query.filter(
        PersistentIssue.id == issue_id,
        PersistentIssue.deleted_at.is_(None),
    ).first_or_404()


def _selected_project_from_request(projects):
    project_id = request.form.get("project_id", type=int) or request.args.get("project_id", type=int)
    if project_id:
        return next((project for project in projects if project.id == project_id), None)
    return projects[0] if len(projects) == 1 else None
