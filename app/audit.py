from flask import has_request_context, request
from flask_login import current_user
from sqlalchemy import func

from app.extensions import db
from app.models import AuditLog


# These groups are the single policy source for the audit-log reader and future
# retention work.  Keep explicit exceptions above the suffix rules: several
# authority actions otherwise look like ordinary mutations or destructive work.
AUDIT_GROUP_DESTRUCTIVE = "destructive"
AUDIT_GROUP_AUTHORITY = "authority"
AUDIT_GROUP_MUTATION = "mutation"
AUDIT_GROUP_SECURITY = "security"
AUDIT_GROUP_DISCLOSURE = "disclosure"
AUDIT_GROUP_RETAIN_FOREVER = "retain_forever"


AUDIT_ACTION_GROUPS = {
    # Authority exceptions must precede suffix rules.
    "project_membership.assign": AUDIT_GROUP_AUTHORITY,
    "project_membership.update": AUDIT_GROUP_AUTHORITY,
    "project_membership.deactivate": AUDIT_GROUP_AUTHORITY,
    "project_user.assign": AUDIT_GROUP_AUTHORITY,
    "project_user.remove": AUDIT_GROUP_AUTHORITY,
    "role.create": AUDIT_GROUP_AUTHORITY,
    "role.permissions.update": AUDIT_GROUP_AUTHORITY,
    "role.permissions.reset_defaults": AUDIT_GROUP_AUTHORITY,
    "user.create": AUDIT_GROUP_AUTHORITY,
    "user.update": AUDIT_GROUP_AUTHORITY,
    "user.activate": AUDIT_GROUP_AUTHORITY,
    "user.reset_password": AUDIT_GROUP_AUTHORITY,
    "document.folder.share": AUDIT_GROUP_AUTHORITY,
    "document.folder.revoke": AUDIT_GROUP_AUTHORITY,
    "company_media.album.share": AUDIT_GROUP_AUTHORITY,
    "company_media.album.revoke": AUDIT_GROUP_AUTHORITY,
    # Non-suffix mutations.
    "company_media.album.cover": AUDIT_GROUP_MUTATION,
    "account.ui_preferences.updated": AUDIT_GROUP_MUTATION,
    "project.customer.move": AUDIT_GROUP_MUTATION,
    "document.folder.move": AUDIT_GROUP_MUTATION,
    "issue.close": AUDIT_GROUP_MUTATION,
    "issue.reopen": AUDIT_GROUP_MUTATION,
    # Security actions include CLI-only seed actions.
    "auth.login_failed": AUDIT_GROUP_SECURITY,
    "user.seed_admin": AUDIT_GROUP_SECURITY,
    "user.seed_admin.update": AUDIT_GROUP_SECURITY,
    # Disclosure actions record access to private originals, not previews.
    "document.file.download": AUDIT_GROUP_DISCLOSURE,
    "company_media.file.download": AUDIT_GROUP_DISCLOSURE,
    "attachment.download": AUDIT_GROUP_DISCLOSURE,
    "bulk_download.create": AUDIT_GROUP_DISCLOSURE,
    # Legacy content-create records remain classified, even though new ones
    # are no longer emitted.  They must not silently fall into the fallback.
    "attachment.create": AUDIT_GROUP_MUTATION,
    "category.create": AUDIT_GROUP_MUTATION,
    "company_media.album.create": AUDIT_GROUP_MUTATION,
    "company_media.file.create": AUDIT_GROUP_MUTATION,
    "construction_progress.entry.create": AUDIT_GROUP_MUTATION,
    "construction_progress.group.create": AUDIT_GROUP_MUTATION,
    "construction_progress.item.create": AUDIT_GROUP_MUTATION,
    "construction_progress.type.create": AUDIT_GROUP_MUTATION,
    "customer.create": AUDIT_GROUP_MUTATION,
    "document.custom_root.create": AUDIT_GROUP_MUTATION,
    "document.file.create": AUDIT_GROUP_MUTATION,
    "document.folder.create": AUDIT_GROUP_MUTATION,
    "issue.create": AUDIT_GROUP_MUTATION,
    "partner.create": AUDIT_GROUP_MUTATION,
    "partner_company.create": AUDIT_GROUP_MUTATION,
    "partner_department.create": AUDIT_GROUP_MUTATION,
    "partner_field.create": AUDIT_GROUP_MUTATION,
    "partner_field_collection.create": AUDIT_GROUP_MUTATION,
    "partner_relationship.create": AUDIT_GROUP_MUTATION,
    "project.create": AUDIT_GROUP_MUTATION,
    "project_contractor.create": AUDIT_GROUP_MUTATION,
    "project_contractor_assignment.create": AUDIT_GROUP_MUTATION,
    "project_update.create": AUDIT_GROUP_MUTATION,
    "report.create": AUDIT_GROUP_MUTATION,
    # Historical action: no emitter produces this anymore.  The compatibility
    # /partners/<id>/deactivate route delegates to archive(), which emits
    # partner.archive, so do not search for a separate deactivate emitter.
    "partner.deactivate": AUDIT_GROUP_DESTRUCTIVE,
}

_AUDIT_SUFFIX_GROUPS = (
    ((".delete", ".archive", ".restore", ".deactivate"), AUDIT_GROUP_DESTRUCTIVE),
    ((".update", ".rename", ".end"), AUDIT_GROUP_MUTATION),
)


def audit_group_for_action(action):
    """Return an audit action group, retaining unknown future actions safely."""
    if action in AUDIT_ACTION_GROUPS:
        return AUDIT_ACTION_GROUPS[action]
    for suffixes, group in _AUDIT_SUFFIX_GROUPS:
        if action.endswith(suffixes):
            return group
    return AUDIT_GROUP_RETAIN_FOREVER


def log_audit(action, entity_type, entity_id=None, old_values=None, new_values=None):
    log = AuditLog(
        actor_user_id=_actor_user_id(),
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_values_json=old_values,
        new_values_json=new_values,
        ip_address=_ip_address(),
        user_agent=_user_agent(),
    )
    _add_with_sqlite_id(log)
    return log


def _actor_user_id():
    if not has_request_context() or not current_user.is_authenticated:
        return None
    return current_user.id


def _ip_address():
    if not has_request_context():
        return None
    return request.headers.get("X-Forwarded-For", request.remote_addr)


def _user_agent():
    if not has_request_context():
        return None
    return request.headers.get("User-Agent")


def _add_with_sqlite_id(instance):
    if getattr(instance, "id", None) is None and db.engine.name == "sqlite":
        max_id = db.session.query(func.max(type(instance).id)).scalar() or 0
        instance.id = max_id + 1
    db.session.add(instance)


audit = log_audit
