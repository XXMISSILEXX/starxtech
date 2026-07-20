from app.users import bp
from app.permissions.services import permission_required


@bp.get("/")
@permission_required("users.view")
def index():
    return "Users blueprint ready"
