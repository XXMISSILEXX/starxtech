from datetime import datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.company_media import services as media_services
from app.extensions import db
from app.models import CompanyMediaAlbum, CompanyMediaFile, StorageObject, UploadBatch, UploadBatchItem, UploadSelectionSession, User
from app.storage.exceptions import StorageUploadContractError
from app.storage.providers import FakeStorageProvider
from app.storage.services import (
    create_upload_batch_presign,
    create_upload_selection_session,
    finalize_upload_selection_session,
)


def _file(client_file_id="phase4-file", *, filename="phase4.JPG", mime_type="image/jpg", size=5):
    return {"client_file_id": client_file_id, "filename": filename, "mime_type": mime_type, "size": size}


def _selection(user, album_id, *, count=3, size=30):
    return create_upload_selection_session(
        user=user, module_type="company_media", target_type="album", target_id=album_id,
        declared_files=count, declared_size_bytes=size,
    )


def _album():
    admin = db.session.get(User, 6)
    album = CompanyMediaAlbum(name="Phase 4 idempotency", created_by_id=admin.id)
    db.session.add(album)
    db.session.commit()
    return admin, album


def test_selection_presign_replays_one_item_object_key_and_counter_once(app):
    with app.app_context():
        user, album = _album()
        provider = FakeStorageProvider()
        selection = _selection(user, album.id)
        first = create_upload_batch_presign(
            user=user, module_type="company_media", target_type="album", target_id=album.id,
            selection_session_id=selection["selection_session_id"], files=[_file()], provider=provider,
        )
        second = create_upload_batch_presign(
            user=user, module_type="company_media", target_type="album", target_id=album.id,
            selection_session_id=selection["selection_session_id"], files=[_file(filename="phase4.jpg", mime_type="image/jpeg")], provider=provider,
        )
        first_item, second_item = first["items"][0], second["items"][0]
        assert first_item["idempotent_replay"] is False
        assert second_item["idempotent_replay"] is True
        assert first_item["upload_batch_item_id"] == second_item["upload_batch_item_id"]
        assert first_item["storage_object_id"] == second_item["storage_object_id"]
        assert first_item["url"] and second_item["url"]
        assert UploadBatchItem.query.filter_by(selection_session_id=selection["selection_session_id"]).count() == 1
        assert StorageObject.query.count() == 1
        session = db.session.get(UploadSelectionSession, selection["selection_session_id"])
        assert (session.presigned_files, session.presigned_size_bytes) == (1, 5)


@pytest.mark.parametrize("changed", [
    {"filename": "other.jpg"}, {"size": 6}, {"mime_type": "image/png", "filename": "phase4.png"},
])
def test_selection_presign_conflict_creates_no_extra_rows_or_counter(app, changed):
    with app.app_context():
        user, album = _album()
        selection = _selection(user, album.id)
        create_upload_batch_presign(
            user=user, module_type="company_media", target_type="album", target_id=album.id,
            selection_session_id=selection["selection_session_id"], files=[_file()], provider=FakeStorageProvider(),
        )
        with pytest.raises(StorageUploadContractError) as exc_info:
            create_upload_batch_presign(
                user=user, module_type="company_media", target_type="album", target_id=album.id,
                selection_session_id=selection["selection_session_id"], files=[_file(**changed)], provider=FakeStorageProvider(),
            )
        assert exc_info.value.code == "idempotency_conflict"
        assert exc_info.value.status_code == 409 and exc_info.value.retryable is False
        assert UploadBatchItem.query.filter_by(selection_session_id=selection["selection_session_id"]).count() == 1
        assert StorageObject.query.count() == 1
        session = db.session.get(UploadSelectionSession, selection["selection_session_id"])
        assert (session.presigned_files, session.presigned_size_bytes) == (1, 5)


def test_selection_constraint_is_scoped_to_session_and_rejects_duplicate_key(app):
    with app.app_context():
        user, album = _album()
        first = _selection(user, album.id)
        second = _selection(user, album.id)
        batch = UploadBatch(module_type="company_media", target_type="album", target_id=album.id, created_by_id=user.id)
        second_batch = UploadBatch(module_type="company_media", target_type="album", target_id=album.id, created_by_id=user.id)
        db.session.add_all([batch, second_batch])
        db.session.flush()
        kwargs = dict(upload_batch_id=batch.id, client_file_id="direct-key", original_filename="x.jpg", mime_type="image/jpeg", file_size=1, status="rejected")
        db.session.add_all([
            UploadBatchItem(selection_session_id=first["selection_session_id"], **kwargs),
            UploadBatchItem(selection_session_id=second["selection_session_id"], upload_batch_id=second_batch.id,
                            client_file_id="direct-key", original_filename="x.jpg", mime_type="image/jpeg", file_size=1, status="rejected"),
        ])
        db.session.commit()
        db.session.add(UploadBatchItem(selection_session_id=first["selection_session_id"], **kwargs))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_completed_presign_replay_skips_new_upload_and_complete_is_idempotent(app, monkeypatch):
    with app.app_context():
        user, album = _album()
        provider = FakeStorageProvider()
        app.extensions["storage_provider"] = provider
        selection = _selection(user, album.id)
        created = media_services.presign(user, album, [_file()], selection["selection_session_id"])["items"][0]
        storage = db.session.get(StorageObject, created["storage_object_id"])
        provider.register_object(storage.bucket, storage.object_key, 5, "image/jpeg")
        enqueued = []
        monkeypatch.setattr("app.media_processing.services.enqueue_media_processing_for_storage_object", enqueued.append)
        assert media_services.complete(user, album, created["upload_batch_item_id"], {})["idempotent_replay"] is False
        repeated_complete = media_services.complete(user, album, created["upload_batch_item_id"], {})
        assert repeated_complete["idempotent_replay"] is True
        replay = media_services.presign(user, album, [_file(filename="phase4.jpg", mime_type="image/jpeg")], selection["selection_session_id"])["items"][0]
        assert replay["accepted"] is True and replay["status"] == "completed"
        assert replay["idempotent_replay"] is True and "url" not in replay
        assert CompanyMediaFile.query.filter_by(storage_object_id=storage.id).count() == 1
        assert enqueued == [storage.id]


def test_expired_presign_creates_nothing_but_existing_item_can_complete_and_finalize(app):
    with app.app_context():
        user, album = _album()
        provider = FakeStorageProvider()
        app.extensions["storage_provider"] = provider
        selection = _selection(user, album.id)
        created = media_services.presign(user, album, [_file()], selection["selection_session_id"])["items"][0]
        session = db.session.get(UploadSelectionSession, selection["selection_session_id"])
        session.expires_at = datetime.utcnow() - timedelta(seconds=1)
        db.session.commit()
        with pytest.raises(StorageUploadContractError) as exc_info:
            media_services.presign(user, album, [_file("new-file", filename="new.jpg", mime_type="image/jpeg")], selection["selection_session_id"])
        assert exc_info.value.code == "selection_session_expired" and exc_info.value.status_code == 410
        assert UploadBatchItem.query.filter_by(selection_session_id=session.id).count() == 1
        storage = db.session.get(StorageObject, created["storage_object_id"])
        provider.register_object(storage.bucket, storage.object_key, 5, "image/jpeg")
        media_services.complete(user, album, created["upload_batch_item_id"], {})
        finalized = finalize_upload_selection_session(
            user=user, selection_session_id=session.id, module_type="company_media", target_type="album", target_id=album.id,
        )
        repeated = finalize_upload_selection_session(
            user=user, selection_session_id=session.id, module_type="company_media", target_type="album", target_id=album.id,
        )
        assert finalized["status"] == "completed" and finalized["idempotent_replay"] is False
        assert repeated["status"] == "completed" and repeated["idempotent_replay"] is True


def test_presign_route_returns_safe_http_409_idempotency_conflict(client, app):
    with app.app_context():
        admin = db.session.get(User, 6)
        album = CompanyMediaAlbum(name="Phase 4 route conflict", created_by_id=admin.id)
        db.session.add(album)
        db.session.commit()
        album_id = album.id
    assert client.post("/login", data={"username_or_email": "admin", "password": "password123"}).status_code == 302
    session_response = client.post(
        f"/company-media/albums/{album_id}/files/upload-selection-sessions",
        json={"file_count": 1, "total_size_bytes": 5},
    )
    session_id = session_response.get_json()["selection_session_id"]
    payload = {"selection_session_id": session_id, "files": [_file(filename="route.jpg", mime_type="image/jpeg")]}
    assert client.post(f"/company-media/albums/{album_id}/files/presign-batch", json=payload).status_code == 200
    payload["files"] = [_file(filename="different.jpg", mime_type="image/jpeg")]
    conflict = client.post(f"/company-media/albums/{album_id}/files/presign-batch", json=payload)
    assert conflict.status_code == 409
    assert conflict.get_json() == {
        "ok": False,
        "error": {
            "code": "idempotency_conflict", "message": "Mã tệp đã được sử dụng cho một tệp khác.",
            "details": {}, "retryable": False,
        },
    }
