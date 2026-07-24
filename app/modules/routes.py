from flask import abort, flash, redirect, render_template, session, url_for
from flask_login import current_user

from app.auth.permissions import can_access_partners_module, can_access_reports_module
from app.modules import bp
from app.modules.services import get_accessible_modules


@bp.get("/")
def index():
    return render_template("modules/index.html", modules=get_accessible_modules(current_user))


@bp.get("/select/reports")
def select_reports():
    if not can_access_reports_module(current_user):
        abort(403)
    session["active_module"] = "reports"
    flash("Đã chuyển sang phân hệ Báo cáo hàng ngày.", "success")
    return redirect(url_for("dashboard.index"))


@bp.get("/select/partners")
def select_partners():
    if not can_access_partners_module(current_user):
        abort(403)
    session["active_module"] = "partners"
    flash("Đã chuyển sang phân hệ Quản lý đối tác.", "success")
    return redirect(url_for("partners.dashboard"))


@bp.get("/select/admin")
def select_admin():
    if not any(current_user.can(code) for code in ("users.view", "roles.view", "projects.view", "storage.dashboard.view", "settings.branding.view")):
        abort(403)
    session["active_module"] = "admin"
    return redirect(url_for("admin.users_index") if current_user.can("users.view") else url_for("admin.branding"))
