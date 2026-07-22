from app.extensions import db
from app.models import ProjectDocumentFolder


def login(client, username):
    return client.post("/login", data={"username_or_email": username, "password": "password123"})


def test_document_library_groups_and_super_admin_can_create_custom_root(client, app):
    login(client, "super")
    response = client.get("/project-documents/")
    assert response.status_code == 200
    assert "Hồ sơ theo dự án".encode() in response.data
    assert "Hồ sơ khác".encode() in response.data
    response = client.post("/project-documents/custom-roots", data={"name": "Hành chính", "description": "Nội bộ"})
    assert response.status_code == 302
    with app.app_context():
        root = ProjectDocumentFolder.query.filter_by(name="Hành chính", root_type="custom").one()
        assert root.project_id is None and root.is_root


def test_new_project_creates_project_document_root(client, app):
    login(client, "super")
    response = client.post("/admin/projects/new", data={"code": "P003", "name": "New project", "status": "active"})
    assert response.status_code == 302
    with app.app_context():
        root = ProjectDocumentFolder.query.filter_by(project_id=3, is_root=True).one()
        assert root.root_type == "project"
