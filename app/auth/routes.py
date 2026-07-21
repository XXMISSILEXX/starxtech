from datetime import datetime, timezone
from urllib.parse import urlsplit

from flask import current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import or_
from werkzeug.security import generate_password_hash

from app.auth import bp
from app.auth.forms import ChangePasswordForm, LoginForm
from app.auth.permissions import permitted_modules
from app.extensions import db
from app.extensions import limiter
from app.audit import log_audit
from app.models import User


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit(lambda: current_app.config.get("RATELIMIT_LOGIN_LIMIT", "5 per minute"), methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(_post_login_redirect())

    form = LoginForm()
    if form.validate_on_submit():
        login_value = form.username_or_email.data.strip()
        user = User.query.filter(
            or_(
                User.username == login_value,
                User.email == login_value,
            )
        ).first()

        if not user or not user.check_password(form.password.data):
            log_audit("auth.login_failed", "User", user.id if user else None, new_values={"login": login_value})
            db.session.commit()
            flash("Tên đăng nhập/email hoặc mật khẩu không đúng.", "danger")
            return render_template("auth/login.html", form=form), 401

        if not user.is_active:
            flash("Tài khoản của bạn đã bị vô hiệu hóa. Vui lòng liên hệ quản trị viên.", "danger")
            return render_template("auth/login.html", form=form), 403

        user.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.session.commit()
        login_user(user, remember=form.remember.data)
        return redirect(_safe_next_url() or _post_login_redirect(user))

    return render_template("auth/login.html", form=form)


@bp.post("/logout")
@login_required
def logout():
    session.pop("active_module", None)
    logout_user()
    flash("Bạn đã đăng xuất.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash("Mật khẩu hiện tại không đúng.", "danger")
            return render_template("auth/change_password.html", form=form), 400

        current_user.password_hash = generate_password_hash(form.new_password.data)
        db.session.commit()
        flash("Đã đổi mật khẩu thành công.", "success")
        return redirect(url_for("dashboard.index"))

    return render_template("auth/change_password.html", form=form)


def _safe_next_url():
    next_url = request.args.get("next")
    if not next_url:
        return None

    parsed = urlsplit(next_url)
    if parsed.scheme or parsed.netloc or not next_url.startswith("/"):
        return None

    return next_url


def _post_login_redirect(user=None):
    user = user or current_user
    modules = permitted_modules(user)
    if len(modules) > 1:
        session.pop("active_module", None)
        return url_for("modules.index")
    if modules == ["partners"]:
        session["active_module"] = "partners"
        return url_for("partners.dashboard")
    if modules == ["company_media"]:
        session["active_module"] = "company_media"
        return url_for("company_media.index")
    if modules == ["project_documents"]:
        session["active_module"] = "project_documents"
        return url_for("project_documents.index")
    if not modules:
        session.pop("active_module", None)
        return url_for("modules.index")
    session["active_module"] = "reports"
    return url_for("dashboard.index")
