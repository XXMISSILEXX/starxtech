"""Secure regression: assignment managers must not assign themselves to arbitrary projects."""

pytest_plugins = ("tests.conftest",)

from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import Permission, ProjectUser, Role, RolePermission, User
from app.project_memberships import CAPABILITY_FIELDS


def _login(client, username):
    # The shared TestConfig disables CSRF, which is the repository's normal test convention.
    return client.post("/login", data={"username_or_email": username, "password": "password123"})


def test_assignment_manager_cannot_insert_self_as_owner_in_unrelated_project(client, app):
    with app.app_context():
        role = Role(id=9002, code="AUDIT_ASSIGNMENT_MANAGER", name="Audit assignment manager", is_system=False)
        actor = User(
            id=9002,
            full_name="Audit Assignment Manager",
            username="audit-assignment-manager",
            email="audit-assignment-manager@example.com",
            password_hash=generate_password_hash("password123"),
            role=role,
            legacy_role=role.code,
        )
        db.session.add_all([role, actor])
        db.session.flush()
        permission = Permission.query.filter_by(code="project_assignments.manage").one()
        db.session.add(RolePermission(role_id=role.id, permission_id=permission.id))
        db.session.commit()
        actor_id = actor.id

    assert _login(client, "audit-assignment-manager").status_code == 302
    response = client.post(
        "/admin/projects/2/memberships",
        data={
            "user_id": str(actor_id),
            "project_role_code": "PROJECT_OWNER",
            **{field: "1" for field in CAPABILITY_FIELDS},
        },
    )

    with app.app_context():
        db.session.expire_all()
        membership = ProjectUser.query.filter_by(project_id=2, user_id=actor_id).first()
        full_capability_membership_exists = bool(
            membership and membership.is_active and all(getattr(membership, field) for field in CAPABILITY_FIELDS)
        )

    secure = response.status_code in {400, 403, 404, 422} and not full_capability_membership_exists
    assert secure, (
        "secure behavior must reject arbitrary self-assignment and create no owner-equivalent membership; "
        f"got HTTP {response.status_code}, owner-equivalent membership created={full_capability_membership_exists}"
    )
