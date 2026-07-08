from flask import Blueprint

bp = Blueprint("issues", __name__, url_prefix="/issues")

from app.issues import routes  # noqa: E402,F401
