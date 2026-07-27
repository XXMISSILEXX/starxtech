from datetime import date

import pytest

from app.extensions import db
from app.models import (
    AuditLog,
    Customer,
    Permission,
    Project,
    ProjectContractor,
    ProjectContractorAssignment,
    ProjectContractorAssignmentStatus,
    ProjectContractorRole,
    ProjectUser,
    Role,
    RolePermission,
    User,
)
from app.project_operations.services import (
    active_assignment_count,
    archive_contractor,
    assign_contractor,
    end_assignment,
    update_assignment,
)


def login(client, username, password="password123"):
    return client.post("/login", data={"username_or_email": username, "password": password})


def _contractor(app, name="VTS"):
    with app.app_context():
        contractor = ProjectContractor(name=name, normalized_name=name.casefold(), is_active=True)
        db.session.add(contractor)
        db.session.commit()
        return contractor.id


def _grant(app, username, *codes):
    with app.app_context():
        user = User.query.filter_by(username=username).one()
        permissions = Permission.query.filter(Permission.code.in_(codes)).all()
        db.session.add_all(RolePermission(role_id=user.role_id, permission_id=permission.id) for permission in permissions)
        db.session.commit()


def test_contractor_domain_is_independent_and_supports_multiple_projects_customers(app):
    with app.app_context():
        first_customer = Customer(name="Geleximco", normalized_name="geleximco")
        second_customer = Customer(name="Handico", normalized_name="handico")
        contractor = ProjectContractor(name="VTS", normalized_name="vts")
        db.session.add_all([first_customer, second_customer, contractor])
        db.session.flush()
        first = db.session.get(Project, 1)
        second = db.session.get(Project, 2)
        first.customer_id = first_customer.id
        second.customer_id = second_customer.id
        first_assignment = assign_contractor(project=first, contractor=contractor, role="CONSTRUCTION", status="ACTIVE")
        second_assignment = assign_contractor(project=second, contractor=contractor, role="SOLUTION", status="PAUSED")
        db.session.commit()

        assert {first_assignment.project.customer_id, second_assignment.project.customer_id} == {first_customer.id, second_customer.id}
        assert ProjectContractor.__table__.foreign_keys
        assert all("partner" not in foreign_key.target_fullname.lower() and "companies" not in foreign_key.target_fullname.lower() for foreign_key in ProjectContractor.__table__.foreign_keys)


def test_assignment_allows_both_roles_rejects_duplicate_and_allows_reassignment_after_end(app):
    with app.app_context():
        contractor = ProjectContractor(name="ZTSS", normalized_name="ztss")
        db.session.add(contractor)
        db.session.flush()
        project = db.session.get(Project, 1)
        construction = assign_contractor(project=project, contractor=contractor, role="CONSTRUCTION", status="ACTIVE")
        solution = assign_contractor(project=project, contractor=contractor, role="SOLUTION", status="ACTIVE")
        db.session.commit()
        assert active_assignment_count(project.id) == 2
        assert active_assignment_count(project.id, "CONSTRUCTION") == 1
        with pytest.raises(ValueError, match="chưa kết thúc"):
            assign_contractor(project=project, contractor=contractor, role="CONSTRUCTION", status="PAUSED")
        end_assignment(construction, ended_on=date(2026, 7, 26))
        db.session.commit()
        replacement = assign_contractor(project=project, contractor=contractor, role="CONSTRUCTION", status="ACTIVE")
        db.session.commit()
        assert solution.status == "ACTIVE"
        assert construction.status == "ENDED"
        assert construction.ended_on == date(2026, 7, 26)
        assert replacement.id != construction.id


def test_archive_requires_no_active_assignment_and_history_is_preserved(app):
    with app.app_context():
        contractor = ProjectContractor(name="HT Hyundai", normalized_name="ht hyundai")
        db.session.add(contractor)
        db.session.flush()
        assignment = assign_contractor(project=db.session.get(Project, 1), contractor=contractor, role="CONSTRUCTION", status="ACTIVE")
        db.session.commit()
        with pytest.raises(ValueError, match="đang hoạt động"):
            archive_contractor(contractor)
        end_assignment(assignment)
        archive_contractor(contractor)
        db.session.commit()
        assert contractor.is_active is False
        assert db.session.get(ProjectContractorAssignment, assignment.id).status == "ENDED"
        assert AuditLog.query.filter(AuditLog.action.in_(("project_contractor_assignment.end", "project_contractor.archive"))).count() == 2


def test_routes_enforce_catalog_assignment_permissions_scope_and_post_methods(client, app):
    contractor_id = _contractor(app)
    _grant(app, "reporter", "project_operations.view", "project_contractors.view", "contractor_assignments.view")
    login(client, "reporter")
    assert client.get("/project-operations/contractors").status_code == 200
    assert client.get(f"/project-operations/contractors/{contractor_id}").status_code == 200
    assert client.get("/projects/1/contractors/construction").status_code == 200
    assert client.get("/projects/2/contractors/construction").status_code == 403
    assert client.post("/project-operations/contractors/new", data={"name": "Blocked"}).status_code == 403
    assert client.get(f"/project-operations/contractors/{contractor_id}/archive").status_code == 405


def test_custom_assignment_manager_needs_project_scope_and_can_mutate_only_assigned_project(client, app):
    contractor_id = _contractor(app, "Scope contractor")
    with app.app_context():
        role = Role(id=201, code="CONTRACTOR_COORDINATOR", name="Contractor coordinator", is_system=False)
        user = User(id=201, full_name="Coordinator", username="coordinator", password_hash="unused", role=role, legacy_role=role.code)
        db.session.add_all([role, user])
        permissions = Permission.query.filter(Permission.code.in_((
            "modules.reports.access", "project_operations.view", "project_contractors.view",
            "contractor_assignments.view", "contractor_assignments.manage", "contractor_assignments.end",
        ))).all()
        db.session.add_all(RolePermission(role_id=role.id, permission_id=permission.id) for permission in permissions)
        db.session.add(ProjectUser(
            id=201,
            project_id=1,
            user_id=user.id,
            project_role_code="CUSTOM",
            is_active=True,
            can_view_project=True,
        ))
        db.session.commit()

    with client.session_transaction() as session:
        session["_user_id"] = "201"
        session["_fresh"] = True
    blocked = client.post("/projects/2/contractors/construction", data={"contractor_id": str(contractor_id)})
    assert blocked.status_code == 403
    allowed = client.post("/projects/1/contractors/construction", data={"contractor_id": str(contractor_id)})
    assert allowed.status_code == 302
    with app.app_context():
        assignment = ProjectContractorAssignment.query.filter_by(project_id=1, contractor_id=contractor_id).one()
        assert assignment.status == ProjectContractorAssignmentStatus.ACTIVE.value
        assert assignment.role == ProjectContractorRole.CONSTRUCTION.value
        assert AuditLog.query.filter_by(action="project_contractor_assignment.create", entity_id=assignment.id).count() == 1


def test_assignment_page_uses_modal_vietnamese_labels_and_removal_confirmation(client, app):
    contractor_id = _contractor(app, "Modal contractor")
    with app.app_context():
        assignment = assign_contractor(project=db.session.get(Project, 1), contractor=db.session.get(ProjectContractor, contractor_id), role="CONSTRUCTION", status="ACTIVE", actor_id=1)
        db.session.commit()
        assignment_id = assignment.id
    login(client, "super")
    page = client.get("/projects/1/contractors/construction")
    assert page.status_code == 200
    assert "Thêm đối tác".encode() in page.data
    assert b"addContractorModal" in page.data
    assert "Đối tác thi công".encode() in page.data
    assert "Đang hoạt động".encode() in page.data
    assert "Gỡ đối tác khỏi dự án".encode() in page.data
    assert b"editAssignmentModal" in page.data
    assert "Chỉnh sửa đối tác trong dự án".encode() in page.data
    assert b"data-vn-date" in page.data
    response = client.post(f"/project-operations/assignments/{assignment_id}/end")
    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(ProjectContractorAssignment, assignment_id).status == "ENDED"


def test_assignment_lifecycle_dates_are_nullable_and_validate_status_policy(app):
    with app.app_context():
        contractor = ProjectContractor(name="Lifecycle contractor", normalized_name="lifecycle contractor")
        db.session.add(contractor); db.session.flush()
        assignment = assign_contractor(project=db.session.get(Project, 1), contractor=contractor, role="CONSTRUCTION", status="ACTIVE")
        db.session.commit()

        update_assignment(assignment, status="COMPLETED", started_on=None, ended_on=None, note="done")
        db.session.commit()
        assert assignment.started_on is None and assignment.ended_on is None
        with pytest.raises(ValueError, match="trước ngày bắt đầu"):
            update_assignment(assignment, status="COMPLETED", started_on=date(2026, 7, 20), ended_on=date(2026, 7, 19))
        with pytest.raises(ValueError, match="xóa ngày kết thúc"):
            update_assignment(assignment, status="PAUSED", started_on=None, ended_on=date(2026, 7, 20))

        end_assignment(assignment, ended_on=None)
        db.session.commit()
        assert assignment.status == "ENDED" and assignment.ended_on is None
        update_assignment(assignment, status="ENDED", started_on=None, ended_on=None, note="history corrected")
        db.session.commit()
        assert assignment.note == "history corrected"
