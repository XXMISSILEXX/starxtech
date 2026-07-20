from functools import wraps

from flask import abort, request
from flask_login import current_user

from app.models import ProjectUser, UserRole

ASSIGNED_PROJECT_ROLES = {UserRole.REPORTER.value, UserRole.PROJECT_MANAGER.value}
ADMIN_ROLES = {UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value}
PARTNER_MODULE_DENY_MESSAGE = "Bạn không có quyền truy cập phân hệ Quản lý đối tác."
REPORTS_MODULE_DENY_MESSAGE = "Bạn không có quyền truy cập phân hệ Báo cáo hàng ngày."


def role_required(*roles):
    allowed_roles = {role.value if isinstance(role, UserRole) else role for role in roles}

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role_code not in allowed_roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def viewer_or_admin_required():
    return role_required(UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value, UserRole.VIEWER_ADMIN.value)


def admin_read_required():
    return viewer_or_admin_required()


def super_admin_required():
    return role_required(UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value)


def can_manage_users(user=None):
    user = user or current_user
    return bool(user.is_authenticated and user.can("users.view"))


def can_write_users(user=None):
    user = user or current_user
    return bool(user.is_authenticated and user.can("users.manage"))


def can_access_reports_module(user=None):
    user = user or current_user
    return bool(user.is_authenticated and user.can("modules.reports.access"))


def reports_module_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not can_access_reports_module():
            abort(403, description=REPORTS_MODULE_DENY_MESSAGE)
        return view(*args, **kwargs)
    return wrapped


def can_access_partners_module(user=None):
    user = user or current_user
    return bool(user.is_authenticated and user.can("modules.partners.access"))


def can_access_project_documents_module(user=None):
    user = user or current_user
    return bool(user.is_authenticated and user.can("modules.project_documents.access"))


def partner_module_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not can_access_partners_module():
            abort(403, description=PARTNER_MODULE_DENY_MESSAGE)
        return view(*args, **kwargs)
    return wrapped


def permitted_modules(user=None):
    user = user or current_user
    modules = []
    if can_access_reports_module(user):
        modules.append("reports")
    if can_access_partners_module(user):
        modules.append("partners")
    if can_access_project_documents_module(user):
        modules.append("project_documents")
    return modules


def can_manage_partner_fields(user=None):
    user = user or current_user
    return bool(user.is_authenticated and user.can("partner_fields.manage"))


def can_create_partner(user=None):
    user = user or current_user
    return bool(user.is_authenticated and user.can("partners.create"))


def can_edit_partner(user=None, partner=None):
    if partner is None:
        partner = user
        user = current_user
    user = user or current_user
    return bool(user.is_authenticated and user.can("partners.edit"))


def can_delete_partner(user=None, partner=None):
    if partner is None:
        partner = user
        user = current_user
    user = user or current_user
    return bool(user.is_authenticated and user.can("partners.delete"))


def can_view_partner(user=None, partner=None):
    if partner is None:
        partner = user
        user = current_user
    user = user or current_user
    return bool(user.is_authenticated and user.can("partners.view"))


def _user_or_current(user=None):
    return user or current_user


def _has_project_scope(user, project_id):
    if not user.is_authenticated:
        return False
    if user.role_code in ADMIN_ROLES | {UserRole.VIEWER_ADMIN.value}:
        return True
    if user.role_code not in ASSIGNED_PROJECT_ROLES:
        return False
    return _is_assigned_to_project(project_id, user)


def _can_in_project(permission, project_id, user=None):
    user = _user_or_current(user)
    return bool(user.is_authenticated and user.can(permission) and _has_project_scope(user, project_id))


def can_read_project(project_id, user=None):
    return _can_in_project("projects.view", project_id, user)


def can_create_report(user, project_id):
    return _can_in_project("reports.create", project_id, user)


def can_view_report(user, report):
    return _can_in_project("reports.view", report.project_id, user)


def can_edit_report(user, report):
    user = _user_or_current(user)
    if not _can_in_project("reports.edit", report.project_id, user):
        return False
    if user.role_code in ADMIN_ROLES:
        return True
    if user.has_role(UserRole.PROJECT_MANAGER.value):
        return True
    return user.has_role(UserRole.REPORTER.value) and report.created_by_user_id == user.id


def can_delete_report(user, report):
    user = _user_or_current(user)
    if not _can_in_project("reports.delete", report.project_id, user):
        return False
    return user.role_code in ADMIN_ROLES or user.has_role(UserRole.PROJECT_MANAGER.value)


def can_view_issue(user, issue):
    return _can_in_project("issues.view", issue.project_id, user)


def can_create_persistent_issue(project_id=None, user=None):
    user = _user_or_current(user)
    if project_id is None:
        return bool(user.is_authenticated and user.can("issues.create") and (
            user.role_code in ADMIN_ROLES or _has_any_project_assignment(user)
        ))
    return _can_in_project("issues.create", project_id, user)


def can_edit_persistent_issue(issue, user=None):
    return _can_in_project("issues.edit", issue.project_id, user)


def can_close_persistent_issue(issue, user=None):
    return _can_in_project("issues.close", issue.project_id, user)


def can_delete_persistent_issue(issue, user=None):
    return _can_in_project("issues.delete", issue.project_id, user)


def can_manage_categories_for_project(project_id, user=None):
    return _can_in_project("categories.manage", project_id, user)


def can_view_categories_for_project(project_id, user=None):
    return _can_in_project("categories.view", project_id, user)


# Compatibility adapters retained for older templates and integrations.
def can_write_project(project_id):
    return _can_in_project("reports.edit", project_id)


def can_manage_project(project_id):
    return _can_in_project("projects.manage", project_id)


def can_delete_report_for_project(project_id):
    return False


def can_delete_issue_for_project(project_id):
    return _can_in_project("issues.delete", project_id)


def can_manage_persistent_issues(project_id):
    return _can_in_project("issues.edit", project_id)


def project_read_required(project_id_arg="project_id"):
    return _project_permission_required(can_read_project, project_id_arg)


def project_write_required(project_id_arg="project_id"):
    return _project_permission_required(can_write_project, project_id_arg)


def project_manage_required(project_id_arg="project_id"):
    return _project_permission_required(can_manage_project, project_id_arg)


def _project_permission_required(checker, project_id_arg):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            project_id = kwargs.get(project_id_arg)
            if project_id is None and request.view_args:
                project_id = request.view_args.get(project_id_arg)

            if project_id is None or not checker(project_id):
                abort(403)

            return view(*args, **kwargs)

        return wrapped

    return decorator


def _is_assigned_to_project(project_id, user=None):
    try:
        normalized_project_id = int(project_id)
    except (TypeError, ValueError):
        return False

    return (
        ProjectUser.query.filter_by(
            project_id=normalized_project_id,
            user_id=(user or current_user).id,
        ).first()
        is not None
    )


def _has_any_project_assignment(user=None):
    return ProjectUser.query.filter_by(user_id=(user or current_user).id).first() is not None
