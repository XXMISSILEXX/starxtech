"""JSON-only Daily Report create API.

This module deliberately has no form parsing dependency.  Edit remains on the
legacy controller until it receives its own migration.
"""
from flask import Blueprint, jsonify, request, url_for
from flask_login import current_user

from app.auth.permissions import can_create_report
from app.extensions import limiter
from app.models import Project
from app.reports.services import DailyReportCreateV2Error, finalize_daily_report_create_v2
from app.reports import direct_uploads
from app.storage.exceptions import StorageAuthorizationError, StorageNotFoundError, StorageValidationError

bp = Blueprint("daily_report_create_v2", __name__, url_prefix="/api/projects/<int:project_id>/daily-reports")


def _ok(**data):
    return jsonify(ok=True, data=data)


def _fail(code, message, status=400, **extra):
    return jsonify(ok=False, error={"code": code, "message": message, **extra}), status


def _project(project_id):
    project = Project.query.filter_by(id=project_id, deleted_at=None).first()
    if not project:
        return None, _fail("project_not_found", "Không tìm thấy dự án.", 404)
    if not can_create_report(current_user, project.id):
        return None, _fail("forbidden", "Bạn không có quyền tạo báo cáo cho dự án này.", 403)
    return project, None


def _payload():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise DailyReportCreateV2Error("invalid_json", "Dữ liệu JSON không hợp lệ.")
    return payload


@bp.errorhandler(DailyReportCreateV2Error)
def _v2_error(exc):
    return _fail(exc.code, str(exc), exc.status, field_errors=exc.errors or None)


@bp.post("/upload-sessions")
@limiter.limit("30 per minute")
def create_session(project_id):
    project, error = _project(project_id)
    if error: return error
    try:
        payload = _payload()
        result = direct_uploads.create_session(user=current_user, project_id=project.id,
            declared_files=payload.get("file_count"), declared_size_bytes=payload.get("total_size_bytes"))
        return _ok(**result)
    except (DailyReportCreateV2Error, StorageValidationError) as exc:
        return _fail("invalid_upload_session", str(exc), 422)


@bp.get("/upload-sessions/<int:session_id>")
def session_state(project_id, session_id):
    project, error = _project(project_id)
    if error: return error
    try: return _ok(**direct_uploads.session_payload(direct_uploads._session(current_user, project.id, session_id, allow_finalized=True)))
    except StorageAuthorizationError: return _fail("upload_session_forbidden", "Phiên tải ảnh không hợp lệ.", 403)
    except StorageValidationError as exc: return _fail("upload_session_invalid", str(exc), 409)


@bp.post("/upload-sessions/<int:session_id>/presign")
@limiter.limit("60 per minute")
def presign(project_id, session_id):
    project, error = _project(project_id)
    if error: return error
    try: return _ok(**direct_uploads.v2_presign(user=current_user, project_id=project.id, session_id=session_id, files=_payload().get("files")))
    except StorageAuthorizationError: return _fail("upload_session_forbidden", "Phiên tải ảnh không hợp lệ.", 403)
    except StorageValidationError as exc: return _fail("invalid_upload", str(exc), 422)


@bp.post("/upload-sessions/<int:session_id>/items/<int:item_id>/complete")
@limiter.limit("120 per minute")
def complete(project_id, session_id, item_id):
    project, error = _project(project_id)
    if error: return error
    try: return _ok(**direct_uploads.complete(user=current_user, project_id=project.id, session_id=session_id, item_id=item_id, checksum_sha256=_payload().get("checksum_sha256")))
    except StorageAuthorizationError: return _fail("upload_item_forbidden", "Upload item không thuộc phiên này.", 403)
    except (StorageValidationError, StorageNotFoundError) as exc: return _fail("upload_verification_failed", str(exc), 422)


@bp.post("/upload-sessions/<int:session_id>/cancel")
def cancel(project_id, session_id):
    project, error = _project(project_id)
    if error: return error
    try:
        session = direct_uploads._session(current_user, project.id, session_id)
        session.status = "cancelled"
        from app.extensions import db
        db.session.commit()
        return _ok(upload_session_id=session.id, status=session.status)
    except StorageAuthorizationError: return _fail("upload_session_forbidden", "Phiên tải ảnh không hợp lệ.", 403)
    except StorageValidationError as exc: return _fail("upload_session_invalid", str(exc), 409)


@bp.post("/finalize")
@limiter.limit("20 per minute")
def finalize(project_id):
    project, error = _project(project_id)
    if error: return error
    result = finalize_daily_report_create_v2(project=project, user=current_user, payload=_payload())
    return _ok(report_id=result.id, redirect_url=url_for("reports.detail", report_id=result.id))
