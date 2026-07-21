from app.company_media.services import set_permission
from app.extensions import db
from app.models import (CompanyMediaAlbum, CompanyMediaFile, Permission, RolePermission,
                        StorageObject, User)


def _login(client, username):
    return client.post("/login", data={"username_or_email": username, "password": "password123"})


def _album(name, restricted=True):
    album = CompanyMediaAlbum(name=name, is_restricted=restricted, created_by_id=6)
    db.session.add(album)
    db.session.commit()
    return album


def _grant(role_id, *codes):
    for permission in Permission.query.filter(Permission.code.in_(codes)).all():
        db.session.add(RolePermission(role_id=role_id, permission_id=permission.id))
    db.session.commit()


def _media(album):
    storage = StorageObject(bucket="test", object_key=f"switch/{album.id}.png",
        original_filename="switch.png", mime_type="image/png", file_ext="png", file_size=1,
        uploaded_by_id=6, upload_status="active", processing_status="none")
    db.session.add(storage)
    db.session.flush()
    media = CompanyMediaFile(album_id=album.id, storage_object_id=storage.id,
        display_name="switch.png", media_type="image", created_by_id=6)
    db.session.add(media)
    db.session.commit()
    return media


def test_module_switch_is_always_visible_for_authenticated_user(client):
    _login(client, "reporter")
    page = client.get("/modules/")
    assert page.status_code == 200
    assert "Chọn phân hệ".encode() in page.data
    assert "Đổi phân hệ".encode() in page.data


def test_company_media_card_requires_global_access_or_album_acl(client, app):
    with app.app_context():
        album = _album("Album được chia sẻ")
        admin, reporter = db.session.get(User, 6), db.session.get(User, 3)
        album_id = album.id
    _login(client, "reporter")
    page = client.get("/modules/")
    assert b'data-module-card="company_media"' not in page.data
    client.post("/logout")
    with app.app_context():
        set_permission(db.session.get(User, 6), db.session.get(CompanyMediaAlbum, album_id), "user", 3, {"can_view": "1"})
    _login(client, "reporter")
    page = client.get("/modules/")
    assert b'data-module-card="company_media"' in page.data
    assert client.get("/company-media/").status_code == 200
    assert "Album được chia sẻ".encode() in client.get("/company-media/").data


def test_company_media_role_acl_is_visible_and_allows_album_detail(client, app):
    with app.app_context():
        album = _album("Album role")
        admin, reporter = db.session.get(User, 6), db.session.get(User, 3)
        set_permission(admin, album, "role", reporter.role_id, {"can_view": "1"})
        album_id = album.id
    _login(client, "reporter")
    assert b'data-module-card="company_media"' in client.get("/modules/").data
    assert client.get(f"/company-media/albums/{album_id}").status_code == 200


def test_company_media_index_unions_global_view_and_acl_without_leak(client, app):
    with app.app_context():
        visible = _album("Album công khai", restricted=False)
        shared = _album("Album hạn chế được share")
        hidden = _album("Album hạn chế ẩn")
        admin, reporter = db.session.get(User, 6), db.session.get(User, 3)
        _grant(reporter.role_id, "modules.company_media.access", "company_media_albums.view")
        set_permission(admin, shared, "user", reporter.id, {"can_view": "1"})
        set_permission(admin, visible, "user", reporter.id, {"can_view": "1"})
    _login(client, "reporter")
    page = client.get("/company-media/")
    assert page.status_code == 200
    assert "Album công khai".encode() in page.data
    assert "Album hạn chế được share".encode() in page.data
    assert "Album hạn chế ẩn".encode() not in page.data


def test_shared_album_preview_and_download_follow_separate_acl_flags(client, app):
    with app.app_context():
        album = _album("Album preview")
        media = _media(album)
        admin, reporter = db.session.get(User, 6), db.session.get(User, 3)
        set_permission(admin, album, "user", reporter.id, {"can_view": "1"})
        album_id = album.id
        media_id = media.id
    _login(client, "reporter")
    assert client.post(f"/company-media/files/{media_id}/signed-preview", json={}).status_code == 200
    assert client.post(f"/company-media/files/{media_id}/signed-download", json={}).status_code == 403
    client.post("/logout")
    with app.app_context():
        set_permission(db.session.get(User, 6), db.session.get(CompanyMediaAlbum, album_id), "user", 3,
                       {"can_view": "1", "can_download": "1"})
    _login(client, "reporter")
    assert client.post(f"/company-media/files/{media_id}/signed-download", json={}).status_code == 200
