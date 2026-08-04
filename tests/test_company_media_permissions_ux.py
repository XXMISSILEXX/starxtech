import pytest

from app.company_media import permissions as album_permissions
from app.company_media.services import CompanyMediaError, set_permission
from app.extensions import db
from app.models import (AuditLog, CompanyMediaAlbum, CompanyMediaAlbumPermission, CompanyMediaFile,
                        Permission, Role, RolePermission, StorageObject, User)
from app.storage.providers import FakeStorageProvider
from app.storage.exceptions import StorageUploadContractError, StorageValidationError
from app.storage.services import create_upload_selection_session, finalize_upload_selection_session


def _album(app):
    with app.app_context():
        album = CompanyMediaAlbum(name="Ảnh công trường", is_restricted=True, created_by_id=6)
        db.session.add(album)
        db.session.commit()
        return album.id


def _login(client, username):
    return client.post("/login", data={"username_or_email": username, "password": "password123"})


def _grant_role_codes(role_id, codes):
    for permission in Permission.query.filter(Permission.code.in_(codes)).all():
        db.session.add(RolePermission(role_id=role_id, permission_id=permission.id))


def _media(album, user_id=6):
    storage = StorageObject(bucket="test", object_key=f"company-media/{album.id}.png",
        original_filename="album.png", mime_type="image/png", file_ext="png", file_size=1,
        uploaded_by_id=user_id, upload_status="active", processing_status="none")
    db.session.add(storage)
    db.session.flush()
    media = CompanyMediaFile(album_id=album.id, storage_object_id=storage.id,
        display_name="album.png", media_type="image", created_by_id=user_id)
    db.session.add(media)
    db.session.commit()
    return media


def test_permissions_page_has_picker_presets_and_six_flag_table(client, app):
    album_id = _album(app)
    _login(client, "admin")
    page = client.get(f"/company-media/albums/{album_id}/permissions")
    assert page.status_code == 200
    for text in ("Thư viện media", "Chia sẻ album:", "principalSearch", "Người nhận quyền",
                 "Chỉ xem", "Xem + tải xuống", "Cộng tác viên", "Quản lý album", "Tùy chỉnh",
                 "Tải xuống", "Quyền truy cập trực tiếp"):
        assert text.encode() in page.data
    assert b"company-media-permissions.js" in page.data
    assert b'placeholder="ID"' not in page.data
    assert b"document-permissions-table" in page.data


def test_album_acl_validates_principal_flags_and_updates_in_place(app):
    with app.app_context():
        admin, reporter = db.session.get(User, 6), db.session.get(User, 3)
        album = CompanyMediaAlbum(name="Album ACL", is_restricted=True, created_by_id=admin.id)
        db.session.add(album)
        db.session.commit()
        entry = set_permission(admin, album, "user", reporter.id, {"can_view": "1"})
        updated = set_permission(admin, album, "user", reporter.id, {"can_download": "1"})
        assert updated.id == entry.id
        assert not updated.can_view and updated.can_download
        assert CompanyMediaAlbumPermission.query.filter_by(album_id=album.id, user_id=reporter.id).count() == 1
        role = db.session.get(Role, reporter.role_id)
        role_entry = set_permission(admin, album, "role", role.id, {"can_view": "1", "can_upload": "1"})
        assert role_entry.role_id == role.id and role_entry.can_upload
        with pytest.raises(CompanyMediaError, match="ít nhất một quyền"):
            set_permission(admin, album, "user", reporter.id, {})
        with pytest.raises(CompanyMediaError, match="ngừng hoạt động"):
            set_permission(admin, album, "user", 4, {"can_view": "1"})
        with pytest.raises(CompanyMediaError, match="Vai trò không tồn tại"):
            set_permission(admin, album, "role", 9999, {"can_view": "1"})


def test_permissions_remove_is_post_only_and_requires_share(client, app):
    album_id = _album(app)
    with app.app_context():
        admin, reporter = db.session.get(User, 6), db.session.get(User, 3)
        album = db.session.get(CompanyMediaAlbum, album_id)
        entry = set_permission(admin, album, "user", reporter.id, {"can_view": "1"})
        entry_id = entry.id
    _login(client, "viewer")
    assert client.get(f"/company-media/albums/{album_id}/permissions").status_code == 403
    assert client.post(f"/company-media/albums/{album_id}/permissions", data={"remove_id": entry_id}).status_code == 403
    client.post("/logout")
    _login(client, "admin")
    assert client.get(f"/company-media/albums/{album_id}/permissions?remove_id={entry_id}").status_code == 200
    with app.app_context():
        assert db.session.get(CompanyMediaAlbumPermission, entry_id) is not None
    assert client.post(f"/company-media/albums/{album_id}/permissions", data={"remove_id": entry_id}).status_code == 302
    with app.app_context():
        assert db.session.get(CompanyMediaAlbumPermission, entry_id) is None


def test_restricted_album_accepts_matching_role_acl_and_viewer_read_bypass(app):
    with app.app_context():
        admin, reporter, viewer = (db.session.get(User, 6), db.session.get(User, 3),
                                   db.session.get(User, 2))
        album = CompanyMediaAlbum(name="Album theo vai trò", is_restricted=True, created_by_id=admin.id)
        db.session.add(album)
        codes = {"modules.company_media.access", "company_media_albums.view",
                 "company_media_albums.share", "company_media_files.upload"}
        _grant_role_codes(reporter.role_id, codes)
        db.session.commit()
        set_permission(admin, album, "role", reporter.role_id,
                       {"can_view": "1", "can_upload": "1", "can_share": "1"})
        assert album_permissions.view_album(reporter, album)
        assert album_permissions.upload_album(reporter, album)
        assert album_permissions.share_album(reporter, album)
        assert album_permissions.view_album(viewer, album)


def test_viewer_can_read_restricted_album_and_media_but_cannot_mutate(client, app):
    album_id = _album(app)
    with app.app_context():
        album, admin, reporter = (db.session.get(CompanyMediaAlbum, album_id), db.session.get(User, 6),
                                  db.session.get(User, 3))
        media_id = _media(album).id
        acl_id = set_permission(admin, album, "user", reporter.id, {"can_view": "1"}).id
    _login(client, "viewer")
    assert client.get("/company-media/").status_code == 200
    assert client.get(f"/company-media/albums/{album_id}").status_code == 200
    assert client.post(f"/company-media/files/{media_id}/signed-preview", json={}).status_code == 200
    assert client.post(f"/company-media/files/{media_id}/signed-download", json={}).status_code == 200
    assert client.post("/company-media/albums/create", data={"name": "Không được tạo"}).status_code == 403
    for path, data in (
        (f"/company-media/albums/{album_id}/rename", {"name": "Không được đổi"}),
        (f"/company-media/albums/{album_id}/archive", {}),
        (f"/company-media/albums/{album_id}/restore", {}),
        (f"/company-media/albums/{album_id}/cover", {"media_id": media_id}),
        (f"/company-media/albums/{album_id}/cover/clear", {}),
        (f"/company-media/albums/{album_id}/permissions", {"principal_type": "user", "principal_id": 3, "can_view": "1"}),
        (f"/company-media/albums/{album_id}/permissions", {"remove_id": acl_id}),
        (f"/company-media/files/{media_id}/rename", {"display_name": "Không được đổi.png"}),
        (f"/company-media/files/{media_id}/archive", {}),
        (f"/company-media/files/{media_id}/restore", {}),
        (f"/company-media/albums/{album_id}/files/presign-batch", {}),
        (f"/company-media/albums/{album_id}/files/complete-upload", {"upload_batch_item_id": 1}),
    ):
        assert client.post(path, data=data).status_code == 403


def test_normal_user_requires_acl_to_read_restricted_album_and_can_upload_with_acl(client, app):
    album_id = _album(app)
    upload_payload = {
        "files": [{"client_file_id": "acl-upload", "filename": "acl-upload.png",
                   "mime_type": "image/png", "size": 1}],
    }
    with app.app_context():
        admin, reporter = db.session.get(User, 6), db.session.get(User, 3)
        admin_id, reporter_id, reporter_role_id = admin.id, reporter.id, reporter.role_id
        codes = {"modules.company_media.access", "company_media_albums.view", "company_media_files.view",
                 "company_media_files.upload"}
        _grant_role_codes(reporter_role_id, codes)
        db.session.commit()
    _login(client, "reporter")
    assert client.get(f"/company-media/albums/{album_id}").status_code == 403
    client.post("/logout")
    with app.app_context():
        album = db.session.get(CompanyMediaAlbum, album_id)
        admin = db.session.get(User, admin_id)
        set_permission(admin, album, "user", reporter_id, {"can_view": "1"})
    _login(client, "reporter")
    assert client.post(f"/company-media/albums/{album_id}/files/presign-batch", json=upload_payload).status_code == 403
    client.post("/logout")
    with app.app_context():
        album = db.session.get(CompanyMediaAlbum, album_id)
        admin = db.session.get(User, admin_id)
        set_permission(admin, album, "user", reporter_id, {"can_view": "1", "can_upload": "1"})
    _login(client, "reporter")
    assert client.get(f"/company-media/albums/{album_id}").status_code == 200
    assert client.post(f"/company-media/albums/{album_id}/files/presign-batch", json=upload_payload).status_code == 200
    assert client.post(f"/company-media/albums/{album_id}/files/presign-batch", json={"files": []}).status_code == 422


def test_company_media_upload_page_has_persistent_result_overlay(client, app):
    album_id = _album(app)
    _login(client, "admin")
    page = client.get(f"/company-media/albums/{album_id}")
    assert page.status_code == 200
    assert b"data-company-media-upload" in page.data
    assert b"data-company-media-upload-overlay" in page.data
    assert "Thử lại file lỗi".encode() in page.data
    assert "Bị chặn".encode() in page.data
    assert b"company-media-upload.js" in page.data
    assert b"project-document-upload.js" not in page.data


def test_company_media_batch_keeps_client_ids_and_finalizes_partial_success(app, monkeypatch):
    from app.company_media import services as media_services

    with app.app_context():
        admin = db.session.get(User, 6)
        album = CompanyMediaAlbum(name="Album direct upload", created_by_id=admin.id)
        db.session.add(album)
        db.session.commit()
        provider = FakeStorageProvider()
        app.extensions["storage_provider"] = provider
        selection = create_upload_selection_session(
            user=admin, module_type="company_media", target_type="album", target_id=album.id,
            declared_files=3, declared_size_bytes=12,
        )
        batch = media_services.presign(admin, album, [
            {"client_file_id": "same-name-a", "filename": "trung-ten.jpg", "mime_type": "image/jpeg", "size": 5},
            {"client_file_id": "same-name-b", "filename": "trung-ten.jpg", "mime_type": "image/jpeg", "size": 6},
            {"client_file_id": "blocked", "filename": "unsafe.exe", "mime_type": "application/octet-stream", "size": 1},
        ], selection["selection_session_id"])
        by_id = {item["client_file_id"]: item for item in batch["items"]}
        assert by_id["same-name-a"]["accepted"] is True
        assert by_id["same-name-b"]["accepted"] is True
        assert by_id["blocked"]["accepted"] is False
        first = by_id["same-name-a"]
        storage = db.session.get(StorageObject, first["storage_object_id"])
        provider.register_object(storage.bucket, storage.object_key, 5, "image/jpeg")
        before_audits = AuditLog.query.count()
        enqueued = []
        monkeypatch.setattr("app.media_processing.services.enqueue_media_processing_for_storage_object", enqueued.append)
        complete = media_services.complete(admin, album, first["upload_batch_item_id"], {})
        assert complete["file"]["display_name"] == "trung-ten.jpg"
        assert media_services.complete(admin, album, first["upload_batch_item_id"], {})["idempotent"] is True
        assert enqueued == [storage.id]
        result = finalize_upload_selection_session(
            user=admin, selection_session_id=selection["selection_session_id"], module_type="company_media", target_type="album", target_id=album.id,
            failed_upload_batch_item_ids=[by_id["same-name-b"]["upload_batch_item_id"]],
        )
        assert result["succeeded_files"] == 1 and result["failed_files"] == 2
        assert CompanyMediaFile.query.filter_by(album_id=album.id).count() == 1
        assert AuditLog.query.count() == before_audits


def test_company_media_does_not_enqueue_derivative_when_head_validation_fails(app, monkeypatch):
    from app.company_media import services as media_services

    with app.app_context():
        admin = db.session.get(User, 6)
        album = CompanyMediaAlbum(name="Album invalid object", created_by_id=admin.id)
        db.session.add(album)
        db.session.commit()
        provider = FakeStorageProvider()
        app.extensions["storage_provider"] = provider
        batch = media_services.presign(admin, album, [
            {"client_file_id": "wrong-size", "filename": "wrong-size.jpg", "mime_type": "image/jpeg", "size": 5},
        ])
        item = batch["items"][0]
        storage = db.session.get(StorageObject, item["storage_object_id"])
        provider.register_object(storage.bucket, storage.object_key, 4, "image/jpeg")
        enqueued = []
        monkeypatch.setattr("app.media_processing.services.enqueue_media_processing_for_storage_object", enqueued.append)
        with pytest.raises(StorageUploadContractError, match="Không thể xác minh") as exc_info:
            media_services.complete(admin, album, item["upload_batch_item_id"], {})
        assert exc_info.value.code == "head_verification_failed"
        assert enqueued == []
        assert CompanyMediaFile.query.filter_by(album_id=album.id).count() == 0
