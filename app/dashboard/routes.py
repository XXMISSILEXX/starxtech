from flask import render_template

from app.dashboard import bp


@bp.get("/")
def index():
    return render_template("dashboard/index.html")
