from app.attachments import bp


@bp.get("/")
def index():
    return "Attachments blueprint ready"
