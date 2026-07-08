from app.reports import bp


@bp.get("/")
def index():
    return "Reports blueprint ready"
