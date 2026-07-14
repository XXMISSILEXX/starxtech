from flask import Blueprint

bp = Blueprint("partner_companies", __name__, url_prefix="/partner-companies")

from app.partner_companies import routes  # noqa: E402,F401
