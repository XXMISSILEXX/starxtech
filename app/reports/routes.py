from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.auth.permissions import can_access_reports_module, can_create_report, can_delete_report, can_edit_report, can_view_report
from app.extensions import db
from app.models import DailyReport, DailyReportStatus, Project, SectionStatus
from app.reports import bp
from app.reports.services import (
    ReportValidationError,
    accessible_projects_query,
    build_report_form_data,
    categories_for_report,
    delete_report,
    reports_query,
    update_report,
)


@bp.get("")
@bp.get("/")
def index():
    if not can_access_reports_module(current_user):
        abort(403)
    query = reports_query()
    projects = accessible_projects_query().all()

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
        projects=projects,
        statuses=[status.value for status in DailyReportStatus],
        filters={
            "project_id": project_id,
            "status": status,
            "date_from": date_from,
            "date_to": date_to,
        },
        project=None,
        can_create_report_entry=any(can_create_report(current_user, project.id) for project in projects),
        can_write_by_project={report.id: can_edit_report(current_user, report) for report in reports},
        can_delete_by_report={report.id: _can_delete_report(report) for report in reports},
    )


@bp.get("/<int:report_id>")
def detail(report_id):
    report = _report_or_404(report_id)
    _require_can_read(report)
    return render_template(
        "reports/detail.html",
        report=report,
        can_write=can_edit_report(current_user, report),
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
            _flash_reselect_images_if_needed(request.files)
            return _render_form(
                report,
                form_data=build_report_form_data(request.form, report),
                form_errors=exc.errors,
            ), 400
        flash("Đã cập nhật báo cáo thành công.", "success")
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


def _render_form(report, form_data=None, form_errors=None):
    return render_template(
        "reports/form.html",
        report=report,
        project=report.project,
        form_data=form_data,
        form_errors=form_errors or {},
        categories=categories_for_report(report),
        statuses=[status.value for status in DailyReportStatus],
        section_statuses=[status.value for status in SectionStatus],
        can_write=can_edit_report(current_user, report),
        can_delete_attachment=current_user.can("report_attachments.delete") and can_edit_report(current_user, report),
    )


def _report_or_404(report_id):
    return DailyReport.query.filter(
        DailyReport.id == report_id,
        DailyReport.deleted_at.is_(None),
    ).first_or_404()


def _require_can_read(report):
    project = Project.query.filter(Project.id == report.project_id, Project.deleted_at.is_(None)).first()
    if not project or not can_view_report(current_user, report):
        abort(403)


def _require_can_write(report):
    if not can_edit_report(current_user, report):
        abort(403)


def _can_delete_report(report):
    return can_delete_report(current_user, report)


def _flash_reselect_images_if_needed(files):
    if any(file and file.filename for key in files for file in files.getlist(key)):
        flash("Vui lòng chọn lại ảnh đính kèm sau khi sửa lỗi.", "warning")
