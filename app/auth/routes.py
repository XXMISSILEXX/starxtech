from app.auth import bp


@bp.get("/login")
def login():
    return "Auth blueprint ready"
