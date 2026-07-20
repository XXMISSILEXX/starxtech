from flask import Blueprint

bp = Blueprint("project_documents", __name__, url_prefix="/project-documents")

from app.project_documents import routes  # noqa: E402,F401
