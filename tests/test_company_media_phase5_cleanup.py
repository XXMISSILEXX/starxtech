from datetime import datetime, timedelta

from app.company_media import services as media_services
from app.company_media.upload_cleanup import cancel_company_media_upload_session
from app.extensions import db
from app.models import (
    CompanyMediaAlbum,
    CompanyMediaAlbumPermission,
    CompanyMediaFile,
    StorageObject,
    UploadBatchItem,
    UploadSelectionSession,
    User,
)
from app.storage.exceptions import StorageAuthorizationError
from app.storage.providers import FakeStorageProvider
from app.storage.services import create_upload_selection_session


def _album(name="Phase 5 cleanup"):
    admin = db.session.get(User, 6)
    album = CompanyMediaAlbum(name=name, created_by_id=admin.id)
    db.session.add(album)
    db.session.commit()
    return admin, album


def _selection(user, album, *, old=False):
    result = create_upload_selection_session(
        user=user, module_type="company_media", target_type="album", target_id=album.id,
        declared_files=3, declared_size_bytes=30,
    )
    session = db.session.get(UploadSelectionSession, result["selection_session_id"])
    if old:
        session.expires_at = datetime.utcnow() - timedelta(hours=72)
        db.session.commit()
    return session


def _presigned_item(user, album, session, client_file_id):
    provider = FakeStorageProvider()
    app_data = media_services.presign(
        user, album,
        [{"client_file_id": client_file_id, "filename": f"{client_file_id}.jpg", "mime_type": "image/jpeg", "size": 5}],
        session.id,
    )["items"][0]
    return db.session.get(UploadBatchItem, app_data["upload_batch_item_id"]), provider


def _complete(user, album, item):
    item.storage_object.upload_status = "active"
    item.status = "completed"
    db.session.add(CompanyMediaFile(
        album_id=album.id, storage_object_id=item.storage_object_id,
        display_name=item.original_filename, media_type="image", created_by_id=user.id,
    ))
    db.session.commit()
    return db.session.get(UploadBatchItem, item.id)


def test_cancel_pending_item_hard_deletes_only_its_database_rows(app, monkeypatch):
    with app.app_context():
        user, album = _album()
        session = _selection(user, album)
        item, _provider = _presigned_item(user, album, session, "pending")
        object_id = item.storage_object_id
        monkeypatch.setattr("app.storage.providers.get_storage_provider", lambda: (_ for _ in ()).throw(AssertionError("S3 must not be called")))
        result = cancel_company_media_upload_session(actor=user, album_id=album.id, session_id=session.id)
        db.session.commit()
        assert result.pending_items_removed == 1
        assert result.pending_storage_objects_removed == 1
        assert db.session.get(UploadBatchItem, item.id) is None
        assert db.session.get(StorageObject, object_id) is None
        assert db.session.get(UploadSelectionSession, session.id).status == "cancelled"
        assert db.session.get(UploadSelectionSession, session.id).cleaned_at is not None


def test_cancel_mixed_session_preserves_completed_media_and_active_object(app):
    with app.app_context():
        user, album = _album()
        session = _selection(user, album)
        completed, _ = _presigned_item(user, album, session, "completed")
        pending, _ = _presigned_item(user, album, session, "pending")
        completed = _complete(user, album, completed)
        completed_object_id, media_id, pending_object_id = completed.storage_object_id, CompanyMediaFile.query.filter_by(storage_object_id=completed.storage_object_id).one().id, pending.storage_object_id
        result = cancel_company_media_upload_session(actor=user, album_id=album.id, session_id=session.id)
        db.session.commit()
        assert result.completed_files_preserved == 1
        assert result.pending_items_removed == 1
        assert db.session.get(UploadBatchItem, completed.id).status == "completed"
        assert db.session.get(CompanyMediaFile, media_id).storage_object_id == completed_object_id
        assert db.session.get(StorageObject, completed_object_id).upload_status == "active"
        assert db.session.get(StorageObject, pending_object_id) is None


def test_cleanup_keeps_pending_object_with_business_reference_even_if_status_is_unusual(app):
    with app.app_context():
        user, album = _album()
        session = _selection(user, album)
        item, _ = _presigned_item(user, album, session, "referenced")
        object_id = item.storage_object_id
        media = CompanyMediaFile(album_id=album.id, storage_object_id=object_id, display_name="existing.jpg", media_type="image", created_by_id=user.id)
        db.session.add(media)
        db.session.commit()
        result = cancel_company_media_upload_session(actor=user, album_id=album.id, session_id=session.id)
        db.session.commit()
        assert result.pending_items_removed == 1
        assert result.pending_storage_objects_removed == 0
        assert result.protected_storage_objects_preserved == 1
        assert db.session.get(StorageObject, object_id) is not None
        assert db.session.get(CompanyMediaFile, media.id) is not None


def test_cancel_replay_is_idempotent_and_non_owner_is_denied(app):
    with app.app_context():
        user, album = _album()
        session = _selection(user, album)
        _presigned_item(user, album, session, "pending")
        first = cancel_company_media_upload_session(actor=user, album_id=album.id, session_id=session.id)
        db.session.commit()
        second = cancel_company_media_upload_session(actor=user, album_id=album.id, session_id=session.id)
        db.session.commit()
        assert first.idempotent_replay is False
        assert second.idempotent_replay is True
        assert second.pending_items_removed == second.pending_storage_objects_removed == 0
        other = db.session.get(User, 3)
        with __import__("pytest").raises(StorageAuthorizationError):
            cancel_company_media_upload_session(actor=other, album_id=album.id, session_id=session.id)
        db.session.rollback()


def test_cancel_route_enforces_owner_album_and_csrf_contract(client, app):
    with app.app_context():
        user, album = _album()
        other_album = CompanyMediaAlbum(name="Other album", created_by_id=user.id)
        db.session.add(other_album)
        db.session.commit()
        session = _selection(user, album)
        route_item, _ = _presigned_item(user, album, session, "route")
        album_id, other_album_id, session_id, route_item_id = album.id, other_album.id, session.id, route_item.id
        reporter = db.session.get(User, 3)
        db.session.add(CompanyMediaAlbumPermission(album_id=album_id, principal_type="user", user_id=reporter.id,
                       can_upload=True, created_by_id=user.id))
        db.session.commit()
    assert client.post("/login", data={"username_or_email": "admin", "password": "password123"}).status_code == 302
    wrong_album = client.post(f"/company-media/albums/{other_album_id}/upload-sessions/{session_id}/cancel", json={})
    assert wrong_album.status_code == 403
    app.config["WTF_CSRF_ENABLED"] = True
    assert client.post(f"/company-media/albums/{album_id}/upload-sessions/{session_id}/cancel", json={}).status_code == 400
    app.config["WTF_CSRF_ENABLED"] = False
    assert client.post(f"/company-media/albums/{album_id}/upload-sessions/{session_id}/cancel", json={}).status_code == 200
    complete = client.post(f"/company-media/albums/{album_id}/files/complete-upload", json={"upload_batch_item_id": route_item_id})
    assert complete.status_code in {404, 409}
    assert complete.get_json()["error"]["code"] in {"upload_item_not_found", "upload_item_not_available"}


def test_cleanup_cli_dry_run_apply_limit_and_session_filter(app):
    with app.app_context():
        user, album = _album()
        old_one = _selection(user, album)
        old_two = _selection(user, album)
        fresh = _selection(user, album)
        old_one_item, _ = _presigned_item(user, album, old_one, "old-one")
        old_two_item, _ = _presigned_item(user, album, old_two, "old-two")
        fresh_item, _ = _presigned_item(user, album, fresh, "fresh")
        old_one.expires_at = old_two.expires_at = datetime.utcnow() - timedelta(hours=72)
        db.session.commit()
        ids = (old_one.id, old_two.id, fresh.id, old_one_item.id, old_two_item.id, fresh_item.id)
    runner = app.test_cli_runner()
    dry = runner.invoke(args=["cleanup-company-media-uploads", "--older-than-hours", "48", "--dry-run"])
    assert dry.exit_code == 0 and "matched=2" in dry.output and "processed=0" in dry.output
    applied = runner.invoke(args=["cleanup-company-media-uploads", "--older-than-hours", "48", "--apply", "--limit", "1", "--session-id", str(ids[1])])
    assert applied.exit_code == 0 and "matched=1" in applied.output and "items_removed=1" in applied.output
    with app.app_context():
        assert db.session.get(UploadBatchItem, ids[4]) is None
        assert db.session.get(UploadBatchItem, ids[3]) is not None
        assert db.session.get(UploadBatchItem, ids[5]) is not None
