from functools import wraps

from flask import abort, request
from flask_login import current_user

from app.models import ProjectStatus, UserRole
from app.project_memberships import is_project_admin, is_viewer_admin, user_has_project_capability

ADMIN_ROLES = {UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value}
PARTNER_MODULE_DENY_MESSAGE = "Bạn không có quyền truy cập phân hệ Quản lý đối tác."
REPORTS_MODULE_DENY_MESSAGE = "Bạn không có quyền truy cập phân hệ Quản lý dự án."


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
    from app.project_memberships import has_any_project_capability
    return bool(user.is_authenticated and user.is_active and (
        user.can("modules.reports.access") or is_project_admin(user) or is_viewer_admin(user) or
        has_any_project_capability(user, ("can_view_reports", "can_create_reports"))))


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
    from app.project_memberships import has_any_project_capability
    return bool(user.is_authenticated and user.is_active and (
        is_project_admin(user) or is_viewer_admin(user) or user.can("modules.project_documents.access") or
        has_any_project_capability(user, ("can_view_documents", "can_upload_documents"))))
def can_access_company_media_module(user=None):
    user = user or current_user
    from app.company_media.permissions import access
    return access(user)


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
    if can_access_company_media_module(user):
        modules.append("company_media")
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


def can_read_project(project_id, user=None):
    return user_has_project_capability(_user_or_current(user), project_id, "can_view_project")


def can_create_report(user, project_id):
    return user_has_project_capability(_user_or_current(user), project_id, "can_create_reports")


def project_accepts_report_mutation(project):
    """The canonical lifecycle gate for every report write path.

    Archived, inactive, and soft-deleted projects retain historical read rules,
    but cannot be changed through a report endpoint (including upload and
    attachment endpoints).
    """
    return bool(
        project
        and getattr(project, "deleted_at", None) is None
        and getattr(project, "status", None) == ProjectStatus.ACTIVE.value
    )


def can_view_report(user, report):
    return user_has_project_capability(_user_or_current(user), report.project_id, "can_view_reports")


def can_edit_report(user, report):
    user = _user_or_current(user)
    return bool(is_project_admin(user) or user_has_project_capability(user, report.project_id, "can_edit_all_reports") or
                (report.created_by_user_id == user.id and user_has_project_capability(user, report.project_id, "can_edit_own_reports")))


def can_delete_report(user, report):
    user = _user_or_current(user)
    return user_has_project_capability(user, report.project_id, "can_archive_reports")


def can_delete_report_attachment(user, attachment):
    """Attachment deletion needs both report scope and its dangerous grant."""
    user = _user_or_current(user)
    report = getattr(getattr(attachment, "section", None), "daily_report", None)
    return bool(
        user
        and getattr(attachment, "deleted_at", None) is None
        and report is not None
        and can_edit_report(user, report)
        and user.can("report_attachments.delete")
    )


def can_view_issue(user, issue):
    return user_has_project_capability(_user_or_current(user), issue.project_id, "can_view_issues")


def can_create_persistent_issue(project_id=None, user=None):
    user = _user_or_current(user)
    if project_id is None:
        from app.project_memberships import has_any_project_capability
        return has_any_project_capability(user, ("can_create_issues",))
    return user_has_project_capability(user, project_id, "can_create_issues")


def can_edit_persistent_issue(issue, user=None):
    return user_has_project_capability(_user_or_current(user), issue.project_id, "can_edit_issues")


def can_close_persistent_issue(issue, user=None):
    return user_has_project_capability(_user_or_current(user), issue.project_id, "can_close_reopen_issues")


def can_delete_persistent_issue(issue, user=None):
    user = _user_or_current(user)
    return bool(
        getattr(issue, "deleted_at", None) is None
        and can_edit_persistent_issue(issue, user)
        and user.can("issues.delete")
    )


def can_manage_categories_for_project(project_id, user=None):
    return user_has_project_capability(_user_or_current(user), project_id, "can_manage_report_categories")


def can_view_categories_for_project(project_id, user=None):
    return user_has_project_capability(_user_or_current(user), project_id, "can_view_project")


def can_view_project_progress(project_id, user=None):
    return user_has_project_capability(_user_or_current(user), project_id, "can_view_progress")


def can_create_progress_entry(project_id, user=None):
    return user_has_project_capability(_user_or_current(user), project_id, "can_create_progress_entries")


def can_manage_progress_structure(project_id, user=None):
    return user_has_project_capability(_user_or_current(user), project_id, "can_manage_progress_structure")


def can_edit_progress_entry(entry, user=None):
    user = _user_or_current(user)
    return bool(
        entry
        and (
            is_project_admin(user)
            or user_has_project_capability(user, entry.project_id, "can_edit_all_progress_entries")
            or (
                entry.created_by_id == user.id
                and user_has_project_capability(user, entry.project_id, "can_create_progress_entries")
            )
        )
    )


# Compatibility adapters retained for older templates and integrations.
def can_write_project(project_id):
    return user_has_project_capability(current_user, project_id, "can_edit_all_reports")


def can_manage_project(project_id):
    return user_has_project_capability(current_user, project_id, "can_manage_report_categories")


def can_delete_report_for_project(project_id):
    return False


def can_delete_issue_for_project(project_id):
    return bool(
        user_has_project_capability(current_user, project_id, "can_edit_issues")
        and current_user.can("issues.delete")
    )


def can_manage_persistent_issues(project_id):
    return user_has_project_capability(current_user, project_id, "can_edit_issues")


def project_read_required(project_id_arg="project_id"):
    return _project_permission_required(can_read_project, project_id_arg)


def project_write_required(project_id_arg="project_id"):
    return _project_permission_required(can_write_project, project_id_arg)


def project_manage_required(project_id_arg="project_id"):
    return _project_permission_required(can_manage_project, project_id_arg)


def progress_read_required(project_id_arg="project_id"):
    return _project_permission_required(can_view_project_progress, project_id_arg)


def progress_entry_required(project_id_arg="project_id"):
    return _project_permission_required(can_create_progress_entry, project_id_arg)


def progress_structure_required(project_id_arg="project_id"):
    return _project_permission_required(can_manage_progress_structure, project_id_arg)


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
