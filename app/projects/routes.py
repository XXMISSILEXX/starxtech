from app.projects import bp


@bp.get("/")
def index():
    return "Projects blueprint ready"
