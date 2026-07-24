from flask import abort, current_app, flash, redirect, request, url_for
from flask_login import current_user

from app.attachments import bp
from app.auth.permissions import can_edit_report, can_view_report
from app.extensions import db
from app.models import ReportAttachment, StorageDerivative
from app.reports.services import delete_attachment
from app.storage.providers import get_storage_provider
from app.storage.quota import ensure_bandwidth, record_download


@bp.get("/<int:attachment_id>")
def view(attachment_id):
    attachment = _authorised(attachment_id)
    obj = attachment.storage_object
    if not obj or obj.deleted_at is not None or obj.upload_status != "active":
        abort(410, description="Ảnh chưa được chuyển sang storage S3. Hãy migrate hoặc xóa dữ liệu development cũ.")
    derivative = StorageDerivative.query.filter(StorageDerivative.storage_object_id == obj.id,
        StorageDerivative.derivative_type.in_(("preview", "thumbnail")), StorageDerivative.deleted_at.is_(None)).order_by(
        StorageDerivative.derivative_type.desc()).first()
    target = derivative or obj
    source = derivative.derivative_type if derivative else "original"
    ensure_bandwidth(current_user, target.file_size, preview=True)
    record_download(current_user, kind="preview" if derivative else "original", source_type=source,
        module="daily-reports", estimated_bytes=target.file_size, storage_object_id=None if derivative else obj.id,
        derivative_id=derivative.id if derivative else None, estimated_storage_egress_bytes=target.file_size,
        estimated_client_egress_bytes=target.file_size)
    db.session.commit()
    return redirect(get_storage_provider().create_presigned_download(target.bucket, target.object_key,
        current_app.config["STORAGE_DOWNLOAD_URL_TTL_SECONDS"], "inline", obj.original_filename)["url"])


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
