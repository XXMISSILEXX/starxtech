from flask import abort, flash, redirect, render_template, session, url_for
from flask_login import current_user

from app.auth.permissions import (can_access_admin_module, can_access_partners_module,
    can_access_reports_module)
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
    flash("Đã chuyển sang phân hệ Quản lý dự án.", "success")
    if current_user.can("dashboards.system.view") and current_user.can("projects.scope_all"):
        return redirect(url_for("dashboard.system_dashboard"))
    return redirect(url_for("projects.index"))


@bp.get("/select/partners")
def select_partners():
    if not can_access_partners_module(current_user):
        abort(403)
    session["active_module"] = "partners"
    flash("Đã chuyển sang phân hệ Quản lý đối tác.", "success")
    return redirect(url_for("partners.dashboard"))


@bp.get("/select/admin")
def select_admin():
    if not can_access_admin_module(current_user):
        abort(403)
    session["active_module"] = "admin"
    if current_user.can("users.view"):
        return redirect(url_for("admin.users_index"))
    if current_user.can("roles.view"):
        return redirect(url_for("admin.roles_index"))
    if current_user.can("storage.dashboard.view"):
        return redirect(url_for("admin_storage.index"))
    if current_user.can("settings.branding.view"):
        return redirect(url_for("admin.branding"))
    abort(403)
