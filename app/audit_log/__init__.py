from flask import Blueprint

bp = Blueprint("audit_log", __name__, url_prefix="/admin/audit-log")

from app.audit_log import routes  # noqa: E402,F401
