from io import BytesIO
import zipfile

import pytest

from app.bulk_downloads.services import (BulkDownloadError, cleanup_expired_jobs, request_document_download,
                                         request_media_download, run_job, stream_zip_download)
from app.extensions import db
from app.models import (BulkDownloadJob, CompanyMediaAlbum, CompanyMediaFile, Project, ProjectDocumentFile,
                        DownloadEvent, StorageObject, User)
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


def test_document_bulk_zip_stream_uses_existing_object_keys_without_s3_zip(app, tmp_path):
    with app.app_context():
        provider = FakeStorageProvider(); app.extensions["storage_provider"] = provider
        app.config["BULK_DOWNLOAD_TEMP_ROOT"] = str(tmp_path)
        admin = db.session.get(User, 6)
        root = get_or_create_project_root_folder(db.session.get(Project, 1), admin)
        first = _storage(admin, "dev/originals/legacy.pdf", "same.pdf", b"one")
        second = _storage(admin, "dev/document-library/originals/new.pdf", "same.pdf", b"two")
        provider.put_bytes("b", first.object_key, b"one", "application/pdf"); provider.put_bytes("b", second.object_key, b"two", "application/pdf")
        files = [ProjectDocumentFile(project_id=root.project_id, folder_id=root.id, storage_object_id=item.id, display_name="same.pdf", created_by_id=admin.id) for item in (first, second)]
        db.session.add_all(files); db.session.commit()
        result = request_document_download(admin, root, [item.id for item in files])
        assert result["kind"] == "zip" and BulkDownloadJob.query.count() == 0
        with app.test_request_context():
            response = stream_zip_download(admin, result)
            assert response.mimetype == "application/zip"
            assert list(tmp_path.glob("zip-stream-*"))
            response.direct_passthrough = False
            with zipfile.ZipFile(BytesIO(response.get_data())) as archive:
                assert archive.namelist() == ["same.pdf", "same (2).pdf"]
            response.close()
            assert not list(tmp_path.glob("zip-stream-*"))
        assert not any("bulk-downloads/" in key for _, key in provider.objects)
        event = DownloadEvent.query.one()
        assert event.source_type == "zip_stream" and event.module == "document-library"
        assert event.estimated_storage_egress_bytes == 6 and event.estimated_client_egress_bytes > 0


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


def test_media_bulk_zip_stream_does_not_create_s3_zip_or_job(app):
    with app.app_context():
        provider = FakeStorageProvider(); app.extensions["storage_provider"] = provider
        admin = db.session.get(User, 6); album = CompanyMediaAlbum(name="Bulk", created_by_id=admin.id)
        db.session.add(album); db.session.flush()
        objects = [_storage(admin, f"company-media/originals/{index}.jpg", "same.jpg", bytes([index])) for index in range(2)]
        for item in objects: provider.put_bytes("b", item.object_key, b"image", "image/jpeg")
        files = [CompanyMediaFile(album_id=album.id, storage_object_id=item.id, display_name="same.jpg", media_type="image", created_by_id=admin.id) for item in objects]
        db.session.add_all(files); db.session.commit()
        result = request_media_download(admin, album, [item.id for item in files])
        assert result["kind"] == "zip" and BulkDownloadJob.query.count() == 0
        with app.test_request_context():
            response = stream_zip_download(admin, result); response.direct_passthrough = False
            assert response.mimetype == "application/zip"
            with zipfile.ZipFile(BytesIO(response.get_data())) as archive:
                assert archive.namelist() == ["same.jpg", "same (2).jpg"]
            response.close()
        assert not any("bulk-downloads/" in key for _, key in provider.objects)


def test_zip_stream_rejects_limit_and_missing_source_before_response(app):
    with app.app_context():
        provider = FakeStorageProvider(); app.extensions["storage_provider"] = provider
        admin = db.session.get(User, 6); root = get_or_create_project_root_folder(db.session.get(Project, 1), admin)
        objects = [_storage(admin, f"originals/{index}.pdf", f"{index}.pdf") for index in range(2)]
        files = [ProjectDocumentFile(project_id=root.project_id, folder_id=root.id, storage_object_id=item.id, display_name=item.original_filename, created_by_id=admin.id) for item in objects]
        db.session.add_all(files); db.session.commit()
        app.config["BULK_DOWNLOAD_MAX_FILES"] = 1
        with pytest.raises(BulkDownloadError, match="tối đa 100"):
            request_document_download(admin, root, [item.id for item in files])
        app.config["BULK_DOWNLOAD_MAX_FILES"] = 100
        selection = request_document_download(admin, root, [item.id for item in files])
        with app.test_request_context(), pytest.raises(BulkDownloadError, match="Không tìm thấy"):
            stream_zip_download(admin, selection)


def test_zip_stream_bundles_precompressed_sources(app):
    with app.app_context():
        provider = FakeStorageProvider(); app.extensions["storage_provider"] = provider
        admin = db.session.get(User, 6); root = get_or_create_project_root_folder(db.session.get(Project, 1), admin)
        nested = BytesIO()
        with zipfile.ZipFile(nested, "w") as archive: archive.writestr("inside.txt", "x")
        first = _storage(admin, "originals/first.zip", "first.zip", nested.getvalue())
        second = _storage(admin, "originals/second.pdf", "second.pdf", b"pdf")
        provider.put_bytes("b", first.object_key, nested.getvalue(), "application/zip")
        provider.put_bytes("b", second.object_key, b"pdf", "application/pdf")
        files = [ProjectDocumentFile(project_id=root.project_id, folder_id=root.id, storage_object_id=item.id, display_name=item.original_filename, created_by_id=admin.id) for item in (first, second)]
        db.session.add_all(files); db.session.commit()
        with app.test_request_context():
            response = stream_zip_download(admin, request_document_download(admin, root, [item.id for item in files]))
            response.direct_passthrough = False
            with zipfile.ZipFile(BytesIO(response.get_data())) as archive:
                assert archive.namelist() == ["first.zip", "second.pdf"]
            response.close()


def test_company_media_upload_uses_company_media_namespace(app):
    with app.app_context():
        admin = db.session.get(User, 6)
        album = CompanyMediaAlbum(name="Upload", created_by_id=admin.id)
        db.session.add(album); db.session.commit()
        result = presign(admin, album, [{"client_file_id": "x", "filename": "photo.jpg", "mime_type": "image/jpeg", "size": 1}])
        storage = db.session.get(StorageObject, result["items"][0]["storage_object_id"])
        assert "company-media/originals/" in storage.object_key and storage.storage_module == "company-media"
