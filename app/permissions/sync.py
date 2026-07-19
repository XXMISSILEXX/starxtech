from app.extensions import db
from app.models import Permission, Role, RolePermission
from app.permissions.registry import DEFAULTS, PERMISSIONS, SYSTEM_ROLES

def sync_registry(apply_defaults=False, reset_defaults=False):
    roles_created = permissions_created = grants_added = 0
    roles = {}
    for code, name in SYSTEM_ROLES.items():
        role = Role.query.filter_by(code=code).first()
        if not role:
            role = Role(code=code, name=name, is_system=True)
            db.session.add(role); roles_created += 1
        else:
            role.name, role.is_system = name, True
        roles[code] = role
    db.session.flush()
    permissions = {}
    for data in PERMISSIONS:
        permission = Permission.query.filter_by(code=data["code"]).first()
        if not permission:
            permission = Permission(**data); db.session.add(permission); permissions_created += 1
        else:
            for key, value in data.items(): setattr(permission, key, value)
        permissions[data["code"]] = permission
    db.session.flush()
    if apply_defaults or reset_defaults:
        for role_code, codes in DEFAULTS.items():
            role = roles[role_code]
            if reset_defaults:
                RolePermission.query.filter_by(role_id=role.id).delete()
            existing = {item.permission_id for item in role.role_permissions} if not reset_defaults else set()
            for code in codes:
                if permissions[code].id not in existing:
                    db.session.add(RolePermission(role_id=role.id, permission_id=permissions[code].id)); grants_added += 1
    db.session.commit()
    return {"roles_created": roles_created, "permissions_created": permissions_created, "grants_added": grants_added,
            "deprecated_orphan": Permission.query.filter_by(is_deprecated=True).count()}
