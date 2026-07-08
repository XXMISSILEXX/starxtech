from app.users import bp


@bp.get("/")
def index():
    return "Users blueprint ready"
