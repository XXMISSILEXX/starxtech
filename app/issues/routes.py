from flask import abort, flash, redirect, render_template, request, url_for

from app.auth.permissions import can_read_project, can_write_project
from app.extensions import db
from app.issues import bp
from app.issues.services import (
    IssueValidationError,
    close_issue,
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
        issues = (
            PersistentIssue.query.filter(
                PersistentIssue.project_id.in_(project_ids),
                PersistentIssue.deleted_at.is_(None),
            )
            .order_by(PersistentIssue.opened_date.desc(), PersistentIssue.id.desc())
            .all()
        )
    return render_template("issues/index.html", issues=issues, project=None, can_write=False)


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
        flash("Issue saved.", "success")
        return redirect(url_for("projects.issues", project_id=issue.project_id))

    return _render_form(issue)


@bp.post("/<int:issue_id>/close")
def close(issue_id):
    issue = _issue_or_404(issue_id)
    if not can_write_project(issue.project_id):
        abort(403)
    close_issue(issue)
    flash("Issue closed.", "success")
    return redirect(url_for("projects.issues", project_id=issue.project_id))


@bp.post("/<int:issue_id>/reopen")
def reopen(issue_id):
    issue = _issue_or_404(issue_id)
    if not can_write_project(issue.project_id):
        abort(403)
    reopen_issue(issue)
    flash("Issue reopened.", "success")
    return redirect(url_for("projects.issues", project_id=issue.project_id))


def _render_form(issue):
    return render_template(
        "issues/form.html",
        issue=issue,
        project=issue.project,
        owners=owner_choices(issue.project_id),
        severities=[severity.value for severity in IssueSeverity],
        statuses=[status.value for status in IssueStatus],
        can_write=can_write_project(issue.project_id),
    )


def _issue_or_404(issue_id):
    return PersistentIssue.query.filter(
        PersistentIssue.id == issue_id,
        PersistentIssue.deleted_at.is_(None),
    ).first_or_404()
