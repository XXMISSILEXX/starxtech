import pytest

from app.extensions import db
from app.models import MediaProcessingJob, Project, ProjectDocumentFile, StorageDerivative, StorageObject, User
from app.media_processing.services import retry_media_jobs
from app.project_documents.services import (archive_file, complete_folder_upload_item, create_file_download_url,
    create_file_preview_url, get_or_create_project_root_folder, list_folder_files, presign_folder_upload_batch,
    rename_file, restore_file)
from app.storage.providers import FakeStorageProvider


def _root():
    admin = db.session.get(User, 6)
    return get_or_create_project_root_folder(db.session.get(Project, 1), admin)


def test_preview_uses_real_model_columns_only():
    from app.models import MediaProcessingJob

    assert "job_type" in MediaProcessingJob.__table__.columns
    assert "kind" not in MediaProcessingJob.__table__.columns
    assert "file_size" in StorageObject.__table__.columns
    assert "size_bytes" not in StorageObject.__table__.columns
    assert {"storage_object_id", "derivative_type", "object_key", "mime_type"} <= set(StorageDerivative.__table__.columns.keys())
    assert {"storage_object_id", "display_name", "is_active", "deleted_at"} <= set(ProjectDocumentFile.__table__.columns.keys())


def test_presign_complete_creates_metadata_idempotently_and_downloads(app):
    with app.app_context():
        provider = FakeStorageProvider(); app.extensions["storage_provider"] = provider
        pm, root = db.session.get(User, 5), _root()
        result = presign_folder_upload_batch(pm, root, [
            {"client_file_id": "ok", "filename": "contract.pdf", "mime_type": "application/pdf", "size": 5},
            {"client_file_id": "bad", "filename": "bad.exe", "mime_type": "application/octet-stream", "size": 1},
        ], provider=provider)
        assert [item["accepted"] for item in result["items"]] == [True, False]
        item = result["items"][0]; storage = db.session.get(StorageObject, item["storage_object_id"])
        provider.register_object(storage.bucket, storage.object_key, 5, "application/pdf")
        complete = complete_folder_upload_item(pm, root, item["upload_batch_item_id"], provider=provider)
        assert complete["file"]["display_name"] == "contract.pdf" and ProjectDocumentFile.query.count() == 1
        complete_folder_upload_item(pm, root, item["upload_batch_item_id"], provider=provider)
        assert ProjectDocumentFile.query.count() == 1
        assert "signature=fake" in create_file_download_url(pm, ProjectDocumentFile.query.one(), provider=provider)["url"]


def test_complete_route_rejects_missing_item_id_and_accepts_valid_id(client, app):
    with app.app_context():
        provider = FakeStorageProvider(); app.extensions["storage_provider"] = provider
        pm, root = db.session.get(User, 5), _root()
        result = presign_folder_upload_batch(pm, root, [{"client_file_id": "one", "filename": "one.pdf", "mime_type": "application/pdf", "size": 1}], provider=provider)
        item = result["items"][0]; storage = db.session.get(StorageObject, item["storage_object_id"]); provider.register_object(storage.bucket, storage.object_key, 1, "application/pdf")
        root_id, item_id = root.id, item["upload_batch_item_id"]
    client.post("/login", data={"username_or_email": "pm", "password": "password123"})
    assert client.post(f"/project-documents/folders/{root_id}/files/complete-upload", json={"upload_batch_item_id": None}).status_code == 400
    assert client.post(f"/project-documents/folders/{root_id}/files/complete-upload", json={"upload_batch_item_id": item_id}).status_code == 200


def test_file_archive_restore_listing_and_preview(app, monkeypatch):
    with app.app_context():
        provider = FakeStorageProvider(); app.extensions["storage_provider"] = provider
        monkeypatch.setattr("app.media_processing.services.enqueue_media_processing_for_storage_object", lambda storage_object_id: None)
        pm, root = db.session.get(User, 5), _root()
        result = presign_folder_upload_batch(pm, root, [{"client_file_id": "img", "filename": "a.jpg", "mime_type": "image/jpeg", "size": 2}], provider=provider)
        item = result["items"][0]; storage = db.session.get(StorageObject, item["storage_object_id"]); provider.register_object(storage.bucket, storage.object_key, 2, "image/jpeg")
        document = db.session.get(ProjectDocumentFile, complete_folder_upload_item(pm, root, item["upload_batch_item_id"], provider=provider)["file"]["id"])
        assert create_file_preview_url(pm, document, provider=provider)["status"] in {"processing", "unavailable"}
        db.session.add(StorageDerivative(storage_object_id=storage.id, derivative_type="preview", bucket="b", object_key="derivatives/a.webp", mime_type="image/webp", file_ext="webp", file_size=1)); db.session.commit()
        assert create_file_preview_url(pm, document, provider=provider)["status"] == "ready"
        admin = db.session.get(User, 6); archive_file(admin, document)
        assert document not in list_folder_files(admin, root, "active") and document in list_folder_files(admin, root, "archived")
        restore_file(admin, document); assert document in list_folder_files(admin, root, "active")


def test_upload_routes_enforce_permissions(client, app):
    with app.app_context(): root_id = _root().id
    client.post("/login", data={"username_or_email": "viewer", "password": "password123"})
    assert client.post(f"/project-documents/folders/{root_id}/files/presign-batch", json={"files": []}).status_code == 403


def test_upload_page_contains_interactive_dropzone_contract(client, app):
    with app.app_context(): root_id = _root().id
    client.post("/login", data={"username_or_email": "pm", "password": "password123"})
    page = client.get(f"/project-documents/folders/{root_id}").data
    assert b'id="project-document-dropzone"' in page and "Kéo thả tệp vào đây".encode() in page
    assert b'id="project-document-file-input"' in page and b'multiple' in page
    assert "Chọn thêm tệp".encode() in page and "Tải lên".encode() in page and b'type="button"' in page
    assert b'data-presign-url=' in page and b'data-complete-url=' in page and b'data-csrf-token=' in page
    assert b'project-document-upload.js' in page


def test_signed_preview_returns_ready_contract_and_folder_renders_preview_controls(client, app):
    with app.app_context():
        provider = FakeStorageProvider(); app.extensions["storage_provider"] = provider
        pm, root = db.session.get(User, 5), _root()
        storage = StorageObject(bucket="b", object_key="originals/preview.jpg", original_filename="preview.jpg", mime_type="image/jpeg", file_ext="jpg", file_size=12, uploaded_by_id=pm.id, upload_status="active", processing_status="completed")
        db.session.add(storage); db.session.flush()
        document = ProjectDocumentFile(project_id=root.project_id, folder_id=root.id, storage_object_id=storage.id, display_name="preview.jpg", created_by_id=pm.id)
        db.session.add(document); db.session.add(StorageDerivative(storage_object_id=storage.id, derivative_type="thumbnail", bucket="b", object_key="derivatives/preview.webp", mime_type="image/webp", file_ext="webp", file_size=2)); db.session.commit()
        root_id, file_id = root.id, document.id
    client.post("/login", data={"username_or_email": "pm", "password": "password123"})
    response = client.post(f"/project-documents/files/{file_id}/signed-preview", json={"variant": "thumbnail"})
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True and payload["status"] == "ready" and payload["mime_type"] == "image/webp"
    assert "url" in payload and "expires_at" in payload
    page = client.get(f"/project-documents/folders/{root_id}").data
    assert b"document-card-preview" in page and "Xem nhanh".encode() in page
    assert b"fake-storage.invalid" not in page


def test_file_archive_restore_routes_and_filter_do_not_delete_storage(client, app):
    with app.app_context():
        provider = FakeStorageProvider(); app.extensions["storage_provider"] = provider
        admin, root = db.session.get(User, 6), _root()
        storage = StorageObject(bucket="b", object_key="originals/archive.pdf", original_filename="archive.pdf", mime_type="application/pdf", file_ext="pdf", file_size=3, uploaded_by_id=admin.id, upload_status="active")
        db.session.add(storage); db.session.flush()
        document = ProjectDocumentFile(project_id=root.project_id, folder_id=root.id, storage_object_id=storage.id, display_name="archive.pdf", created_by_id=admin.id)
        db.session.add(document); db.session.commit()
        root_id, file_id = root.id, document.id
    client.post("/login", data={"username_or_email": "admin", "password": "password123"})
    active_page = client.get(f"/project-documents/folders/{root_id}").data
    assert "Lưu trữ".encode() in active_page
    assert client.post(f"/project-documents/files/{file_id}/archive", data={}).status_code == 302
    with app.app_context():
        assert db.session.get(ProjectDocumentFile, file_id).deleted_at is not None
        assert provider.deleted == []
    assert b"archive.pdf" not in client.get(f"/project-documents/folders/{root_id}").data
    archived_page = client.get(f"/project-documents/folders/{root_id}?file_status=archived").data
    assert b"archive.pdf" in archived_page and "Khôi phục".encode() in archived_page
    assert client.post(f"/project-documents/files/{file_id}/restore", data={}).status_code == 302
    with app.app_context():
        restored = db.session.get(ProjectDocumentFile, file_id)
        assert restored.is_active is True and restored.deleted_at is None


def test_viewer_admin_cannot_see_file_archive_control(client, app):
    with app.app_context():
        root = _root()
        admin = db.session.get(User, 6)
        storage = StorageObject(bucket="b", object_key="originals/viewer.pdf", original_filename="viewer.pdf", mime_type="application/pdf", file_ext="pdf", file_size=1, uploaded_by_id=admin.id, upload_status="active")
        db.session.add(storage); db.session.flush()
        db.session.add(ProjectDocumentFile(project_id=root.project_id, folder_id=root.id, storage_object_id=storage.id, display_name="viewer.pdf", created_by_id=admin.id)); db.session.commit()
        root_id = root.id
    client.post("/login", data={"username_or_email": "viewer", "password": "password123"})
    assert "Lưu trữ".encode() not in client.get(f"/project-documents/folders/{root_id}").data


def test_queued_preview_is_rendered_and_signed_preview_enforces_project_scope(client, app):
    with app.app_context():
        admin = db.session.get(User, 6)
        root = get_or_create_project_root_folder(db.session.get(Project, 2), admin)
        storage = StorageObject(bucket="b", object_key="originals/queued.jpg", original_filename="queued.jpg", mime_type="image/jpeg", file_ext="jpg", file_size=1, uploaded_by_id=admin.id, upload_status="active", processing_status="queued")
        db.session.add(storage); db.session.flush()
        document = ProjectDocumentFile(project_id=root.project_id, folder_id=root.id, storage_object_id=storage.id, display_name="queued.jpg", created_by_id=admin.id)
        db.session.add(document); db.session.commit()
        root_id, file_id = root.id, document.id
    client.post("/login", data={"username_or_email": "admin", "password": "password123"})
    assert "Đang xử lý preview".encode() in client.get(f"/project-documents/folders/{root_id}").data
    client.post("/logout", data={})
    client.post("/login", data={"username_or_email": "reporter", "password": "password123"})
    assert client.post(f"/project-documents/files/{file_id}/signed-preview", json={"variant": "thumbnail"}).status_code == 403


def test_retry_media_jobs_skips_ready_derivatives_and_dry_run_is_read_only(app, monkeypatch):
    with app.app_context():
        user = db.session.get(User, 5)
        pending = StorageObject(bucket="b", object_key="originals/pending.jpg", original_filename="pending.jpg", mime_type="image/jpeg", file_ext="jpg", file_size=1, uploaded_by_id=user.id, upload_status="active", processing_status="queued")
        ready = StorageObject(bucket="b", object_key="originals/ready.jpg", original_filename="ready.jpg", mime_type="image/jpeg", file_ext="jpg", file_size=1, uploaded_by_id=user.id, upload_status="active", processing_status="completed")
        db.session.add_all([pending, ready]); db.session.flush()
        pending_job = MediaProcessingJob(storage_object_id=pending.id, job_type="image_derivatives", status="failed", error_message="old error")
        ready_job = MediaProcessingJob(storage_object_id=ready.id, job_type="image_derivatives", status="failed")
        db.session.add_all([pending_job, ready_job])
        db.session.add_all([
            StorageDerivative(storage_object_id=ready.id, derivative_type="thumbnail", bucket="b", object_key="derivatives/ready-thumb.webp", mime_type="image/webp", file_ext="webp", file_size=1),
            StorageDerivative(storage_object_id=ready.id, derivative_type="preview", bucket="b", object_key="derivatives/ready-preview.webp", mime_type="image/webp", file_ext="webp", file_size=1),
        ])
        db.session.commit()
        dry_run = retry_media_jobs("failed", dry_run=True)
        assert dry_run["re_enqueued"] == 1 and dry_run["skipped"] == 1
        assert db.session.get(MediaProcessingJob, pending_job.id).status == "failed"
        monkeypatch.setattr("app.media_processing.services._dispatch_media_job", lambda job: job)
        applied = retry_media_jobs("failed", dry_run=False)
        assert applied["re_enqueued"] == 1 and MediaProcessingJob.query.count() == 2
        assert db.session.get(MediaProcessingJob, pending_job.id).status == "pending"


def test_media_jobs_cli_exposes_status_and_dry_run(app):
    runner = app.test_cli_runner()
    status = runner.invoke(args=["media-jobs", "status"])
    dry_run = runner.invoke(args=["media-jobs", "retry-pending", "--dry-run"])
    assert status.exit_code == 0 and "Media processing jobs" in status.output
    assert dry_run.exit_code == 0 and "mode=dry-run" in dry_run.output


def test_rename_file_preserves_extension_and_rejects_active_sibling_duplicate(app):
    with app.app_context():
        pm, root = db.session.get(User, 5), _root()
        first = StorageObject(bucket="b", object_key="originals/one.pdf", original_filename="one.pdf", mime_type="application/pdf", file_ext="pdf", file_size=1, uploaded_by_id=pm.id, upload_status="active")
        second = StorageObject(bucket="b", object_key="originals/two.pdf", original_filename="two.pdf", mime_type="application/pdf", file_ext="pdf", file_size=1, uploaded_by_id=pm.id, upload_status="active")
        db.session.add_all([first, second]); db.session.flush()
        document = ProjectDocumentFile(project_id=root.project_id, folder_id=root.id, storage_object_id=first.id, display_name="one.pdf", created_by_id=pm.id)
        duplicate = ProjectDocumentFile(project_id=root.project_id, folder_id=root.id, storage_object_id=second.id, display_name="two.pdf", created_by_id=pm.id)
        db.session.add_all([document, duplicate]); db.session.commit()
        rename_file(pm, document, "renamed")
        assert document.display_name == "renamed.pdf" and first.object_key == "originals/one.pdf"
        with pytest.raises(ValueError, match="cùng tên"):
            rename_file(pm, document, "two.pdf")


def test_bulk_file_routes_apply_acl_and_never_delete_storage(client, app):
    with app.app_context():
        provider = FakeStorageProvider(); app.extensions["storage_provider"] = provider
        admin, root = db.session.get(User, 6), _root()
        objects = [StorageObject(bucket="b", object_key=f"originals/bulk-{index}.pdf", original_filename=f"bulk-{index}.pdf", mime_type="application/pdf", file_ext="pdf", file_size=1, uploaded_by_id=admin.id, upload_status="active") for index in range(2)]
        db.session.add_all(objects); db.session.flush()
        files = [ProjectDocumentFile(project_id=root.project_id, folder_id=root.id, storage_object_id=item.id, display_name=item.original_filename, created_by_id=admin.id) for item in objects]
        db.session.add_all(files); db.session.commit()
        root_id, ids = root.id, [item.id for item in files]
    client.post("/login", data={"username_or_email": "admin", "password": "password123"})
    archived = client.post(f"/project-documents/folders/{root_id}/files/bulk-archive", json={"file_ids": ids})
    assert archived.status_code == 200 and archived.get_json()["archived"] == 2
    with app.app_context():
        assert all(db.session.get(ProjectDocumentFile, file_id).deleted_at is not None for file_id in ids)
        assert provider.deleted == []
    restored = client.post(f"/project-documents/folders/{root_id}/files/bulk-restore", json={"file_ids": ids})
    assert restored.status_code == 200 and restored.get_json()["restored"] == 2
    downloads = client.post(f"/project-documents/folders/{root_id}/files/bulk-signed-download", json={"file_ids": ids})
    assert downloads.status_code == 200 and len(downloads.get_json()["downloads"]) == 2
    client.post("/logout", data={})
    client.post("/login", data={"username_or_email": "viewer", "password": "password123"})
    assert client.post(f"/project-documents/folders/{root_id}/files/bulk-archive", json={"file_ids": ids}).status_code == 403
    assert client.post(f"/project-documents/files/{ids[0]}/rename", data={"display_name": "forbidden.pdf"}).status_code == 403


def test_video_and_pdf_preview_use_runtime_signed_urls(app):
    with app.app_context():
        provider = FakeStorageProvider(); app.extensions["storage_provider"] = provider
        pm, root = db.session.get(User, 5), _root()
        video = StorageObject(bucket="b", object_key="originals/demo.mp4", original_filename="demo.mp4", mime_type="video/mp4", file_ext="mp4", file_size=1, uploaded_by_id=pm.id, upload_status="active")
        pdf = StorageObject(bucket="b", object_key="originals/demo.pdf", original_filename="demo.pdf", mime_type="application/pdf", file_ext="pdf", file_size=1, uploaded_by_id=pm.id, upload_status="active")
        db.session.add_all([video, pdf]); db.session.flush()
        video_file = ProjectDocumentFile(project_id=root.project_id, folder_id=root.id, storage_object_id=video.id, display_name="demo.mp4", created_by_id=pm.id)
        pdf_file = ProjectDocumentFile(project_id=root.project_id, folder_id=root.id, storage_object_id=pdf.id, display_name="demo.pdf", created_by_id=pm.id)
        db.session.add_all([video_file, pdf_file]); db.session.commit()
        assert create_file_preview_url(pm, video_file, variant="stream", provider=provider)["kind"] == "video"
        assert create_file_preview_url(pm, pdf_file, variant="document", provider=provider)["kind"] == "pdf"


def test_folder_file_grid_hides_long_metadata_and_mutation_actions_for_viewer(client, app):
    with app.app_context():
        root = _root(); admin = db.session.get(User, 6)
        storage = StorageObject(bucket="b", object_key="originals/grid.pdf", original_filename="grid.pdf", mime_type="application/pdf", file_ext="pdf", file_size=72037, uploaded_by_id=admin.id, upload_status="active", processing_status="completed")
        db.session.add(storage); db.session.flush(); db.session.add(ProjectDocumentFile(project_id=root.project_id, folder_id=root.id, storage_object_id=storage.id, display_name="grid.pdf", created_by_id=admin.id)); db.session.commit(); root_id = root.id
    client.post("/login", data={"username_or_email": "viewer", "password": "password123"})
    page = client.get(f"/project-documents/folders/{root_id}").data
    assert b"document-file-grid" in page and b"bi-three-dots-vertical" in page
    assert b"image/jpeg" not in page and b"72037 bytes" not in page
    assert b"data-rename-file" not in page and b"data-bulk-archive>" not in page
