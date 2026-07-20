"""Shared lifecycle helpers for Partner and Company business records."""


LIFECYCLE_STATUSES = {"active", "archived", "all"}


def lifecycle_status(args):
    """Return a safe lifecycle filter value from request arguments."""
    value = args.get("status", "active").strip().lower()
    return value if value in LIFECYCLE_STATUSES else "active"


def apply_lifecycle_scope(query, model, status):
    if status == "archived":
        return query.filter(model.deleted_at.isnot(None))
    if status == "all":
        return query
    return query.filter(model.deleted_at.is_(None), model.is_active.is_(True))


def active_record_query(model):
    return model.query.filter(model.deleted_at.is_(None), model.is_active.is_(True))


def archived_record_query(model):
    return model.query.filter(model.deleted_at.isnot(None))
