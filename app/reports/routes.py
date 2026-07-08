from flask import abort, flash, redirect, render_template, request, url_for
from app.auth.permissions import can_delete_report_for_project, can_read_project, can_write_project
from app.extensions import db
from app.models import DailyReport, DailyReportStatus, Project, SectionStatus
from app.reports import bp
from app.reports.services import (
    ReportValidationError,
    accessible_projects_query,
    categories_for_report,
    delete_report,
    reports_query,
    update_report,
)


@bp.get("")
@bp.get("/")
def index():
    query = reports_query()

    project_id = request.args.get("project_id", type=int)
    status = request.args.get("status", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    if project_id:
        query = query.filter(DailyReport.project_id == project_id)
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
        projects=accessible_projects_query().all(),
        statuses=[status.value for status in DailyReportStatus],
        filters={
            "project_id": project_id,
            "status": status,
            "date_from": date_from,
            "date_to": date_to,
        },
        project=None,
    )


@bp.get("/<int:report_id>")
def detail(report_id):
    report = _report_or_404(report_id)
    _require_can_read(report)
    return render_template(
        "reports/detail.html",
        report=report,
        can_write=can_write_project(report.project_id),
        can_delete=_can_delete_report(report),
    )


@bp.route("/<int:report_id>/edit", methods=["GET", "POST"])
def edit(report_id):
    report = _report_or_404(report_id)
    _require_can_read(report)

    if request.method == "POST":
        _require_can_write(report)
        try:
            update_report(report, request.form, request.files)
        except ReportValidationError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
            return _render_form(report), 400
        flash("Đã lưu báo cáo.", "success")
        return redirect(url_for("reports.detail", report_id=report.id))

    return _render_form(report)


@bp.post("/<int:report_id>/delete")
def delete(report_id):
    report = _report_or_404(report_id)
    if not _can_delete_report(report):
        abort(403)
    delete_report(report)
    flash("Đã xóa báo cáo.", "success")
    return redirect(url_for("reports.index"))


def _render_form(report):
    return render_template(
        "reports/form.html",
        report=report,
        project=report.project,
        categories=categories_for_report(report),
        statuses=[status.value for status in DailyReportStatus],
        section_statuses=[status.value for status in SectionStatus],
        can_write=can_write_project(report.project_id),
    )


def _report_or_404(report_id):
    return DailyReport.query.filter(
        DailyReport.id == report_id,
        DailyReport.deleted_at.is_(None),
    ).first_or_404()


def _require_can_read(report):
    project = Project.query.filter(Project.id == report.project_id, Project.deleted_at.is_(None)).first()
    if not project or not can_read_project(report.project_id):
        abort(403)


def _require_can_write(report):
    if not can_write_project(report.project_id):
        abort(403)


def _can_delete_report(report):
    return can_delete_report_for_project(report.project_id)
