from datetime import datetime, timedelta

import pytest

from app.extensions import db
from app.models import CompanyMediaAlbum, UploadSelectionSession, User
from app.storage.exceptions import StorageUploadContractError
from app.storage.limits import get_company_media_upload_limits
from app.storage.providers import FakeStorageProvider
from app.storage.services import create_upload_batch_presign, create_upload_selection_session


MIB = 1024 * 1024
GIB = 1024 * MIB


def _media_file(client_file_id="one", *, filename="one.jpg", mime_type="image/jpeg", size=1):
    return {"client_file_id": client_file_id, "filename": filename, "mime_type": mime_type, "size": size}


def _album(app):
    with app.app_context():
        album = CompanyMediaAlbum(name="Upload limit album", created_by_id=6)
        db.session.add(album)
        db.session.commit()
        return album.id


def _login(client):
    return client.post("/login", data={"username_or_email": "admin", "password": "password123"})


def test_company_media_default_resolved_limits_preserve_current_behavior(app):
    with app.app_context():
        assert get_company_media_upload_limits() == {
            "max_selection_files": 500,
            "max_selection_bytes": 2 * GIB,
            "max_files_per_batch": 50,
            "max_batch_bytes": 512 * MIB,
            "max_file_bytes": 300 * MIB,
            "max_image_bytes": 50 * MIB,
            "max_video_bytes": 300 * MIB,
            "upload_concurrency": 3,
            "session_ttl_seconds": 7200,
        }


def test_company_media_resolver_honours_each_override_and_rejects_invalid_values(app):
    with app.app_context():
        config = dict(app.config)
        overrides = {
            "COMPANY_MEDIA_MAX_SELECTION_FILES": 9,
            "COMPANY_MEDIA_MAX_SELECTION_BYTES": 90,
            "COMPANY_MEDIA_MAX_FILES_PER_BATCH": 8,
            "COMPANY_MEDIA_MAX_PRESIGN_BATCH_BYTES": 80,
            "COMPANY_MEDIA_MAX_FILE_BYTES": 70,
            "COMPANY_MEDIA_MAX_IMAGE_BYTES": 60,
            "COMPANY_MEDIA_MAX_VIDEO_BYTES": 65,
            "COMPANY_MEDIA_UPLOAD_CONCURRENCY": 2,
            "COMPANY_MEDIA_UPLOAD_SESSION_TTL_SECONDS": 7,
        }
        config.update(overrides)
        limits = get_company_media_upload_limits(config)
        assert limits == {
            "max_selection_files": 9, "max_selection_bytes": 90, "max_files_per_batch": 8,
            "max_batch_bytes": 80, "max_file_bytes": 70, "max_image_bytes": 60,
            "max_video_bytes": 65, "upload_concurrency": 2, "session_ttl_seconds": 7,
        }
        for invalid in (0, -1, "not-an-integer"):
            config["COMPANY_MEDIA_MAX_FILES_PER_BATCH"] = invalid
            with pytest.raises(ValueError, match="positive integer"):
                get_company_media_upload_limits(config)


def test_project_documents_keep_shared_limits_when_company_media_is_overridden(app):
    with app.app_context():
        app.config["COMPANY_MEDIA_MAX_FILES_PER_BATCH"] = 1
        result = create_upload_batch_presign(
            user=db.session.get(User, 3), module_type="project_documents", target_type="folder", target_id=1,
            files=[
                {"client_file_id": "document-a", "filename": "a.pdf", "mime_type": "application/pdf", "size": 1},
                {"client_file_id": "document-b", "filename": "b.pdf", "mime_type": "application/pdf", "size": 1},
            ], provider=FakeStorageProvider(),
        )
        assert result["status"] == "uploading"


@pytest.mark.parametrize("count,expected_code", [(499, None), (500, None), (501, "selection_file_count_exceeded")])
def test_company_media_selection_file_boundaries(app, count, expected_code):
    with app.app_context():
        kwargs = dict(user=db.session.get(User, 6), module_type="company_media", target_type="album", target_id=1,
                      declared_files=count, declared_size_bytes=1)
        if expected_code:
            with pytest.raises(StorageUploadContractError) as exc_info:
                create_upload_selection_session(**kwargs)
            assert exc_info.value.code == expected_code
            assert exc_info.value.details == {"actual_files": count, "max_files": 500}
        else:
            assert create_upload_selection_session(**kwargs)["selection_session_id"]


@pytest.mark.parametrize("size,expected_code", [(2 * GIB - 1, None), (2 * GIB, None), (2 * GIB + 1, "selection_total_bytes_exceeded")])
def test_company_media_selection_byte_boundaries_and_ttl(app, size, expected_code):
    with app.app_context():
        app.config["COMPANY_MEDIA_UPLOAD_SESSION_TTL_SECONDS"] = 13
        kwargs = dict(user=db.session.get(User, 6), module_type="company_media", target_type="album", target_id=1,
                      declared_files=1, declared_size_bytes=size)
        if expected_code:
            with pytest.raises(StorageUploadContractError) as exc_info:
                create_upload_selection_session(**kwargs)
            assert exc_info.value.code == expected_code
            assert exc_info.value.details == {"actual_bytes": size, "max_bytes": 2 * GIB}
        else:
            result = create_upload_selection_session(**kwargs)
            session = db.session.get(UploadSelectionSession, result["selection_session_id"])
            assert 11 <= (session.expires_at - datetime.utcnow()).total_seconds() <= 14


@pytest.mark.parametrize("files,bytes,code", [(None, 1, "invalid_selection_file_count"), ("1", 1, "invalid_selection_file_count"), (1, None, "invalid_selection_total_bytes"), (1, "1", "invalid_selection_total_bytes")])
def test_company_media_selection_rejects_invalid_declared_types(app, files, bytes, code):
    with app.app_context():
        with pytest.raises(StorageUploadContractError) as exc_info:
            create_upload_selection_session(
                user=db.session.get(User, 6), module_type="company_media", target_type="album", target_id=1,
                declared_files=files, declared_size_bytes=bytes,
            )
        assert exc_info.value.code == code
        assert exc_info.value.status_code == 422


@pytest.mark.parametrize("count,expected_code", [(49, None), (50, None), (51, "presign_batch_file_count_exceeded")])
def test_company_media_presign_batch_file_boundaries(app, count, expected_code):
    with app.app_context():
        files = [_media_file(str(index)) for index in range(count)]
        kwargs = dict(user=db.session.get(User, 6), module_type="company_media", target_type="album", target_id=1,
                      files=files, provider=FakeStorageProvider())
        if expected_code:
            with pytest.raises(StorageUploadContractError) as exc_info:
                create_upload_batch_presign(**kwargs)
            assert exc_info.value.code == expected_code
            assert exc_info.value.details == {"actual_files": 51, "max_files": 50}
        else:
            assert len(create_upload_batch_presign(**kwargs)["items"]) == count


@pytest.mark.parametrize("size,expected_code", [(255 * MIB, None), (256 * MIB, None), (257 * MIB, "presign_batch_bytes_exceeded")])
def test_company_media_presign_batch_byte_boundaries(app, size, expected_code):
    with app.app_context():
        files = [_media_file("a", filename="a.mp4", mime_type="video/mp4", size=size),
                 _media_file("b", filename="b.mp4", mime_type="video/mp4", size=size)]
        kwargs = dict(user=db.session.get(User, 6), module_type="company_media", target_type="album", target_id=1,
                      files=files, provider=FakeStorageProvider())
        if expected_code:
            with pytest.raises(StorageUploadContractError) as exc_info:
                create_upload_batch_presign(**kwargs)
            assert exc_info.value.code == expected_code
            assert exc_info.value.details == {"actual_bytes": 514 * MIB, "max_bytes": 512 * MIB}
        else:
            assert len(create_upload_batch_presign(**kwargs)["items"]) == 2


def test_company_media_presign_empty_and_per_file_structured_rejections(app):
    with app.app_context():
        user = db.session.get(User, 6)
        with pytest.raises(StorageUploadContractError) as empty:
            create_upload_batch_presign(user=user, module_type="company_media", target_type="album", target_id=1, files=[])
        assert empty.value.code == "empty_presign_batch"

        result = create_upload_batch_presign(
            user=user, module_type="company_media", target_type="album", target_id=1,
            files=[_media_file("image", filename="at-limit.jpg", size=50 * MIB),
                   _media_file("image-over", filename="over.jpg", size=50 * MIB + 1)], provider=FakeStorageProvider(),
        )
        assert result["items"][0]["accepted"] is True
        rejected = result["items"][1]
        assert rejected["accepted"] is False
        assert rejected["error"]["code"] == "image_size_exceeded"
        assert rejected["error"]["details"] == {"actual_bytes": 50 * MIB + 1, "max_bytes": 50 * MIB}
        assert rejected["error_message"] == rejected["error"]["message"]

        app.config.update(COMPANY_MEDIA_MAX_FILE_BYTES=350 * MIB, COMPANY_MEDIA_MAX_VIDEO_BYTES=300 * MIB)
        result = create_upload_batch_presign(
            user=user, module_type="company_media", target_type="album", target_id=1,
            files=[_media_file("video", filename="at-limit.mp4", mime_type="video/mp4", size=300 * MIB)], provider=FakeStorageProvider(),
        )
        assert result["items"][0]["accepted"] is True
        result = create_upload_batch_presign(
            user=user, module_type="company_media", target_type="album", target_id=1,
            files=[_media_file("video-over", filename="over.mp4", mime_type="video/mp4", size=300 * MIB + 1)], provider=FakeStorageProvider(),
        )
        assert result["items"][0]["error"]["code"] == "video_size_exceeded"


def test_company_media_absolute_and_declared_quota_errors_are_separate(app):
    with app.app_context():
        user = db.session.get(User, 6)
        with pytest.raises(StorageUploadContractError) as absolute:
            create_upload_batch_presign(
                user=user, module_type="company_media", target_type="album", target_id=1,
                files=[_media_file("big", filename="big.mp4", mime_type="video/mp4", size=300 * MIB + 1)], provider=FakeStorageProvider(),
            )
        assert absolute.value.code == "file_size_exceeded"
        assert absolute.value.details["max_bytes"] == 300 * MIB

        selection = create_upload_selection_session(user=user, module_type="company_media", target_type="album", target_id=1,
                                                    declared_files=1, declared_size_bytes=10)
        create_upload_batch_presign(user=user, module_type="company_media", target_type="album", target_id=1,
                                    selection_session_id=selection["selection_session_id"], files=[_media_file("one", size=10)], provider=FakeStorageProvider())
        with pytest.raises(StorageUploadContractError) as count:
            create_upload_batch_presign(user=user, module_type="company_media", target_type="album", target_id=1,
                                        selection_session_id=selection["selection_session_id"], files=[_media_file("two", size=1)], provider=FakeStorageProvider())
        assert count.value.code == "selection_declared_file_quota_exceeded"
        assert count.value.status_code == 409

        selection = create_upload_selection_session(user=user, module_type="company_media", target_type="album", target_id=1,
                                                    declared_files=2, declared_size_bytes=10)
        create_upload_batch_presign(user=user, module_type="company_media", target_type="album", target_id=1,
                                    selection_session_id=selection["selection_session_id"], files=[_media_file("three", size=10)], provider=FakeStorageProvider())
        with pytest.raises(StorageUploadContractError) as bytes_exceeded:
            create_upload_batch_presign(user=user, module_type="company_media", target_type="album", target_id=1,
                                        selection_session_id=selection["selection_session_id"], files=[_media_file("four", size=1)], provider=FakeStorageProvider())
        assert bytes_exceeded.value.code == "selection_declared_byte_quota_exceeded"
        assert bytes_exceeded.value.status_code == 409


def test_company_media_upload_routes_return_structured_errors_and_template_limits(client, app):
    album_id = _album(app)
    _login(client)
    app.config.update(COMPANY_MEDIA_MAX_FILES_PER_BATCH=7, COMPANY_MEDIA_UPLOAD_CONCURRENCY=2)
    page = client.get(f"/company-media/albums/{album_id}")
    assert page.status_code == 200
    assert b'data-company-media-upload-limits=' in page.data
    assert b'"max_files_per_batch": 7' in page.data
    assert b'"upload_concurrency": 2' in page.data
    assert b"2 GiB" in page.data
    assert b"50 MiB" in page.data
    assert b"300 MiB" in page.data
    for marker in (
        b"data-company-media-upload-summary", b"data-selected-count", b"data-selected-max",
        b"data-selected-bytes", b"data-selected-bytes-max", b"data-valid-count",
        b"data-blocked-count", b"data-batch-estimate", b"data-upload-validation-message",
        b"data-upload-selection-status",
        b"data-company-media-upload-queue", b"data-company-media-start-upload",
        b"data-company-media-upload-overlay",
    ):
        assert marker in page.data
    assert b'aria-live="polite"' in page.data
    assert b'role="alert"' in page.data
    assert b"STORAGE_ACCESS_KEY" not in page.data
    assert b"STORAGE_SECRET" not in page.data
    assert b"company-media-upload.js?v=20260730-8404" in page.data

    selection = client.post(f"/company-media/albums/{album_id}/files/upload-selection-sessions", json={"file_count": 501, "total_size_bytes": 1})
    assert selection.status_code == 422
    assert selection.get_json() == {
        "ok": False,
        "error": {"code": "selection_file_count_exceeded", "message": "Bạn đã chọn 501 tệp, tối đa 500 tệp mỗi lần tải.",
                  "details": {"actual_files": 501, "max_files": 500}, "retryable": False},
    }
    batch = client.post(f"/company-media/albums/{album_id}/files/presign-batch", json={"files": []})
    assert batch.status_code == 422
    assert batch.get_json()["error"]["code"] == "empty_presign_batch"

    valid_session = client.post(
        f"/company-media/albums/{album_id}/files/upload-selection-sessions",
        json={"file_count": 1, "total_size_bytes": 1},
    ).get_json()["selection_session_id"]
    with app.app_context():
        db.session.get(UploadSelectionSession, valid_session).expires_at = datetime.utcnow() - timedelta(seconds=1)
        db.session.commit()
    expired = client.post(
        f"/company-media/albums/{album_id}/files/presign-batch",
        json={"selection_session_id": valid_session, "files": [_media_file()]},
    )
    assert expired.status_code == 410
    assert expired.get_json()["error"] == {
        "code": "selection_session_expired", "message": "Phiên tải đã hết hạn hoặc đã hoàn tất.",
        "details": {}, "retryable": False,
    }


def test_company_media_expired_and_target_mismatch_sessions_are_safe(app):
    with app.app_context():
        user = db.session.get(User, 6)
        session = create_upload_selection_session(user=user, module_type="company_media", target_type="album", target_id=1,
                                                  declared_files=1, declared_size_bytes=1)
        row = db.session.get(UploadSelectionSession, session["selection_session_id"])
        row.expires_at = datetime.utcnow() - timedelta(seconds=1)
        db.session.commit()
        with pytest.raises(StorageUploadContractError) as expired:
            create_upload_batch_presign(user=user, module_type="company_media", target_type="album", target_id=1,
                                        selection_session_id=row.id, files=[_media_file()], provider=FakeStorageProvider())
        assert expired.value.code == "selection_session_expired" and expired.value.status_code == 410

        with pytest.raises(StorageUploadContractError) as mismatch:
            create_upload_batch_presign(user=user, module_type="company_media", target_type="album", target_id=2,
                                        selection_session_id=row.id, files=[_media_file()], provider=FakeStorageProvider())
        assert mismatch.value.code == "selection_session_target_mismatch"
        assert mismatch.value.details == {}
