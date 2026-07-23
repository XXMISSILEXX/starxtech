from flask import Blueprint

bp = Blueprint("admin_storage", __name__, url_prefix="/admin/storage")

from app.admin_storage import routes  # noqa: E402,F401
