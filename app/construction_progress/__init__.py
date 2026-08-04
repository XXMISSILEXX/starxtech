from flask import Blueprint

bp = Blueprint("construction_progress", __name__)

from app.construction_progress import routes  # noqa: E402,F401
