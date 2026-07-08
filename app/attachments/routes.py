from pathlib import Path

from flask import abort, flash, redirect, request, send_file, url_for

from app.attachments import bp
from app.auth.permissions import can_read_project, can_write_project
from app.models import ReportAttachment
from app.reports.services import delete_attachment


@bp.get("/<int:attachment_id>")
def view(attachment_id):
    attachment = _attachment_or_404(attachment_id)
    project_id = attachment.section.daily_report.project_id
    if not can_read_project(project_id):
        abort(403)

    path = Path(attachment.file_path)
    if not path.exists():
        abort(404)
    return send_file(path, mimetype=attachment.mime_type, download_name=attachment.original_filename)


@bp.post("/<int:attachment_id>/delete")
def delete(attachment_id):
    attachment = _attachment_or_404(attachment_id)
    report = attachment.section.daily_report
    if not can_write_project(report.project_id):
        abort(403)
    delete_attachment(attachment)
    flash("Attachment deleted.", "success")
    next_url = request.form.get("next") or url_for("reports.edit", report_id=report.id)
    return redirect(next_url)


def _attachment_or_404(attachment_id):
    return ReportAttachment.query.filter(
        ReportAttachment.id == attachment_id,
        ReportAttachment.deleted_at.is_(None),
    ).first_or_404()
