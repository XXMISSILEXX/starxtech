import re
import unicodedata

from sqlalchemy import or_

from app.extensions import db
from app.models import Customer, Project
from app.project_memberships import accessible_project_ids, is_project_admin


def normalize_customer_name(value):
    normalized = unicodedata.normalize("NFKC", value or "")
    return re.sub(r"\s+", " ", normalized).strip().casefold()


def accessible_customers_query(user, *, include_archived=False):
    query = Customer.query
    if not include_archived:
        query = query.filter(Customer.is_active.is_(True))

    project_ids = accessible_project_ids(user, ("can_view_project",))
    if project_ids is None:
        return query

    accessible_projects = Project.query.filter(Project.id.in_(project_ids or [0])).subquery()
    return query.filter(
        or_(
            ~Customer.projects.any(),
            Customer.id.in_(db.session.query(accessible_projects.c.customer_id)),
        )
    )


def can_access_customer(user, customer):
    return accessible_customers_query(user, include_archived=True).filter(Customer.id == customer.id).first() is not None


def can_manage_customer(user, customer):
    if is_project_admin(user) or user.can("projects.scope_all"):
        return True
    project_ids = [project.id for project in customer.projects if project.deleted_at is None]
    if not project_ids:
        return True
    visible_ids = accessible_project_ids(user, ("can_view_project",)) or []
    return set(project_ids).issubset(visible_ids)


def active_customer_choices(user):
    return accessible_customers_query(user).order_by(Customer.name.asc()).all()


def customer_name_is_available(name, customer_id=None):
    normalized_name = normalize_customer_name(name)
    query = Customer.query.filter(
        Customer.normalized_name == normalized_name,
        Customer.is_active.is_(True),
    )
    if customer_id is not None:
        query = query.filter(Customer.id != customer_id)
    return bool(normalized_name) and query.first() is None
