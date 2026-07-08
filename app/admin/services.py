import secrets
import string
from datetime import datetime

from flask import request
from sqlalchemy import func

from app.audit import log_audit
from app.extensions import db
from app.models import ProjectUser, ReportCategory, User


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
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


audit = log_audit


def replace_project_reporters(project, reporter_ids):
    current_assignments = {
        assignment.user_id: assignment for assignment in project.user_assignments
    }
    wanted_ids = set(reporter_ids)
    current_ids = set(current_assignments)

    added_ids = sorted(wanted_ids - current_ids)
    removed_ids = sorted(current_ids - wanted_ids)

    for user_id in added_ids:
        assignment = ProjectUser(
            project_id=project.id,
            user_id=user_id,
            role_in_project="MEMBER",
        )
        add_with_sqlite_id(assignment)
        audit(
            "project_user.assign",
            "ProjectUser",
            None,
            new_values={"project_id": project.id, "user_id": user_id},
        )

    for user_id in removed_ids:
        assignment = current_assignments[user_id]
        audit(
            "project_user.remove",
            "ProjectUser",
            assignment.id,
            old_values={"project_id": project.id, "user_id": user_id},
        )
        db.session.delete(assignment)

    return added_ids, removed_ids


def parse_date(value):
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()
