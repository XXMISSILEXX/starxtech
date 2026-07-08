from datetime import datetime, timezone
from urllib.parse import urlsplit

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import or_
from werkzeug.security import generate_password_hash

from app.auth import bp
from app.auth.forms import ChangePasswordForm, LoginForm
from app.extensions import db
from app.models import User


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    form = LoginForm()
    if form.validate_on_submit():
        login_value = form.username_or_email.data.strip()
        user = User.query.filter(
            or_(
                User.username == login_value,
                User.email == login_value,
            )
        ).first()

        if not user or not user.is_active or not user.check_password(form.password.data):
            flash("Invalid username/email or password.", "danger")
            return render_template("auth/login.html", form=form), 401

        user.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.session.commit()
        login_user(user, remember=form.remember.data)
        return redirect(_safe_next_url() or url_for("dashboard.index"))

    return render_template("auth/login.html", form=form)


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash("Current password is incorrect.", "danger")
            return render_template("auth/change_password.html", form=form), 400

        current_user.password_hash = generate_password_hash(form.new_password.data)
        db.session.commit()
        flash("Password changed successfully.", "success")
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
