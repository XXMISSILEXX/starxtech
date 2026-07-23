import json

from app.extensions import db
from app.models import (BulkDownloadJob, CompanyMediaAlbum, CompanyMediaFile, DownloadEvent,
                        Project, ProjectDocumentFile, StorageObject, User)
from app.project_documents.services import get_or_create_project_root_folder
from app.storage.providers import FakeStorageProvider


def _storage(user, key, name, data=b"x"):
    storage = StorageObject(bucket="b", object_key=key, original_filename=name,
        mime_type="application/pdf", file_ext="pdf", file_size=len(data),
        uploaded_by_id=user.id, upload_status="active")
    db.session.add(storage)
    db.session.flush()
    return storage


def test_document_preflight_and_native_form_support_json_and_form_ids(client, app, tmp_path):
    with app.app_context():
        provider = FakeStorageProvider()
        app.extensions["storage_provider"] = provider
        app.config["BULK_DOWNLOAD_TEMP_ROOT"] = str(tmp_path)
        admin = db.session.get(User, 6)
        folder = get_or_create_project_root_folder(db.session.get(Project, 1), admin)
        objects = [_storage(admin, f"documents/{index}.pdf", f"{index}.pdf") for index in range(2)]
        for storage in objects:
            provider.put_bytes(storage.bucket, storage.object_key, b"x", storage.mime_type)
        files = [ProjectDocumentFile(project_id=folder.project_id, folder_id=folder.id,
            storage_object_id=storage.id, display_name=storage.original_filename,
            created_by_id=admin.id) for storage in objects]
        db.session.add_all(files)
        db.session.commit()
        folder_id, ids = folder.id, [item.id for item in files]

    client.post("/login", data={"username_or_email": "admin", "password": "password123"})
    validate_url = f"/project-documents/folders/{folder_id}/files/bulk-download-validate"
    assert client.post(validate_url, json={"file_ids": ids}).get_json() == {"ok": True, "kind": "zip"}
    assert client.post(validate_url, data={"file_ids_json": json.dumps(ids)}).get_json() == {"ok": True, "kind": "zip"}
    assert client.post(validate_url, data={"file_ids[]": [str(value) for value in ids]}).get_json() == {"ok": True, "kind": "zip"}
    assert client.post(validate_url, data={"file_ids_json": "not-json"}).get_json()["error"] == "Danh sách tệp không hợp lệ."
    with app.app_context():
        assert DownloadEvent.query.count() == 0
        assert BulkDownloadJob.query.count() == 0
        assert not list(tmp_path.glob("zip-stream-*"))

    response = client.post(f"/project-documents/folders/{folder_id}/files/bulk-signed-download",
        data={"file_ids_json": json.dumps(ids)})
    assert response.status_code == 200
    assert response.mimetype == "application/zip"
    response.close()


def test_media_preflight_and_native_form_support_form_ids(client, app, tmp_path):
    with app.app_context():
        provider = FakeStorageProvider()
        app.extensions["storage_provider"] = provider
        app.config["BULK_DOWNLOAD_TEMP_ROOT"] = str(tmp_path)
        admin = db.session.get(User, 6)
        album = CompanyMediaAlbum(name="Native form", created_by_id=admin.id)
        db.session.add(album)
        db.session.flush()
        objects = [_storage(admin, f"media/{index}.pdf", f"{index}.pdf") for index in range(2)]
        for storage in objects:
            provider.put_bytes(storage.bucket, storage.object_key, b"x", storage.mime_type)
        files = [CompanyMediaFile(album_id=album.id, storage_object_id=storage.id,
            display_name=storage.original_filename, media_type="image", created_by_id=admin.id)
            for storage in objects]
        db.session.add_all(files)
        db.session.commit()
        album_id, ids = album.id, [item.id for item in files]

    client.post("/login", data={"username_or_email": "admin", "password": "password123"})
    validate_url = f"/company-media/albums/{album_id}/files/bulk-download-validate"
    assert client.post(validate_url, data={"file_ids_json": json.dumps(ids)}).get_json() == {"ok": True, "kind": "zip"}
    assert client.post(validate_url, data={"file_ids[]": [str(value) for value in ids]}).get_json() == {"ok": True, "kind": "zip"}
    response = client.post(f"/company-media/albums/{album_id}/files/bulk-signed-download",
        data={"file_ids_json": json.dumps(ids)})
    assert response.status_code == 200
    assert response.mimetype == "application/zip"
    response.close()


def test_bulk_download_script_uses_preflight_and_native_form():
    source = open("app/static/js/project-document-file-actions.js", encoding="utf-8").read()
    assert "bulkDownloadValidateUrl" in source
    assert '"csrf_token"' in source
    assert '"file_ids_json"' in source
    assert "form.submit()" in source
    assert "response.blob" not in source
