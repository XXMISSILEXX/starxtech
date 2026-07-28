"""Regression coverage for Phase 10 project/customer/contractor scope controls."""

from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import (
    AuditLog,
    Customer,
    Permission,
    Project,
    ProjectContractor,
    ProjectContractorAssignment,
    ProjectUser,
    Role,
    RolePermission,
    User,
)
from app.project_memberships import CAPABILITY_FIELDS, preset_flags


def _login(client, username):
    return client.post("/login", data={"username_or_email": username, "password": "password123"})


def _make_user(app, user_id, *, permissions=(), memberships=()):
    """Create a custom actor with explicit global grants and project flags."""
    username = f"scope-{user_id}"
    with app.app_context():
        role = Role(id=user_id, code=f"SCOPE_{user_id}", name=f"Scope {user_id}", is_system=False)
        user = User(
            id=user_id,
            full_name=f"Scope actor {user_id}",
            username=username,
            email=f"scope-{user_id}@example.com",
            password_hash=generate_password_hash("password123"),
            role=role,
            legacy_role=role.code,
        )
        db.session.add_all([role, user])
        db.session.flush()
        granted = Permission.query.filter(Permission.code.in_(permissions)).all()
        db.session.add_all(RolePermission(role_id=role.id, permission_id=item.id) for item in granted)
        for offset, (project_id, role_code, flags) in enumerate(memberships, start=1):
            db.session.add(ProjectUser(
                id=user_id * 10 + offset,
                project_id=project_id,
                user_id=user.id,
                project_role_code=role_code,
                is_active=True,
                **flags,
            ))
        db.session.commit()
    return username


def _create_target_user(app, user_id):
    return _make_user(app, user_id)


def _membership_payload(role_code, enabled):
    enabled_fields = (
        {field for field, value in enabled.items() if value}
        if isinstance(enabled, dict)
        else set(enabled)
    )
    return {
        "project_role_code": role_code,
        **{field: "1" for field in enabled_fields},
    }


def test_assignment_permission_alone_cannot_create_memberships_in_unrelated_project(client, app):
    username = _make_user(app, 1101, permissions=("project_assignments.manage",))
    other_username = _create_target_user(app, 1102)
    with app.app_context():
        actor_id = User.query.filter_by(username=username).one().id
        other_id = User.query.filter_by(username=other_username).one().id

    assert _login(client, username).status_code == 302
    for target_id in (actor_id, other_id):
        response = client.post(
            "/admin/projects/2/memberships",
            data={"user_id": str(target_id), **_membership_payload("PROJECT_OWNER", CAPABILITY_FIELDS)},
        )
        assert response.status_code == 403

    with app.app_context():
        assert ProjectUser.query.filter(ProjectUser.project_id == 2, ProjectUser.user_id.in_((actor_id, other_id))).count() == 0


def test_project_manager_can_manage_subordinate_but_not_owner_equivalent_membership(client, app):
    username = _make_user(
        app,
        1111,
        permissions=("project_assignments.manage",),
        memberships=((1, "PROJECT_OWNER", preset_flags("PROJECT_OWNER")),),
    )
    subordinate_username = _create_target_user(app, 1112)
    owner_username = _create_target_user(app, 1113)
    with app.app_context():
        subordinate_id = User.query.filter_by(username=subordinate_username).one().id
        owner_id = User.query.filter_by(username=owner_username).one().id

    assert _login(client, username).status_code == 302
    allowed = client.post(
        "/admin/projects/1/memberships",
        data={"user_id": str(subordinate_id), **_membership_payload("PROJECT_EDITOR", preset_flags("PROJECT_EDITOR"))},
    )
    rejected = client.post(
        "/admin/projects/1/memberships",
        data={"user_id": str(owner_id), **_membership_payload("PROJECT_OWNER", preset_flags("PROJECT_OWNER"))},
    )
    assert allowed.status_code == 302
    assert rejected.status_code == 403
    with app.app_context():
        assert ProjectUser.query.filter_by(project_id=1, user_id=subordinate_id, is_active=True).one().project_role_code == "PROJECT_EDITOR"
        assert ProjectUser.query.filter_by(project_id=1, user_id=owner_id).count() == 0


def test_membership_grant_ceiling_and_malformed_input_leave_no_partial_membership(client, app):
    manager_flags = {"can_view_project": True, "can_manage_report_categories": True}
    username = _make_user(
        app,
        1121,
        permissions=("project_assignments.manage",),
        memberships=((1, "CUSTOM", manager_flags),),
    )
    target_username = _create_target_user(app, 1122)
    with app.app_context():
        target_id = User.query.filter_by(username=target_username).one().id

    assert _login(client, username).status_code == 302
    excessive = client.post(
        "/admin/projects/1/memberships",
        data={"user_id": str(target_id), **_membership_payload("PROJECT_VIEWER", {"can_view_reports"})},
    )
    malformed_role = client.post(
        "/admin/projects/1/memberships",
        data={"user_id": str(target_id), **_membership_payload("NOT_A_ROLE", {"can_view_project"})},
    )
    malformed_flag = client.post(
        "/admin/projects/1/memberships",
        data={"user_id": str(target_id), **_membership_payload("PROJECT_VIEWER", {"can_view_project"}), "can_unknown": "1"},
    )
    assert excessive.status_code == 403
    assert malformed_role.status_code == 400
    assert malformed_flag.status_code == 400
    with app.app_context():
        assert ProjectUser.query.filter_by(project_id=1, user_id=target_id).count() == 0


def test_rejected_membership_edit_deactivate_and_reactivation_leave_state_unchanged(client, app):
    target_username = _create_target_user(app, 1132)
    with app.app_context():
        target_id = User.query.filter_by(username=target_username).one().id
        membership = ProjectUser(
            id=11321,
            project_id=2,
            user_id=target_id,
            project_role_code="PROJECT_VIEWER",
            is_active=True,
            **preset_flags("PROJECT_VIEWER"),
        )
        db.session.add(membership)
        db.session.commit()
        membership_id = membership.id
    username = _make_user(app, 1131, permissions=("project_assignments.manage",))

    assert _login(client, username).status_code == 302
    edited = client.post(
        f"/admin/projects/2/memberships/{membership_id}",
        data=_membership_payload("PROJECT_EDITOR", preset_flags("PROJECT_EDITOR")),
    )
    deactivated = client.post(f"/admin/projects/2/memberships/{membership_id}/deactivate")
    assert edited.status_code == 403
    assert deactivated.status_code == 403
    with app.app_context():
        membership = db.session.get(ProjectUser, membership_id)
        assert membership.is_active is True
        assert membership.project_role_code == "PROJECT_VIEWER"
        membership.is_active = False
        db.session.commit()
    reactivated = client.post(
        "/admin/projects/2/memberships",
        data={"user_id": str(target_id), **_membership_payload("PROJECT_VIEWER", preset_flags("PROJECT_VIEWER"))},
    )
    assert reactivated.status_code == 403
    with app.app_context():
        assert db.session.get(ProjectUser, membership_id).is_active is False


def test_super_admin_still_manages_memberships(client, app):
    target_username = _create_target_user(app, 1141)
    with app.app_context():
        target_id = User.query.filter_by(username=target_username).one().id
    assert _login(client, "super").status_code == 302
    response = client.post(
        "/admin/projects/2/memberships",
        data={"user_id": str(target_id), **_membership_payload("PROJECT_OWNER", preset_flags("PROJECT_OWNER"))},
    )
    assert response.status_code == 302
    with app.app_context():
        assert ProjectUser.query.filter_by(project_id=2, user_id=target_id, is_active=True).one().project_role_code == "PROJECT_OWNER"


def _customer(app, name, *, active=True):
    with app.app_context():
        customer = Customer(name=name, normalized_name=name.casefold(), is_active=active)
        db.session.add(customer)
        db.session.commit()
        return customer.id


def _set_customer(app, project_id, customer_id):
    with app.app_context():
        db.session.get(Project, project_id).customer_id = customer_id
        db.session.commit()


def _customer_actor(app, user_id, memberships):
    return _make_user(
        app,
        user_id,
        permissions=("modules.reports.access", "customers.edit"),
        memberships=memberships,
    )


def test_customer_move_requires_project_and_both_customer_management_scopes(client, app):
    source_id = _customer(app, "Source scope")
    target_id = _customer(app, "Target scope")
    _set_customer(app, 1, source_id)
    _set_customer(app, 2, target_id)
    source_manager = _customer_actor(app, 1201, ((1, "PROJECT_OWNER", preset_flags("PROJECT_OWNER")),))
    target_manager = _customer_actor(app, 1202, ((2, "PROJECT_OWNER", preset_flags("PROJECT_OWNER")),))
    reader = _customer_actor(app, 1203, ((1, "PROJECT_VIEWER", preset_flags("PROJECT_VIEWER")),))

    for username in (reader, target_manager, source_manager):
        assert _login(client, username).status_code == 302
        response = client.post(
            f"/customers/{source_id}/projects/1/move", data={"target_customer_id": str(target_id)}
        )
        assert response.status_code == 403
        client.post("/logout")
    with app.app_context():
        assert db.session.get(Project, 1).customer_id == source_id


def test_authorized_customer_move_audits_ids_and_rejects_url_or_target_errors(client, app):
    source_id = _customer(app, "Move source")
    target_id = _customer(app, "Move target")
    inactive_id = _customer(app, "Move inactive", active=False)
    _set_customer(app, 1, source_id)
    _set_customer(app, 2, target_id)
    username = _customer_actor(
        app,
        1211,
        (
            (1, "PROJECT_OWNER", preset_flags("PROJECT_OWNER")),
            (2, "PROJECT_OWNER", preset_flags("PROJECT_OWNER")),
        ),
    )
    assert _login(client, username).status_code == 302
    same_customer = client.post(
        f"/customers/{source_id}/projects/1/move", data={"target_customer_id": str(source_id)}
    )
    mismatch = client.post(
        f"/customers/{target_id}/projects/1/move", data={"target_customer_id": str(source_id)}
    )
    inactive = client.post(
        f"/customers/{source_id}/projects/1/move", data={"target_customer_id": str(inactive_id)}
    )
    missing = client.post(
        f"/customers/{source_id}/projects/1/move", data={"target_customer_id": "999999"}
    )
    assert same_customer.status_code == 400
    assert mismatch.status_code == 403
    assert inactive.status_code == 404
    assert missing.status_code == 404
    with app.app_context():
        assert db.session.get(Project, 1).customer_id == source_id

    moved = client.post(
        f"/customers/{source_id}/projects/1/move", data={"target_customer_id": str(target_id)}
    )
    assert moved.status_code == 302
    with app.app_context():
        assert db.session.get(Project, 1).customer_id == target_id
        audit = AuditLog.query.filter_by(action="project.customer.move", entity_id=1).one()
        assert audit.actor_user_id == 1211
        assert audit.old_values_json == {"customer_id": source_id}
        assert audit.new_values_json == {"customer_id": target_id}


def _contractor_manager(app, user_id, memberships):
    return _make_user(
        app,
        user_id,
        permissions=("modules.reports.access", "contractor_assignments.view", "contractor_assignments.manage", "contractor_assignments.end"),
        memberships=memberships,
    )


def test_assignment_rejects_cross_scope_inactive_invalid_and_duplicate_contractors(client, app):
    username = _contractor_manager(app, 1301, ((1, "PROJECT_OWNER", preset_flags("PROJECT_OWNER")),))
    with app.app_context():
        foreign = ProjectContractor(id=1301, name="Foreign", normalized_name="foreign")
        inactive = ProjectContractor(id=1302, name="Inactive", normalized_name="inactive", is_active=False)
        duplicate = ProjectContractor(id=1303, name="Duplicate", normalized_name="duplicate")
        db.session.add_all([foreign, inactive, duplicate])
        db.session.flush()
        db.session.add_all([
            ProjectContractorAssignment(id=1301, project_id=2, contractor_id=foreign.id, role="CONSTRUCTION", status="ACTIVE"),
            ProjectContractorAssignment(id=1302, project_id=1, contractor_id=duplicate.id, role="CONSTRUCTION", status="ACTIVE"),
        ])
        db.session.commit()

    assert _login(client, username).status_code == 302
    cross_scope = client.post("/projects/1/contractors/construction", data={"contractor_id": "1301"})
    archived = client.post("/projects/1/contractors/construction", data={"contractor_id": "1302"})
    invalid_path = client.post("/projects/1/contractors/not-a-role", data={"contractor_id": "1301"})
    duplicate = client.post("/projects/1/contractors/construction", data={"contractor_id": "1303"})
    assert cross_scope.status_code == 404
    assert archived.status_code == 404
    assert invalid_path.status_code == 404
    assert duplicate.status_code == 400
    with app.app_context():
        assert ProjectContractorAssignment.query.filter_by(project_id=1, contractor_id=1301).count() == 0
        assert ProjectContractorAssignment.query.filter_by(project_id=1, contractor_id=1302).count() == 0
        assert ProjectContractorAssignment.query.filter_by(project_id=1, contractor_id=1303).count() == 1


def test_authorized_assignment_manager_can_assign_visible_contractor_and_end_historically(client, app):
    username = _contractor_manager(app, 1311, ((1, "PROJECT_OWNER", preset_flags("PROJECT_OWNER")),))
    with app.app_context():
        contractor = ProjectContractor(id=1311, name="Visible", normalized_name="visible")
        db.session.add(contractor)
        db.session.commit()
    assert _login(client, username).status_code == 302
    created = client.post("/projects/1/contractors/construction", data={"contractor_id": "1311"})
    assert created.status_code == 302
    with app.app_context():
        assignment = ProjectContractorAssignment.query.filter_by(project_id=1, contractor_id=1311).one()
        assignment_id = assignment.id
    ended = client.post(f"/project-operations/assignments/{assignment_id}/end")
    assert ended.status_code == 302
    with app.app_context():
        assignment = db.session.get(ProjectContractorAssignment, assignment_id)
        assert assignment is not None
        assert assignment.status == "ENDED"
