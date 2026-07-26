import re
import unicodedata
from datetime import date, datetime

from sqlalchemy import or_

from app.audit import log_audit
from app.extensions import db
from app.models import (
    Project,
    ProjectContractor,
    ProjectContractorAssignment,
    ProjectContractorAssignmentStatus,
)
from app.project_memberships import accessible_project_ids, is_project_admin


def normalize_contractor_name(value):
    normalized = unicodedata.normalize("NFKC", value or "")
    return re.sub(r"\s+", " ", normalized).strip().casefold()


def contractor_name_is_available(name, contractor_id=None):
    normalized_name = normalize_contractor_name(name)
    query = ProjectContractor.query.filter(
        ProjectContractor.normalized_name == normalized_name,
        ProjectContractor.is_active.is_(True),
    )
    if contractor_id is not None:
        query = query.filter(ProjectContractor.id != contractor_id)
    return bool(normalized_name) and query.first() is None


def accessible_contractors_query(user, *, include_archived=False):
    query = ProjectContractor.query
    if not include_archived:
        query = query.filter(ProjectContractor.is_active.is_(True))

    project_ids = accessible_project_ids(user, ("can_view_project",))
    if project_ids is None:
        return query
    return query.filter(
        or_(
            ~ProjectContractor.assignments.any(),
            ProjectContractor.assignments.any(
                ProjectContractorAssignment.project_id.in_(project_ids or [0])
            ),
        )
    )


def can_access_contractor(user, contractor):
    return accessible_contractors_query(user, include_archived=True).filter(
        ProjectContractor.id == contractor.id
    ).first() is not None


def can_manage_contractor(user, contractor):
    if is_project_admin(user) or user.can("projects.scope_all"):
        return True
    assignment_project_ids = [assignment.project_id for assignment in contractor.assignments]
    if not assignment_project_ids:
        return True
    visible_ids = accessible_project_ids(user, ("can_view_project",)) or []
    return set(assignment_project_ids).issubset(visible_ids)


def active_assignment_count(project_id, role=None):
    query = ProjectContractorAssignment.query.filter(
        ProjectContractorAssignment.project_id == project_id,
        ProjectContractorAssignment.status == ProjectContractorAssignmentStatus.ACTIVE.value,
    )
    if role:
        query = query.filter(ProjectContractorAssignment.role == role)
    return query.count()


def contractor_snapshot(contractor):
    return {
        "name": contractor.name,
        "normalized_name": contractor.normalized_name,
        "short_name": contractor.short_name,
        "description": contractor.description,
        "phone": contractor.phone,
        "email": contractor.email,
        "address": contractor.address,
        "is_active": contractor.is_active,
        "archived_at": contractor.archived_at.isoformat() if contractor.archived_at else None,
    }


def assignment_snapshot(assignment):
    return {
        "project_id": assignment.project_id,
        "contractor_id": assignment.contractor_id,
        "role": assignment.role,
        "status": assignment.status,
        "started_on": assignment.started_on.isoformat() if assignment.started_on else None,
        "ended_on": assignment.ended_on.isoformat() if assignment.ended_on else None,
        "note": assignment.note,
    }


def create_or_update_contractor(contractor, *, name, short_name=None, description=None, phone=None, email=None, address=None, actor_id=None):
    if not contractor_name_is_available(name, contractor.id if contractor else None):
        raise ValueError("Tên nhà thầu đã tồn tại.")
    is_new = contractor is None
    old_values = contractor_snapshot(contractor) if contractor else None
    if contractor is None:
        contractor = ProjectContractor(created_by_id=actor_id)
        db.session.add(contractor)
    contractor.name = name.strip()
    contractor.normalized_name = normalize_contractor_name(name)
    contractor.short_name = (short_name or "").strip() or None
    contractor.description = (description or "").strip() or None
    contractor.phone = (phone or "").strip() or None
    contractor.email = (email or "").strip() or None
    contractor.address = (address or "").strip() or None
    contractor.updated_by_id = actor_id
    db.session.flush()
    log_audit(
        "project_contractor.create" if is_new else "project_contractor.update",
        "ProjectContractor",
        contractor.id,
        old_values=old_values,
        new_values=contractor_snapshot(contractor),
    )
    return contractor


def archive_contractor(contractor, *, actor_id=None):
    if ProjectContractorAssignment.query.filter_by(
        contractor_id=contractor.id,
        status=ProjectContractorAssignmentStatus.ACTIVE.value,
    ).first():
        raise ValueError("Không thể lưu trữ nhà thầu khi còn assignment đang hoạt động.")
    if not contractor.is_active:
        return contractor
    old_values = contractor_snapshot(contractor)
    contractor.is_active = False
    contractor.archived_at = datetime.utcnow()
    contractor.updated_by_id = actor_id
    log_audit("project_contractor.archive", "ProjectContractor", contractor.id, old_values=old_values, new_values=contractor_snapshot(contractor))
    return contractor


def restore_contractor(contractor, *, actor_id=None):
    if contractor.is_active:
        return contractor
    if not contractor_name_is_available(contractor.name, contractor.id):
        raise ValueError("Không thể khôi phục vì tên nhà thầu đã được dùng.")
    old_values = contractor_snapshot(contractor)
    contractor.is_active = True
    contractor.archived_at = None
    contractor.updated_by_id = actor_id
    log_audit("project_contractor.restore", "ProjectContractor", contractor.id, old_values=old_values, new_values=contractor_snapshot(contractor))
    return contractor


def assign_contractor(*, project, contractor, role, status, started_on=None, note=None, actor_id=None):
    if project.deleted_at is not None or project.status != "active":
        raise ValueError("Chỉ có thể gán nhà thầu cho dự án đang hoạt động.")
    if not contractor.is_active:
        raise ValueError("Không thể gán nhà thầu đã lưu trữ.")
    duplicate = ProjectContractorAssignment.query.filter(
        ProjectContractorAssignment.project_id == project.id,
        ProjectContractorAssignment.contractor_id == contractor.id,
        ProjectContractorAssignment.role == role,
        ProjectContractorAssignment.status != ProjectContractorAssignmentStatus.ENDED.value,
    ).first()
    if duplicate:
        raise ValueError("Nhà thầu đã có assignment chưa kết thúc với vai trò này.")
    assignment = ProjectContractorAssignment(
        project_id=project.id,
        contractor_id=contractor.id,
        role=role,
        status=status,
        started_on=started_on,
        note=(note or "").strip() or None,
        created_by_id=actor_id,
        updated_by_id=actor_id,
    )
    db.session.add(assignment)
    db.session.flush()
    log_audit("project_contractor_assignment.create", "ProjectContractorAssignment", assignment.id, new_values=assignment_snapshot(assignment))
    return assignment


def update_assignment(assignment, *, status, started_on=None, ended_on=None, note=None, actor_id=None):
    if assignment.status == ProjectContractorAssignmentStatus.ENDED.value:
        raise ValueError("Assignment đã kết thúc không thể cập nhật. Hãy tạo assignment mới khi cần.")
    if status == ProjectContractorAssignmentStatus.ENDED.value:
        raise ValueError("Dùng thao tác kết thúc assignment để lưu ngày kết thúc.")
    old_values = assignment_snapshot(assignment)
    assignment.status = status
    assignment.started_on = started_on
    assignment.ended_on = ended_on
    assignment.note = (note or "").strip() or None
    assignment.updated_by_id = actor_id
    if status == ProjectContractorAssignmentStatus.ENDED.value and assignment.ended_on is None:
        assignment.ended_on = date.today()
    log_audit("project_contractor_assignment.update", "ProjectContractorAssignment", assignment.id, old_values=old_values, new_values=assignment_snapshot(assignment))
    return assignment


def end_assignment(assignment, *, ended_on=None, actor_id=None):
    if assignment.status == ProjectContractorAssignmentStatus.ENDED.value:
        return assignment
    old_values = assignment_snapshot(assignment)
    assignment.status = ProjectContractorAssignmentStatus.ENDED.value
    assignment.ended_on = ended_on or date.today()
    assignment.updated_by_id = actor_id
    log_audit("project_contractor_assignment.end", "ProjectContractorAssignment", assignment.id, old_values=old_values, new_values=assignment_snapshot(assignment))
    return assignment
