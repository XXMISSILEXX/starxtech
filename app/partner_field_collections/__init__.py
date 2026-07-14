from flask import Blueprint

bp = Blueprint("partner_field_collections", __name__, url_prefix="/partner-field-collections")

from app.partner_field_collections import routes  # noqa: E402,F401
