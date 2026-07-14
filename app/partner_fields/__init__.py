from flask import Blueprint

bp = Blueprint("partner_fields", __name__, url_prefix="/partner-fields")

from app.partner_fields import routes  # noqa: E402,F401
