import logging
from functools import wraps

from flask import abort, g
from flask_login import current_user
from sqlalchemy import select

from app.extensions import db
from app.models import Permission, RolePermission, UserRole

logger = logging.getLogger(__name__)
DENY_MESSAGE = "Bạn không có quyền truy cập chức năng này."

def user_has_permission(user, code):
    if not user or not getattr(user, "is_authenticated", False) or not user.is_active:
        return False
    if user.has_role(UserRole.SUPER_ADMIN.value):
        return True
    cache = getattr(g, "_permission_codes", None)
    cache_key = getattr(g, "_permission_user_id", None)
    if cache is None or cache_key != user.id:
        cache = set(db.session.execute(select(Permission.code).join(RolePermission).where(RolePermission.role_id == user.role_id)).scalars())
        g._permission_codes, g._permission_user_id = cache, user.id
    if code not in cache:
        # Unknown codes are denied too; warning makes registry mistakes visible.
        if db.session.execute(select(Permission.id).where(Permission.code == code)).scalar() is None:
            logger.warning("Unknown permission requested: %s", code)
        return False
    return True

def permission_required(code):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not user_has_permission(current_user, code):
                abort(403, description=DENY_MESSAGE)
            return view(*args, **kwargs)
        return wrapped
    return decorator

def any_permission_required(*codes):
    return _multiple_permission_required(codes, any)

def all_permissions_required(*codes):
    return _multiple_permission_required(codes, all)

def _multiple_permission_required(codes, operation):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not operation(user_has_permission(current_user, code) for code in codes):
                abort(403, description=DENY_MESSAGE)
            return view(*args, **kwargs)
        return wrapped
    return decorator
