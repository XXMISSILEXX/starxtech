"""Project-scoped membership presets and authorization helpers."""

from sqlalchemy import or_

from app.models import ProjectStatus, ProjectUser, UserRole


CAPABILITY_FIELDS = (
    "can_view_project", "can_view_reports", "can_create_reports",
    "can_edit_own_reports", "can_edit_all_reports", "can_archive_reports",
    "can_view_issues", "can_create_issues", "can_edit_issues",
    "can_close_reopen_issues", "can_manage_report_categories",
    "can_view_documents", "can_upload_documents", "can_edit_documents",
    "can_share_documents", "can_archive_documents", "can_restore_documents",
    "can_view_progress", "can_create_progress_entries", "can_edit_all_progress_entries",
    "can_manage_progress_structure",
)

CAPABILITY_LABELS = {
    "can_view_project": "Xem dự án", "can_view_reports": "Xem báo cáo",
    "can_create_reports": "Tạo báo cáo", "can_edit_own_reports": "Sửa báo cáo của mình",
    "can_edit_all_reports": "Sửa tất cả báo cáo", "can_archive_reports": "Lưu trữ báo cáo",
    "can_view_issues": "Xem vấn đề", "can_create_issues": "Tạo vấn đề",
    "can_edit_issues": "Sửa vấn đề", "can_close_reopen_issues": "Đóng/mở lại vấn đề",
    "can_manage_report_categories": "Quản lý danh mục báo cáo",
    "can_view_documents": "Xem hồ sơ", "can_upload_documents": "Tải lên hồ sơ",
    "can_edit_documents": "Sửa hồ sơ", "can_share_documents": "Chia sẻ hồ sơ",
    "can_archive_documents": "Lưu trữ hồ sơ", "can_restore_documents": "Khôi phục hồ sơ",
    "can_view_progress": "Xem tiến độ thi công",
    "can_create_progress_entries": "Tạo phiếu tiến độ",
    "can_edit_all_progress_entries": "Sửa mọi phiếu tiến độ",
    "can_manage_progress_structure": "Quản lý cấu trúc tiến độ",
}

PROJECT_ROLE_LABELS = {
    "PROJECT_VIEWER": "Người xem dự án", "PROJECT_REPORTER": "Người lập báo cáo",
    "PROJECT_EDITOR": "Người biên tập báo cáo", "PROJECT_DOCUMENT_CONTROLLER": "Quản lý hồ sơ dự án",
    "PROJECT_ISSUE_COORDINATOR": "Điều phối vấn đề", "PROJECT_OWNER": "Chủ trì dự án",
    "CUSTOM": "Tùy chỉnh",
}

PROJECT_ROLE_PRESETS = {
    "PROJECT_VIEWER": {"can_view_project", "can_view_reports", "can_view_issues", "can_view_documents", "can_view_progress"},
    "PROJECT_REPORTER": {"can_view_project", "can_view_reports", "can_create_reports", "can_edit_own_reports", "can_view_issues", "can_view_documents", "can_view_progress", "can_create_progress_entries"},
    "PROJECT_EDITOR": {"can_view_project", "can_view_reports", "can_create_reports", "can_edit_all_reports", "can_view_issues", "can_create_issues", "can_edit_issues", "can_view_documents", "can_view_progress", "can_create_progress_entries", "can_edit_all_progress_entries"},
    "PROJECT_DOCUMENT_CONTROLLER": {"can_view_project", "can_view_reports", "can_view_issues", "can_view_documents", "can_upload_documents", "can_edit_documents", "can_share_documents", "can_view_progress"},
    "PROJECT_ISSUE_COORDINATOR": {"can_view_project", "can_view_reports", "can_view_issues", "can_create_issues", "can_edit_issues", "can_close_reopen_issues", "can_view_documents", "can_view_progress"},
    "PROJECT_OWNER": set(CAPABILITY_FIELDS),
}

# Role codes remain presentation presets; capability flags are the authority
# source.  The levels below only constrain who may assign a named preset.
PROJECT_ROLE_LEVELS = {
    "CUSTOM": 0,
    "PROJECT_VIEWER": 1,
    "PROJECT_REPORTER": 2,
    "PROJECT_DOCUMENT_CONTROLLER": 2,
    "PROJECT_ISSUE_COORDINATOR": 2,
    "PROJECT_EDITOR": 3,
    "PROJECT_OWNER": 4,
}
MANAGE_MEMBERSHIPS_CAPABILITY = "can_manage_report_categories"

ADMIN_ROLE_CODES = {UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value}
VIEWER_ADMIN_CODE = UserRole.VIEWER_ADMIN.value
READ_CAPABILITIES = {"can_view_project", "can_view_reports", "can_view_issues", "can_view_documents", "can_view_progress"}


def has_global_project_scope(user):
    """Whether a custom role may read every project in the Reports scope.

    This is deliberately a scope permission, not a mutation capability.
    Existing write helpers remain governed by active ProjectUser capability flags.
    """
    return bool(user and getattr(user, "is_authenticated", False) and user.is_active and
                user.can("projects.scope_all"))


def active_membership(user, project_id):
    if not user or not getattr(user, "is_authenticated", False) or not user.is_active:
        return None
    try:
        project_id = int(project_id)
    except (TypeError, ValueError):
        return None
    return ProjectUser.query.filter_by(project_id=project_id, user_id=user.id, is_active=True).first()


def is_project_admin(user):
    return bool(user and getattr(user, "is_authenticated", False) and user.is_active and user.role_code in ADMIN_ROLE_CODES)


def is_super_admin(user):
    return bool(
        user and getattr(user, "is_authenticated", False) and user.is_active
        and user.role_code == UserRole.SUPER_ADMIN.value
    )


def is_viewer_admin(user):
    return bool(user and getattr(user, "is_authenticated", False) and user.is_active and user.role_code == VIEWER_ADMIN_CODE)


def user_has_project_capability(user, project_id, capability):
    """Return whether a user has a project capability; flags are canonical."""
    if capability not in CAPABILITY_FIELDS:
        return False
    if is_project_admin(user):
        return True
    if is_viewer_admin(user):
        return capability in READ_CAPABILITIES
    # ``projects.scope_all`` is intentionally only a project-surface scope.
    # It must not turn a broad project reader into a reader of reports, issues,
    # or documents, which each have their own canonical capability.
    if capability == "can_view_project" and has_global_project_scope(user):
        return True
    membership = active_membership(user, project_id)
    return bool(membership and getattr(membership, capability, False))


def has_any_project_capability(user, capabilities):
    if is_project_admin(user) or is_viewer_admin(user):
        return True
    if not user or not getattr(user, "is_authenticated", False) or not user.is_active:
        return False
    return ProjectUser.query.filter(
        ProjectUser.user_id == user.id, ProjectUser.is_active.is_(True),
        or_(*[getattr(ProjectUser, capability).is_(True) for capability in capabilities]),
    ).first() is not None


def accessible_project_ids(user, capabilities=("can_view_project",)):
    if is_project_admin(user) or is_viewer_admin(user):
        return None
    if not user or not getattr(user, "is_authenticated", False) or not user.is_active:
        return []
    capabilities = tuple(capabilities)
    if capabilities == ("can_view_project",) and has_global_project_scope(user):
        return None
    query = ProjectUser.query.filter(ProjectUser.user_id == user.id, ProjectUser.is_active.is_(True))
    for capability in capabilities:
        query = query.filter(getattr(ProjectUser, capability).is_(True))
    return [item.project_id for item in query.all()]


def _is_active_project(project):
    return bool(
        project
        and project.deleted_at is None
        and project.status == ProjectStatus.ACTIVE.value
    )


def project_management_membership(user, project):
    """Return the active membership that grants project-management authority.

    Project membership capabilities are the canonical scoped authority.  A
    global RBAC permission alone never produces this membership.
    """
    if not _is_active_project(project):
        return None
    membership = active_membership(user, project.id)
    if membership and getattr(membership, MANAGE_MEMBERSHIPS_CAPABILITY, False):
        return membership
    return None


def can_manage_project_scope(user, project):
    """Whether ``user`` has management authority over this active project."""
    if not _is_active_project(project):
        return False
    return is_project_admin(user) or project_management_membership(user, project) is not None


def can_manage_project_memberships(user, project):
    """Whether ``user`` may administer memberships on this active project.

    Only SUPER_ADMIN has a global bypass.  Every other actor needs both the
    dangerous global assignment permission and a management-capable membership
    on the same project.
    """
    if not _is_active_project(project):
        return False
    if is_super_admin(user):
        return True
    return bool(
        user and getattr(user, "is_authenticated", False) and user.is_active
        and user.can("project_assignments.manage")
        and project_management_membership(user, project) is not None
    )


def manageable_project_capabilities(user, project):
    """Return the exact capability ceiling the actor may grant on a project."""
    if not can_manage_project_memberships(user, project):
        return set()
    if is_super_admin(user):
        return set(CAPABILITY_FIELDS)
    membership = project_management_membership(user, project)
    return {field for field in CAPABILITY_FIELDS if getattr(membership, field, False)}


def manageable_project_role_level(user, project):
    """Return the highest named project-role preset this actor may assign."""
    if not can_manage_project_memberships(user, project):
        return -1
    if is_super_admin(user):
        return PROJECT_ROLE_LEVELS["PROJECT_OWNER"]
    membership = project_management_membership(user, project)
    return PROJECT_ROLE_LEVELS.get(membership_summary(membership), -1)


def is_owner_equivalent_membership(role_code, capabilities):
    """Identify the owner preset and any custom membership with all powers."""
    return role_code == "PROJECT_OWNER" or set(capabilities) == set(CAPABILITY_FIELDS)


def preset_flags(code):
    return {field: field in PROJECT_ROLE_PRESETS.get(code, set()) for field in CAPABILITY_FIELDS}


def membership_summary(membership):
    enabled = {field for field in CAPABILITY_FIELDS if getattr(membership, field)}
    preset = PROJECT_ROLE_PRESETS.get(membership.project_role_code, set())
    return membership.project_role_code if enabled == preset else "CUSTOM"


def membership_capability_labels(membership):
    return [CAPABILITY_LABELS[field] for field in CAPABILITY_FIELDS if getattr(membership, field)]
