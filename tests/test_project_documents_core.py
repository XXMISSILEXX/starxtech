import pytest

from app.extensions import db
from app.models import ProjectDocumentFolder, ProjectDocumentFolderPermission, User
from app.project_documents.permissions import can_create_project_document_folder, can_view_project_document_folder
from app.project_documents.services import (DocumentValidationError, archive_folder, create_folder, get_or_create_project_root_folder,
    list_folder_children, move_folder, restore_folder)


def _login(client, username):
    return client.post("/login", data={"username_or_email": username, "password": "password123"})


def test_root_is_lazy_and_project_manager_can_browse(app):
    with app.app_context():
        pm = db.session.get(User, 5)
        from app.models import Project
        root = get_or_create_project_root_folder(db.session.get(Project, 1), pm)
        assert root.is_root and root.parent_id is None
        assert get_or_create_project_root_folder(db.session.get(Project, 1), pm).id == root.id
        assert can_view_project_document_folder(pm, root)
        assert can_create_project_document_folder(pm, root)


def test_folder_tree_rejects_duplicate_and_cycle(app):
    with app.app_context():
        pm = db.session.get(User, 5)
        from app.models import Project
        root = get_or_create_project_root_folder(db.session.get(Project, 1), pm)
        one = create_folder(pm, root, "Hợp đồng")
        with pytest.raises(DocumentValidationError):
            create_folder(pm, root, "hợp đồng")
        child = create_folder(pm, one, "Phụ lục")
        with pytest.raises(DocumentValidationError):
            move_folder(pm, one, child)


def test_restricted_folder_requires_matching_acl(app):
    with app.app_context():
        pm, reporter = db.session.get(User, 5), db.session.get(User, 3)
        from app.models import Project
        root = get_or_create_project_root_folder(db.session.get(Project, 1), pm)
        restricted = create_folder(pm, root, "Nội bộ", is_restricted=True)
        assert not can_view_project_document_folder(reporter, restricted)
        db.session.add(ProjectDocumentFolderPermission(folder_id=restricted.id, principal_type="user", user_id=reporter.id, can_view=True, created_by_id=pm.id))
        db.session.commit()
        assert can_view_project_document_folder(reporter, restricted)


def test_move_rejects_root_cross_project_archived_parent_and_duplicate(app):
    with app.app_context():
        from app.models import Project
        admin = db.session.get(User, 6)
        root = get_or_create_project_root_folder(db.session.get(Project, 1), admin)
        other_root = get_or_create_project_root_folder(db.session.get(Project, 2), admin)
        source = create_folder(admin, root, "Nguồn")
        descendant = create_folder(admin, source, "Con")
        archived_parent = create_folder(admin, root, "Đã lưu trữ")
        archive_folder(admin, archived_parent)
        duplicate_parent = create_folder(admin, root, "Đích")
        create_folder(admin, duplicate_parent, "Nguồn")
        with pytest.raises(DocumentValidationError): move_folder(admin, root, duplicate_parent)
        with pytest.raises(DocumentValidationError): move_folder(admin, source, descendant)
        with pytest.raises(DocumentValidationError): move_folder(admin, source, other_root)
        with pytest.raises(DocumentValidationError): move_folder(admin, source, archived_parent)
        with pytest.raises(DocumentValidationError): move_folder(admin, source, duplicate_parent)


def test_archive_filter_restore_and_archived_parent_policy(app):
    with app.app_context():
        from app.models import Project
        admin = db.session.get(User, 6)
        root = get_or_create_project_root_folder(db.session.get(Project, 1), admin)
        parent = create_folder(admin, root, "Cha")
        child = create_folder(admin, parent, "Con")
        archive_folder(admin, child)
        assert child not in list_folder_children(admin, parent, "active")
        assert child in list_folder_children(admin, parent, "archived")
        restore_folder(admin, child)
        assert child in list_folder_children(admin, parent, "active")
        archive_folder(admin, child)
        archive_folder(admin, parent)
        with pytest.raises(DocumentValidationError, match="khôi phục thư mục cha"):
            restore_folder(admin, child)


def test_move_and_restore_routes_enforce_backend_permissions(client, app):
    with app.app_context():
        from app.models import Project
        admin = db.session.get(User, 6)
        root = get_or_create_project_root_folder(db.session.get(Project, 1), admin)
        source, destination = create_folder(admin, root, "Nguồn"), create_folder(admin, root, "Đích")
        archive_folder(admin, source)
        source_id, destination_id = source.id, destination.id
    _login(client, "reporter")
    assert client.post(f"/project-documents/folders/{source_id}/restore").status_code == 403
    assert client.post(f"/project-documents/folders/{source_id}/move", data={"parent_id": destination_id}).status_code == 403
    assert client.get(f"/project-documents/folders/{source_id}/move").status_code == 405


def test_viewer_admin_can_browse_any_project_including_lazy_root(client, app):
    response = _login(client, "viewer")
    assert response.status_code == 302
    response = client.get("/project-documents/projects/2")
    assert response.status_code == 302
    response = client.get(response.headers["Location"])
    assert response.status_code == 200
    assert "Hồ sơ dự án".encode() in response.data


def test_viewer_admin_is_read_only_and_can_view_restricted_folder(client, app):
    with app.app_context():
        from app.models import Project
        admin = db.session.get(User, 6)
        root = get_or_create_project_root_folder(db.session.get(Project, 1), admin)
        restricted = create_folder(admin, root, "Hạn chế", is_restricted=True)
        root_id, restricted_id = root.id, restricted.id
    _login(client, "viewer")
    response = client.get(f"/project-documents/folders/{root_id}")
    assert response.status_code == 200
    for label in ("Tạo thư mục", "Đổi tên", "Di chuyển", "Lưu trữ", "Chia sẻ"):
        assert label.encode() not in response.data
    assert client.get(f"/project-documents/folders/{restricted_id}").status_code == 200
    assert client.post("/project-documents/folders/new", data={"parent_id": root_id, "name": "Không được"}).status_code == 403
    assert client.post(f"/project-documents/folders/{restricted_id}/rename", data={"name": "Không được"}).status_code == 403
    assert client.post(f"/project-documents/folders/{restricted_id}/move", data={"parent_id": root_id}).status_code == 403
    assert client.post(f"/project-documents/folders/{restricted_id}/archive").status_code == 403
    assert client.post(f"/project-documents/folders/{restricted_id}/permissions").status_code == 403


def test_assigned_scope_and_restricted_acl_remain_for_project_roles(app):
    with app.app_context():
        from app.models import Project
        admin, pm, reporter = db.session.get(User, 6), db.session.get(User, 5), db.session.get(User, 3)
        other_root = get_or_create_project_root_folder(db.session.get(Project, 2), admin)
        assert not can_view_project_document_folder(pm, other_root)
        assert not can_view_project_document_folder(reporter, other_root)
