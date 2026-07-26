from flask import Blueprint


bp = Blueprint("project_operations", __name__)

from app.project_operations import routes  # noqa: E402,F401
