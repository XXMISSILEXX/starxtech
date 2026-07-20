from pathlib import Path

from flask import abort, current_app, flash, redirect, request, send_file, url_for

from app.attachments import bp
from flask_login import current_user

from app.auth.permissions import can_edit_report, can_view_report
from app.models import ReportAttachment
from app.reports.services import delete_attachment


@bp.get("/<int:attachment_id>")
def view(attachment_id):
    attachment = _attachment_or_404(attachment_id)
    report = attachment.section.daily_report
    if not current_user.can("report_attachments.view") or not can_view_report(current_user, report):
        abort(403)

    path = _resolve_attachment_path(attachment.file_path)
    if not path.exists():
        abort(404)
    return send_file(path, mimetype=attachment.mime_type, download_name=attachment.original_filename)


@bp.post("/<int:attachment_id>/delete")
def delete(attachment_id):
    attachment = _attachment_or_404(attachment_id)
    report = attachment.section.daily_report
    if not current_user.can("report_attachments.delete") or not can_edit_report(current_user, report):
        abort(403)
    delete_attachment(attachment)
    flash("Đã xóa ảnh đính kèm.", "success")
    next_url = request.form.get("next") or url_for("reports.edit", report_id=report.id)
    return redirect(next_url)


def _resolve_attachment_path(stored_path):
    path = Path(stored_path or "")
    upload_root = Path(current_app.config["UPLOAD_ROOT"]).resolve()
    if path.is_absolute() or ".." in path.parts:
        abort(404)
    candidate = (upload_root / path).resolve()
    try:
        candidate.relative_to(upload_root)
    except ValueError:
        abort(404)
    return candidate


def _attachment_or_404(attachment_id):
    return ReportAttachment.query.filter(
        ReportAttachment.id == attachment_id,
        ReportAttachment.deleted_at.is_(None),
    ).first_or_404()
