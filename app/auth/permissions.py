from functools import wraps

from flask import abort, request
from flask_login import current_user

from app.models import ProjectUser, UserRole

ASSIGNED_PROJECT_ROLES = {UserRole.REPORTER.value, UserRole.PROJECT_MANAGER.value}
ADMIN_ROLES = {UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value}
PARTNER_WRITE_ROLES = ADMIN_ROLES | {UserRole.PROJECT_MANAGER.value}
PARTNER_READ_ROLES = PARTNER_WRITE_ROLES | {UserRole.VIEWER_ADMIN.value, UserRole.REPORTER.value}


def role_required(*roles):
    allowed_roles = {role.value if isinstance(role, UserRole) else role for role in roles}

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in allowed_roles:
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
    return bool(user.is_authenticated and user.role in ADMIN_ROLES | {UserRole.VIEWER_ADMIN.value})


def can_write_users(user=None):
    user = user or current_user
    return bool(user.is_authenticated and user.role == UserRole.SUPER_ADMIN.value)


def can_access_reports_module(user=None):
    user = user or current_user
    if not user.is_authenticated:
        return False
    if user.role in ADMIN_ROLES | {UserRole.VIEWER_ADMIN.value}:
        return True
    return user.role in ASSIGNED_PROJECT_ROLES


def can_access_partners_module(user=None):
    user = user or current_user
    return bool(user.is_authenticated and user.role in PARTNER_READ_ROLES)


def permitted_modules(user=None):
    user = user or current_user
    modules = []
    if can_access_reports_module(user):
        modules.append("reports")
    if can_access_partners_module(user):
        modules.append("partners")
    return modules


def can_manage_partner_fields(user=None):
    user = user or current_user
    return bool(user.is_authenticated and user.role in ADMIN_ROLES)


def can_create_partner(user=None):
    user = user or current_user
    return bool(user.is_authenticated and user.role in PARTNER_WRITE_ROLES)


def can_edit_partner(user=None, partner=None):
    if partner is None:
        partner = user
        user = current_user
    user = user or current_user
    return bool(user.is_authenticated and user.role in PARTNER_WRITE_ROLES)


def can_delete_partner(user=None, partner=None):
    if partner is None:
        partner = user
        user = current_user
    user = user or current_user
    return bool(user.is_authenticated and user.role in ADMIN_ROLES)


def can_view_partner(user=None, partner=None):
    if partner is None:
        partner = user
        user = current_user
    user = user or current_user
    return bool(user.is_authenticated and user.role in PARTNER_READ_ROLES)


def can_read_project(project_id):
    if not current_user.is_authenticated:
        return False

    if current_user.role in ADMIN_ROLES | {UserRole.VIEWER_ADMIN.value}:
        return True

    if current_user.role not in ASSIGNED_PROJECT_ROLES:
        return False

    return _is_assigned_to_project(project_id)


def can_write_project(project_id):
    if not current_user.is_authenticated:
        return False

    if current_user.role in ADMIN_ROLES:
        return True

    if current_user.role == UserRole.VIEWER_ADMIN.value:
        return False

    if current_user.role not in ASSIGNED_PROJECT_ROLES:
        return False

    return _is_assigned_to_project(project_id)


def can_manage_project(project_id):
    if not current_user.is_authenticated:
        return False

    if current_user.role in ADMIN_ROLES:
        return True

    if current_user.role == UserRole.PROJECT_MANAGER.value:
        return _is_assigned_to_project(project_id)

    return False


def can_delete_report_for_project(project_id):
    return can_manage_project(project_id)


def can_delete_issue_for_project(project_id):
    return can_manage_project(project_id)


def can_manage_persistent_issues(project_id):
    return can_manage_project(project_id)


def can_create_persistent_issue(project_id=None):
    if not current_user.is_authenticated:
        return False

    if current_user.role in ADMIN_ROLES:
        return True

    if current_user.role == UserRole.PROJECT_MANAGER.value:
        if project_id is None:
            return _has_any_project_assignment()
        return _is_assigned_to_project(project_id)

    return False


def can_edit_persistent_issue(issue):
    return can_write_project(issue.project_id)


def can_delete_persistent_issue(issue):
    return can_delete_issue_for_project(issue.project_id)


def can_manage_categories_for_project(project_id):
    return can_manage_project(project_id)


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


def _is_assigned_to_project(project_id):
    try:
        normalized_project_id = int(project_id)
    except (TypeError, ValueError):
        return False

    return (
        ProjectUser.query.filter_by(
            project_id=normalized_project_id,
            user_id=current_user.id,
        ).first()
        is not None
    )


def _has_any_project_assignment():
    return ProjectUser.query.filter_by(user_id=current_user.id).first() is not None
