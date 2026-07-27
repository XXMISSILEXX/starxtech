import secrets
import string
from datetime import datetime

from flask import request
from sqlalchemy import func

from app.audit import log_audit
from app.date_utils import parse_iso_date
from app.extensions import db
from app.models import ProjectUser, ReportCategory, User
from app.project_memberships import CAPABILITY_FIELDS, PROJECT_ROLE_PRESETS, preset_flags


def form_bool(name):
    return name in request.form


def optional_text(name):
    value = request.form.get(name, "").strip()
    return value or None


def next_sqlite_id(model):
    if db.engine.name != "sqlite":
        return None

    max_id = db.session.query(func.max(model.id)).scalar() or 0
    return max_id + 1


def add_with_sqlite_id(instance):
    if getattr(instance, "id", None) is None:
        next_id = next_sqlite_id(type(instance))
        if next_id is not None:
            instance.id = next_id

    db.session.add(instance)


def validate_unique_user(username, email=None, user_id=None):
    errors = []
    username_query = User.query.filter(User.username == username)
    if user_id:
        username_query = username_query.filter(User.id != user_id)
    if username_query.first():
        errors.append("Tên đăng nhập đã tồn tại.")

    if email:
        email_query = User.query.filter(User.email == email)
        if user_id:
            email_query = email_query.filter(User.id != user_id)
        if email_query.first():
            errors.append("Email đã tồn tại.")

    return errors


def validate_unique_project_code(project_model, code, project_id=None):
    query = project_model.query.filter(project_model.code == code)
    if project_id:
        query = query.filter(project_model.id != project_id)
    return query.first() is None


def validate_unique_category_name(project_id, name, category_id=None):
    query = ReportCategory.query.filter(
        ReportCategory.project_id == project_id,
        ReportCategory.name == name,
        ReportCategory.deleted_at.is_(None),
    )
    if category_id:
        query = query.filter(ReportCategory.id != category_id)
    return query.first() is None


def temporary_password(length=14):
    # Deliberately include every policy group so administrator resets remain valid.
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "Aa1!" + "".join(secrets.choice(alphabet) for _ in range(max(0, length - 4)))


audit = log_audit


def save_project_memberships(project, form, allowed_user_ids):
    """Update memberships without deleting history; inactive rows can be reactivated."""
    current_assignments = {
        assignment.user_id: assignment for assignment in project.user_assignments
    }
    submitted_ids = form.getlist("member_ids") or form.getlist("reporter_ids")
    wanted_ids = {int(value) for value in submitted_ids if value.isdigit() and int(value) in allowed_user_ids}
    added_ids, removed_ids = [], []
    for user_id in wanted_ids:
        assignment = current_assignments.get(user_id)
        code = form.get(f"membership-{user_id}-project_role_code", "PROJECT_REPORTER")
        if code not in PROJECT_ROLE_PRESETS:
            code = "PROJECT_VIEWER"
        has_explicit_flags = any(f"membership-{user_id}-{field}" in form for field in CAPABILITY_FIELDS)
        flags = ({field: form.get(f"membership-{user_id}-{field}") == "1" for field in CAPABILITY_FIELDS}
                 if has_explicit_flags else preset_flags(code))
        if assignment is None:
            assignment = ProjectUser(project_id=project.id, user_id=user_id)
            add_with_sqlite_id(assignment); added_ids.append(user_id)
        else:
            assignment.is_active = True
        assignment.project_role_code = code
        for field, value in flags.items():
            setattr(assignment, field, value)
        audit("project_membership.assign" if user_id in added_ids else "project_membership.update", "ProjectUser", assignment.id,
              new_values={"project_id": project.id, "user_id": user_id, "project_role_code": code, **flags})
        if user_id in added_ids:
            audit("project_user.assign", "ProjectUser", assignment.id, new_values={"project_id": project.id, "user_id": user_id})
    for user_id, assignment in current_assignments.items():
        if user_id not in wanted_ids and assignment.is_active:
            assignment.is_active = False; removed_ids.append(user_id)
            audit("project_membership.deactivate", "ProjectUser", assignment.id, old_values={"is_active": True}, new_values={"is_active": False})
            audit("project_user.remove", "ProjectUser", assignment.id, old_values={"project_id": project.id, "user_id": user_id})
    return sorted(added_ids), sorted(removed_ids)


def parse_date(value):
    return parse_iso_date(value, field_label="Ngày")
