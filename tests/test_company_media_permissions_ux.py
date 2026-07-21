import pytest

from app.company_media import permissions as album_permissions
from app.company_media.services import CompanyMediaError, set_permission
from app.extensions import db
from app.models import (CompanyMediaAlbum, CompanyMediaAlbumPermission, CompanyMediaFile,
                        Permission, Role, RolePermission, StorageObject, User)


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
    with app.app_context():
        admin, reporter = db.session.get(User, 6), db.session.get(User, 3)
        codes = {"modules.company_media.access", "company_media_albums.view", "company_media_files.view",
                 "company_media_files.upload"}
        _grant_role_codes(reporter.role_id, codes)
        db.session.commit()
    _login(client, "reporter")
    assert client.get(f"/company-media/albums/{album_id}").status_code == 403
    client.post("/logout")
    with app.app_context():
        album = db.session.get(CompanyMediaAlbum, album_id)
        set_permission(admin, album, "user", reporter.id, {"can_view": "1", "can_upload": "1"})
    _login(client, "reporter")
    assert client.get(f"/company-media/albums/{album_id}").status_code == 200
    assert client.post(f"/company-media/albums/{album_id}/files/presign-batch", json={"files": []}).status_code == 200
