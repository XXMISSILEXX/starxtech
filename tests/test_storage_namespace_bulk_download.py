from app.bulk_downloads.services import cleanup_expired_jobs, request_document_download, request_media_download, run_job
from app.extensions import db
from app.models import (BulkDownloadJob, CompanyMediaAlbum, CompanyMediaFile, Project, ProjectDocumentFile,
                        StorageObject, User)
from app.project_documents.services import get_or_create_project_root_folder
from app.company_media.services import presign
from app.storage.keys import build_bulk_zip_key, build_derivative_key, build_original_key, safe_storage_filename
from app.storage.providers import FakeStorageProvider


def test_module_key_builders_are_safe_and_namespaced():
    document = build_original_key("project_documents", "abc", "../../contract.pdf", "dev")
    media = build_original_key("company_media", "abc", "photo.jpg", "dev")
    assert document.startswith("dev/document-library/originals/") and ".." not in document
    assert media.startswith("dev/company-media/originals/")
    assert "/document-library/derivatives/" in build_derivative_key("document-library", 1, "thumbnail", "webp", "dev")
    assert "/company-media/bulk-downloads/" in build_bulk_zip_key("company-media", 1, "../album", "dev")
    assert safe_storage_filename("../../a.pdf") == "a.pdf"


def _storage(user, key, name, data=b"x"):
    item = StorageObject(bucket="b", object_key=key, original_filename=name, mime_type="application/pdf",
                         file_ext="pdf", file_size=len(data), uploaded_by_id=user.id, upload_status="active")
    db.session.add(item); db.session.flush(); return item


def test_document_bulk_zip_job_uses_existing_object_keys_and_cleans_up(app):
    with app.app_context():
        provider = FakeStorageProvider(); app.extensions["storage_provider"] = provider
        admin = db.session.get(User, 6)
        root = get_or_create_project_root_folder(db.session.get(Project, 1), admin)
        first = _storage(admin, "dev/originals/legacy.pdf", "same.pdf", b"one")
        second = _storage(admin, "dev/document-library/originals/new.pdf", "same.pdf", b"two")
        provider.put_bytes("b", first.object_key, b"one", "application/pdf"); provider.put_bytes("b", second.object_key, b"two", "application/pdf")
        files = [ProjectDocumentFile(project_id=root.project_id, folder_id=root.id, storage_object_id=item.id, display_name="same.pdf", created_by_id=admin.id) for item in (first, second)]
        db.session.add_all(files); db.session.commit()
        result = request_document_download(admin, root, [item.id for item in files])
        job = db.session.get(BulkDownloadJob, result["job"]["id"])
        assert result["kind"] == "job" and job.status == "pending"
        run_job(job.id)
        assert job.status == "succeeded"
        assert job.zip_object_key.startswith("document-library/bulk-downloads/")
        assert (app.config["STORAGE_BUCKET"], job.zip_object_key) in provider.objects
        job.expires_at = __import__("datetime").datetime.utcnow(); db.session.commit()
        cleanup_expired_jobs()
        assert job.status == "expired" and (app.config["STORAGE_BUCKET"], job.zip_object_key) in provider.deleted


def test_media_bulk_download_requires_album_download_acl_and_single_is_direct(app):
    with app.app_context():
        provider = FakeStorageProvider(); app.extensions["storage_provider"] = provider
        admin = db.session.get(User, 6); album = CompanyMediaAlbum(name="Flamingo", created_by_id=admin.id)
        db.session.add(album); db.session.flush()
        storage = _storage(admin, "legacy/photo.jpg", "photo.jpg")
        provider.put_bytes("b", storage.object_key, b"x", "application/pdf")
        media = CompanyMediaFile(album_id=album.id, storage_object_id=storage.id, display_name="photo.jpg", media_type="image", created_by_id=admin.id)
        db.session.add(media); db.session.commit()
        result = request_media_download(admin, album, [media.id])
        assert result["kind"] == "direct" and result["download"]["url"]


def test_company_media_upload_uses_company_media_namespace(app):
    with app.app_context():
        admin = db.session.get(User, 6)
        album = CompanyMediaAlbum(name="Upload", created_by_id=admin.id)
        db.session.add(album); db.session.commit()
        result = presign(admin, album, [{"client_file_id": "x", "filename": "photo.jpg", "mime_type": "image/jpeg", "size": 1}])
        storage = db.session.get(StorageObject, result["items"][0]["storage_object_id"])
        assert "company-media/originals/" in storage.object_key and storage.storage_module == "company-media"
