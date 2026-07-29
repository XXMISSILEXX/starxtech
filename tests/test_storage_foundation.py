from datetime import datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import StorageObject, UploadBatchItem, User
from app.storage.exceptions import StorageNotFoundError, StorageValidationError
from app.storage.providers import FakeStorageProvider
from app.storage.keys import STORAGE_MODULE_DOCUMENT_LIBRARY
from app.storage.services import cleanup_pending_uploads, complete_upload_item, create_signed_download_url, create_upload_batch_presign


def _files():
    return [
        {"client_file_id": "img", "filename": "summer.jpg", "mime_type": "image/jpeg", "size": 12},
        {"client_file_id": "pdf", "filename": "contract.pdf", "mime_type": "application/pdf", "size": 13},
        {"client_file_id": "bad", "filename": "run.exe", "mime_type": "application/octet-stream", "size": 5},
    ]


def test_batch_presign_partial_success_generates_private_keys(app):
    with app.app_context():
        result = create_upload_batch_presign(user=db.session.get(User, 3), module_type="project_documents", target_type="folder", target_id=9, files=_files(), provider=FakeStorageProvider())
        assert result["status"] == "uploading"
        assert [item["accepted"] for item in result["items"]] == [True, True, False]
        assert all(isinstance(item["upload_batch_item_id"], int) and isinstance(item["storage_object_id"], int) for item in result["items"] if item["accepted"])
        assert "upload_batch_item_id" not in result["items"][2]
        objects = StorageObject.query.all()
        assert len(objects) == 2 and len({item.object_key for item in objects}) == 2
        assert all(
            "summer" not in item.object_key
            and (item.object_key.startswith(f"{STORAGE_MODULE_DOCUMENT_LIBRARY}/originals/")
                 or f"/{STORAGE_MODULE_DOCUMENT_LIBRARY}/originals/" in item.object_key)
            and item.storage_module == STORAGE_MODULE_DOCUMENT_LIBRARY
            for item in objects
        )
        assert UploadBatchItem.query.filter_by(status="rejected").one().storage_object_id is None


@pytest.mark.parametrize("filename,mime", [("x.html", "text/html"), ("x.svg", "image/svg+xml"), ("x.zip", "application/zip"), ("x.jpg", "image/png")])
def test_batch_rejects_invalid_item_per_item(app, filename, mime):
    with app.app_context():
        result = create_upload_batch_presign(user=db.session.get(User, 3), module_type="company_media", target_type="album", target_id=2, files=[{"client_file_id": "one", "filename": filename, "mime_type": mime, "size": 1}], provider=FakeStorageProvider())
        assert result["items"][0]["accepted"] is False
        assert StorageObject.query.count() == 0


@pytest.mark.parametrize("module_type,target_type,filename,mime,stored_mime", [
    ("company_media", "album", "a.heic", "image/heic", "image/heic"),
    ("company_media", "album", "a.heic", "", "image/heic"),
    ("company_media", "album", "a.heic", "application/octet-stream", "image/heic"),
    ("company_media", "album", "a.heif", "image/heif", "image/heif"),
    ("company_media", "album", "a.heif", "", "image/heif"),
    ("company_media", "album", "a.heif", "application/octet-stream", "image/heif"),
    ("project_documents", "folder", "a.heic", "image/heic-sequence", "image/heic"),
    ("project_documents", "folder", "a.heif", "image/heif-sequence", "image/heif"),
])
def test_heif_browser_mime_fallback_is_extension_scoped(app, module_type, target_type, filename, mime, stored_mime):
    with app.app_context():
        result = create_upload_batch_presign(
            user=db.session.get(User, 3), module_type=module_type, target_type=target_type, target_id=1,
            files=[{"client_file_id": "heif", "filename": filename, "mime_type": mime, "size": 10}], provider=FakeStorageProvider(),
        )
        assert result["items"][0]["accepted"] is True, result
        storage = db.session.get(StorageObject, result["items"][0]["storage_object_id"])
        assert storage.mime_type == stored_mime


@pytest.mark.parametrize("filename,mime", [("run.exe", "application/octet-stream"), ("script.js", ""), ("vector.svg", "image/svg+xml")])
def test_browser_mime_fallback_does_not_allow_unsafe_extensions(app, filename, mime):
    with app.app_context():
        result = create_upload_batch_presign(
            user=db.session.get(User, 3), module_type="company_media", target_type="album", target_id=1,
            files=[{"client_file_id": "unsafe", "filename": filename, "mime_type": mime, "size": 10}], provider=FakeStorageProvider(),
        )
        assert result["items"][0]["accepted"] is False
        assert StorageObject.query.count() == 0


def test_heic_presign_keeps_single_file_limit(app):
    with app.app_context():
        with pytest.raises(StorageValidationError, match="300 MB"):
            create_upload_batch_presign(
                user=db.session.get(User, 3), module_type="company_media", target_type="album", target_id=1,
                files=[{"client_file_id": "large", "filename": "large.heic", "mime_type": "", "size": 300 * 1024 * 1024 + 1}], provider=FakeStorageProvider(),
            )


def test_batch_rejects_duplicate_ids_and_total_limit(app):
    with app.app_context():
        user = db.session.get(User, 3)
        with pytest.raises(StorageValidationError):
            create_upload_batch_presign(user=user, module_type="project_documents", target_type="folder", target_id=1, files=[{"client_file_id": "same", "filename": "a.pdf", "mime_type": "application/pdf", "size": 1}, {"client_file_id": "same", "filename": "b.pdf", "mime_type": "application/pdf", "size": 1}])
        app.config["STORAGE_MAX_BATCH_SIZE_MB"] = 0
        with pytest.raises(StorageValidationError):
            create_upload_batch_presign(user=user, module_type="project_documents", target_type="folder", target_id=1, files=[{"client_file_id": "x", "filename": "a.pdf", "mime_type": "application/pdf", "size": 1}])


@pytest.mark.parametrize("filename,mime,size", [
    ("empty.jpg", "image/jpeg", 0),
    ("too-large.jpg", "image/jpeg", 50 * 1024 * 1024 + 1),
])
def test_invalid_size_is_rejected_before_presign(app, filename, mime, size):
    class RecordingProvider(FakeStorageProvider):
        def __init__(self):
            super().__init__()
            self.presign_calls = 0

        def create_presigned_upload(self, *args, **kwargs):
            self.presign_calls += 1
            return super().create_presigned_upload(*args, **kwargs)

    with app.app_context():
        provider = RecordingProvider()
        result = create_upload_batch_presign(
            user=db.session.get(User, 3), module_type="company_media", target_type="album", target_id=1,
            files=[{"client_file_id": "invalid-size", "filename": filename, "mime_type": mime, "size": size}], provider=provider,
        )
        assert result["items"][0]["client_file_id"] == "invalid-size"
        assert result["items"][0]["accepted"] is False
        assert provider.presign_calls == 0


def test_complete_and_download_are_idempotent_and_safe(app):
    with app.app_context():
        provider, user = FakeStorageProvider(), db.session.get(User, 3)
        result = create_upload_batch_presign(user=user, module_type="project_documents", target_type="folder", target_id=1, files=[{"client_file_id": "a", "filename": "a.pdf", "mime_type": "application/pdf", "size": 10}], provider=provider)
        item = db.session.get(UploadBatchItem, result["items"][0]["upload_batch_item_id"])
        provider.register_object(item.storage_object.bucket, item.storage_object.object_key, 10, "application/pdf")
        assert complete_upload_item(user=user, upload_batch_item_id=item.id, provider=provider)["upload_status"] == "active"
        assert complete_upload_item(user=user, upload_batch_item_id=item.id, provider=provider)["idempotent"] is True
        assert "signature=fake" in create_signed_download_url(user=user, storage_object_id=item.storage_object_id, provider=provider)["url"]
        assert item.upload_batch.status == "completed"


def test_complete_head_failure_never_activates(app):
    with app.app_context():
        provider, user = FakeStorageProvider(), db.session.get(User, 3)
        result = create_upload_batch_presign(user=user, module_type="company_media", target_type="album", target_id=1, files=[{"client_file_id": "a", "filename": "a.jpg", "mime_type": "image/jpeg", "size": 10}], provider=provider)
        assert result["items"][0]["accepted"] is True, result
        item = db.session.get(UploadBatchItem, result["items"][0]["upload_batch_item_id"])
        with pytest.raises(StorageNotFoundError):
            complete_upload_item(user=user, upload_batch_item_id=item.id, provider=provider)
        assert item.storage_object.upload_status == "pending" and item.status == "failed"
        with pytest.raises(StorageNotFoundError):
            create_signed_download_url(user=user, storage_object_id=item.storage_object_id, provider=provider)


@pytest.mark.parametrize("actual_size", [9, 11])
def test_complete_rejects_head_size_that_is_not_exact(app, actual_size):
    with app.app_context():
        provider, user = FakeStorageProvider(), db.session.get(User, 3)
        result = create_upload_batch_presign(
            user=user, module_type="company_media", target_type="album", target_id=1,
            files=[{"client_file_id": "size-check", "filename": "size-check.jpg", "mime_type": "image/jpeg", "size": 10}], provider=provider,
        )
        item = db.session.get(UploadBatchItem, result["items"][0]["upload_batch_item_id"])
        provider.register_object(item.storage_object.bucket, item.storage_object.object_key, actual_size, "image/jpeg")
        with pytest.raises(StorageValidationError, match="Kích thước object không khớp"):
            complete_upload_item(user=user, upload_batch_item_id=item.id, provider=provider)
        assert item.status == "failed"
        assert item.storage_object.upload_status == "pending"


def test_complete_rejects_another_users_upload_item(app):
    with app.app_context():
        provider, owner, other = FakeStorageProvider(), db.session.get(User, 3), db.session.get(User, 5)
        result = create_upload_batch_presign(
            user=owner, module_type="company_media", target_type="album", target_id=1,
            files=[{"client_file_id": "owner-only", "filename": "owner-only.jpg", "mime_type": "image/jpeg", "size": 1}], provider=provider,
        )
        item = db.session.get(UploadBatchItem, result["items"][0]["upload_batch_item_id"])
        provider.register_object(item.storage_object.bucket, item.storage_object.object_key, 1, "image/jpeg")
        from app.storage.exceptions import StorageAuthorizationError
        with pytest.raises(StorageAuthorizationError):
            complete_upload_item(user=other, upload_batch_item_id=item.id, provider=provider)
        assert item.status == "accepted" and item.storage_object.upload_status == "pending"


def test_cleanup_pending_dry_run_and_execute(app):
    with app.app_context():
        provider, user = FakeStorageProvider(), db.session.get(User, 3)
        result = create_upload_batch_presign(user=user, module_type="company_media", target_type="album", target_id=1, files=[{"client_file_id": "a", "filename": "a.png", "mime_type": "image/png", "size": 10}], provider=provider)
        item = db.session.get(UploadBatchItem, result["items"][0]["upload_batch_item_id"])
        item.storage_object.created_at = datetime.utcnow() - timedelta(hours=25)
        db.session.commit()
        assert cleanup_pending_uploads(older_than_hours=24, dry_run=True, provider=provider)["cleaned"] == 0
        assert cleanup_pending_uploads(older_than_hours=24, dry_run=False, provider=provider)["cleaned"] == 1
        assert item.storage_object.upload_status == "failed"


def test_model_unique_bucket_object_key(app):
    with app.app_context():
        user = db.session.get(User, 3)
        db.session.add_all([StorageObject(bucket="b", object_key="originals/a.pdf", original_filename="a.pdf", mime_type="application/pdf", file_ext="pdf", file_size=1, uploaded_by_id=user.id), StorageObject(bucket="b", object_key="originals/a.pdf", original_filename="b.pdf", mime_type="application/pdf", file_ext="pdf", file_size=1, uploaded_by_id=user.id)])
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()
