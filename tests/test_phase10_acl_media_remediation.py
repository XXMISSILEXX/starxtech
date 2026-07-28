from werkzeug.datastructures import MultiDict

import pytest

from app.company_media.services import CompanyMediaError, remove_permission, set_permission
from app.extensions import db
from app.models import (CompanyMediaAlbum, CompanyMediaAlbumPermission, CompanyMediaFile,
                        Project, ProjectDocumentFolder, ProjectDocumentFolderPermission,
                        ProjectUser, Role, StorageDerivative, StorageObject, User)
from app.project_documents.services import (DocumentValidationError, create_folder,
    get_or_create_project_root_folder, set_folder_permission)
from app.storage.providers import FakeStorageProvider


def _login(client, username):
    return client.post("/login", data={"username_or_email": username, "password": "password123"})


def _company_album(app):
    with app.app_context():
        admin = db.session.get(User, 6)
        album = CompanyMediaAlbum(name="Phase 10 ACL", is_restricted=True, created_by_id=admin.id)
        db.session.add(album)
        db.session.commit()
        return album.id


def _enable_document_sharing(app):
    with app.app_context():
        membership = ProjectUser.query.filter_by(project_id=1, user_id=3).one()
        membership.can_share_documents = True
        membership.can_upload_documents = True
        membership.can_edit_documents = True
        membership.can_archive_documents = True
        db.session.commit()


def _restricted_folder(app):
    _enable_document_sharing(app)
    with app.app_context():
        admin = db.session.get(User, 6)
        root = get_or_create_project_root_folder(db.session.get(Project, 1), admin)
        folder = create_folder(admin, root, "Phase 10 restricted", is_restricted=True)
        set_folder_permission(admin, folder, "user", 3, {"can_share": "1"})
        return folder.id


def _acl_flags(entry, flags):
    return {flag: getattr(entry, flag) for flag in flags}


def test_company_media_share_only_ceiling_covers_self_user_role_and_atomic_rejections(client, app):
    album_id = _company_album(app)
    with app.app_context():
        admin, actor, target = (db.session.get(User, 6), db.session.get(User, 3), db.session.get(User, 5))
        album = db.session.get(CompanyMediaAlbum, album_id)
        own = set_permission(admin, album, "user", actor.id, {"can_share": "1"})
        own_before = _acl_flags(own, ("can_view", "can_upload", "can_edit", "can_delete", "can_download", "can_share"))
        with pytest.raises(CompanyMediaError, match="vượt quá"):
            set_permission(actor, album, "user", actor.id, {"can_share": "1", "can_edit": "1"})
        assert _acl_flags(own, own_before) == own_before
        with pytest.raises(CompanyMediaError, match="phân quyền không hợp lệ"):
            set_permission(actor, album, "user", target.id, {"can_download": "1"})
        with pytest.raises(CompanyMediaError, match="phân quyền không hợp lệ"):
            set_permission(actor, album, "role", target.role_id, {"can_upload": "1"})
        with pytest.raises(CompanyMediaError, match="phân quyền không hợp lệ"):
            set_permission(actor, album, "user", target.id, {"can_share": "1"})
        assert CompanyMediaAlbumPermission.query.filter_by(album_id=album.id, user_id=target.id).count() == 0
        with pytest.raises(CompanyMediaError, match="phân quyền không hợp lệ"):
            set_permission(actor, album, "user", "", {"can_share": "1"})
        with pytest.raises(CompanyMediaError, match="phân quyền không hợp lệ"):
            set_permission(actor, album, "role", "99999", {"can_share": "1"})

    _login(client, "reporter")
    response = client.post(
        f"/company-media/albums/{album_id}/permissions",
        data={"principal_type": "user", "principal_id": "3", "can_share": "1", "can_delete": "1"},
    )
    assert response.status_code == 400
    with app.app_context():
        own = CompanyMediaAlbumPermission.query.filter_by(album_id=album_id, user_id=3).one()
        assert _acl_flags(own, own_before) == own_before


def test_company_media_admin_keeps_legitimate_management_and_acl_bounds_module_access(app):
    album_id = _company_album(app)
    with app.app_context():
        admin, actor, target = (db.session.get(User, 6), db.session.get(User, 3), db.session.get(User, 5))
        album = db.session.get(CompanyMediaAlbum, album_id)
        created = set_permission(admin, album, "user", actor.id, {"can_share": "1"})
        updated = set_permission(admin, album, "user", target.id, {
            "can_view": "1", "can_upload": "1", "can_edit": "1", "can_delete": "1",
            "can_download": "1", "can_share": "1",
        })
        assert created.id and all(getattr(updated, flag) for flag in (
            "can_view", "can_upload", "can_edit", "can_delete", "can_download", "can_share"))
        from app.company_media.permissions import effective_album_capabilities
        assert effective_album_capabilities(actor, album) == frozenset({"can_share"})


def test_project_document_ceiling_covers_self_role_inheritance_and_atomic_rejections(app):
    folder_id = _restricted_folder(app)
    with app.app_context():
        admin, actor, target = (db.session.get(User, 6), db.session.get(User, 3), db.session.get(User, 5))
        folder = db.session.get(ProjectDocumentFolder, folder_id)
        own = ProjectDocumentFolderPermission.query.filter_by(folder_id=folder.id, user_id=actor.id).one()
        own_before = _acl_flags(own, ("can_view", "can_upload", "can_edit", "can_delete", "can_share"))
        with pytest.raises(DocumentValidationError, match="vượt quá"):
            set_folder_permission(actor, folder, "user", actor.id, {"can_share": "1", "can_edit": "1"})
        with pytest.raises(DocumentValidationError, match="vượt quá"):
            set_folder_permission(actor, folder, "role", target.role_id, {"can_upload": "1"})
        delegated = set_folder_permission(actor, folder, "user", target.id, {"can_share": "1"})
        assert delegated.can_share and not delegated.can_edit
        child = create_folder(admin, folder, "Inherited child")
        with pytest.raises(DocumentValidationError, match="vượt quá"):
            set_folder_permission(actor, child, "user", target.id, {"can_edit": "1"})
        with pytest.raises(DocumentValidationError):
            set_folder_permission(actor, folder, "user", target.id,
                                  MultiDict([("can_share", "1"), ("can_share", "0")]))
        assert _acl_flags(own, own_before) == own_before
        assert ProjectDocumentFolderPermission.query.filter_by(folder_id=folder.id, user_id=target.id).one().can_share


def test_project_document_owner_and_super_admin_can_share_legitimately(app):
    with app.app_context():
        owner, super_admin, reporter = (db.session.get(User, 5), db.session.get(User, 1), db.session.get(User, 3))
        root = get_or_create_project_root_folder(db.session.get(Project, 1), owner)
        owner_entry = set_folder_permission(owner, root, "user", reporter.id, {"can_view": "1", "can_share": "1"})
        super_entry = set_folder_permission(super_admin, root, "role", reporter.role_id,
                                           {"can_view": "1", "can_upload": "1", "can_edit": "1"})
        assert owner_entry.can_share and super_entry.can_edit


def test_company_media_video_preview_never_returns_original_to_viewer(client, app):
    with app.app_context():
        provider = FakeStorageProvider()
        app.extensions["storage_provider"] = provider
        admin, viewer = db.session.get(User, 6), db.session.get(User, 3)
        album = CompanyMediaAlbum(name="Video preview", is_restricted=True, created_by_id=admin.id)
        db.session.add(album)
        db.session.flush()
        original = StorageObject(bucket="media", object_key="company-media/originals/secret.mp4",
            original_filename="secret.mp4", mime_type="video/mp4", file_ext="mp4", file_size=9,
            uploaded_by_id=admin.id, upload_status="active", processing_status="completed")
        db.session.add(original)
        db.session.flush()
        video = CompanyMediaFile(album_id=album.id, storage_object_id=original.id,
            display_name="secret.mp4", media_type="video", created_by_id=admin.id)
        image_object = StorageObject(bucket="media", object_key="company-media/originals/visible.png",
            original_filename="visible.png", mime_type="image/png", file_ext="png", file_size=4,
            uploaded_by_id=admin.id, upload_status="active", processing_status="completed")
        db.session.add(image_object)
        db.session.flush()
        image = CompanyMediaFile(album_id=album.id, storage_object_id=image_object.id,
            display_name="visible.png", media_type="image", created_by_id=admin.id)
        poster = StorageDerivative(storage_object_id=original.id, derivative_type="poster", bucket="media",
            object_key="company-media/derivatives/secret-poster.webp", mime_type="image/webp",
            file_ext="webp", file_size=1)
        thumbnail = StorageDerivative(storage_object_id=image_object.id, derivative_type="thumbnail", bucket="media",
            object_key="company-media/derivatives/visible-thumbnail.webp", mime_type="image/webp",
            file_ext="webp", file_size=1)
        missing_object = StorageObject(bucket="media", object_key="company-media/originals/no-poster.mp4",
            original_filename="no-poster.mp4", mime_type="video/mp4", file_ext="mp4", file_size=3,
            uploaded_by_id=admin.id, upload_status="active", processing_status="completed")
        db.session.add(missing_object)
        db.session.flush()
        missing = CompanyMediaFile(album_id=album.id, storage_object_id=missing_object.id,
            display_name="no-poster.mp4", media_type="video", created_by_id=admin.id)
        db.session.add_all([video, image, missing, poster, thumbnail])
        set_permission(admin, album, "user", viewer.id, {"can_view": "1"})
        db.session.commit()
        album_id, video_id, image_id, missing_id = album.id, video.id, image.id, missing.id

    _login(client, "reporter")
    for variant in (None, "preview", "stream", "original"):
        response = client.post(f"/company-media/files/{video_id}/signed-preview", json={"variant": variant})
        assert response.status_code == 200
        payload = response.get_json()
        assert payload["ok"] is True and "company-media/derivatives/secret-poster.webp" in payload["url"]
        assert "company-media/originals/secret.mp4" not in str(payload)
    image_preview = client.post(f"/company-media/files/{image_id}/signed-preview", json={})
    assert image_preview.status_code == 200
    assert "company-media/derivatives/visible-thumbnail.webp" in image_preview.get_json()["url"]
    unavailable = client.post(f"/company-media/files/{missing_id}/signed-preview", json={"variant": "stream"})
    assert unavailable.status_code == 200
    assert unavailable.get_json()["ok"] is False and "url" not in unavailable.get_json()
    assert client.post(f"/company-media/files/{video_id}/signed-download", json={}).status_code == 403
    assert client.post(f"/company-media/albums/{album_id}/files/bulk-signed-download", json={"file_ids": [video_id]}).status_code == 403

    client.post("/logout")
    with app.app_context():
        admin, album, viewer = db.session.get(User, 6), db.session.get(CompanyMediaAlbum, album_id), db.session.get(User, 3)
        set_permission(admin, album, "user", viewer.id, {"can_view": "1", "can_download": "1"})
    _login(client, "reporter")
    download = client.post(f"/company-media/files/{video_id}/signed-download", json={})
    assert download.status_code == 200
    assert "company-media/originals/secret.mp4" in download.get_json()["url"]
