from flask import Blueprint

bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")
api_bp = Blueprint("dashboard_api", __name__, url_prefix="/api/dashboard")

from app.dashboard import routes  # noqa: E402,F401
