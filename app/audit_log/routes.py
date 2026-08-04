"""Read-only audit-log views and their URL-backed filters."""
from datetime import datetime, time, timedelta
import json

from flask import abort, render_template, request, url_for
from sqlalchemy import false
from sqlalchemy.orm import joinedload

from app.audit import (
    AUDIT_GROUP_AUTHORITY,
    AUDIT_GROUP_DESTRUCTIVE,
    AUDIT_GROUP_DISCLOSURE,
    AUDIT_GROUP_MUTATION,
    AUDIT_GROUP_RETAIN_FOREVER,
    AUDIT_GROUP_SECURITY,
    LEGACY_CONTENT_CREATE_ACTIONS,
    audit_group_for_action,
)
from app.audit_log import bp
from app.date_utils import parse_iso_date
from app.extensions import db
from app.models import AuditLog, User
from app.permissions.services import permission_required


PER_PAGE = 20
DEFAULT_GROUPS = (
    AUDIT_GROUP_DESTRUCTIVE,
    AUDIT_GROUP_AUTHORITY,
    AUDIT_GROUP_MUTATION,
    AUDIT_GROUP_SECURITY,
)
GROUP_OPTIONS = (
    (AUDIT_GROUP_DESTRUCTIVE, "Phá dữ liệu"),
    (AUDIT_GROUP_AUTHORITY, "Phân quyền"),
    (AUDIT_GROUP_MUTATION, "Thay đổi"),
    (AUDIT_GROUP_SECURITY, "Bảo mật"),
    (AUDIT_GROUP_DISCLOSURE, "Tiết lộ dữ liệu"),
    (AUDIT_GROUP_RETAIN_FOREVER, "Giữ vĩnh viễn"),
)
SENSITIVE_KEY_PARTS = (
    "password", "pass", "token", "secret", "hash", "key", "credential",
    "signature", "api_key", "access_token", "refresh_token",
)
SAFE_SNAPSHOT_KEYS = {"object_key"}
MASKED_VALUE = "••• đã che •••"


def _distinct_values(column):
    return [value for value in db.session.query(column).distinct().order_by(column).all() if value[0] is not None]


def _audit_list_state(source=None):
    source = source or request.args
    state = {
        "group": source.get("group", ""),
        "date_from": source.get("date_from", ""),
        "date_to": source.get("date_to", ""),
        "action": source.get("action", ""),
        "entity_type": source.get("entity_type", ""),
        "actor_user_id": source.get("actor_user_id", ""),
        "hide_legacy_content_creates": source.get("hide_legacy_content_creates", "1") != "0",
        "page": source.get("page", 1),
        "errors": [],
    }
    state["actions"] = [value for value, in _distinct_values(AuditLog.action)]
    state["entity_types"] = [value for value, in _distinct_values(AuditLog.entity_type)]
    state["actors"] = db.session.query(User).join(
        AuditLog, AuditLog.actor_user_id == User.id
    ).distinct().order_by(User.full_name, User.username).all()

    if state["group"]:
        valid_groups = {value for value, _ in GROUP_OPTIONS}
        if state["group"] not in valid_groups:
            state["errors"].append("Nhóm thao tác không hợp lệ.")
            state["group_value"] = ()
        else:
            state["group_value"] = (state["group"],)
    else:
        state["group_value"] = DEFAULT_GROUPS

    try:
        state["date_from_value"] = parse_iso_date(state["date_from"], field_label="Từ ngày")
        state["date_to_value"] = parse_iso_date(state["date_to"], field_label="Đến ngày")
    except ValueError as exc:
        state["errors"].append(str(exc))
        state["date_from_value"] = state["date_to_value"] = None
    if state["date_from_value"] and state["date_to_value"] and state["date_from_value"] > state["date_to_value"]:
        state["errors"].append("Từ ngày không được lớn hơn đến ngày.")

    if state["action"] and state["action"] not in state["actions"]:
        state["errors"].append("Hành động không hợp lệ.")
    if state["entity_type"] and state["entity_type"] not in state["entity_types"]:
        state["errors"].append("Loại đối tượng không hợp lệ.")
    try:
        state["actor_user_id_value"] = int(state["actor_user_id"]) if state["actor_user_id"] else None
    except ValueError:
        state["actor_user_id_value"] = None
        state["errors"].append("Người thực hiện không hợp lệ.")
    try:
        state["page"] = max(1, int(state["page"]))
    except ValueError:
        state["page"] = 1
    state["has_explicit_filters"] = any(state[key] for key in ("group", "date_from", "date_to", "action", "entity_type", "actor_user_id"))
    return state


def _list_url(state, page):
    values = {
        "page": page,
        "hide_legacy_content_creates": "1" if state["hide_legacy_content_creates"] else "0",
    }
    for key in ("group", "date_from", "date_to", "action", "entity_type", "actor_user_id"):
        if state.get(key):
            values[key] = state[key]
    return url_for("audit_log.index", **values)


def _filtered_query(state, *, apply_legacy_content_visibility=True):
    query = AuditLog.query
    grouped_actions = [action for action in state["actions"] if audit_group_for_action(action) in state["group_value"]]
    query = query.filter(AuditLog.action.in_(grouped_actions) if grouped_actions else false())
    if state["date_from_value"]:
        query = query.filter(AuditLog.created_at >= datetime.combine(state["date_from_value"], time.min))
    if state["date_to_value"]:
        query = query.filter(AuditLog.created_at < datetime.combine(state["date_to_value"] + timedelta(days=1), time.min))
    if state["action"]:
        query = query.filter(AuditLog.action == state["action"])
    if state["entity_type"]:
        query = query.filter(AuditLog.entity_type == state["entity_type"])
    if state["actor_user_id_value"] is not None:
        query = query.filter(AuditLog.actor_user_id == state["actor_user_id_value"])
    if apply_legacy_content_visibility and state["hide_legacy_content_creates"]:
        query = query.filter(~AuditLog.action.in_(LEGACY_CONTENT_CREATE_ACTIONS))
    return query


def _is_sensitive_key(key):
    lowered = str(key).lower()
    if lowered in SAFE_SNAPSHOT_KEYS:
        return False
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)


def _redact_snapshot(value):
    if isinstance(value, dict):
        return {
            key: MASKED_VALUE if _is_sensitive_key(key) else _redact_snapshot(child)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [_redact_snapshot(child) for child in value]
    return value


def _snapshot_rows(value):
    """Turn a JSON object into readable key/value rows without raw JSON."""
    if not isinstance(value, dict):
        return None
    rows = []

    def add_values(prefix, item):
        if isinstance(item, dict):
            if not item:
                rows.append((prefix, "{}"))
            for key, child in item.items():
                add_values(f"{prefix}.{key}" if prefix else str(key), child)
        elif isinstance(item, list):
            if not item:
                rows.append((prefix, "[]"))
            for index, child in enumerate(item):
                add_values(f"{prefix}[{index}]", child)
        elif item is None:
            rows.append((prefix, "—"))
        elif isinstance(item, bool):
            rows.append((prefix, "Có" if item else "Không"))
        elif isinstance(item, (str, int, float)):
            rows.append((prefix, str(item)))
        else:
            rows.append((prefix, json.dumps(item, ensure_ascii=False, default=str)))

    for key, child in _redact_snapshot(value).items():
        add_values(str(key), child)
    return rows


@bp.get("")
@bp.get("/")
@permission_required("audit_logs.view")
def index():
    state = _audit_list_state()
    rows, total, legacy_hidden_total = [], 0, 0
    if not state["errors"]:
        if state["hide_legacy_content_creates"]:
            legacy_hidden_total = _filtered_query(state, apply_legacy_content_visibility=False).filter(
                AuditLog.action.in_(LEGACY_CONTENT_CREATE_ACTIONS)
            ).order_by(None).count()
        query = _filtered_query(state)
        total = query.order_by(None).count()
        rows = query.options(joinedload(AuditLog.actor)).order_by(
            AuditLog.created_at.desc(), AuditLog.id.desc()
        ).offset((state["page"] - 1) * PER_PAGE).limit(PER_PAGE).all()
    return render_template(
        "audit_log/index.html",
        audit_logs=rows,
        audit_total=total,
        audit_page_size=PER_PAGE,
        audit_legacy_hidden_total=legacy_hidden_total,
        audit_state=state,
        audit_groups=GROUP_OPTIONS,
        audit_group_for_action=audit_group_for_action,
        page_url=lambda page: _list_url(state, page),
    )


@bp.get("/<int:audit_log_id>")
@permission_required("audit_logs.view")
def detail(audit_log_id):
    record = AuditLog.query.options(joinedload(AuditLog.actor)).filter_by(id=audit_log_id).first()
    if record is None:
        abort(404)
    return render_template(
        "audit_log/detail.html",
        audit_log=record,
        audit_group=audit_group_for_action(record.action),
        old_value_rows=_snapshot_rows(record.old_values_json),
        new_value_rows=_snapshot_rows(record.new_values_json),
    )
