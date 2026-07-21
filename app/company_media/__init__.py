from flask import Blueprint
bp = Blueprint("company_media", __name__, url_prefix="/company-media")
from app.company_media import routes  # noqa
