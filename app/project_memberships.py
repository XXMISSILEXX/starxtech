"""Project-scoped membership presets and authorization helpers."""

from sqlalchemy import or_

from app.models import ProjectUser, UserRole


CAPABILITY_FIELDS = (
    "can_view_project", "can_view_reports", "can_create_reports",
    "can_edit_own_reports", "can_edit_all_reports", "can_archive_reports",
    "can_view_issues", "can_create_issues", "can_edit_issues",
    "can_close_reopen_issues", "can_manage_report_categories",
    "can_view_documents", "can_upload_documents", "can_edit_documents",
    "can_share_documents", "can_archive_documents", "can_restore_documents",
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
}

PROJECT_ROLE_LABELS = {
    "PROJECT_VIEWER": "Người xem dự án", "PROJECT_REPORTER": "Người lập báo cáo",
    "PROJECT_EDITOR": "Người biên tập báo cáo", "PROJECT_DOCUMENT_CONTROLLER": "Quản lý hồ sơ dự án",
    "PROJECT_ISSUE_COORDINATOR": "Điều phối vấn đề", "PROJECT_OWNER": "Chủ trì dự án",
    "CUSTOM": "Tùy chỉnh",
}

PROJECT_ROLE_PRESETS = {
    "PROJECT_VIEWER": {"can_view_project", "can_view_reports", "can_view_issues", "can_view_documents"},
    "PROJECT_REPORTER": {"can_view_project", "can_view_reports", "can_create_reports", "can_edit_own_reports", "can_view_issues", "can_view_documents"},
    "PROJECT_EDITOR": {"can_view_project", "can_view_reports", "can_create_reports", "can_edit_all_reports", "can_view_issues", "can_create_issues", "can_edit_issues", "can_view_documents"},
    "PROJECT_DOCUMENT_CONTROLLER": {"can_view_project", "can_view_reports", "can_view_issues", "can_view_documents", "can_upload_documents", "can_edit_documents", "can_share_documents"},
    "PROJECT_ISSUE_COORDINATOR": {"can_view_project", "can_view_reports", "can_view_issues", "can_create_issues", "can_edit_issues", "can_close_reopen_issues", "can_view_documents"},
    "PROJECT_OWNER": set(CAPABILITY_FIELDS),
}

ADMIN_ROLE_CODES = {UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value}
VIEWER_ADMIN_CODE = UserRole.VIEWER_ADMIN.value
READ_CAPABILITIES = {"can_view_project", "can_view_reports", "can_view_issues", "can_view_documents"}


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
    query = ProjectUser.query.filter(ProjectUser.user_id == user.id, ProjectUser.is_active.is_(True))
    for capability in capabilities:
        query = query.filter(getattr(ProjectUser, capability).is_(True))
    return [item.project_id for item in query.all()]


def preset_flags(code):
    return {field: field in PROJECT_ROLE_PRESETS.get(code, set()) for field in CAPABILITY_FIELDS}


def membership_summary(membership):
    enabled = {field for field in CAPABILITY_FIELDS if getattr(membership, field)}
    preset = PROJECT_ROLE_PRESETS.get(membership.project_role_code, set())
    return membership.project_role_code if enabled == preset else "CUSTOM"


def membership_capability_labels(membership):
    return [CAPABILITY_LABELS[field] for field in CAPABILITY_FIELDS if getattr(membership, field)]
