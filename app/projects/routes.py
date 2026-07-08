from flask import abort, flash, redirect, render_template, request, url_for

from app.auth.permissions import can_read_project, can_write_project
from app.dashboard.services import project_dashboard_context
from app.extensions import db
from app.issues.services import (
    IssueValidationError,
    create_issue,
    owner_choices,
    project_issues_query,
)
from app.models import DailyReport, DailyReportStatus, Project, SectionStatus
from app.models import IssueSeverity, IssueStatus, PersistentIssue
from app.projects import bp
from app.reports.services import (
    ReportValidationError,
    accessible_projects_query,
    categories_for_create,
    create_report,
    reports_query,
)


@bp.get("")
@bp.get("/")
def index():
    return render_template("projects/index.html", projects=accessible_projects_query().all())


@bp.get("/<int:project_id>/dashboard")
def dashboard(project_id):
    project = _project_or_404(project_id)
    if not can_read_project(project.id):
        abort(403)
    return render_template(
        "dashboard/project.html",
        can_write=can_write_project(project.id),
        **project_dashboard_context(project),
    )


@bp.get("/<int:project_id>/reports")
def reports(project_id):
    project = _project_or_404(project_id)
    if not can_read_project(project.id):
        abort(403)

    query = reports_query().filter(DailyReport.project_id == project.id)
    status = request.args.get("status", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    if status:
        query = query.filter(DailyReport.overall_status == status)
    if date_from:
        query = query.filter(DailyReport.report_date >= date_from)
    if date_to:
        query = query.filter(DailyReport.report_date <= date_to)

    return render_template(
        "reports/index.html",
        reports=query.order_by(DailyReport.report_date.desc(), DailyReport.id.desc()).all(),
        projects=[project],
        statuses=[status.value for status in DailyReportStatus],
        filters={
            "project_id": project.id,
            "status": status,
            "date_from": date_from,
            "date_to": date_to,
        },
        project=project,
    )


@bp.route("/<int:project_id>/reports/create", methods=["GET", "POST"])
def reports_create(project_id):
    project = _project_or_404(project_id)
    if not can_read_project(project.id):
        abort(403)

    report = DailyReport(project_id=project.id)
    report.sections = []

    if request.method == "POST":
        if not can_write_project(project.id):
            abort(403)
        try:
            report, duplicate = create_report(project, request.form, request.files)
        except ReportValidationError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
            return _render_create_form(project, report), 400
        if duplicate:
            flash("A report already exists for this project and date.", "warning")
            return redirect(url_for("reports.edit", report_id=report.id))
        flash("Report created.", "success")
        return redirect(url_for("reports.detail", report_id=report.id))

    return _render_create_form(project, report)


@bp.get("/<int:project_id>/issues")
def issues(project_id):
    project = _project_or_404(project_id)
    if not can_read_project(project.id):
        abort(403)
    return render_template(
        "issues/index.html",
        project=project,
        issues=project_issues_query(project.id).all(),
        can_write=can_write_project(project.id),
    )


@bp.route("/<int:project_id>/issues/create", methods=["GET", "POST"])
def issues_create(project_id):
    project = _project_or_404(project_id)
    if not can_read_project(project.id):
        abort(403)

    issue = PersistentIssue(project_id=project.id)
    if request.method == "POST":
        if not can_write_project(project.id):
            abort(403)
        try:
            create_issue(project, request.form)
        except IssueValidationError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
            return _render_issue_form(project, issue), 400
        flash("Issue created.", "success")
        return redirect(url_for("projects.issues", project_id=project.id))

    return _render_issue_form(project, issue)


def _render_create_form(project, report):
    return render_template(
        "reports/form.html",
        project=project,
        report=report,
        categories=categories_for_create(project.id),
        statuses=[status.value for status in DailyReportStatus],
        section_statuses=[status.value for status in SectionStatus],
        can_write=can_write_project(project.id),
    )


def _render_issue_form(project, issue):
    return render_template(
        "issues/form.html",
        project=project,
        issue=issue,
        owners=owner_choices(project.id),
        severities=[severity.value for severity in IssueSeverity],
        statuses=[status.value for status in IssueStatus],
        can_write=can_write_project(project.id),
    )


def _project_or_404(project_id):
    return Project.query.filter(
        Project.id == project_id,
        Project.deleted_at.is_(None),
    ).first_or_404()
