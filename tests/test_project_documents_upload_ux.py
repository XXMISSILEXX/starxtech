import sys
import types

import pytest

from app.extensions import db
from app.models import Project, ProjectDocumentFile, StorageObject, User
from app.project_documents.services import create_folder, get_or_create_project_root_folder
from app.storage.exceptions import StorageConfigurationError
from app.storage.providers import S3StorageProvider


def test_upload_controls_are_permission_gated(client, app):
    with app.app_context():
        root = get_or_create_project_root_folder(db.session.get(Project, 1), db.session.get(User, 6))
        root_id = root.id
    client.post("/login", data={"username_or_email": "pm", "password": "password123"})
    response = client.get(f"/project-documents/folders/{root_id}")
    assert "Kéo thả tệp vào đây".encode() in response.data
    assert "Tải lên".encode() in response.data and b"multiple" in response.data and b"csrf_token" in response.data
    assert b"data-select-all disabled" in response.data
    client.post("/logout")
    client.post("/login", data={"username_or_email": "viewer", "password": "password123"})
    assert "Kéo thả tệp vào đây".encode() not in client.get(f"/project-documents/folders/{root_id}").data


def test_file_grid_select_all_only_targets_rendered_files(client, app):
    with app.app_context():
        admin = db.session.get(User, 6)
        root = get_or_create_project_root_folder(db.session.get(Project, 1), admin)
        objects = [
            StorageObject(bucket="b", object_key=f"originals/select-{name}.pdf", original_filename=f"{name}.pdf", mime_type="application/pdf", file_ext="pdf", file_size=1, uploaded_by_id=admin.id, upload_status="active")
            for name in ("visible", "hidden")
        ]
        db.session.add_all(objects); db.session.flush()
        files = [ProjectDocumentFile(project_id=root.project_id, folder_id=root.id, storage_object_id=item.id, display_name=item.original_filename, created_by_id=admin.id) for item in objects]
        db.session.add_all(files); db.session.commit()
        root_id, visible_id, hidden_id = root.id, files[0].id, files[1].id
    client.post("/login", data={"username_or_email": "admin", "password": "password123"})
    page = client.get(f"/project-documents/folders/{root_id}?q=visible").data
    assert b"data-select-all" in page and b"data-select-all disabled" not in page
    assert page.count(b"data-file-select") == 1
    assert f'data-file-id="{visible_id}"'.encode() in page
    assert f'data-file-id="{hidden_id}"'.encode() not in page
    assert b"data-bulk-bar" in page and b"document-file-card.is-selected" in client.get("/static/css/app.css").data


def test_folder_share_links_are_rendered_only_for_share_permission(client, app):
    with app.app_context():
        admin = db.session.get(User, 6)
        root = get_or_create_project_root_folder(db.session.get(Project, 1), admin)
        child = create_folder(admin, root, "Shared child")
        root_id = root.id
    client.post("/login", data={"username_or_email": "admin", "password": "password123"})
    page = client.get(f"/project-documents/folders/{root_id}").data
    assert "Chia sẻ thư mục".encode() in page and "Chia sẻ quyền".encode() in page
    assert b"document-folder-card" in page and b"document-folder-open" in page
    client.post("/logout")
    client.post("/login", data={"username_or_email": "viewer", "password": "password123"})
    viewer_page = client.get(f"/project-documents/folders/{root_id}").data
    assert "Chia sẻ thư mục".encode() not in viewer_page and "Chia sẻ quyền".encode() not in viewer_page


def test_s3_provider_validates_config_and_presign_shape(monkeypatch):
    with pytest.raises(StorageConfigurationError):
        S3StorageProvider({"STORAGE_BUCKET": "", "STORAGE_ACCESS_KEY_ID": "x", "STORAGE_SECRET_ACCESS_KEY": "y"})
    class Client:
        def generate_presigned_post(self, *args, **kwargs): return {"url": "http://s3.test/bucket", "fields": {"key": "generated"}}
    monkeypatch.setitem(sys.modules, "boto3", types.SimpleNamespace(client=lambda *args, **kwargs: Client()))
    provider = S3StorageProvider({"STORAGE_BUCKET": "bucket", "STORAGE_ACCESS_KEY_ID": "key", "STORAGE_SECRET_ACCESS_KEY": "secret", "STORAGE_REGION": "us-east-1", "STORAGE_ENDPOINT_URL": "http://s3.test"})
    result = provider.create_presigned_upload("bucket", "generated", "application/pdf", 1, 300)
    assert result["method"] == "POST" and result["url"] == "http://s3.test/bucket" and "fields" in result
