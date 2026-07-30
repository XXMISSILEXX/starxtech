import csv
import re
from datetime import date
from io import StringIO

from app.company_media import routes as media_routes
from app.company_media.services import set_permission
from app.csv_safety import safe_csv_cell
from app.extensions import db
from app.models import (AuditLog, Company, CompanyDepartment, CompanyMediaAlbum,
    CompanyMediaAlbumPermission, Partner, PartnerRelationship, Permission,
    Project, ProjectContractor, ProjectContractorAssignment, RolePermission,
    User)
from app.project_documents.services import find_project_root_folder
from tests.test_auth_permissions import login


def grant(app, username, *codes):
    with app.app_context():
        user = User.query.filter_by(username=username).one()
        permissions = Permission.query.filter(Permission.code.in_(codes)).all()
        db.session.add_all(RolePermission(role_id=user.role_id, permission_id=permission.id) for permission in permissions)
        db.session.commit()


def test_company_and_department_generic_edits_cannot_change_lifecycle(client, app):
    grant(app, "reporter", "modules.partners.access", "partner_companies.view", "partner_companies.edit")
    with app.app_context():
        company = Company(id=9101, name="Lifecycle Co", is_active=False)
        company.deleted_at = date.today()
        department = CompanyDepartment(id=9102, company=company, name="Inactive Dept", is_active=False)
        db.session.add_all([company, department])
        db.session.commit()

    login(client, "reporter")
    rejected_company = client.post("/partner-companies/9101/edit", data={"name": "Changed", "is_active": "on"})
    rejected_department = client.post(
        "/partner-companies/9101/departments/9102/edit",
        data={"name": "Changed dept", "is_active": "on"},
    )
    assert rejected_company.status_code == 404
    assert rejected_department.status_code == 404
    with app.app_context():
        company = db.session.get(Company, 9101)
        department = db.session.get(CompanyDepartment, 9102)
        assert (company.name, company.is_active, company.deleted_at is not None) == ("Lifecycle Co", False, True)
        assert (department.name, department.is_active) == ("Inactive Dept", False)

    client.post("/logout")
    login(client, "super")
    assert client.post("/partner-companies/9101/restore").status_code == 302
    assert client.post("/partner-companies/9101/departments/9102/restore").status_code == 302
    client.post("/logout")
    login(client, "reporter")
    assert client.post("/partner-companies/9101/edit", data={"name": "Ordinary edit"}).status_code == 302
    assert client.post(
        "/partner-companies/9101/departments/9102/edit",
        data={"name": "Ordinary dept edit", "parent_department_id": "", "display_order": "0"},
    ).status_code == 302
    with app.app_context():
        assert db.session.get(Company, 9101).name == "Ordinary edit"
        assert db.session.get(CompanyDepartment, 9102).name == "Ordinary dept edit"


def test_relationship_graph_rejects_indirect_cycle_and_archived_company_details(client, app):
    with app.app_context():
        company = Company(id=9201, name="Graph Co")
        department = CompanyDepartment(id=9202, company=company, name="Graph Dept")
        partners = [
            Partner(id=9203, full_name="A", company=company, department_id=9202, department="Graph Dept", position="Lead"),
            Partner(id=9204, full_name="B", company=company, department_id=9202, department="Graph Dept", position="Lead"),
            Partner(id=9205, full_name="C", company=company, department_id=9202, department="Graph Dept", position="Lead"),
        ]
        db.session.add_all([company, department, *partners])
        db.session.commit()

    login(client, "super")
    assert client.post("/partner-relations/company/9201/manage", data={"partner_id": "9203", "parent_partner_id": "9204", "relationship_type": "manager"}).status_code == 302
    assert client.post("/partner-relations/company/9201/manage", data={"partner_id": "9204", "parent_partner_id": "9205", "relationship_type": "manager"}).status_code == 302
    rejected = client.post("/partner-relations/company/9201/manage", data={"partner_id": "9205", "parent_partner_id": "9203", "relationship_type": "manager"})
    assert rejected.status_code == 400
    with app.app_context():
        assert [(item.partner_id, item.parent_partner_id) for item in PartnerRelationship.query.filter_by(company_id=9201).order_by(PartnerRelationship.id)] == [(9203, 9204), (9204, 9205)]
        company = db.session.get(Company, 9201)
        company.is_active = False
        company.deleted_at = date.today()
        db.session.commit()
    assert client.get("/partner-relations/company/9201").status_code == 404
    assert client.get("/partner-relations/company/9201/tree").status_code == 404


def test_document_root_get_is_read_only_and_post_provision_is_authorized_csrf_and_idempotent(client, app):
    with app.app_context():
        project = db.session.get(Project, 1)
        assert find_project_root_folder(project) is None
        before_folders = db.session.query(__import__("app.models", fromlist=["ProjectDocumentFolder"]).ProjectDocumentFolder).count()
        before_audits = AuditLog.query.count()
    login(client, "reporter")
    assert client.get("/project-documents/projects/1").status_code == 404
    assert client.post("/project-documents/projects/1/provision-root").status_code == 403
    with app.app_context():
        project = db.session.get(Project, 1)
        assert find_project_root_folder(project) is None
        assert db.session.query(__import__("app.models", fromlist=["ProjectDocumentFolder"]).ProjectDocumentFolder).count() == before_folders
        assert AuditLog.query.count() == before_audits

    client.post("/logout")
    login(client, "admin")
    app.config["WTF_CSRF_ENABLED"] = True
    assert client.post("/project-documents/projects/1/provision-root").status_code == 400
    page = client.get("/project-documents/")
    token = re.search(r'name="csrf_token" value="([^"]+)"', page.get_data(as_text=True)).group(1)
    created = client.post("/project-documents/projects/1/provision-root", data={"csrf_token": token})
    assert created.status_code == 302
    with app.app_context():
        root = find_project_root_folder(db.session.get(Project, 1))
        root_id = root.id
        audit_count = AuditLog.query.count()
    page = client.get("/project-documents/")
    token = re.search(r'name="csrf_token" value="([^"]+)"', page.get_data(as_text=True)).group(1)
    assert client.post("/project-documents/projects/1/provision-root", data={"csrf_token": token}).status_code == 302
    with app.app_context():
        assert find_project_root_folder(db.session.get(Project, 1)).id == root_id
        assert AuditLog.query.count() == audit_count
    app.config["WTF_CSRF_ENABLED"] = False


def test_csv_safe_cell_neutralizes_all_formula_prefixes_without_changing_normal_text():
    dangerous = ["=1+1", "+1", "-1", "@cmd", "\tformula", "\rformula", " =1", "\n+1", "\v@x"]
    assert all(safe_csv_cell(value) == "'" + value for value in dangerous)
    assert safe_csv_cell("normal, \"quoted\" tiếng Việt") == "normal, \"quoted\" tiếng Việt"
    assert safe_csv_cell(42) == 42
    output = StringIO()
    csv.writer(output).writerow([safe_csv_cell("=x"), safe_csv_cell("normal, \"quoted\" tiếng Việt")])
    assert next(csv.reader(StringIO(output.getvalue()))) == ["'=x", "normal, \"quoted\" tiếng Việt"]


def test_media_principal_picker_and_provider_error_are_bounded(client, app, monkeypatch):
    with app.app_context():
        admin, reporter = db.session.get(User, 6), db.session.get(User, 3)
        album = CompanyMediaAlbum(name="Bounded ACL", is_restricted=True, created_by_id=admin.id)
        db.session.add(album)
        db.session.commit()
        set_permission(admin, album, "user", reporter.id, {"can_share": "1"})
        album_id = album.id
    login(client, "reporter")
    page = client.get(f"/company-media/albums/{album_id}/permissions")
    assert page.status_code == 200
    text = page.get_data(as_text=True)
    assert "pm@example.com" not in text and "viewer@example.com" not in text
    assert "email" not in text and "description" not in text
    rejected = client.post(f"/company-media/albums/{album_id}/permissions", data={"principal_type": "user", "principal_id": "5", "can_share": "1"})
    assert rejected.status_code == 400
    assert rejected.get_json()["error"] == "Đối tượng phân quyền không hợp lệ."
    with app.app_context():
        assert CompanyMediaAlbumPermission.query.filter_by(album_id=album_id, user_id=5).count() == 0

    client.post("/logout")
    login(client, "super")
    secret = "bucket=private object_key=very-secret presigned=https://bearer.example/token"
    monkeypatch.setattr(media_routes.s, "presign", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError(secret)))
    response = client.post(f"/company-media/albums/{album_id}/files/presign-batch", json={"files": []})
    assert response.status_code == 502
    assert secret not in response.get_data(as_text=True)
    assert response.get_json()["error"]["code"] == "presign_unavailable"
    assert response.get_json()["error"]["retryable"] is True
    assert all(secret not in value for value in response.headers.values())


def test_foreign_project_update_assignment_returns_generic_error(client, app):
    grant(app, "reporter", "project_updates.create", "project_operations.view")
    with app.app_context():
        contractor = ProjectContractor(id=9301, name="Hidden contractor", normalized_name="hidden contractor", is_active=True)
        assignment = ProjectContractorAssignment(id=9302, project_id=2, contractor=contractor, role="CONSTRUCTION", status="ACTIVE")
        db.session.add_all([contractor, assignment])
        db.session.commit()
    login(client, "reporter")
    response = client.post("/projects/1/updates", data={
        "contractor_assignment_id": "9302", "update_type": "GENERAL", "title": "Safe", "content": "Safe",
        "update_date": date.today().isoformat(),
    })
    assert response.status_code == 400
    assert "Đối tác được chọn không hợp lệ." in response.get_data(as_text=True)
    assert "Hidden contractor" not in response.get_data(as_text=True)
    invalid = client.post("/projects/1/updates", data={
        "contractor_assignment_id": "not-an-assignment", "update_type": "GENERAL", "title": "Safe", "content": "Safe",
        "update_date": date.today().isoformat(),
    })
    assert invalid.status_code == response.status_code
    assert "Đối tác được chọn không hợp lệ." in invalid.get_data(as_text=True)
