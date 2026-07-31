"""Real PostgreSQL concurrency verification; opt in with PHASE4_POSTGRES_URL.

The URL is deliberately restricted to the named disposable database so this
test cannot silently run its write workload against an operator database.
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
from app.extensions import db
from app.models import CompanyMediaAlbum, CompanyMediaFile, Role, StorageObject, UploadBatchItem, UploadSelectionSession, User, UserRole
from app.storage.providers import FakeStorageProvider
from app.storage.services import create_upload_batch_presign, create_upload_selection_session


POSTGRES_URL = os.getenv("PHASE4_POSTGRES_URL", "")
if POSTGRES_URL and not POSTGRES_URL.startswith("postgresql+psycopg://starx_phase4:starx_phase4@127.0.0.1:55433/starx_phase4"):
    raise RuntimeError("PHASE4_POSTGRES_URL must point to the disposable starx_phase4 database.")


@pytest.fixture(scope="module")
def pg_app():
    if not POSTGRES_URL:
        pytest.skip("set PHASE4_POSTGRES_URL to run real PostgreSQL Phase 4 concurrency tests")

    class PostgreSQLPhase4Config:
        APP_ENV = "testing"
        TESTING = True
        SECRET_KEY = "phase4-postgres-test"
        SQLALCHEMY_DATABASE_URI = POSTGRES_URL
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        WTF_CSRF_ENABLED = False
        STORAGE_PROVIDER = "fake"
        STORAGE_BUCKET = "phase4-test"
        STORAGE_PREFIX = ""

    app = create_app(PostgreSQLPhase4Config)
    app.extensions["storage_provider"] = FakeStorageProvider()
    return app


def _fixtures(app):
    token = uuid.uuid4().hex[:12]
    with app.app_context():
        role = Role(code=f"PHASE4_{token}", name="Phase 4 PostgreSQL", is_system=False)
        db.session.add(role)
        db.session.flush()
        user = User(
            username=f"phase4_{token}", email=f"phase4_{token}@example.test", full_name="Phase 4",
            password_hash=generate_password_hash("password123"), role=role, legacy_role=UserRole.ADMIN.value,
            is_active=True,
        )
        db.session.add(user)
        db.session.flush()
        album = CompanyMediaAlbum(name=f"Phase 4 PostgreSQL {token}", created_by_id=user.id)
        db.session.add(album)
        db.session.commit()
        return user.id, album.id


def test_postgresql_concurrent_presign_and_complete_create_one_canonical_row(pg_app):
    user_id, album_id = _fixtures(pg_app)
    with pg_app.app_context():
        user = db.session.get(User, user_id)
        selection = create_upload_selection_session(
            user=user, module_type="company_media", target_type="album", target_id=album_id,
            declared_files=1, declared_size_bytes=5,
        )
        selection_id = selection["selection_session_id"]

    barrier = threading.Barrier(2)
    payload = [{"client_file_id": "postgres-race", "filename": "race.jpg", "mime_type": "image/jpeg", "size": 5}]

    def presign_worker():
        with pg_app.app_context():
            try:
                user = db.session.get(User, user_id)
                barrier.wait(timeout=10)
                return create_upload_batch_presign(
                    user=user, module_type="company_media", target_type="album", target_id=album_id,
                    selection_session_id=selection_id, files=payload,
                )
            finally:
                db.session.remove()

    with ThreadPoolExecutor(max_workers=2) as pool:
        presigned = list(pool.map(lambda _index: presign_worker(), range(2)))
    assert {result["items"][0]["upload_batch_item_id"] for result in presigned}.__len__() == 1
    assert sorted(result["items"][0]["idempotent_replay"] for result in presigned) == [False, True]

    with pg_app.app_context():
        item = UploadBatchItem.query.filter_by(selection_session_id=selection_id, client_file_id="postgres-race").one()
        obj = db.session.get(StorageObject, item.storage_object_id)
        pg_app.extensions["storage_provider"].register_object(obj.bucket, obj.object_key, 5, "image/jpeg")
        assert UploadBatchItem.query.filter_by(selection_session_id=selection_id).count() == 1
        assert StorageObject.query.filter_by(id=obj.id).count() == 1
        session = db.session.get(UploadSelectionSession, selection_id)
        assert (session.presigned_files, session.presigned_size_bytes) == (1, 5)
        item_id = item.id

    complete_barrier = threading.Barrier(2)
    enqueued = []

    def complete_worker():
        with pg_app.app_context():
            try:
                user = db.session.get(User, user_id)
                album = db.session.get(CompanyMediaAlbum, album_id)
                complete_barrier.wait(timeout=10)
                return media_services.complete(user, album, item_id, {})
            finally:
                db.session.remove()

    with patch("app.media_processing.services.enqueue_media_processing_for_storage_object", enqueued.append):
        with ThreadPoolExecutor(max_workers=2) as pool:
            completed = list(pool.map(lambda _index: complete_worker(), range(2)))
    assert sorted(result["idempotent_replay"] for result in completed) == [False, True]
    with pg_app.app_context():
        assert CompanyMediaFile.query.filter_by(storage_object_id=item.storage_object_id).count() == 1
        assert db.session.get(StorageObject, item.storage_object_id).upload_status == "active"
    assert enqueued == [item.storage_object_id]
