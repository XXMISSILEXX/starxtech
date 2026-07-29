from flask import abort, flash, jsonify, redirect, render_template, request, url_for
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
    project_accepts_report_mutation,
)
from app.dashboard.routes import dashboard_navigation_context
from app.date_utils import local_today
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
    parse_report_date,
    reports_query,
)
from app.reports.direct_uploads import (UploadSessionCleanupError,
                                        cancel_upload_session_for_actor,
                                        complete as complete_report_upload,
                                        create_session as create_report_upload_session,
                                        v2_presign as presign_report_uploads,
                                        session_payload as report_upload_session_payload,
                                        _session as report_upload_session)
from app.reports.constants import MAX_ATTACHMENTS_PER_REPORT_SECTION
from app.storage.exceptions import StorageAuthorizationError, StorageNotFoundError, StorageValidationError
from app.extensions import limiter


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
    if (
        not can_access_reports_module(current_user)
        or not current_user.can("dashboards.project.view")
        or not can_read_project(project.id)
    ):
        abort(403)
    return render_template(
        "dashboard/project.html",
        dashboard_kind="project",
        can_write=can_create_report(current_user, project.id),
        **dashboard_navigation_context("project", project_id=project.id),
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
    try:
        if date_from:
            query = query.filter(DailyReport.report_date >= parse_report_date(date_from))
        if date_to:
            query = query.filter(DailyReport.report_date <= parse_report_date(date_to))
    except ReportValidationError:
        flash("Ngày lọc phải theo định dạng YYYY-MM-DD.", "warning")

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


@bp.get("/<int:project_id>/reports/create")
def reports_create(project_id):
    project = _project_or_404(project_id)
    if not can_read_project(project.id) or not project_accepts_report_mutation(project) or not can_create_report(current_user, project.id):
        abort(403)

    report = DailyReport(project_id=project.id)
    report.sections = []

    return _render_create_form(project, report)


@bp.post("/<int:project_id>/reports/create")
def reports_create_legacy_post_rejected(project_id):
    _project_or_404(project_id)
    return jsonify(ok=False, error="legacy_create_post_not_supported",
                   message="Trang tạo báo cáo chỉ hỗ trợ quy trình JSON mới."), 405


@bp.post("/<int:project_id>/reports/upload-sessions")
@limiter.limit("30 per minute")
def report_upload_session_create(project_id):
    project = _project_or_404(project_id)
    if not project_accepts_report_mutation(project) or not can_create_report(current_user, project.id): abort(403)
    payload = request.get_json(silent=True) or {}
    try:
        return jsonify(create_report_upload_session(user=current_user, project_id=project.id,
            declared_files=payload.get("file_count"), declared_size_bytes=payload.get("total_size_bytes")))
    except StorageValidationError as exc: return jsonify(error=str(exc)), 400


@bp.get("/<int:project_id>/reports/upload-sessions/<int:session_id>")
def report_upload_session_state(project_id, session_id):
    project = _project_or_404(project_id)
    if not project_accepts_report_mutation(project) or not can_create_report(current_user, project.id): abort(403)
    try: return jsonify(report_upload_session_payload(report_upload_session(current_user, project.id, session_id, allow_finalized=True)))
    except StorageAuthorizationError: abort(403)
    except StorageValidationError as exc: return jsonify(error=str(exc)), 400


@bp.post("/<int:project_id>/reports/upload-sessions/<int:session_id>/presign")
@limiter.limit("60 per minute")
def report_upload_session_presign(project_id, session_id):
    project = _project_or_404(project_id)
    if not project_accepts_report_mutation(project) or not can_create_report(current_user, project.id): abort(403)
    try: return jsonify(presign_report_uploads(user=current_user, project_id=project.id, session_id=session_id, files=(request.get_json(silent=True) or {}).get("files", [])))
    except StorageAuthorizationError: abort(403)
    except StorageValidationError as exc: return jsonify(error=str(exc)), 400


@bp.post("/<int:project_id>/reports/upload-sessions/<int:session_id>/complete")
@limiter.limit("120 per minute")
def report_upload_session_complete(project_id, session_id):
    project = _project_or_404(project_id)
    if not project_accepts_report_mutation(project) or not can_create_report(current_user, project.id): abort(403)
    payload = request.get_json(silent=True) or {}
    try: item_id = int(payload.get("upload_batch_item_id"))
    except (TypeError, ValueError): return jsonify(error="upload_batch_item_id không hợp lệ."), 400
    try: return jsonify(complete_report_upload(user=current_user, project_id=project.id, session_id=session_id, item_id=item_id, checksum_sha256=payload.get("checksum_sha256")))
    except StorageAuthorizationError: abort(403)
    except (StorageValidationError, StorageNotFoundError) as exc: return jsonify(error=str(exc)), 400


@bp.post("/<int:project_id>/reports/upload-sessions/<int:session_id>/cancel")
def report_upload_session_cancel(project_id, session_id):
    project = _project_or_404(project_id)
    if not project_accepts_report_mutation(project) or not can_create_report(current_user, project.id): abort(403)
    try:
        session, cleanup = cancel_upload_session_for_actor(
            actor=current_user, project=project, session_id=session_id,
        )
        if not cleanup["complete"]:
            return jsonify(
                ok=False,
                error="upload_session_cleanup_incomplete",
                upload_session_id=session.id,
                status=session.status,
                cleanup=cleanup,
            ), 409
        return jsonify(upload_session_id=session.id, status=session.status, cleanup=cleanup)
    except StorageAuthorizationError: abort(403)
    except StorageValidationError as exc: return jsonify(error=str(exc)), 400
    except UploadSessionCleanupError as exc:
        db.session.rollback()
        return jsonify(error=str(exc)), 500


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
    from flask import current_app
    from app.ui import status_presentation
    return render_template(
        "reports/form.html",
        project=project,
        report=report,
        form_data=form_data,
        form_errors=form_errors or {},
        categories=categories_for_create(project.id),
        statuses=[status.value for status in DailyReportStatus],
        section_statuses=[status.value for status in SectionStatus],
        status_metadata=[status_presentation(status.value) for status in {*DailyReportStatus, *SectionStatus}],
        can_write=can_create_report(current_user, project.id),
        can_delete_attachment=False,
        direct_upload_limits={"enabled": current_app.config["DAILY_REPORT_DIRECT_UPLOAD_ENABLED"], "max_files": current_app.config["DAILY_REPORT_MAX_FILES"], "max_files_per_section": MAX_ATTACHMENTS_PER_REPORT_SECTION, "max_file_bytes": current_app.config["DAILY_REPORT_MAX_FILE_BYTES"], "max_total_bytes": current_app.config["DAILY_REPORT_MAX_TOTAL_BYTES"], "concurrency": current_app.config["DAILY_REPORT_UPLOAD_CONCURRENCY"]},
        daily_report_create_v2_enabled=True,
        create_v2_api_base=f"/api/projects/{project.id}/daily-reports",
        today_iso=local_today().isoformat(),
    )


def _reject_legacy_multipart_files(*, project, report):
    from flask import current_app

    if not current_app.config["DAILY_REPORT_DIRECT_UPLOAD_ENABLED"]:
        return None
    if not any(file and file.filename for key in request.files for file in request.files.getlist(key)):
        return None
    message = "Ảnh đính kèm phải được tải lên bằng trình tải ảnh của hệ thống."
    if _wants_json():
        return jsonify(ok=False, error="legacy_multipart_upload_not_supported", message=message), 400
    flash(message + " Vui lòng tải lại trang và thử lại.", "danger")
    return _render_create_form(project, report, form_data=build_report_form_data(request.form)), 400


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


def _wants_json():
    return request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.accept_mimetypes.best == "application/json"
