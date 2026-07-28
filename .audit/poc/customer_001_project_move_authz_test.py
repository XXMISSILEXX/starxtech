"""Secure regression for CUSTOMER-001: source-customer management is required."""

pytest_plugins = ("tests.conftest",)

from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import Customer, Permission, Project, ProjectUser, Role, RolePermission, User


def _login(client, username):
    # The shared TestConfig disables CSRF, which is the repository's normal test convention.
    return client.post("/login", data={"username_or_email": username, "password": "password123"})


def test_project_reader_cannot_move_project_without_managing_source_customer(client, app):
    with app.app_context():
        role = Role(id=9101, code="AUDIT_CUSTOMER_MOVER", name="Audit customer mover", is_system=False)
        actor = User(
            id=9101,
            full_name="Audit Customer Mover",
            username="audit-customer-mover",
            email="audit-customer-mover@example.com",
            password_hash=generate_password_hash("password123"),
            role=role,
            legacy_role=role.code,
        )
        source = Customer(id=9101, name="Audit source customer", normalized_name="audit source customer")
        target = Customer(id=9102, name="Audit empty target", normalized_name="audit empty target")
        db.session.add_all([role, actor, source, target])
        db.session.flush()
        permissions = Permission.query.filter(Permission.code.in_(("modules.reports.access", "customers.edit"))).all()
        db.session.add_all(RolePermission(role_id=role.id, permission_id=item.id) for item in permissions)
        db.session.add(ProjectUser(
            id=9101,
            project_id=1,
            user_id=actor.id,
            project_role_code="CUSTOM",
            is_active=True,
            can_view_project=True,
        ))
        db.session.get(Project, 1).customer_id = source.id
        db.session.get(Project, 2).customer_id = source.id
        db.session.commit()
        source_id, target_id = source.id, target.id

    assert _login(client, "audit-customer-mover").status_code == 302
    response = client.post(
        f"/customers/{source_id}/projects/1/move",
        data={"target_customer_id": str(target_id)},
    )

    with app.app_context():
        db.session.expire_all()
        persisted_customer_id = db.session.get(Project, 1).customer_id

    secure = response.status_code in {400, 403, 404, 422} and persisted_customer_id == source_id
    assert secure, (
        "secure behavior must reject a move by a caller who only reads the source project and retain its source customer; "
        f"got HTTP {response.status_code}, persisted customer_id={persisted_customer_id}, expected {source_id}"
    )
