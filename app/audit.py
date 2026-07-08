from flask import has_request_context, request
from flask_login import current_user
from sqlalchemy import func

from app.extensions import db
from app.models import AuditLog


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
