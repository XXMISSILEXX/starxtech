import io
import multiprocessing
import os
import threading
import time

import pytest
from PIL import Image
from werkzeug.datastructures import FileStorage

from app.storage.cache import CacheSource, MediaCache, MediaCacheError, cleanup_media_cache


def _config(root, **overrides):
    return {
        "MEDIA_CACHE_ROOT": str(root), "MEDIA_CACHE_MAX_BYTES": 1024 * 1024,
        "MEDIA_CACHE_MAX_AGE_DAYS": 30, "MEDIA_CACHE_DELIVERY_MODE": "send_file",
        "MEDIA_CACHE_X_ACCEL_PREFIX": "/_protected_media_cache/", **overrides,
    }


def _source(**overrides):
    values = {"category": "daily-report-thumbnail", "object_id": 72, "derivative_type": "thumbnail",
        "immutable_key": "daily-reports/derivatives/a.webp", "version_id": 91, "extension": "webp",
        "mime_type": "image/webp", "file_size": 4, "bucket": "test-media"}
    values.update(overrides)
    return CacheSource(**values)


def _process_fill(root, started, calls):
    cache = MediaCache(_config(root))
    started.wait(5)

    def source():
        with calls.get_lock():
            calls.value += 1
        time.sleep(.15)
        return io.BytesIO(b"data")

    cache.get_or_fill(_source(), source)


def test_cache_miss_fills_once_then_hit_does_not_open_source(tmp_path):
    cache = MediaCache(_config(tmp_path))
    calls = 0

    def source():
        nonlocal calls
        calls += 1
        return io.BytesIO(b"data")

    first = cache.get_or_fill(_source(), source)
    second = cache.get_or_fill(_source(), source)
    assert calls == 1
    assert first.path == second.path
    assert first.path.read_bytes() == b"data"


def test_competing_threads_fill_once(tmp_path):
    calls = 0
    calls_lock = threading.Lock()
    barrier = threading.Barrier(2)
    results = []

    def run():
        cache = MediaCache(_config(tmp_path))
        barrier.wait()

        def source():
            nonlocal calls
            with calls_lock:
                calls += 1
            time.sleep(.1)
            return io.BytesIO(b"data")

        results.append(cache.get_or_fill(_source(), source))

    threads = [threading.Thread(target=run), threading.Thread(target=run)]
    [thread.start() for thread in threads]
    [thread.join() for thread in threads]
    assert calls == 1
    assert len({item.path for item in results}) == 1


def test_competing_processes_fill_once_with_flock(tmp_path):
    context = multiprocessing.get_context("fork")
    started = context.Event()
    calls = context.Value("i", 0)
    processes = [context.Process(target=_process_fill, args=(str(tmp_path), started, calls)) for _ in range(2)]
    [process.start() for process in processes]
    started.set()
    [process.join(5) for process in processes]
    assert all(process.exitcode == 0 for process in processes)
    assert calls.value == 1


def test_empty_or_partial_download_never_becomes_cache_hit(tmp_path):
    cache = MediaCache(_config(tmp_path))
    with pytest.raises(MediaCacheError):
        cache.get_or_fill(_source(), lambda: io.BytesIO(b""))
    path, _ = cache.cache_path(_source())
    assert not path.exists()
    with pytest.raises(MediaCacheError):
        cache.get_or_fill(_source(), lambda: io.BytesIO(b"dat"))
    assert not path.exists()
    assert not list(path.parent.glob("*.tmp-*"))


def test_download_error_cleans_temporary_file_and_atomic_final(tmp_path):
    cache = MediaCache(_config(tmp_path))

    class Broken:
        def read(self, _size):
            raise OSError("storage unavailable")

        def close(self):
            pass

    with pytest.raises(MediaCacheError):
        cache.get_or_fill(_source(), Broken)
    path, _ = cache.cache_path(_source())
    assert not path.exists()
    assert not list(path.parent.glob("*.tmp-*"))


def test_immutable_version_and_storage_key_do_not_collide(tmp_path):
    cache = MediaCache(_config(tmp_path))
    first, _ = cache.cache_path(_source())
    second, _ = cache.cache_path(_source(version_id=92))
    third, _ = cache.cache_path(_source(immutable_key="different/key.webp"))
    assert len({first, second, third}) == 3


def test_cache_rejects_traversal_and_symlinks(tmp_path):
    cache = MediaCache(_config(tmp_path))
    with pytest.raises(MediaCacheError):
        cache.cache_path(_source(category="../../outside"))
    path, _ = cache.cache_path(_source())
    target = tmp_path / "outside"
    target.write_bytes(b"data")
    path.symlink_to(target)
    with pytest.raises(MediaCacheError):
        cache.get_or_fill(_source(), lambda: io.BytesIO(b"data"))


def test_cleanup_is_dry_run_by_default_and_never_leaves_root(tmp_path):
    config = _config(tmp_path, MEDIA_CACHE_MAX_AGE_DAYS=1)
    cache = MediaCache(config)
    cached = cache.get_or_fill(_source(), lambda: io.BytesIO(b"data"))
    old = time.time() - 3 * 86400
    os.utime(cached.path, (old, old))
    outside = tmp_path.parent / "outside-cache-file"
    outside.write_bytes(b"outside")
    dry = cleanup_media_cache(config, dry_run=True)
    assert dry["deleted"] == 1
    assert cached.path.exists() and outside.exists()
    applied = cleanup_media_cache(config, dry_run=False)
    assert applied["deleted"] == 1
    assert not cached.path.exists() and outside.exists()


def test_cleanup_skips_file_while_its_cross_process_lock_is_held(tmp_path):
    config = _config(tmp_path, MEDIA_CACHE_MAX_AGE_DAYS=1)
    cache = MediaCache(config)
    cached = cache.get_or_fill(_source(), lambda: io.BytesIO(b"data"))
    old = time.time() - 3 * 86400
    os.utime(cached.path, (old, old))
    with cache._key_lock(cached.path):
        result = cleanup_media_cache(config, dry_run=False)
    assert result["deleted"] == 0
    assert cached.path.exists()


def _image_upload():
    output = io.BytesIO()
    Image.new("RGB", (16, 16), "navy").save(output, "JPEG")
    output.seek(0)
    return FileStorage(output, filename="avatar.jpg", content_type="image/jpeg")


def test_avatar_cache_uses_local_delivery_and_authorises_before_hit(client, app, tmp_path):
    from app.display_images import replace_display_image
    from app.extensions import db
    from app.models import User

    with app.app_context():
        user = User.query.filter_by(username="reporter").one()
        replace_display_image(user, _image_upload(), attribute="avatar_storage_object", scope="account-profiles", user=user)
        db.session.commit()
        app.config.update(MEDIA_CACHE_ENABLED=True, MEDIA_CACHE_ROOT=str(tmp_path), MEDIA_CACHE_DELIVERY_MODE="send_file")
    response = client.post("/login", data={"username_or_email": "reporter", "password": "password123"})
    assert response.status_code == 302
    response = client.get("/account/avatar?v=wrong")
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("image/webp")
    assert response.headers["Content-Disposition"] == "inline"
    assert response.headers["Cache-Control"] == "private, max-age=86400, immutable"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    response.close()
    client.post("/logout")
    assert client.get("/account/avatar").status_code == 302


def test_x_accel_delivery_uses_only_validated_relative_path(client, app, tmp_path):
    from app.display_images import replace_display_image
    from app.extensions import db
    from app.models import User

    with app.app_context():
        user = User.query.filter_by(username="reporter").one()
        replace_display_image(user, _image_upload(), attribute="avatar_storage_object", scope="account-profiles", user=user)
        db.session.commit()
        app.config.update(MEDIA_CACHE_ENABLED=True, MEDIA_CACHE_ROOT=str(tmp_path), MEDIA_CACHE_DELIVERY_MODE="x_accel")
    client.post("/login", data={"username_or_email": "reporter", "password": "password123"})
    response = client.get("/account/avatar")
    assert response.status_code == 200
    assert response.headers["X-Accel-Redirect"].startswith("/_protected_media_cache/user-avatar/")
    assert str(tmp_path) not in response.headers["X-Accel-Redirect"]


def test_branding_logo_cache_is_private_and_never_redirects_to_s3(client, app, tmp_path):
    from app.display_images import replace_display_image
    from app.extensions import db
    from app.models import SystemSetting, User

    with app.app_context():
        user = User.query.filter_by(username="reporter").one()
        setting = SystemSetting(key="branding")
        db.session.add(setting)
        replace_display_image(setting, _image_upload(), attribute="brand_logo_storage_object", scope="branding", user=user)
        db.session.commit()
        app.config.update(MEDIA_CACHE_ENABLED=True, MEDIA_CACHE_ROOT=str(tmp_path), MEDIA_CACHE_DELIVERY_MODE="send_file")
    client.post("/login", data={"username_or_email": "reporter", "password": "password123"})
    response = client.get("/branding/logo")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "private, max-age=86400, immutable"
    response.close()


def test_daily_thumbnail_uses_cache_but_preview_and_original_remain_direct_s3(client, app, tmp_path):
    from app.extensions import db
    from app.models import ReportAttachment, StorageDerivative
    from tests.test_reports_attachments import direct_report, login

    login(client, "reporter")
    direct_report(client, app)
    with app.app_context():
        attachment = ReportAttachment.query.one()
        obj = attachment.storage_object
        derivative = StorageDerivative(storage_object_id=obj.id, derivative_type="thumbnail", bucket=obj.bucket,
            object_key="daily-reports/derivatives/cache-thumbnail.webp", mime_type="image/webp", file_ext="webp", file_size=4)
        db.session.add(derivative)
        db.session.commit()
        app.extensions["storage_provider"].put_bytes(derivative.bucket, derivative.object_key, b"data", derivative.mime_type)
        app.config.update(MEDIA_CACHE_ENABLED=True, MEDIA_CACHE_ROOT=str(tmp_path), MEDIA_CACHE_DELIVERY_MODE="send_file")
        attachment_id, derivative_id = attachment.id, derivative.id
    thumbnail = client.get(f"/attachments/{attachment_id}/thumbnail?v={derivative_id}")
    assert thumbnail.status_code == 200
    assert thumbnail.headers["Cache-Control"] == "private, max-age=3600"
    thumbnail.close()
    assert client.get(f"/attachments/{attachment_id}").status_code == 302
    assert client.get(f"/attachments/{attachment_id}/download").status_code == 302


def test_document_and_company_thumbnail_routes_authorise_before_local_cache(client, app, tmp_path):
    from app.company_media.services import set_permission
    from app.extensions import db
    from app.models import (CompanyMediaAlbum, CompanyMediaFile, Project, ProjectDocumentFile,
                            StorageDerivative, StorageObject, User)
    from app.project_documents.services import get_or_create_project_root_folder
    from app.storage.providers import FakeStorageProvider

    with app.app_context():
        provider = FakeStorageProvider()
        app.extensions["storage_provider"] = provider
        pm, admin = db.session.get(User, 5), db.session.get(User, 6)
        root = get_or_create_project_root_folder(db.session.get(Project, 1), admin)
        document_object = StorageObject(bucket="test", object_key="document-original", original_filename="document.jpg",
            mime_type="image/jpeg", file_ext="jpg", file_size=4, uploaded_by_id=pm.id, upload_status="active")
        db.session.add(document_object); db.session.flush()
        document = ProjectDocumentFile(project_id=1, folder_id=root.id, storage_object_id=document_object.id,
            display_name="document.jpg", created_by_id=pm.id)
        document_derivative = StorageDerivative(storage_object_id=document_object.id, derivative_type="thumbnail", bucket="test",
            object_key="document-thumb", mime_type="image/webp", file_ext="webp", file_size=4)
        album = CompanyMediaAlbum(name="Cache album", is_restricted=True, created_by_id=admin.id)
        db.session.add_all([document, document_derivative, album]); db.session.flush()
        media_object = StorageObject(bucket="test", object_key="media-original", original_filename="media.jpg",
            mime_type="image/jpeg", file_ext="jpg", file_size=4, uploaded_by_id=admin.id, upload_status="active")
        db.session.add(media_object); db.session.flush()
        media = CompanyMediaFile(album_id=album.id, storage_object_id=media_object.id, display_name="media.jpg", media_type="image", created_by_id=admin.id)
        media_derivative = StorageDerivative(storage_object_id=media_object.id, derivative_type="thumbnail", bucket="test",
            object_key="media-thumb", mime_type="image/webp", file_ext="webp", file_size=4)
        db.session.add_all([media, media_derivative]); db.session.flush()
        set_permission(admin, album, "user", pm.id, {"can_view": "1"})
        db.session.commit()
        provider.put_bytes("test", "document-thumb", b"data", "image/webp")
        provider.put_bytes("test", "media-thumb", b"data", "image/webp")
        app.config.update(MEDIA_CACHE_ENABLED=True, MEDIA_CACHE_ROOT=str(tmp_path), MEDIA_CACHE_DELIVERY_MODE="send_file")
        document_id, document_version = document.id, document_derivative.id
        media_id, media_version = media.id, media_derivative.id
    client.post("/login", data={"username_or_email": "pm", "password": "password123"})
    document_response = client.get(f"/project-documents/files/{document_id}/thumbnail?v={document_version}")
    assert document_response.status_code == 200
    document_response.close()
    media_response = client.get(f"/company-media/files/{media_id}/thumbnail?v={media_version}")
    assert media_response.status_code == 200
    media_response.close()
    with app.app_context():
        db.session.get(ProjectDocumentFile, document_id).is_active = False
        db.session.get(CompanyMediaFile, media_id).is_active = False
        db.session.commit()
    assert client.get(f"/project-documents/files/{document_id}/thumbnail?v={document_version}").status_code == 403
    assert client.get(f"/company-media/files/{media_id}/thumbnail?v={media_version}").status_code == 403
