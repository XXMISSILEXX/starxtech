"""Opt-in PostgreSQL locking tests for Phase 5.

Run only against the disposable database after `flask db upgrade`; SQLite does
not provide evidence for the `FOR UPDATE` behaviour exercised here.
"""

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.company_media import services as media_services
from app.company_media.upload_cleanup import cancel_company_media_upload_session
from app.extensions import db
from app.models import CompanyMediaAlbum, CompanyMediaFile, Role, StorageObject, UploadBatchItem, UploadSelectionSession, User, UserRole
from app.storage.exceptions import StorageNotFoundError, StorageUploadContractError
from app.storage.providers import FakeStorageProvider
from app.storage.services import create_upload_selection_session


POSTGRES_URL = os.getenv("PHASE5_POSTGRES_URL", "")
if POSTGRES_URL and not POSTGRES_URL.startswith("postgresql+psycopg://starx_phase4:starx_phase4@127.0.0.1:55433/starx_phase4"):
    raise RuntimeError("PHASE5_POSTGRES_URL must point to the disposable starx_phase4 database.")


@pytest.fixture(scope="module")
def pg_app():
    if not POSTGRES_URL:
        pytest.skip("set PHASE5_POSTGRES_URL after upgrading the disposable PostgreSQL database")

    class PostgreSQLPhase5Config:
        APP_ENV = "testing"
        TESTING = True
        SECRET_KEY = "phase5-postgres-test"
        SQLALCHEMY_DATABASE_URI = POSTGRES_URL
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        WTF_CSRF_ENABLED = False
        STORAGE_PROVIDER = "fake"
        STORAGE_BUCKET = "phase5-test"
        STORAGE_PREFIX = ""

    app = create_app(PostgreSQLPhase5Config)
    app.extensions["storage_provider"] = FakeStorageProvider()
    return app


def _fixture(pg_app):
    token = uuid.uuid4().hex[:12]
    with pg_app.app_context():
        role = Role(code=f"PHASE5_{token}", name="Phase 5 PostgreSQL", is_system=False)
        db.session.add(role); db.session.flush()
        user = User(username=f"phase5_{token}", email=f"phase5_{token}@example.test", full_name="Phase 5",
                    password_hash=generate_password_hash("password123"), role=role,
                    legacy_role=UserRole.ADMIN.value, is_active=True)
        db.session.add(user); db.session.flush()
        album = CompanyMediaAlbum(name=f"Phase 5 PostgreSQL {token}", created_by_id=user.id)
        db.session.add(album); db.session.commit()
        selection = create_upload_selection_session(user=user, module_type="company_media", target_type="album",
                                                    target_id=album.id, declared_files=1, declared_size_bytes=5)
        created = media_services.presign(user, album, [{"client_file_id": "race", "filename": "race.jpg", "mime_type": "image/jpeg", "size": 5}], selection["selection_session_id"])["items"][0]
        return user.id, album.id, selection["selection_session_id"], created["upload_batch_item_id"], created["storage_object_id"]


def test_postgresql_two_cleanup_workers_serialize_and_do_not_double_delete(pg_app):
    user_id, album_id, selection_id, item_id, object_id = _fixture(pg_app)
    barrier = threading.Barrier(2)

    def worker():
        with pg_app.app_context():
            try:
                barrier.wait(timeout=10)
                user = db.session.get(User, user_id)
                result = cancel_company_media_upload_session(actor=user, album_id=album_id, session_id=selection_id)
                db.session.commit()
                return result
            finally:
                db.session.remove()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _index: worker(), range(2)))
    assert sorted(result.idempotent_replay for result in results) == [False, True]
    with pg_app.app_context():
        assert db.session.get(UploadBatchItem, item_id) is None
        assert db.session.get(StorageObject, object_id) is None
        assert db.session.get(UploadSelectionSession, selection_id).status == "cancelled"


def test_postgresql_complete_cancel_race_preserves_consistent_terminal_state(pg_app):
    user_id, album_id, selection_id, item_id, object_id = _fixture(pg_app)
    with pg_app.app_context():
        obj = db.session.get(StorageObject, object_id)
        pg_app.extensions["storage_provider"].register_object(obj.bucket, obj.object_key, 5, "image/jpeg")
    barrier = threading.Barrier(2)

    def cancel_worker():
        with pg_app.app_context():
            try:
                user = db.session.get(User, user_id); barrier.wait(timeout=10)
                result = cancel_company_media_upload_session(actor=user, album_id=album_id, session_id=selection_id)
                db.session.commit(); return ("cancel", result.idempotent_replay)
            finally:
                db.session.remove()

    def complete_worker():
        with pg_app.app_context():
            try:
                user = db.session.get(User, user_id); album = db.session.get(CompanyMediaAlbum, album_id); barrier.wait(timeout=10)
                try:
                    return ("complete", media_services.complete(user, album, item_id, {})["status"])
                except (StorageNotFoundError, StorageUploadContractError):
                    db.session.rollback(); return ("complete", "not_available")
            finally:
                db.session.remove()

    with patch("app.media_processing.services.enqueue_media_processing_for_storage_object", lambda _id: None):
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda function: function(), (cancel_worker, complete_worker)))
    assert {kind for kind, _value in outcomes} == {"cancel", "complete"}
    with pg_app.app_context():
        item = db.session.get(UploadBatchItem, item_id)
        obj = db.session.get(StorageObject, object_id)
        media = CompanyMediaFile.query.filter_by(storage_object_id=object_id).all()
        assert (item is None and obj is None and not media) or (
            item is not None and item.status == "completed" and obj.upload_status == "active" and len(media) == 1
        )
