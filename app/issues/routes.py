from flask import abort, flash, redirect, render_template, request, url_for

from app.auth.permissions import (
    can_create_persistent_issue,
    can_delete_persistent_issue,
    can_edit_persistent_issue,
    can_read_project,
    can_write_project,
)
from app.extensions import db
from app.issues import bp
from app.issues.services import (
    IssueValidationError,
    build_issue_form_data,
    close_issue,
    create_issue,
    delete_issue,
    owner_choices,
    reopen_issue,
    update_issue,
)
from app.models import IssueSeverity, IssueStatus, PersistentIssue
from app.reports.services import accessible_projects_query


@bp.get("")
@bp.get("/")
def index():
    projects = accessible_projects_query().all()
    project_ids = [project.id for project in projects]
    issues = []
    if project_ids:
        query = (
            PersistentIssue.query.filter(
                PersistentIssue.project_id.in_(project_ids),
                PersistentIssue.deleted_at.is_(None),
            )
        )
        issues = _apply_issue_filters(query).order_by(
            PersistentIssue.opened_date.desc(), PersistentIssue.id.desc()
        ).all()
    can_create = can_create_persistent_issue()
    return render_template(
        "issues/index.html",
        issues=issues,
        project=None,
        can_write=False,
        can_delete=False,
        can_create=can_create,
        create_url=url_for("issues.new") if can_create else None,
        can_edit_by_issue={issue.id: can_edit_persistent_issue(issue) for issue in issues},
        can_delete_by_issue={issue.id: can_delete_persistent_issue(issue) for issue in issues},
    )


@bp.route("/new", methods=["GET", "POST"])
def new():
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
    if not can_read_project(issue.project_id):
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
            return _render_form(form_issue, form_errors=exc.errors), 400
        flash("Đã lưu vấn đề tồn đọng.", "success")
        return redirect(url_for("projects.issues", project_id=issue.project_id))

    return _render_form(issue)


@bp.post("/<int:issue_id>/close")
def close(issue_id):
    issue = _issue_or_404(issue_id)
    if not can_edit_persistent_issue(issue):
        abort(403)
    close_issue(issue)
    flash("Đã đóng vấn đề tồn đọng.", "success")
    return redirect(url_for("projects.issues", project_id=issue.project_id))


@bp.post("/<int:issue_id>/reopen")
def reopen(issue_id):
    issue = _issue_or_404(issue_id)
    if not can_edit_persistent_issue(issue):
        abort(403)
    reopen_issue(issue)
    flash("Đã mở lại vấn đề tồn đọng.", "success")
    return redirect(url_for("projects.issues", project_id=issue.project_id))


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
    return render_template(
        "issues/form.html",
        issue=issue,
        project=issue.project,
        owners=owner_choices(issue.project_id),
        severities=[severity.value for severity in IssueSeverity],
        statuses=[status.value for status in IssueStatus],
        can_write=can_write_project(issue.project_id),
        can_delete=can_delete_persistent_issue(issue),
        form_errors=form_errors or {},
    )


def _render_new_form(issue, projects, selected_project, form_errors=None):
    return render_template(
        "issues/form.html",
        issue=issue,
        project=selected_project,
        projects=projects,
        owners=owner_choices(selected_project.id) if selected_project else [],
        severities=[severity.value for severity in IssueSeverity],
        statuses=[status.value for status in IssueStatus],
        can_write=True,
        can_delete=False,
        form_errors=form_errors or {},
    )


def _issue_or_404(issue_id):
    return PersistentIssue.query.filter(
        PersistentIssue.id == issue_id,
        PersistentIssue.deleted_at.is_(None),
    ).first_or_404()


def _apply_issue_filters(query):
    status = request.args.get("status", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    if status == "CRITICAL":
        query = query.filter(PersistentIssue.severity == IssueSeverity.CRITICAL.value)
    elif status == "ATTENTION":
        query = query.filter(PersistentIssue.severity == IssueSeverity.HIGH.value)
    elif status == "PROCESSING":
        query = query.filter(PersistentIssue.status == IssueStatus.PROCESSING.value)

    if date_from:
        query = query.filter(PersistentIssue.opened_date >= date_from)
    if date_to:
        query = query.filter(PersistentIssue.opened_date <= date_to)
    return query


def _selected_project_from_request(projects):
    project_id = request.form.get("project_id", type=int) or request.args.get("project_id", type=int)
    if project_id:
        return next((project for project in projects if project.id == project_id), None)
    return projects[0] if len(projects) == 1 else None
