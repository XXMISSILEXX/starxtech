from flask import Blueprint

bp = Blueprint("partners", __name__, url_prefix="/partners")

from app.partners import routes  # noqa: E402,F401
