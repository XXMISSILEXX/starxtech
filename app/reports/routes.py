from flask import abort, flash, jsonify, redirect, render_template, request, url_for
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
    ReportDeletionError,
    reports_query,
    update_report,
    parse_report_date,
    format_report_date,
)


@bp.get("")
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
    try:
        if date_from:
            query = query.filter(DailyReport.report_date >= parse_report_date(date_from))
        if date_to:
            query = query.filter(DailyReport.report_date <= parse_report_date(date_to))
    except ReportValidationError:
        flash("Ngày lọc phải đúng định dạng DD/MM/YYYY.", "warning")

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
        legacy_response = _reject_legacy_multipart_files(report=report)
        if legacy_response is not None:
            return legacy_response
        try:
            update_report(report, request.form)
        except ReportValidationError as exc:
            db.session.rollback()
            if _wants_json():
                return jsonify(ok=False, error="validation_error", message=str(exc), field_errors=exc.errors), 422
            flash(str(exc), "danger")
            return _render_form(
                report,
                form_data=build_report_form_data(request.form, report),
                form_errors=exc.errors,
            ), 400
        redirect_url = url_for("reports.detail", report_id=report.id)
        if _wants_json():
            flash("Đã cập nhật báo cáo thành công.", "success")
            return jsonify(ok=True, report_id=report.id, redirect_url=redirect_url)
        flash("Đã cập nhật báo cáo thành công.", "success")
        return redirect(redirect_url)

    return _render_form(report)


@bp.post("/<int:report_id>/delete")
def delete(report_id):
    report = _report_or_404(report_id)
    if not _can_delete_report(report):
        abort(403)
    try:
        delete_report(report)
    except ReportDeletionError as exc:
        db.session.rollback()
        flash(str(exc), "danger")
        return redirect(url_for("reports.detail", report_id=report.id))
    flash("Đã xóa vĩnh viễn báo cáo và toàn bộ ảnh đính kèm.", "success")
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
        direct_upload_limits=_direct_upload_limits(),
        daily_report_legacy_edit_enabled=True,
    )


def _report_or_404(report_id):
    return db.get_or_404(DailyReport, report_id)


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


def _direct_upload_limits():
    from flask import current_app
    return {"enabled": current_app.config["DAILY_REPORT_DIRECT_UPLOAD_ENABLED"], "max_files": current_app.config["DAILY_REPORT_MAX_FILES"], "max_files_per_section": current_app.config["DAILY_REPORT_MAX_FILES_PER_SECTION"], "max_file_bytes": current_app.config["DAILY_REPORT_MAX_FILE_BYTES"], "max_total_bytes": current_app.config["DAILY_REPORT_MAX_TOTAL_BYTES"], "concurrency": current_app.config["DAILY_REPORT_UPLOAD_CONCURRENCY"]}


def _reject_legacy_multipart_files(*, report):
    """Reject browser file parts before the report service can mutate state."""
    from flask import current_app

    if not current_app.config["DAILY_REPORT_DIRECT_UPLOAD_ENABLED"]:
        return None
    if not any(file and file.filename for key in request.files for file in request.files.getlist(key)):
        return None
    message = "Ảnh đính kèm phải được tải lên bằng trình tải ảnh của hệ thống."
    if _wants_json():
        return jsonify(ok=False, error="legacy_multipart_upload_not_supported", message=message), 400
    flash(message + " Vui lòng tải lại trang và thử lại.", "danger")
    return _render_form(report, form_data=build_report_form_data(request.form, report)), 400


def _wants_json():
    return request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.accept_mimetypes.best == "application/json"
