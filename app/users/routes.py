from app.users import bp
from app.auth.permissions import viewer_or_admin_required


@bp.get("/")
@viewer_or_admin_required()
def index():
    return "Users blueprint ready"
