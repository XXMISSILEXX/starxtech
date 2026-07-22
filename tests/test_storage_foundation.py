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


def test_batch_rejects_duplicate_ids_and_total_limit(app):
    with app.app_context():
        user = db.session.get(User, 3)
        with pytest.raises(StorageValidationError):
            create_upload_batch_presign(user=user, module_type="project_documents", target_type="folder", target_id=1, files=[{"client_file_id": "same", "filename": "a.pdf", "mime_type": "application/pdf", "size": 1}, {"client_file_id": "same", "filename": "b.pdf", "mime_type": "application/pdf", "size": 1}])
        app.config["STORAGE_MAX_BATCH_SIZE_MB"] = 0
        with pytest.raises(StorageValidationError):
            create_upload_batch_presign(user=user, module_type="project_documents", target_type="folder", target_id=1, files=[{"client_file_id": "x", "filename": "a.pdf", "mime_type": "application/pdf", "size": 1}])


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
        result = create_upload_batch_presign(user=user, module_type="company_media", target_type="album", target_id=1, files=[{"client_file_id": "a", "filename": "a.mp3", "mime_type": "audio/mpeg", "size": 10}], provider=provider)
        item = db.session.get(UploadBatchItem, result["items"][0]["upload_batch_item_id"])
        with pytest.raises(StorageNotFoundError):
            complete_upload_item(user=user, upload_batch_item_id=item.id, provider=provider)
        assert item.storage_object.upload_status == "pending" and item.status == "failed"
        with pytest.raises(StorageNotFoundError):
            create_signed_download_url(user=user, storage_object_id=item.storage_object_id, provider=provider)


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
