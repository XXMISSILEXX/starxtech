import re
import unicodedata

from sqlalchemy import or_

from app.extensions import db
from app.models import Customer, Project
from app.project_memberships import (
    accessible_project_ids,
    can_manage_project_scope,
    is_project_admin,
)


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
    """Whether a user has management authority over a customer.

    A customer is managed through every active project currently owned by that
    customer.  Read visibility of those projects is deliberately insufficient.
    Empty customers have no project-scoped management surface, so only the
    existing global project-scope authority may manage them.
    """
    if not user or not getattr(user, "is_authenticated", False) or not user.is_active or not customer:
        return False
    if is_project_admin(user) or user.can("projects.scope_all"):
        return True
    projects = Project.query.filter(
        Project.customer_id == customer.id,
        Project.deleted_at.is_(None),
    ).all()
    project_ids = [project.id for project in projects]
    if not project_ids:
        return False
    return all(can_manage_project_scope(user, project) for project in projects)


def active_customer_choices(user):
    return accessible_customers_query(user).order_by(Customer.name.asc()).all()


def active_manageable_customer_choices(user):
    """Return active, non-archived customers the actor can administer.

    Customer mutations affect project grouping, so read access alone is not
    sufficient for a choice in a mutation form.
    """
    customers = (
        accessible_customers_query(user)
        .filter(Customer.archived_at.is_(None))
        .order_by(Customer.name.asc())
        .all()
    )
    return [customer for customer in customers if can_manage_customer(user, customer)]


def manageable_unclassified_projects(user):
    """Return active projects in the actor's management scope without a customer."""
    projects = (
        Project.query.filter(
            Project.customer_id.is_(None),
            Project.deleted_at.is_(None),
        )
        .order_by(Project.code.asc())
        .all()
    )
    return [project for project in projects if can_manage_project_scope(user, project)]


def customer_name_is_available(name, customer_id=None):
    normalized_name = normalize_customer_name(name)
    query = Customer.query.filter(
        Customer.normalized_name == normalized_name,
        Customer.is_active.is_(True),
    )
    if customer_id is not None:
        query = query.filter(Customer.id != customer_id)
    return bool(normalized_name) and query.first() is None
