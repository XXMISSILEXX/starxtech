import pytest

from app.extensions import db
from app.models import Project, ProjectDocumentFolder, ProjectDocumentFolderPermission, User
from app.project_documents.services import (DocumentValidationError, get_or_create_project_root_folder,
    remove_folder_permission, set_folder_permission)


def _root(app):
    with app.app_context():
        admin = db.session.get(User, 6)
        return get_or_create_project_root_folder(db.session.get(Project, 1), admin).id


def _login(client, username):
    return client.post("/login", data={"username_or_email": username, "password": "password123"})


def test_permissions_page_has_selector_presets_and_acl_table(client, app):
    root_id = _root(app)
    _login(client, "admin")
    page = client.get(f"/project-documents/folders/{root_id}/permissions")
    assert page.status_code == 200
    for text in ("Chia sẻ thư mục:", "principalSearch", "Người nhận quyền", "Chỉ xem + tải xuống",
                 "Cộng tác viên", "Quản lý thư mục", "Tùy chỉnh", "Quyền truy cập trực tiếp"):
        assert text.encode() in page.data
    assert b'project-document-permissions.js' in page.data
    assert 'placeholder="ID người dùng/vai trò"'.encode() not in page.data


def test_permissions_page_renders_existing_acl_flags(client, app):
    with app.app_context():
        admin, reporter = db.session.get(User, 6), db.session.get(User, 3)
        root = get_or_create_project_root_folder(db.session.get(Project, 1), admin)
        set_folder_permission(admin, root, "user", reporter.id, {"can_view": "1", "can_share": "1"})
        root_id = root.id
    _login(client, "admin")
    page = client.get(f"/project-documents/folders/{root_id}/permissions")
    assert "Người dùng/Vai trò".encode() in page.data
    assert b'data-can-view="1"' in page.data and b'data-can-share="1"' in page.data
    assert b'data-can-upload="0"' in page.data


def test_folder_acl_validates_principal_flags_and_updates_in_place(app):
    with app.app_context():
        admin, reporter = db.session.get(User, 6), db.session.get(User, 3)
        root = get_or_create_project_root_folder(db.session.get(Project, 1), admin)
        entry = set_folder_permission(admin, root, "user", reporter.id, {"can_view": "1"})
        updated = set_folder_permission(admin, root, "user", reporter.id, {"can_edit": "1"})
        assert entry.id == updated.id
        assert not updated.can_view and updated.can_edit
        assert ProjectDocumentFolderPermission.query.filter_by(folder_id=root.id, user_id=reporter.id).count() == 1
        with pytest.raises(DocumentValidationError, match="ít nhất một quyền"):
            set_folder_permission(admin, root, "user", reporter.id, {})
        with pytest.raises(DocumentValidationError, match="ngừng hoạt động"):
            set_folder_permission(admin, root, "user", 4, {"can_view": "1"})
        with pytest.raises(DocumentValidationError, match="Vai trò không tồn tại"):
            set_folder_permission(admin, root, "role", 9999, {"can_view": "1"})
        remove_folder_permission(admin, root, entry.id)
        assert db.session.get(ProjectDocumentFolderPermission, entry.id) is None


def test_permissions_route_requires_share_and_remove_is_post_only(client, app):
    root_id = _root(app)
    with app.app_context():
        admin, reporter = db.session.get(User, 6), db.session.get(User, 3)
        entry = set_folder_permission(admin, db.session.get(ProjectDocumentFolder, root_id), "user", reporter.id, {"can_view": "1"})
        entry_id = entry.id
    _login(client, "viewer")
    assert client.get(f"/project-documents/folders/{root_id}/permissions").status_code == 403
    assert client.post(f"/project-documents/folders/{root_id}/permissions", data={"remove_id": entry_id}).status_code == 403
    client.post("/logout")
    _login(client, "admin")
    assert client.get(f"/project-documents/folders/{root_id}/permissions?remove_id={entry_id}").status_code == 200
    with app.app_context():
        assert db.session.get(ProjectDocumentFolderPermission, entry_id) is not None
    response = client.post(f"/project-documents/folders/{root_id}/permissions", data={"remove_id": entry_id})
    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(ProjectDocumentFolderPermission, entry_id) is None
    response = client.post(f"/project-documents/folders/{root_id}/permissions", data={"remove_id": 99999}, follow_redirects=True)
    assert response.status_code == 200
    assert "Không tìm thấy quyền chia sẻ.".encode() in response.data
