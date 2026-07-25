from io import BytesIO
from uuid import uuid4

from PIL import Image
from sqlalchemy import select
from werkzeug.datastructures import MultiDict

from app.extensions import db
from app.models import (AuditLog, DailyReport, DailyReportSection, MediaProcessingJob,
                        ReportAttachment, StorageDerivative, StorageObject,
                        UploadBatchItem, UploadSelectionSession, User)
from tests.helpers.daily_report_create_v2 import DailyReportV2UploadFile, submit_daily_report_create_v2


def login(client, username_or_email, password="password123"):
    return client.post(
        "/login",
        data={
            "username_or_email": username_or_email,
            "password": password,
        },
    )


def image_upload(name="photo.jpg", image_format="JPEG"):
    stream = BytesIO()
    Image.new("RGB", (32, 32), color=(40, 120, 200)).save(stream, format=image_format)
    stream.seek(0)
    return stream, name


def image_bytes(image_format="JPEG"):
    stream, _ = image_upload(image_format=image_format)
    return stream.read()


def direct_report(client, app, *, project_id=1, category_id=None, form=None, files=None, submit_url=None):
    form = form or report_form(category_id=category_id or (3 if project_id == 2 else 1))
    date = form["report_date"]
    source_files = [DailyReportV2UploadFile(image_bytes(), "photo.jpg")] if files is None else files
    normalized_files = [DailyReportV2UploadFile(file.data, file.filename, file.mime_type, file.section_index,)
                        if hasattr(file, "data") else file for file in source_files]
    result = submit_daily_report_create_v2(client, app, project_id=project_id,
        report={"report_date": date, "overall_status": form["overall_status"], "highlight": form["highlight"], "summary_note": form["summary_note"]},
        sections=[{"report_category_id": int(form["sections-0-category_id"]), "status": form["sections-0-status"], "content": form["sections-0-content"]}], files=normalized_files)
    result["response"] = result["finalize_response"]
    return result


def report_form(category_id=1, report_date="2026-07-08", content="Concrete poured."):
    return MultiDict(
        [
            ("report_date", report_date),
            ("overall_status", "UPDATED"),
            ("highlight", "Daily progress updated."),
            ("summary_note", "No major blockers."),
            ("sections-0-category_id", str(category_id)),
            ("sections-0-status", "GOOD"),
            ("sections-0-content", content),
        ]
    )


def v2_preflight_payload(form=None, *, project_id=1, sections=None, files=None):
    form = form or report_form(category_id=3 if project_id == 2 else 1)
    sections = sections or [{"category_id": int(form["sections-0-category_id"]), "status": form["sections-0-status"], "content": form["sections-0-content"]}]
    return {"client_request_id": str(uuid4()), "report_date": form["report_date"],
            "overall_status": form["overall_status"], "highlight": form["highlight"],
            "summary_note": form["summary_note"],
            "sections": [{"client_section_id": str(uuid4()), "category_id": row["category_id"], "status": row["status"], "content": row["content"], "sort_order": index} for index, row in enumerate(sections)],
            "files": files or []}


def test_reporter_creates_report_for_assigned_project(client, app):
    login(client, "reporter")
    result = direct_report(client, app)
    response = result["response"]

    assert response.status_code == 200
    with app.app_context():
        report = DailyReport.query.filter_by(project_id=1).one()
        assert report.sections[0].content == "Concrete poured."
        assert len(report.sections[0].attachments) == 1
        assert result["upload_session"].status == "finalized"
        provider = app.extensions["storage_provider"]
        storage = result["storage_objects"][0]
        assert provider.objects[(storage.bucket, storage.object_key)]["bytes"] == image_bytes()
        assert AuditLog.query.filter_by(action="report.create", entity_id=report.id).count() == 1
        assert AuditLog.query.filter_by(action="attachment.create").count() == 1


def test_legacy_multipart_post_returns_405_without_side_effects(client, app):
    login(client, "reporter")
    data = report_form(); data.add("sections-0-images", image_upload())
    response = client.post("/reports/projects/1/reports/create", data=data, content_type="multipart/form-data")
    assert response.status_code == 405
    with app.app_context():
        assert db.session.scalar(select(DailyReport)) is None
        assert db.session.scalar(select(StorageObject)) is None
        assert db.session.scalar(select(MediaProcessingJob)) is None
        assert db.session.scalar(select(UploadSelectionSession)) is None


def test_legacy_json_accept_post_returns_405_without_side_effects(client, app):
    login(client, "reporter")
    data = report_form(); data.add("sections-0-images", image_upload())
    response = client.post("/reports/projects/1/reports/create", data=data,
        content_type="multipart/form-data", headers={"Accept": "application/json"})
    assert response.status_code == 405
    with app.app_context():
        assert db.session.scalar(select(DailyReport)) is None
        assert db.session.scalar(select(UploadSelectionSession)) is None
        assert db.session.scalar(select(StorageObject)) is None


def test_no_image_v2_finalize_creates_report_without_upload_session(client, app):
    login(client, "reporter")
    result = direct_report(client, app, files=[])
    assert result["response"].status_code == 200
    assert result["upload_session_id"] is None
    assert result["upload_session"] is None
    with app.app_context():
        assert DailyReport.query.count() == 1
        assert DailyReportSection.query.count() == 1
        assert ReportAttachment.query.count() == 0


def test_direct_upload_rejects_unsupported_metadata_without_creating_item_or_object(client, app):
    login(client, "reporter")
    session = client.post("/api/projects/1/daily-reports/upload-sessions", json={"file_count": 1, "total_size_bytes": 3}).get_json()["data"]
    response = client.post(f"/api/projects/1/daily-reports/upload-sessions/{session['upload_session_id']}/presign", json={"files": [{
        "client_file_id": "bad-file", "client_section_id": "section-0", "filename": "bad.txt",
        "mime_type": "text/plain", "size": 3,
    }]})
    assert response.status_code == 422
    with app.app_context():
        assert db.session.scalar(select(UploadBatchItem)) is None
        assert db.session.scalar(select(StorageObject)) is None


def test_v2_finalize_rejects_incomplete_upload_item_without_creating_report(client, app):
    login(client, "reporter")
    section_id, file_id = str(uuid4()), str(uuid4())
    session = client.post("/api/projects/1/daily-reports/upload-sessions", json={"file_count": 1, "total_size_bytes": len(image_bytes())}).get_json()["data"]
    presign = client.post(f"/api/projects/1/daily-reports/upload-sessions/{session['upload_session_id']}/presign", json={"files": [{"client_file_id": file_id, "client_section_id": section_id, "filename": "pending.jpg", "mime_type": "image/jpeg", "size": len(image_bytes())}]})
    assert presign.status_code == 200
    item_id = presign.get_json()["data"]["items"][0]["upload_batch_item_id"]
    response = client.post("/api/projects/1/daily-reports/finalize", json={"client_request_id": str(uuid4()), "report_date": "2026-07-08", "overall_status": "UPDATED", "highlight": "Pending upload", "summary_note": "", "upload_session_id": session["upload_session_id"], "sections": [{"client_section_id": section_id, "report_category_id": 1, "status": "GOOD", "content": "Pending", "sort_order": 0}], "attachments": [{"upload_item_id": item_id, "client_section_id": section_id, "sort_order": 0}]})
    assert response.status_code == 422
    with app.app_context():
        assert DailyReport.query.count() == 0
        assert ReportAttachment.query.count() == 0


def test_uploaded_image_url_resolves(client, app):
    login(client, "reporter")
    direct_report(client, app)

    with app.app_context():
        attachment = ReportAttachment.query.one()
        attachment_id = attachment.id
        assert attachment.storage_object_id is not None
        assert attachment.storage_object.storage_module == "daily-reports"
        assert attachment.storage_object.upload_status == "active"

    response = client.get(f"/attachments/{attachment_id}")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/static/img/attachment-processing.svg")


def test_attachment_download_redirects_to_original(client, app):
    login(client, "reporter")
    direct_report(client, app)
    with app.app_context(): attachment_id = ReportAttachment.query.one().id
    response = client.get(f"/attachments/{attachment_id}/download")
    assert response.status_code == 302
    assert "fake-storage.invalid" in response.headers["Location"]


def test_category_icon_appears_in_report_create_form(client):
    login(client, "reporter")
    response = client.get("/reports/projects/1/reports/create")

    assert response.status_code == 200
    assert b"bi-tools" in response.data


def test_category_icon_appears_in_report_edit_form(client, app):
    login(client, "reporter")
    direct_report(client, app)
    with app.app_context():
        report_id = DailyReport.query.one().id

    response = client.get(f"/reports/{report_id}/edit")

    assert response.status_code == 200
    assert b"bi-tools" in response.data


def test_reporter_cannot_create_report_for_unassigned_project(client, app):
    login(client, "reporter")
    response = client.post("/api/projects/2/daily-reports/preflight", json=v2_preflight_payload(project_id=2))
    assert response.status_code == 403
    with app.app_context():
        assert DailyReport.query.count() == UploadSelectionSession.query.count() == StorageObject.query.count() == 0


def test_viewer_admin_cannot_create_or_edit_report(client, app):
    login(client, "super")
    direct_report(client, app)
    client.post("/logout")

    login(client, "viewer")
    create_response = client.post("/api/projects/1/daily-reports/preflight", json=v2_preflight_payload(report_form("1", "2026-07-09")))
    assert create_response.status_code == 403

    with app.app_context():
        report_id = DailyReport.query.filter_by(project_id=1).one().id

    edit_response = client.post(f"/reports/{report_id}/edit", data=report_form())
    assert edit_response.status_code == 403


def test_duplicate_project_date_returns_validation_error_without_second_row(client, app):
    login(client, "reporter")
    direct_report(client, app)
    duplicate = client.post("/api/projects/1/daily-reports/preflight", json=v2_preflight_payload(report_form(content="Second copy.")))
    assert duplicate.status_code == 409
    with app.app_context():
        assert DailyReport.query.filter_by(project_id=1, report_date="2026-07-08").count() == 1


def test_duplicate_report_date_on_edit_returns_validation_error_without_autoflush(client, app):
    login(client, "reporter")
    direct_report(client, app)
    direct_report(client, app, form=report_form(report_date="2026-07-09", content="Second report."))
    with app.app_context():
        reports = DailyReport.query.filter_by(project_id=1).order_by(DailyReport.report_date).all()
        first_id, second_id = reports[0].id, reports[1].id

    response = client.post(
        f"/reports/{second_id}/edit",
        data=report_form(report_date="2026-07-08", content="Must not overwrite."),
    )

    assert response.status_code == 400
    assert "Dự án này đã có báo cáo cho ngày".encode() in response.data
    with app.app_context():
        assert DailyReport.query.filter_by(project_id=1, report_date="2026-07-08").count() == 1
        assert db.session.get(DailyReport, first_id).report_date.isoformat() == "2026-07-08"
        assert db.session.get(DailyReport, second_id).report_date.isoformat() == "2026-07-09"


def test_duplicate_section_category_fails_v2_preflight_without_side_effects(client, app):
    login(client, "reporter")
    payload = v2_preflight_payload(sections=[{"category_id": 1, "status": "GOOD", "content": "One"}, {"category_id": 1, "status": "INFO", "content": "Duplicate"}])
    response = client.post("/api/projects/1/daily-reports/preflight", json=payload)
    assert response.status_code == 422
    assert response.get_json()["error"]["field_errors"]["sections"]
    with app.app_context(): assert DailyReport.query.count() == UploadSelectionSession.query.count() == StorageObject.query.count() == 0


def test_upload_more_than_three_images_for_one_section_fails(client, app):
    login(client, "reporter")
    files = [DailyReportV2UploadFile(image_bytes(), filename=f"photo-{index}.jpg") for index in range(4)]
    import pytest
    with pytest.raises(ValueError, match="three"):
        direct_report(client, app, files=files)
    with app.app_context():
        assert db.session.scalar(select(DailyReport)) is None


def test_non_image_upload_fails(client, app):
    login(client, "reporter")
    session = client.post("/api/projects/1/daily-reports/upload-sessions", json={"file_count": 1, "total_size_bytes": 3}).get_json()["data"]
    response = client.post(f"/api/projects/1/daily-reports/upload-sessions/{session['upload_session_id']}/presign", json={"files": [{"client_file_id": str(uuid4()), "client_section_id": str(uuid4()), "filename": "bad.txt", "mime_type": "text/plain", "size": 3}]})
    assert response.status_code == 422
    with app.app_context():
        assert db.session.scalar(select(DailyReport)) is None


def test_attachment_view_enforces_project_read_permission(client, app):
    login(client, "super")
    direct_report(client, app, project_id=2, category_id=3)

    with app.app_context():
        attachment_id = ReportAttachment.query.one().id

    client.post("/logout")
    login(client, "reporter")
    response = client.get(f"/attachments/{attachment_id}")

    assert response.status_code == 403


def test_attachment_delete_hard_deletes_storage_and_audits(client, app):
    login(client, "reporter")
    direct_report(client, app)

    with app.app_context():
        attachment_id = ReportAttachment.query.one().id
        storage = db.session.get(StorageObject, ReportAttachment.query.one().storage_object_id)
        derivative = StorageDerivative(storage_object_id=storage.id, derivative_type="preview", bucket=storage.bucket,
            object_key="daily-reports/derivatives/delete-preview.webp", mime_type="image/webp", file_ext="webp", file_size=1)
        job = MediaProcessingJob.query.filter_by(storage_object_id=storage.id, job_type="image_derivatives").one()
        db.session.add(derivative); db.session.commit()
        provider = app.extensions["storage_provider"]
        provider.put_bytes(derivative.bucket, derivative.object_key, b"preview", derivative.mime_type)
        storage_id, derivative_id, job_id = storage.id, derivative.id, job.id

    response = client.post(f"/attachments/{attachment_id}/delete")

    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(ReportAttachment, attachment_id) is None
        assert db.session.get(StorageDerivative, derivative_id) is None
        assert db.session.get(MediaProcessingJob, job_id) is None
        assert db.session.get(StorageObject, storage_id) is None
        assert (storage.bucket, storage.object_key) in provider.deleted
        assert (derivative.bucket, derivative.object_key) in provider.deleted
        assert AuditLog.query.filter_by(action="attachment.delete", entity_id=attachment_id).count() == 1


def test_reporter_cannot_delete_attachment_from_another_reporter(client, app):
    login(client, "super")
    direct_report(client, app)
    with app.app_context():
        attachment_id = ReportAttachment.query.one().id

    client.post("/logout")
    login(client, "reporter")
    assert client.post(f"/attachments/{attachment_id}/delete").status_code == 403

    with app.app_context():
        assert db.session.get(ReportAttachment, attachment_id) is not None


def test_viewer_admin_cannot_delete_report_attachment(client, app):
    login(client, "super")
    direct_report(client, app)
    with app.app_context():
        attachment_id = ReportAttachment.query.one().id

    client.post("/logout")
    login(client, "viewer")
    assert client.post(f"/attachments/{attachment_id}/delete").status_code == 403


def test_attachment_delete_requires_report_edit_capability(client, app):
    with app.app_context():
        reporter = User.query.filter_by(username="reporter").one()
        membership = reporter.project_assignments[0]
        membership.can_edit_own_reports = False
        db.session.commit()

    login(client, "reporter")
    direct_report(client, app)
    with app.app_context():
        attachment_id = ReportAttachment.query.one().id

    assert client.post(f"/attachments/{attachment_id}/delete").status_code == 403


def test_report_update_and_delete_write_audit_rows(client, app):
    login(client, "super")
    direct_report(client, app)
    with app.app_context():
        report_id = DailyReport.query.one().id

    updated_data = report_form(content="Updated section content.")
    updated_data["highlight"] = "Updated highlight."
    updated = client.post(f"/reports/{report_id}/edit", data=updated_data)
    assert updated.status_code == 302

    deleted = client.post(f"/reports/{report_id}/delete")
    assert deleted.status_code == 302
    with app.app_context():
        assert db.session.get(DailyReport, report_id) is None
        assert AuditLog.query.filter_by(action="report.update", entity_id=report_id).count() == 1
        assert AuditLog.query.filter_by(action="report.delete", entity_id=report_id).count() == 1


def test_report_delete_hard_deletes_attachments_storage_and_allows_same_date(client, app):
    login(client, "reporter")
    assert direct_report(client, app)["response"].status_code == 200
    with app.app_context():
        attachment = ReportAttachment.query.one()
        report_id, attachment_id, object_id = attachment.section.daily_report_id, attachment.id, attachment.storage_object_id
        obj = db.session.get(StorageObject, object_id)
        derivative = StorageDerivative(storage_object_id=obj.id, derivative_type="preview", bucket=obj.bucket,
            object_key="daily-reports/derivatives/report-delete-preview.webp", mime_type="image/webp",
            file_ext="webp", file_size=1)
        db.session.add(derivative); db.session.commit()
        derivative_id = derivative.id
        provider = app.extensions["storage_provider"]
        provider.put_bytes(obj.bucket, obj.object_key, b"original", obj.mime_type)
        provider.put_bytes(derivative.bucket, derivative.object_key, b"preview", derivative.mime_type)
        deleted_keys = {(obj.bucket, obj.object_key), (derivative.bucket, derivative.object_key)}

    client.post("/logout")
    login(client, "super")
    assert client.post(f"/reports/{report_id}/delete").status_code == 302
    with app.app_context():
        assert db.session.get(DailyReport, report_id) is None
        assert db.session.get(ReportAttachment, attachment_id) is None
        assert db.session.get(StorageDerivative, derivative_id) is None
        assert db.session.get(StorageObject, object_id) is None
    assert deleted_keys <= set(provider.deleted)
    client.post("/logout")
    login(client, "reporter")
    assert direct_report(client, app)["response"].status_code == 200


def test_report_edit_post_success_shows_vietnamese_message(client, app):
    login(client, "reporter")
    direct_report(client, app)
    with app.app_context():
        report_id = DailyReport.query.one().id

    updated_data = report_form(content="Nội dung đã cập nhật.")
    updated_data["highlight"] = "Điểm nổi bật đã cập nhật."
    response = client.post(
        f"/reports/{report_id}/edit",
        data=updated_data,
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Đã cập nhật báo cáo thành công.".encode() in response.data
    assert "Điểm nổi bật đã cập nhật.".encode() in response.data


def test_report_edit_validation_error_shows_message(client, app):
    login(client, "reporter")
    direct_report(client, app)
    with app.app_context():
        report_id = DailyReport.query.one().id

    invalid_data = report_form()
    invalid_data["highlight"] = ""
    response = client.post(f"/reports/{report_id}/edit", data=invalid_data)

    assert response.status_code == 400
    assert "Vui lòng nhập điểm nổi bật.".encode() in response.data


def test_v2_preflight_missing_section_content_creates_no_side_effects(client, app):
    login(client, "reporter")
    payload = v2_preflight_payload(sections=[{"category_id": 1, "status": "GOOD", "content": ""}, {"category_id": 2, "status": "ATTENTION", "content": "Nội dung section khác vẫn còn."}])
    payload["highlight"] = "Highlight giữ lại sau lỗi."
    payload["summary_note"] = "Note giữ lại sau lỗi."
    response = client.post("/api/projects/1/daily-reports/preflight", json=payload)
    assert response.status_code == 422
    assert response.get_json()["error"]["field_errors"]["sections"]
    with app.app_context(): assert DailyReport.query.count() == UploadSelectionSession.query.count() == StorageObject.query.count() == 0


def test_report_edit_validation_fail_keeps_existing_attachment(client, app):
    login(client, "reporter")
    direct_report(client, app)
    with app.app_context():
        report_id = DailyReport.query.one().id
        attachment_id = ReportAttachment.query.one().id

    invalid_data = report_form()
    invalid_data["highlight"] = ""
    response = client.post(f"/reports/{report_id}/edit", data=invalid_data)

    assert response.status_code == 400
    assert f"/attachments/{attachment_id}".encode() in response.data
