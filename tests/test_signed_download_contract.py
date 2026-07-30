from datetime import datetime
from uuid import uuid4

import pytest
from werkzeug.security import generate_password_hash

from app.company_media.services import signed_download
from app.extensions import db
from app.models import CompanyMediaAlbum, CompanyMediaFile, Project, ProjectDocumentFile, StorageObject, User
from app.project_documents.services import create_file_download_url, get_or_create_project_root_folder
from app.storage.downloads import SignedDownloadError
from app.storage.providers import FakeStorageProvider


class RecordingProvider(FakeStorageProvider):
    def __init__(self, result=None, error=None):
        super().__init__()
        self.calls = []
        self.result = result
        self.error = error

    def create_presigned_download(self, bucket, object_key, expires_in, disposition="inline", filename=None):
        self.calls.append((expires_in, disposition, filename))
        if self.error:
            raise self.error
        if self.result is not None:
            return self.result
        return super().create_presigned_download(bucket, object_key, expires_in, disposition, filename)


def _login(client, username):
    client.post("/login", data={"username_or_email": username, "password": "password123"})


def _company_file(app, *, upload_status="active", deleted=False):
    with app.app_context():
        admin = db.session.get(User, 6)
        album = CompanyMediaAlbum(name="Download contract", created_by_id=admin.id)
        db.session.add(album)
        db.session.flush()
        storage = StorageObject(
            bucket="test", object_key=f"company-media/{uuid4().hex}.png", original_filename="source.png",
            mime_type="image/png", file_ext="png", file_size=10, uploaded_by_id=admin.id,
            upload_status=upload_status, deleted_at=datetime.utcnow() if deleted else None,
        )
        db.session.add(storage)
        db.session.flush()
        media = CompanyMediaFile(
            album_id=album.id, storage_object_id=storage.id, display_name="Tên hiển thị.png",
            media_type="image", created_by_id=admin.id,
        )
        db.session.add(media)
        db.session.commit()
        return media.id, storage.id


def _document_file(app, *, upload_status="active", deleted=False):
    with app.app_context():
        pm = db.session.get(User, 5)
        root = get_or_create_project_root_folder(db.session.get(Project, 1), pm)
        storage = StorageObject(
            bucket="test", object_key=f"document-library/{uuid4().hex}.pdf", original_filename="source.pdf",
            mime_type="application/pdf", file_ext="pdf", file_size=10, uploaded_by_id=pm.id,
            upload_status=upload_status, deleted_at=datetime.utcnow() if deleted else None,
        )
        db.session.add(storage)
        db.session.flush()
        document = ProjectDocumentFile(
            project_id=root.project_id, folder_id=root.id, storage_object_id=storage.id,
            display_name="Tên tài liệu.pdf", created_by_id=pm.id,
        )
        db.session.add(document)
        db.session.commit()
        return document.id, storage.id


def _assert_safe_failure(response, code, status):
    assert response.status_code == status
    payload = response.get_json()
    assert payload == {
        "ok": False,
        "error": {
            "code": code,
            "message": payload["error"]["message"],
            "retryable": payload["error"]["retryable"],
        },
    }
    assert "bucket" not in str(payload).lower()
    assert "object_key" not in str(payload).lower()


def test_company_media_signed_download_success_contract_and_ttl(client, app):
    file_id, _ = _company_file(app)
    provider = RecordingProvider()
    app.extensions["storage_provider"] = provider
    app.config["STORAGE_DOWNLOAD_URL_TTL_SECONDS"] = 123

    _login(client, "admin")
    response = client.post(f"/company-media/files/{file_id}/signed-download", json={})

    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "url": response.get_json()["url"],
        "expires_at": response.get_json()["expires_at"],
        "filename": "Tên hiển thị.png",
        "disposition": "attachment",
    }
    assert provider.calls == [(123, "attachment", "Tên hiển thị.png")]


def test_company_media_does_not_sign_inactive_or_deleted_source(client, app):
    for upload_status, deleted in (("pending", False), ("active", True)):
        file_id, _ = _company_file(app, upload_status=upload_status, deleted=deleted)
        provider = RecordingProvider()
        app.extensions["storage_provider"] = provider
        _login(client, "admin")
        response = client.post(f"/company-media/files/{file_id}/signed-download", json={})
        _assert_safe_failure(response, "download_source_unavailable", 404)
        assert provider.calls == []
        client.post("/logout")


def test_company_media_missing_source_is_safe_and_archived_or_unauthorized_is_denied(client, app):
    archived_id, _ = _company_file(app)
    file_id, storage_id = _company_file(app)
    provider = RecordingProvider()
    app.extensions["storage_provider"] = provider
    with app.app_context():
        db.session.get(CompanyMediaFile, archived_id).is_active = False
        db.session.commit()
    _login(client, "admin")
    assert client.post(f"/company-media/files/{archived_id}/signed-download", json={}).status_code == 403
    client.post("/logout")
    _login(client, "reporter")
    assert client.post(f"/company-media/files/{file_id}/signed-download", json={}).status_code == 403
    client.post("/logout")
    with app.app_context():
        storage = db.session.get(StorageObject, storage_id)
        db.session.delete(storage)
        db.session.commit()
    _login(client, "admin")
    response = client.post(f"/company-media/files/{file_id}/signed-download", json={})
    _assert_safe_failure(response, "download_source_unavailable", 404)
    assert provider.calls == []


def test_company_media_provider_failures_are_sanitized(client, app):
    file_id, _ = _company_file(app)
    _login(client, "admin")
    for provider, code in (
        (RecordingProvider(error=RuntimeError("bucket=private credentials=secret")), "signed_download_unavailable"),
        (RecordingProvider(result={"expires_at": "2030-01-01T00:00:00+00:00"}), "signed_download_invalid_response"),
    ):
        app.extensions["storage_provider"] = provider
        response = client.post(f"/company-media/files/{file_id}/signed-download", json={})
        _assert_safe_failure(response, code, 502)
        assert "credentials" not in response.get_data(as_text=True)

    provider = RecordingProvider()
    app.extensions["storage_provider"] = provider
    app.config["STORAGE_DOWNLOAD_URL_TTL_SECONDS"] = 0
    response = client.post(f"/company-media/files/{file_id}/signed-download", json={})
    _assert_safe_failure(response, "signed_download_unavailable", 503)
    assert provider.calls == []


def test_project_documents_signed_download_contract_source_errors_and_ttl(client, app):
    file_id, _ = _document_file(app)
    provider = RecordingProvider()
    app.extensions["storage_provider"] = provider
    app.config["STORAGE_DOWNLOAD_URL_TTL_SECONDS"] = 234
    _login(client, "pm")
    response = client.post(f"/project-documents/files/{file_id}/signed-download", json={})
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True and payload["url"] and payload["expires_at"]
    assert payload["filename"] == "Tên tài liệu.pdf" and payload["disposition"] == "attachment"
    assert provider.calls == [(234, "attachment", "Tên tài liệu.pdf")]
    client.post("/logout")

    inactive_id, _ = _document_file(app, upload_status="pending")
    _login(client, "pm")
    response = client.post(f"/project-documents/files/{inactive_id}/signed-download", json={})
    _assert_safe_failure(response, "download_source_unavailable", 404)
    client.post("/logout")
    with app.app_context():
        denied = User(id=7, username="document-denied", email="document-denied@example.com",
                      full_name="Denied", password_hash=generate_password_hash("password123"),
                      role_id=db.session.get(User, 3).role_id, legacy_role="REPORTER")
        db.session.add(denied)
        db.session.commit()
    _login(client, "document-denied")
    assert client.post(f"/project-documents/files/{file_id}/signed-download", json={}).status_code == 403


def test_project_documents_provider_and_missing_source_failures_are_safe(client, app):
    file_id, _ = _document_file(app)
    _login(client, "pm")
    for provider, code in (
        (RecordingProvider(error=RuntimeError("bucket=private credentials=secret")), "signed_download_unavailable"),
        (RecordingProvider(result={"expires_at": "2030-01-01T00:00:00+00:00"}), "signed_download_invalid_response"),
    ):
        app.extensions["storage_provider"] = provider
        response = client.post(f"/project-documents/files/{file_id}/signed-download", json={})
        _assert_safe_failure(response, code, 502)
        assert "credentials" not in response.get_data(as_text=True)

    missing_file_id, storage_id = _document_file(app)
    provider = RecordingProvider()
    app.extensions["storage_provider"] = provider
    with app.app_context():
        db.session.delete(db.session.get(StorageObject, storage_id))
        db.session.commit()
    response = client.post(f"/project-documents/files/{missing_file_id}/signed-download", json={})
    _assert_safe_failure(response, "download_source_unavailable", 404)
    assert provider.calls == []


def test_project_document_service_provider_failure_is_safe(app):
    file_id, _ = _document_file(app)
    with app.app_context():
        document = db.session.get(ProjectDocumentFile, file_id)
        with pytest.raises(SignedDownloadError) as error:
            create_file_download_url(db.session.get(User, 5), document, provider=RecordingProvider(error=RuntimeError("secret")))
        assert error.value.code == "signed_download_unavailable"


def test_company_media_uses_the_versioned_shared_preview_asset(client, app):
    _company_file(app)
    _login(client, "admin")
    response = client.get("/company-media/albums/1")
    assert response.status_code == 200
    assert b"project-document-preview.js?v=20260730-8301" in response.data
