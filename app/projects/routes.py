from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.auth.permissions import (
    can_create_persistent_issue,
    can_close_persistent_issue,
    can_delete_persistent_issue,
    can_delete_report,
    can_edit_report,
    can_edit_persistent_issue,
    can_create_report,
    can_read_project,
    can_access_reports_module,
    can_view_issue,
)
from app.dashboard.services import project_dashboard_context
from app.extensions import db
from app.issues.services import (
    IssueValidationError,
    build_issue_form_data,
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
    build_report_form_data,
    categories_for_create,
    create_report,
    reports_query,
)


@bp.get("/")
@bp.get("")
def index():
    if not can_access_reports_module(current_user):
        abort(403)
    projects = accessible_projects_query().all()
    create_report_mode = request.args.get("create_report") == "1"
    if create_report_mode:
        flash("Chọn dự án để tạo báo cáo mới", "info")
    return render_template(
        "projects/index.html",
        projects=projects,
        create_report_mode=create_report_mode,
        can_write_by_project={project.id: can_create_report(current_user, project.id) for project in projects},
    )


@bp.get("/<int:project_id>/dashboard")
def dashboard(project_id):
    project = _project_or_404(project_id)
    if not can_read_project(project.id):
        abort(403)
    return render_template(
        "dashboard/project.html",
        can_write=can_create_report(current_user, project.id),
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

    reports = query.order_by(DailyReport.report_date.desc(), DailyReport.id.desc()).all()
    return render_template(
        "reports/index.html",
        reports=reports,
        projects=[project],
        statuses=[status.value for status in DailyReportStatus],
        filters={
            "project_id": project.id,
            "status": status,
            "date_from": date_from,
            "date_to": date_to,
        },
        project=project,
        can_create_report_entry=can_create_report(current_user, project.id),
        can_write_by_project={report.id: can_edit_report(current_user, report) for report in reports},
        can_delete_by_report={report.id: can_delete_report(current_user, report) for report in reports},
    )


@bp.route("/<int:project_id>/reports/create", methods=["GET", "POST"])
def reports_create(project_id):
    project = _project_or_404(project_id)
    if not can_read_project(project.id):
        abort(403)

    report = DailyReport(project_id=project.id)
    report.sections = []

    if request.method == "POST":
        if not can_create_report(current_user, project.id):
            abort(403)
        try:
            report, duplicate = create_report(project, request.form, request.files)
        except ReportValidationError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
            _flash_reselect_images_if_needed(request.files)
            return _render_create_form(
                project,
                report,
                form_data=build_report_form_data(request.form),
                form_errors=exc.errors,
            ), 400
        if duplicate:
            flash("Dự án đã có báo cáo cho ngày này.", "warning")
            return redirect(url_for("reports.edit", report_id=report.id))
        flash("Đã tạo báo cáo.", "success")
        return redirect(url_for("reports.detail", report_id=report.id))

    return _render_create_form(project, report)


@bp.get("/<int:project_id>/issues")
def issues(project_id):
    project = _project_or_404(project_id)
    if not can_read_project(project.id) or not can_view_issue(current_user, PersistentIssue(project_id=project.id)):
        abort(403)
    issues = _apply_issue_filters(project_issues_query(project.id)).all()
    can_create = can_create_persistent_issue(project.id)
    return render_template(
        "issues/index.html",
        project=project,
        issues=issues,
        can_write=False,
        can_delete=False,
        can_create=can_create,
        create_url=url_for("projects.issues_create", project_id=project.id) if can_create else None,
        can_edit_by_issue={issue.id: can_edit_persistent_issue(issue) for issue in issues},
        can_close_by_issue={issue.id: can_close_persistent_issue(issue, current_user) for issue in issues},
        can_delete_by_issue={issue.id: can_delete_persistent_issue(issue, current_user) for issue in issues},
    )


@bp.route("/<int:project_id>/issues/create", methods=["GET", "POST"])
def issues_create(project_id):
    project = _project_or_404(project_id)
    if not can_read_project(project.id) or not can_view_issue(current_user, PersistentIssue(project_id=project.id)):
        abort(403)

    issue = PersistentIssue(project_id=project.id)
    if request.method == "POST":
        if not can_create_persistent_issue(project.id, current_user):
            abort(403)
        try:
            create_issue(project, request.form)
        except IssueValidationError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
            return _render_issue_form(
                project,
                build_issue_form_data(request.form, project.id),
                form_errors=exc.errors,
            ), 400
        flash("Đã thêm vấn đề tồn đọng.", "success")
        return redirect(url_for("projects.issues", project_id=project.id))

    return _render_issue_form(project, issue)


def _render_create_form(project, report, form_data=None, form_errors=None):
    return render_template(
        "reports/form.html",
        project=project,
        report=report,
        form_data=form_data,
        form_errors=form_errors or {},
        categories=categories_for_create(project.id),
        statuses=[status.value for status in DailyReportStatus],
        section_statuses=[status.value for status in SectionStatus],
        can_write=can_create_report(current_user, project.id),
        can_delete_attachment=False,
    )


def _render_issue_form(project, issue, form_errors=None):
    return render_template(
        "issues/form.html",
        project=project,
        issue=issue,
        owners=owner_choices(project.id),
        severities=[severity.value for severity in IssueSeverity],
        statuses=[status.value for status in IssueStatus],
        can_write=can_create_persistent_issue(project.id, current_user),
        can_delete=False,
        form_errors=form_errors or {},
    )


def _project_or_404(project_id):
    return Project.query.filter(
        Project.id == project_id,
        Project.deleted_at.is_(None),
    ).first_or_404()


def _apply_issue_filters(query):
    status = request.args.get("status", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    if status == DailyReportStatus.CRITICAL.value:
        query = query.filter(PersistentIssue.severity == IssueSeverity.CRITICAL.value)
    elif status == DailyReportStatus.ATTENTION.value:
        query = query.filter(PersistentIssue.severity == IssueSeverity.HIGH.value)
    elif status == DailyReportStatus.PROCESSING.value:
        query = query.filter(PersistentIssue.status == IssueStatus.PROCESSING.value)

    if date_from:
        query = query.filter(PersistentIssue.opened_date >= date_from)
    if date_to:
        query = query.filter(PersistentIssue.opened_date <= date_to)
    return query


def _flash_reselect_images_if_needed(files):
    if any(file and file.filename for key in files for file in files.getlist(key)):
        flash("Vui lòng chọn lại ảnh đính kèm sau khi sửa lỗi.", "warning")
