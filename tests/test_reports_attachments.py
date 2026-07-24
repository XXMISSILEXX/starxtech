from io import BytesIO

from PIL import Image
from werkzeug.datastructures import MultiDict

from app.extensions import db
from app.models import AuditLog, DailyReport, ReportAttachment, StorageObject, User


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


def test_reporter_creates_report_for_assigned_project(client, app):
    login(client, "reporter")
    data = report_form()
    data.add("sections-0-images", image_upload())

    response = client.post(
        "/reports/projects/1/reports/create",
        data=data,
        content_type="multipart/form-data",
    )

    assert response.status_code == 302
    with app.app_context():
        report = DailyReport.query.filter_by(project_id=1).one()
        assert report.sections[0].content == "Concrete poured."
        assert len(report.sections[0].attachments) == 1
        assert AuditLog.query.filter_by(action="report.create", entity_id=report.id).count() == 1
        assert AuditLog.query.filter_by(action="attachment.create").count() == 1


def test_uploaded_image_url_resolves(client, app):
    login(client, "reporter")
    data = report_form()
    data.add("sections-0-images", image_upload())
    client.post("/reports/projects/1/reports/create", data=data, content_type="multipart/form-data")

    with app.app_context():
        attachment = ReportAttachment.query.one()
        attachment_id = attachment.id
        assert attachment.storage_object_id is not None
        assert attachment.storage_object.storage_module == "daily-reports"
        assert attachment.storage_object.upload_status == "active"

    response = client.get(f"/attachments/{attachment_id}")
    assert response.status_code == 302
    assert "fake-storage.invalid" in response.headers["Location"]


def test_attachment_download_redirects_to_original(client, app):
    login(client, "reporter")
    data = report_form(); data.add("sections-0-images", image_upload())
    client.post("/reports/projects/1/reports/create", data=data, content_type="multipart/form-data")
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
    client.post("/reports/projects/1/reports/create", data=report_form())
    with app.app_context():
        report_id = DailyReport.query.one().id

    response = client.get(f"/reports/{report_id}/edit")

    assert response.status_code == 200
    assert b"bi-tools" in response.data


def test_reporter_cannot_create_report_for_unassigned_project(client):
    login(client, "reporter")

    response = client.post("/reports/projects/2/reports/create", data=report_form(category_id=3))

    assert response.status_code == 403


def test_viewer_admin_cannot_create_or_edit_report(client, app):
    login(client, "super")
    client.post("/reports/projects/1/reports/create", data=report_form())
    client.post("/logout")

    login(client, "viewer")
    create_response = client.post("/reports/projects/1/reports/create", data=report_form("1", "2026-07-09"))
    assert create_response.status_code == 403

    with app.app_context():
        report_id = DailyReport.query.filter_by(project_id=1).one().id

    edit_response = client.post(f"/reports/{report_id}/edit", data=report_form())
    assert edit_response.status_code == 403


def test_duplicate_project_date_returns_validation_error_without_second_row(client, app):
    login(client, "reporter")
    first = client.post("/reports/projects/1/reports/create", data=report_form())
    assert first.status_code == 302

    duplicate = client.post("/reports/projects/1/reports/create", data=report_form(content="Second copy."))

    assert duplicate.status_code == 400
    assert "Dự án này đã có báo cáo cho ngày".encode() in duplicate.data
    with app.app_context():
        assert DailyReport.query.filter_by(project_id=1, report_date="2026-07-08").count() == 1


def test_duplicate_report_date_on_edit_returns_validation_error_without_autoflush(client, app):
    login(client, "reporter")
    assert client.post("/reports/projects/1/reports/create", data=report_form()).status_code == 302
    assert client.post(
        "/reports/projects/1/reports/create",
        data=report_form(report_date="2026-07-09", content="Second report."),
    ).status_code == 302
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


def test_duplicate_section_category_fails(client):
    login(client, "reporter")
    data = report_form()
    data.add("sections-1-category_id", "1")
    data.add("sections-1-status", "INFO")
    data.add("sections-1-content", "Duplicate category.")

    response = client.post("/reports/projects/1/reports/create", data=data)

    assert response.status_code == 400
    assert "Hạng mục không được trùng".encode() in response.data


def test_upload_more_than_three_images_for_one_section_fails(client):
    login(client, "reporter")
    data = report_form()
    for index in range(4):
        data.add("sections-0-images", image_upload(f"photo-{index}.jpg"))

    response = client.post(
        "/reports/projects/1/reports/create",
        data=data,
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert "tối đa 3 ảnh".encode() in response.data


def test_non_image_upload_fails(client):
    login(client, "reporter")
    data = report_form()
    data.add("sections-0-images", (BytesIO(b"not an image"), "bad.jpg"))

    response = client.post(
        "/reports/projects/1/reports/create",
        data=data,
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert "không phải ảnh hợp lệ".encode() in response.data


def test_attachment_view_enforces_project_read_permission(client, app):
    login(client, "super")
    data = report_form(category_id=3)
    data.add("sections-0-images", image_upload())
    client.post("/reports/projects/2/reports/create", data=data, content_type="multipart/form-data")

    with app.app_context():
        attachment_id = ReportAttachment.query.one().id

    client.post("/logout")
    login(client, "reporter")
    response = client.get(f"/attachments/{attachment_id}")

    assert response.status_code == 403


def test_attachment_delete_soft_deletes_and_audits(client, app):
    login(client, "reporter")
    data = report_form()
    data.add("sections-0-images", image_upload())
    client.post("/reports/projects/1/reports/create", data=data, content_type="multipart/form-data")

    with app.app_context():
        attachment_id = ReportAttachment.query.one().id

    response = client.post(f"/attachments/{attachment_id}/delete")

    assert response.status_code == 302
    with app.app_context():
        attachment = db.session.get(ReportAttachment, attachment_id)
        assert attachment.deleted_at is not None
        assert AuditLog.query.filter_by(action="attachment.delete", entity_id=attachment_id).count() == 1


def test_reporter_cannot_delete_attachment_from_another_reporter(client, app):
    login(client, "super")
    data = report_form()
    data.add("sections-0-images", image_upload())
    client.post("/reports/projects/1/reports/create", data=data, content_type="multipart/form-data")
    with app.app_context():
        attachment_id = ReportAttachment.query.one().id

    client.post("/logout")
    login(client, "reporter")
    assert client.post(f"/attachments/{attachment_id}/delete").status_code == 403

    with app.app_context():
        assert db.session.get(ReportAttachment, attachment_id).deleted_at is None


def test_viewer_admin_cannot_delete_report_attachment(client, app):
    login(client, "super")
    data = report_form()
    data.add("sections-0-images", image_upload())
    client.post("/reports/projects/1/reports/create", data=data, content_type="multipart/form-data")
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
    data = report_form()
    data.add("sections-0-images", image_upload())
    client.post("/reports/projects/1/reports/create", data=data, content_type="multipart/form-data")
    with app.app_context():
        attachment_id = ReportAttachment.query.one().id

    assert client.post(f"/attachments/{attachment_id}/delete").status_code == 403


def test_report_update_and_delete_write_audit_rows(client, app):
    login(client, "super")
    client.post("/reports/projects/1/reports/create", data=report_form())
    with app.app_context():
        report_id = DailyReport.query.one().id

    updated_data = report_form(content="Updated section content.")
    updated_data["highlight"] = "Updated highlight."
    updated = client.post(f"/reports/{report_id}/edit", data=updated_data)
    assert updated.status_code == 302

    deleted = client.post(f"/reports/{report_id}/delete")
    assert deleted.status_code == 302
    with app.app_context():
        report = db.session.get(DailyReport, report_id)
        assert report.deleted_at is not None
        assert AuditLog.query.filter_by(action="report.update", entity_id=report_id).count() == 1
        assert AuditLog.query.filter_by(action="report.delete", entity_id=report_id).count() == 1


def test_report_edit_post_success_shows_vietnamese_message(client, app):
    login(client, "reporter")
    client.post("/reports/projects/1/reports/create", data=report_form())
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
    client.post("/reports/projects/1/reports/create", data=report_form())
    with app.app_context():
        report_id = DailyReport.query.one().id

    invalid_data = report_form()
    invalid_data["highlight"] = ""
    response = client.post(f"/reports/{report_id}/edit", data=invalid_data)

    assert response.status_code == 400
    assert "Vui lòng nhập điểm nổi bật.".encode() in response.data


def test_report_create_missing_section_content_preserves_entered_data(client):
    login(client, "reporter")
    data = report_form(content="")
    data["highlight"] = "Highlight giữ lại sau lỗi."
    data["summary_note"] = "Note giữ lại sau lỗi."
    data.add("sections-1-category_id", "2")
    data.add("sections-1-status", "ATTENTION")
    data.add("sections-1-content", "Nội dung section khác vẫn còn.")

    response = client.post("/reports/projects/1/reports/create", data=data)

    assert response.status_code == 400
    assert "Mỗi phần báo cáo phải có nội dung.".encode() in response.data
    assert "Highlight giữ lại sau lỗi.".encode() in response.data
    assert "Note giữ lại sau lỗi.".encode() in response.data
    assert "Nội dung section khác vẫn còn.".encode() in response.data
    assert b'value="2" data-icon' in response.data
    assert b'value="ATTENTION"' in response.data


def test_report_edit_validation_fail_keeps_existing_attachment(client, app):
    login(client, "reporter")
    data = report_form()
    data.add("sections-0-images", image_upload())
    client.post("/reports/projects/1/reports/create", data=data, content_type="multipart/form-data")
    with app.app_context():
        report_id = DailyReport.query.one().id
        attachment_id = ReportAttachment.query.one().id

    invalid_data = report_form()
    invalid_data["highlight"] = ""
    response = client.post(f"/reports/{report_id}/edit", data=invalid_data)

    assert response.status_code == 400
    assert f"/attachments/{attachment_id}".encode() in response.data
