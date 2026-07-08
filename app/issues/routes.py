from flask import abort, flash, redirect, render_template, request, url_for

from app.auth.permissions import can_delete_issue_for_project, can_read_project, can_write_project
from app.extensions import db
from app.issues import bp
from app.issues.services import (
    IssueValidationError,
    close_issue,
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
    return render_template("issues/index.html", issues=issues, project=None, can_write=False, can_delete=False)


@bp.route("/<int:issue_id>/edit", methods=["GET", "POST"])
def edit(issue_id):
    issue = _issue_or_404(issue_id)
    if not can_read_project(issue.project_id):
        abort(403)

    if request.method == "POST":
        if not can_write_project(issue.project_id):
            abort(403)
        try:
            update_issue(issue, request.form)
        except IssueValidationError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
            return _render_form(issue), 400
        flash("Đã lưu vấn đề tồn đọng.", "success")
        return redirect(url_for("projects.issues", project_id=issue.project_id))

    return _render_form(issue)


@bp.post("/<int:issue_id>/close")
def close(issue_id):
    issue = _issue_or_404(issue_id)
    if not can_write_project(issue.project_id):
        abort(403)
    close_issue(issue)
    flash("Đã đóng vấn đề tồn đọng.", "success")
    return redirect(url_for("projects.issues", project_id=issue.project_id))


@bp.post("/<int:issue_id>/reopen")
def reopen(issue_id):
    issue = _issue_or_404(issue_id)
    if not can_write_project(issue.project_id):
        abort(403)
    reopen_issue(issue)
    flash("Đã mở lại vấn đề tồn đọng.", "success")
    return redirect(url_for("projects.issues", project_id=issue.project_id))


@bp.post("/<int:issue_id>/delete")
def delete(issue_id):
    issue = _issue_or_404(issue_id)
    if not can_delete_issue_for_project(issue.project_id):
        abort(403)
    project_id = issue.project_id
    delete_issue(issue)
    flash("Đã xóa vấn đề tồn đọng.", "success")
    return redirect(url_for("projects.issues", project_id=project_id))


def _render_form(issue):
    return render_template(
        "issues/form.html",
        issue=issue,
        project=issue.project,
        owners=owner_choices(issue.project_id),
        severities=[severity.value for severity in IssueSeverity],
        statuses=[status.value for status in IssueStatus],
        can_write=can_write_project(issue.project_id),
        can_delete=can_delete_issue_for_project(issue.project_id),
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
