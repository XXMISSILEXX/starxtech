from app.extensions import db
from app.models import Project, User
from app.project_documents.services import archive_folder, create_folder, get_or_create_project_root_folder


def _login(client, username):
    return client.post("/login", data={"username_or_email": username, "password": "password123"})


def test_folder_filters_use_folder_status_and_keep_file_filter(client, app):
    with app.app_context():
        admin = db.session.get(User, 6)
        root = get_or_create_project_root_folder(db.session.get(Project, 1), admin)
        active = create_folder(admin, root, "Filter Active Folder")
        archived = create_folder(admin, root, "Filter Archived Folder")
        archive_folder(admin, archived)
        root_id, active_name, archived_name = root.id, active.name, archived.name
    _login(client, "admin")
    active_page = client.get(f"/project-documents/folders/{root_id}?folder_status=active&file_status=archived")
    archived_page = client.get(f"/project-documents/folders/{root_id}?folder_status=archived&file_status=active")
    assert active_name.encode() in active_page.data and archived_name.encode() not in active_page.data
    assert archived_name.encode() in archived_page.data and active_name.encode() not in archived_page.data
    assert b'name="folder_status"' in active_page.data and b'name="status"' not in active_page.data


def test_archive_and_restore_keep_context_and_render_lifecycle_actions(client, app):
    with app.app_context():
        admin = db.session.get(User, 6)
        root = get_or_create_project_root_folder(db.session.get(Project, 1), admin)
        folder = create_folder(admin, root, "Lifecycle")
        root_id, folder_id = root.id, folder.id
    _login(client, "admin")
    context = {"q": "Lifecycle", "folder_status": "all", "file_status": "archived"}
    response = client.post(f"/project-documents/folders/{folder_id}/archive", data=context)
    assert response.status_code == 302
    assert f"/project-documents/folders/{root_id}?q=Lifecycle&folder_status=active&file_status=archived" in response.headers["Location"]
    archived_page = client.get(f"/project-documents/folders/{root_id}?folder_status=archived")
    assert "Đã lưu trữ".encode() in archived_page.data and "Khôi phục".encode() in archived_page.data
    response = client.post(f"/project-documents/folders/{folder_id}/restore", data=context)
    assert response.status_code == 302
    assert f"/project-documents/folders/{root_id}?q=Lifecycle&folder_status=active&file_status=archived" in response.headers["Location"]
