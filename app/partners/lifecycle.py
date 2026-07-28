"""Shared lifecycle helpers for Partner and Company business records."""

from flask import abort


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


def require_active_for_generic_edit(record):
    """Keep ordinary edit paths separate from explicit lifecycle transitions.

    A generic form must never be a back door for restoring, reactivating, or
    otherwise changing an archived record.  ``404`` also avoids turning a
    lifecycle state into a distinct detail oracle for callers without the
    dedicated history/restore workflow.
    """
    if record is None or getattr(record, "deleted_at", None) is not None or not getattr(record, "is_active", False):
        abort(404)
    return record
