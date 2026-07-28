import re
import unicodedata
from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from app.audit import log_audit
from app.extensions import db
from app.date_utils import local_today
from app.models import (
    Project,
    ProjectContractor,
    ProjectContractorAssignment,
    ProjectContractorAssignmentStatus,
    ProjectContractorRole,
    ProjectUpdate,
    ProjectUpdateType,
)
from app.project_memberships import (
    accessible_project_ids,
    can_manage_project_scope,
    is_project_admin,
)


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


def can_manage_contractor_assignment_surface(user, project, permission="contractor_assignments.manage"):
    """Check the global action grant and canonical project management scope."""
    return bool(
        user and getattr(user, "is_authenticated", False) and user.is_active
        and user.can(permission)
        and can_manage_project_scope(user, project)
    )


def get_accessible_contractor_for_assignment(user, contractor_id, project):
    """Load an active contractor through the same scope as the assignment picker.

    This deliberately does not use an unrestricted primary-key lookup: a
    submitted ID must be visible in ``accessible_contractors_query`` before it
    can be attached to the managed project.
    """
    if not can_manage_contractor_assignment_surface(user, project):
        return None
    try:
        contractor_id = int(contractor_id)
    except (TypeError, ValueError):
        return None
    if contractor_id <= 0:
        return None
    return accessible_contractors_query(user).filter(ProjectContractor.id == contractor_id).first()


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
        raise ValueError("Tên đối tác đã tồn tại.")
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
        raise ValueError("Không thể lưu trữ đối tác khi còn liên kết đang hoạt động.")
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
        raise ValueError("Không thể khôi phục vì tên đối tác đã được dùng.")
    old_values = contractor_snapshot(contractor)
    contractor.is_active = True
    contractor.archived_at = None
    contractor.updated_by_id = actor_id
    log_audit("project_contractor.restore", "ProjectContractor", contractor.id, old_values=old_values, new_values=contractor_snapshot(contractor))
    return contractor


def assign_contractor(*, project, contractor, role, status, started_on=None, note=None, actor_id=None):
    if project.deleted_at is not None or project.status != "active":
        raise ValueError("Chỉ có thể gán đối tác cho dự án đang hoạt động.")
    if not contractor.is_active:
        raise ValueError("Không thể gán đối tác đã lưu trữ.")
    if role not in {item.value for item in ProjectContractorRole}:
        raise ValueError("Vai trò đối tác không hợp lệ.")
    if status not in {item.value for item in ProjectContractorAssignmentStatus}:
        raise ValueError("Trạng thái đối tác không hợp lệ.")
    if status == ProjectContractorAssignmentStatus.ENDED.value:
        raise ValueError("Đối tác mới không thể ở trạng thái đã kết thúc.")
    duplicate = ProjectContractorAssignment.query.filter(
        ProjectContractorAssignment.project_id == project.id,
        ProjectContractorAssignment.contractor_id == contractor.id,
        ProjectContractorAssignment.role == role,
        ProjectContractorAssignment.status != ProjectContractorAssignmentStatus.ENDED.value,
    ).first()
    if duplicate:
        raise ValueError("Đối tác đã có liên kết chưa kết thúc với vai trò này.")
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
    if status not in {item.value for item in ProjectContractorAssignmentStatus}:
        raise ValueError("Trạng thái đối tác không hợp lệ.")
    if started_on and ended_on and ended_on < started_on:
        raise ValueError("Ngày kết thúc không được trước ngày bắt đầu.")
    if status in {
        ProjectContractorAssignmentStatus.ACTIVE.value,
        ProjectContractorAssignmentStatus.PAUSED.value,
    } and ended_on is not None:
        raise ValueError("Trạng thái đang hoạt động hoặc tạm dừng không được có ngày kết thúc. Hãy xóa ngày kết thúc trước khi lưu.")
    old_values = assignment_snapshot(assignment)
    assignment.status = status
    assignment.started_on = started_on
    assignment.ended_on = ended_on
    assignment.note = (note or "").strip() or None
    assignment.updated_by_id = actor_id
    log_audit("project_contractor_assignment.update", "ProjectContractorAssignment", assignment.id, old_values=old_values, new_values=assignment_snapshot(assignment))
    return assignment


def end_assignment(assignment, *, ended_on=None, actor_id=None):
    if assignment.status == ProjectContractorAssignmentStatus.ENDED.value:
        return assignment
    old_values = assignment_snapshot(assignment)
    assignment.status = ProjectContractorAssignmentStatus.ENDED.value
    if assignment.started_on and ended_on and ended_on < assignment.started_on:
        raise ValueError("Ngày kết thúc không được trước ngày bắt đầu.")
    assignment.ended_on = ended_on
    assignment.updated_by_id = actor_id
    log_audit("project_contractor_assignment.end", "ProjectContractorAssignment", assignment.id, old_values=old_values, new_values=assignment_snapshot(assignment))
    return assignment


def updates_query(*, project_id=None, assignment_id=None, update_type=None, include_deleted=False):
    query = ProjectUpdate.query
    if not include_deleted:
        query = query.filter(ProjectUpdate.deleted_at.is_(None))
    if project_id is not None:
        query = query.filter(ProjectUpdate.project_id == project_id)
    if assignment_id is not None:
        query = query.filter(ProjectUpdate.contractor_assignment_id == assignment_id)
    if update_type:
        query = query.filter(ProjectUpdate.update_type == update_type)
    return query.options(
        joinedload(ProjectUpdate.created_by),
        joinedload(ProjectUpdate.contractor_assignment).joinedload(ProjectContractorAssignment.contractor),
    ).order_by(ProjectUpdate.update_date.desc(), ProjectUpdate.created_at.desc(), ProjectUpdate.id.desc())


def update_snapshot(update):
    return {
        "project_id": update.project_id,
        "contractor_assignment_id": update.contractor_assignment_id,
        "update_type": update.update_type,
        "title": update.title,
        "content": update.content,
        "update_date": update.update_date.isoformat(),
        "deleted_at": update.deleted_at.isoformat() if update.deleted_at else None,
    }


def validate_update_values(*, project, assignment, update_type, title, content, update_date):
    if project.deleted_at is not None or project.status != "active":
        raise ValueError("Chỉ có thể thêm cập nhật cho dự án đang hoạt động.")
    if update_type not in {item.value for item in ProjectUpdateType}:
        raise ValueError("Loại cập nhật không hợp lệ.")
    if not title or len(title.strip()) > 255:
        raise ValueError("Tiêu đề là bắt buộc và tối đa 255 ký tự.")
    if not content or len(content.strip()) > 10000:
        raise ValueError("Nội dung là bắt buộc và tối đa 10000 ký tự.")
    if update_date > local_today():
        raise ValueError("Ngày cập nhật không được lớn hơn ngày hôm nay.")
    if assignment is not None:
        if assignment.project_id != project.id:
            raise ValueError("Đối tác không thuộc dự án này.")
        if assignment.status == ProjectContractorAssignmentStatus.ENDED.value:
            raise ValueError("Không thể thêm cập nhật cho đối tác đã kết thúc.")
        if not assignment.contractor.is_active:
            raise ValueError("Không thể thêm cập nhật cho đối tác đã lưu trữ.")


def create_project_update(*, project, assignment=None, update_type, title, content, update_date, actor_id):
    validate_update_values(project=project, assignment=assignment, update_type=update_type, title=title, content=content, update_date=update_date)
    update = ProjectUpdate(project_id=project.id, contractor_assignment_id=assignment.id if assignment else None,
                           update_type=update_type, title=title.strip(), content=content.strip(), update_date=update_date,
                           created_by_id=actor_id)
    db.session.add(update)
    db.session.flush()
    log_audit("project_update.create", "ProjectUpdate", update.id, new_values=update_snapshot(update))
    return update


def edit_project_update(update, *, update_type, title, content, update_date, actor_id):
    old_values = update_snapshot(update)
    validate_update_values(project=update.project, assignment=update.contractor_assignment, update_type=update_type, title=title, content=content, update_date=update_date)
    update.update_type, update.title, update.content, update.update_date = update_type, title.strip(), content.strip(), update_date
    update.updated_by_id = actor_id
    log_audit("project_update.update", "ProjectUpdate", update.id, old_values=old_values, new_values=update_snapshot(update))
    return update


def soft_delete_project_update(update, *, actor_id):
    if update.deleted_at is not None:
        return update
    old_values = update_snapshot(update)
    update.deleted_at = datetime.utcnow()
    update.updated_by_id = actor_id
    log_audit("project_update.delete", "ProjectUpdate", update.id, old_values=old_values, new_values=update_snapshot(update))
    return update
