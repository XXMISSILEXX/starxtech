from flask import abort, flash, redirect, render_template, session, url_for
from flask_login import current_user

from app.auth.permissions import can_access_partners_module, can_access_project_documents_module, can_access_reports_module
from app.modules import bp


@bp.get("/")
def index():
    return render_template(
        "modules/index.html",
        can_reports=can_access_reports_module(current_user),
        can_partners=can_access_partners_module(current_user),
        can_project_documents=can_access_project_documents_module(current_user),
    )


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
