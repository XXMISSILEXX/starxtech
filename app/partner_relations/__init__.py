from flask import Blueprint

bp = Blueprint("partner_relations", __name__, url_prefix="/partner-relations")

from app.partner_relations import routes  # noqa: E402,F401
