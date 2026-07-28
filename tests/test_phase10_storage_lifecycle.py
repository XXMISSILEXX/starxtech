from io import BytesIO

import pytest
from PIL import Image
from werkzeug.datastructures import FileStorage

from app.display_images import (DisplayImageCleanupError, DisplayImageError,
                                cleanup_unreferenced_display_images,
                                finalize_display_image_change, remove_display_image,
                                replace_display_image)
from app.extensions import db
from app.models import (Company, Partner, ReportAttachment, StorageDerivative,
                        StorageObject, SystemSetting, UploadSelectionSession, User)
from app.reports import direct_uploads
from app.storage.providers import FakeStorageProvider, get_storage_provider
from app.storage.quota import storage_usage_bytes
from tests.test_phase10_cleanup_delete import _session_with_object
from tests.test_reports_attachments import login
from tests.test_security_hardening import _report_attachment


def _image_upload(name="avatar.jpg", color="navy"):
    data = BytesIO()
    Image.new("RGB", (16, 16), color).save(data, "JPEG")
    data.seek(0)
    return FileStorage(data, filename=name, content_type="image/jpeg")


def test_cancel_cleanup_failure_stays_cancelled_and_is_reconcilable(client, app):
    session_id, object_id, key = _session_with_object(app, "reporter", 1)

    class FailingDeleteProvider(FakeStorageProvider):
        def delete_object(self, bucket, object_key):
            raise RuntimeError("provider unavailable")

    with app.app_context():
        failing = FailingDeleteProvider()
        failing.objects.update(app.extensions["storage_provider"].objects)
        app.extensions["storage_provider"] = failing
    assert login(client, "reporter").status_code == 302
    response = client.post(f"/api/projects/1/daily-reports/upload-sessions/{session_id}/cancel")
    assert response.status_code == 500
    with app.app_context():
        assert db.session.get(UploadSelectionSession, session_id).status == "cancelled"
        assert db.session.get(StorageObject, object_id) is not None
        retry = FakeStorageProvider()
        retry.objects.update(app.extensions["storage_provider"].objects)
        summary = direct_uploads.cleanup_expired_sessions(dry_run=False, provider=retry)
        assert summary["cleaned"] == 1
        assert db.session.get(StorageObject, object_id) is None
        assert key not in retry.objects


def test_display_image_replacement_and_delete_remove_only_unreferenced_bytes(app):
    with app.app_context():
        user = User.query.filter_by(username="reporter").one()
        first = replace_display_image(user, _image_upload(), attribute="avatar_storage_object", scope="account-profiles", user=user)
        db.session.commit()
        finalize_display_image_change(first)
        old_id, old_key = first.object.id, (first.object.bucket, first.object.object_key)

        with pytest.raises(DisplayImageError):
            replace_display_image(user, FileStorage(BytesIO(b"not an image"), filename="bad.txt"), attribute="avatar_storage_object", scope="account-profiles", user=user)
        assert user.avatar_storage_object_id == old_id

        replacement = replace_display_image(user, _image_upload(color="green"), attribute="avatar_storage_object", scope="account-profiles", user=user)
        db.session.commit()
        finalize_display_image_change(replacement)
        assert db.session.get(StorageObject, old_id) is None
        assert old_key not in app.extensions["storage_provider"].objects

        current_id = replacement.object.id
        removal = remove_display_image(user, attribute="avatar_storage_object")
        db.session.commit()
        finalize_display_image_change(removal)
        finalize_display_image_change(removal)  # repeated delete is idempotent
        assert user.avatar_storage_object_id is None
        assert db.session.get(StorageObject, current_id) is None


def test_display_image_references_and_provider_failures_remain_visible_and_retryable(app):
    with app.app_context():
        user = User.query.filter_by(username="reporter").one()
        first = replace_display_image(user, _image_upload(), attribute="avatar_storage_object", scope="account-profiles", user=user)
        db.session.commit()
        finalize_display_image_change(first)
        shared = first.object
        db.session.add(SystemSetting(key="branding", brand_logo_storage_object_id=shared.id))
        replacement = replace_display_image(user, _image_upload(color="purple"), attribute="avatar_storage_object", scope="account-profiles", user=user)
        db.session.commit()
        assert finalize_display_image_change(replacement)["skipped"] is True
        assert db.session.get(StorageObject, shared.id) is not None

        db.session.get(SystemSetting, "branding").brand_logo_storage_object_id = None
        db.session.commit()

        class FailingDeleteProvider(FakeStorageProvider):
            def delete_object(self, bucket, object_key):
                raise RuntimeError("do not disclose provider key")

        failing = FailingDeleteProvider()
        failing.objects.update(app.extensions["storage_provider"].objects)
        with pytest.raises(DisplayImageCleanupError):
            finalize_display_image_change(replacement, provider=failing)
        assert db.session.get(StorageObject, shared.id).upload_status == "active"
        assert storage_usage_bytes() >= shared.file_size

        summary = cleanup_unreferenced_display_images(dry_run=False, provider=app.extensions["storage_provider"], batch_size=20)
        assert summary["cleaned"] >= 1
        assert db.session.get(StorageObject, shared.id) is None


def test_attachment_authorisation_responses_are_never_cacheable(client, app):
    assert login(client, "reporter").status_code == 302
    attachment_id = _report_attachment(client, app)
    with app.app_context():
        attachment = db.session.get(ReportAttachment, attachment_id)
        obj = attachment.storage_object
        derivative = StorageDerivative(storage_object_id=obj.id, derivative_type="preview", bucket=obj.bucket,
            object_key="daily-reports/derivatives/cache-preview.webp", mime_type="image/webp", file_ext="webp", file_size=4)
        db.session.add(derivative)
        app.extensions["storage_provider"].put_bytes(derivative.bucket, derivative.object_key, b"webp", derivative.mime_type)
        db.session.commit()
    for path in (f"/attachments/{attachment_id}", f"/attachments/{attachment_id}/thumbnail", f"/attachments/{attachment_id}/status"):
        response = client.get(path)
        assert response.headers["Cache-Control"] == "no-store, private"
        assert response.headers["Pragma"] == "no-cache"
        assert response.headers["Referrer-Policy"] == "no-referrer"
    with app.app_context():
        db.session.get(ReportAttachment, attachment_id).storage_object_id = None
        db.session.commit()
    error = client.get(f"/attachments/{attachment_id}")
    assert error.status_code == 410
    assert error.headers["Cache-Control"] == "no-store, private"


@pytest.mark.parametrize("kind, path, model", [
    ("profile_photo", "/partners/900/photo/preview", Partner),
    ("company_photo", "/partner-companies/901/photo/preview", Company),
])
def test_partner_photo_preview_is_authorised_same_origin_stream(client, app, kind, path, model):
    with app.app_context():
        owner = User.query.filter_by(username="super").one()
        obj = StorageObject(bucket="test", object_key=f"private/{kind}/secret.webp", storage_module="partner-management",
            original_filename="private-photo.jpg", mime_type="image/webp", file_ext="webp", file_size=4,
            uploaded_by_id=owner.id, upload_status="active")
        db.session.add(obj)
        if model is Partner:
            record = Partner(id=900, full_name="Private partner", created_by_user_id=owner.id, profile_photo_storage_object=obj)
        else:
            record = Company(id=901, name="Private company", company_photo_storage_object=obj)
        db.session.add(record)
        get_storage_provider().put_bytes(obj.bucket, obj.object_key, b"webp", obj.mime_type)
        db.session.commit()
    assert login(client, "super").status_code == 302
    signed = client.post(path.replace("/preview", "/signed-preview"))
    assert signed.status_code == 200
    assert signed.get_json()["url"].startswith("/")
    assert "fake-storage.invalid" not in signed.get_data(as_text=True)
    response = client.get(path)
    assert response.status_code == 200
    assert response.data == b"webp"
    assert "Location" not in response.headers
    assert "fake-storage.invalid" not in response.get_data(as_text=True)
    assert "secret.webp" not in response.get_data(as_text=True)
    assert response.headers["Cache-Control"] == "no-store, private"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    client.post("/logout")
    assert login(client, "reporter").status_code == 302
    assert client.get(path).status_code == 403
    client.post("/logout")
    assert login(client, "super").status_code == 302
    with app.app_context():
        record = db.session.get(model, 900 if model is Partner else 901)
        obj = getattr(record, f"{kind}_storage_object")
        get_storage_provider().objects.pop((obj.bucket, obj.object_key))
    missing = client.get(path)
    assert missing.status_code == 404
    assert missing.headers["Cache-Control"] == "no-store, private"
    assert obj.object_key.encode() not in missing.data
    assert b"fake-storage.invalid" not in missing.data
