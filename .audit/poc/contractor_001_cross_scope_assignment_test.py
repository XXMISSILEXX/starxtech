"""Secure regression for CONTRACTOR-001: assignment must validate contractor scope."""

pytest_plugins = ("tests.conftest",)

from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import (
    Permission,
    ProjectContractor,
    ProjectContractorAssignment,
    ProjectUser,
    Role,
    RolePermission,
    User,
)


def _login(client, username):
    # The shared TestConfig disables CSRF, which is the repository's normal test convention.
    return client.post("/login", data={"username_or_email": username, "password": "password123"})


def test_assignment_manager_cannot_attach_contractor_from_unrelated_project(client, app):
    with app.app_context():
        role = Role(id=9102, code="AUDIT_CONTRACTOR_COORDINATOR", name="Audit contractor coordinator", is_system=False)
        actor = User(
            id=9102,
            full_name="Audit Contractor Coordinator",
            username="audit-contractor-coordinator",
            email="audit-contractor-coordinator@example.com",
            password_hash=generate_password_hash("password123"),
            role=role,
            legacy_role=role.code,
        )
        contractor = ProjectContractor(
            id=9102,
            name="Unrelated Audit Contractor",
            normalized_name="unrelated audit contractor",
            phone="0900000000",
            email="unrelated-contractor@example.com",
        )
        db.session.add_all([role, actor, contractor])
        db.session.flush()
        permissions = Permission.query.filter(Permission.code.in_((
            "modules.reports.access", "contractor_assignments.view", "contractor_assignments.manage",
        ))).all()
        db.session.add_all(RolePermission(role_id=role.id, permission_id=item.id) for item in permissions)
        db.session.add(ProjectUser(
            id=9102,
            project_id=1,
            user_id=actor.id,
            project_role_code="CUSTOM",
            is_active=True,
            can_view_project=True,
        ))
        db.session.add(ProjectContractorAssignment(
            id=9102,
            project_id=2,
            contractor_id=contractor.id,
            role="CONSTRUCTION",
            status="ACTIVE",
            created_by_id=1,
        ))
        db.session.commit()
        contractor_id = contractor.id

    assert _login(client, "audit-contractor-coordinator").status_code == 302
    response = client.post(
        "/projects/1/contractors/construction",
        data={"contractor_id": str(contractor_id), "status": "ACTIVE"},
    )

    with app.app_context():
        db.session.expire_all()
        assignment_inserted = ProjectContractorAssignment.query.filter_by(
            project_id=1, contractor_id=contractor_id
        ).first() is not None

    secure = response.status_code in {400, 403, 404, 422} and not assignment_inserted
    assert secure, (
        "secure behavior must reject assigning a contractor visible only through project 2 to project 1; "
        f"got HTTP {response.status_code}, project-1 assignment inserted={assignment_inserted}"
    )
