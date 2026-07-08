from app.issues import bp


@bp.get("/")
def index():
    return "Issues blueprint ready"
