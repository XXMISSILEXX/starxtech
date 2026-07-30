import re

from app.extensions import db
from app.models import AuditLog, Customer, Permission, Project, Role, RolePermission, User


def _login(client, username):
    return client.post("/login", data={"username_or_email": username, "password": "password123"})


def _customer(app, name, *, active=True, archived_at=None):
    with app.app_context():
        customer = Customer(
            name=name,
            normalized_name=name.casefold(),
            is_active=active,
            archived_at=archived_at,
        )
        db.session.add(customer)
        db.session.commit()
        return customer.id


def test_project_form_assigns_and_clears_customer_with_audit(client, app):
    customer_id = _customer(app, "Customer form")
    assert _login(client, "super").status_code == 302

    created = client.post(
        "/admin/projects/new",
        data={"code": "P-CUSTOMER", "name": "Project customer", "status": "active", "customer_id": str(customer_id)},
    )
    assert created.status_code == 302
    with app.app_context():
        project = Project.query.filter_by(code="P-CUSTOMER").one()
        assert project.customer_id == customer_id
        create_audit = AuditLog.query.filter_by(action="project.create", entity_id=project.id).one()
        assert create_audit.new_values_json["customer_id"] == customer_id
        project_id = project.id

    cleared = client.post(
        f"/admin/projects/{project_id}/edit",
        data={"code": "P-CUSTOMER", "name": "Project customer", "status": "active", "customer_id": ""},
    )
    assert cleared.status_code == 302
    with app.app_context():
        project = db.session.get(Project, project_id)
        assert project.customer_id is None
        update_audit = AuditLog.query.filter_by(action="project.update", entity_id=project_id).one()
        assert update_audit.old_values_json["customer_id"] == customer_id
        assert update_audit.new_values_json["customer_id"] is None


def test_project_form_rejects_invalid_or_archived_customer_and_keeps_posted_data(client, app):
    archived_id = _customer(app, "Archived form", active=False)
    assert _login(client, "super").status_code == 302

    for customer_id in ("999999", str(archived_id)):
        response = client.post(
            "/admin/projects/new",
            data={"code": "P-INVALID", "name": "Posted project name", "status": "active", "customer_id": customer_id},
        )
        assert response.status_code == 400
        assert b"Posted project name" in response.data
        assert b"customer_id" in response.data


def test_project_customer_change_requires_customer_edit_permission(client, app):
    customer_id = _customer(app, "Permission target")
    with app.app_context():
        role = Role(id=1901, code="PROJECT_MUTATOR", name="Project mutator", is_system=False)
        user = User(
            id=1901,
            full_name="Project mutator",
            username="project_mutator",
            password_hash="not-used",
            role=role,
            legacy_role=role.code,
        )
        db.session.add_all([role, user])
        permissions = Permission.query.filter(Permission.code.in_(("projects.manage",))).all()
        db.session.add_all(RolePermission(role_id=role.id, permission_id=permission.id) for permission in permissions)
        db.session.commit()

    with client.session_transaction() as session:
        session["_user_id"] = "1901"
        session["_fresh"] = True
    response = client.post(
        "/admin/projects/1/edit",
        data={"code": "P001", "name": "Assigned Project", "status": "active", "customer_id": str(customer_id)},
    )
    assert response.status_code == 403


def test_customer_detail_attaches_only_unclassified_project_and_audits(client, app):
    customer_id = _customer(app, "Attach target")
    other_customer_id = _customer(app, "Already assigned")
    with app.app_context():
        db.session.get(Project, 2).customer_id = other_customer_id
        db.session.commit()

    assert _login(client, "super").status_code == 302
    page = client.get(f"/customers/{customer_id}")
    assert page.status_code == 200
    assert "Gắn dự án".encode() in page.data
    assert b"Assigned Project" in page.data
    assert b"Other Project" not in page.data

    attached = client.post(f"/customers/{customer_id}/projects/1/attach")
    assert attached.status_code == 302
    with app.app_context():
        assert db.session.get(Project, 1).customer_id == customer_id
        audit = AuditLog.query.filter_by(action="project.customer.attach", entity_id=1).one()
        assert audit.old_values_json == {"customer_id": None}
        assert audit.new_values_json == {"customer_id": customer_id}

    rejected = client.post(f"/customers/{customer_id}/projects/2/attach")
    assert rejected.status_code == 403


def test_customer_attachment_post_is_csrf_protected(client, app):
    customer_id = _customer(app, "CSRF customer")
    assert _login(client, "super").status_code == 302
    app.config["WTF_CSRF_ENABLED"] = True
    try:
        page = client.get(f"/customers/{customer_id}")
        token = re.search(r'name="csrf_token" value="([^"]+)"', page.get_data(as_text=True)).group(1)
        assert client.post(f"/customers/{customer_id}/projects/1/attach").status_code == 400
        attached = client.post(f"/customers/{customer_id}/projects/1/attach", data={"csrf_token": token})
        assert attached.status_code == 302
    finally:
        app.config["WTF_CSRF_ENABLED"] = False
