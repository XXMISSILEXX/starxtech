from datetime import datetime, timedelta
from flask import abort, current_app, flash, jsonify, redirect, request, url_for
from flask_login import current_user

from app.attachments import bp
from app.auth.permissions import can_edit_report, can_view_report
from app.extensions import db
from app.models import MediaProcessingJob, ReportAttachment, StorageDerivative
from app.reports.services import delete_attachment
from app.storage.providers import get_storage_provider
from app.storage.quota import ensure_bandwidth, record_download


@bp.get("/<int:attachment_id>")
def view(attachment_id):
    attachment = _authorised(attachment_id)
    obj, derivative = _preview_target(attachment, ("preview", "thumbnail"))
    if derivative is None:
        return _no_store(redirect(url_for("static", filename="img/attachment-processing.svg")))
    target = derivative
    source = derivative.derivative_type
    ensure_bandwidth(current_user, target.file_size, preview=True)
    record_download(current_user, kind="preview", source_type=source,
        module="daily-reports", estimated_bytes=target.file_size, storage_object_id=None,
        derivative_id=derivative.id, estimated_storage_egress_bytes=target.file_size,
        estimated_client_egress_bytes=target.file_size)
    db.session.commit()
    response = redirect(get_storage_provider().create_presigned_download(target.bucket, target.object_key,
        current_app.config["STORAGE_DOWNLOAD_URL_TTL_SECONDS"], "inline", obj.original_filename)["url"])
    response.headers["Cache-Control"] = "private, max-age=60"
    return response


@bp.get("/<int:attachment_id>/thumbnail")
def thumbnail(attachment_id):
    attachment = _authorised(attachment_id)
    obj, derivative = _preview_target(attachment, ("thumbnail",))
    if derivative is None:
        return _no_store(redirect(url_for("static", filename="img/attachment-processing.svg")))
    response = redirect(get_storage_provider().create_presigned_download(
        derivative.bucket, derivative.object_key,
        current_app.config["STORAGE_DOWNLOAD_URL_TTL_SECONDS"], "inline", obj.original_filename,
    )["url"])
    response.headers["Cache-Control"] = "private, max-age=60"
    return response


@bp.get("/<int:attachment_id>/status")
def status(attachment_id):
    response = jsonify(_attachment_status(_authorised(attachment_id)))
    return _no_store(response)


@bp.post("/status-batch")
def status_batch():
    payload = request.get_json(silent=True) or {}
    values = payload.get("attachment_ids", [])
    if not isinstance(values, list) or len(values) > 100:
        abort(400, description="Danh sách ảnh không hợp lệ.")
    ids = list(dict.fromkeys(value for value in values if isinstance(value, int)))
    rows = ReportAttachment.query.filter(ReportAttachment.id.in_(ids), ReportAttachment.deleted_at.is_(None)).all()
    allowed = []
    for attachment in rows:
        if can_view_report(current_user, attachment.section.daily_report):
            allowed.append(_attachment_status(attachment))
    return _no_store(jsonify(attachments=allowed))


@bp.get("/<int:attachment_id>/download")
def download(attachment_id):
    attachment = _authorised(attachment_id)
    obj = attachment.storage_object
    if not obj or obj.deleted_at is not None or obj.upload_status != "active":
        abort(410, description="Ảnh chưa được chuyển sang storage S3.")
    ensure_bandwidth(current_user, obj.file_size)
    record_download(current_user, kind="original", source_type="original", module="daily-reports",
        estimated_bytes=obj.file_size, storage_object_id=obj.id, estimated_storage_egress_bytes=obj.file_size,
        estimated_client_egress_bytes=obj.file_size)
    db.session.commit()
    return redirect(get_storage_provider().create_presigned_download(obj.bucket, obj.object_key,
        current_app.config["STORAGE_DOWNLOAD_URL_TTL_SECONDS"], "attachment", obj.original_filename)["url"])


@bp.post("/<int:attachment_id>/delete")
def delete(attachment_id):
    attachment = _attachment_or_404(attachment_id)
    report = attachment.section.daily_report
    if not can_edit_report(current_user, report): abort(403)
    delete_attachment(attachment)
    flash("Đã xóa ảnh đính kèm.", "success")
    return redirect(request.form.get("next") or url_for("reports.edit", report_id=report.id))


def _authorised(attachment_id):
    attachment = _attachment_or_404(attachment_id)
    if not can_view_report(current_user, attachment.section.daily_report): abort(403)
    return attachment


def _attachment_or_404(attachment_id):
    return ReportAttachment.query.filter(ReportAttachment.id == attachment_id, ReportAttachment.deleted_at.is_(None)).first_or_404()


def _preview_target(attachment, preferred_types):
    obj = attachment.storage_object
    if not obj or obj.deleted_at is not None or obj.upload_status != "active":
        abort(410, description="Ảnh chưa được chuyển sang storage S3.")
    for derivative_type in preferred_types:
        derivative = StorageDerivative.query.filter_by(
            storage_object_id=obj.id, derivative_type=derivative_type, deleted_at=None,
        ).first()
        if derivative:
            return obj, derivative
    return obj, None


def _attachment_status(attachment):
    obj = attachment.storage_object
    if not obj or obj.upload_status != "active":
        return {"attachment_id": attachment.id, "status": "failed", "message": "Không thể tạo ảnh xem trước."}
    derivatives = {item.derivative_type: item for item in StorageDerivative.query.filter_by(
        storage_object_id=obj.id, deleted_at=None
    ).all()}
    thumbnail, preview = derivatives.get("thumbnail"), derivatives.get("preview")
    result = {"attachment_id": attachment.id, "thumbnail_ready": bool(thumbnail), "preview_ready": bool(preview)}
    if thumbnail:
        result["thumbnail_url"] = url_for("attachments.thumbnail", attachment_id=attachment.id, v=thumbnail.id)
    if preview or thumbnail:
        version = (preview or thumbnail).id
        result["preview_url"] = url_for("attachments.view", attachment_id=attachment.id, v=version)
    if thumbnail and preview:
        result["status"] = "ready"
    elif thumbnail:
        result["status"] = "partial"
    else:
        job = MediaProcessingJob.query.filter_by(storage_object_id=obj.id, job_type="image_derivatives").first()
        if obj.processing_status == "failed" or (job and job.status == "failed"):
            result.update(status="failed", message="Không thể tạo ảnh xem trước.")
        elif job and job.status == "succeeded":
            result.update(status="failed", message="Không thể tạo ảnh xem trước.")
        elif not job and attachment.created_at and attachment.created_at < datetime.utcnow() - timedelta(minutes=5):
            result.update(status="recovery_pending", message="Ảnh đang chờ xử lý lại.")
        else:
            result["status"] = "processing"
    return result


def _no_store(response):
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
