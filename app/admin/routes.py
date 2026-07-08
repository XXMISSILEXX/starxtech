from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from werkzeug.security import generate_password_hash

from app.admin import bp
from app.admin.services import (
    add_with_sqlite_id,
    audit,
    form_bool,
    optional_text,
    parse_date,
    replace_project_reporters,
    temporary_password,
    validate_unique_category_name,
    validate_unique_project_code,
    validate_unique_user,
)
from app.auth.permissions import admin_read_required, can_manage_categories_for_project, super_admin_required
from app.extensions import db
from app.models import Project, ProjectStatus, ReportCategory, User, UserRole


@bp.get("/")
@admin_read_required()
def index():
    return redirect(url_for("admin.users_index"))


@bp.get("/users")
@admin_read_required()
def users_index():
    users = User.query.order_by(User.full_name.asc()).all()
    return render_template("admin/users/index.html", users=users)


@bp.route("/users/new", methods=["GET", "POST"])
@admin_read_required()
def users_new():
    if request.method == "POST":
        _require_super_admin_post()
        return _save_user()

    return render_template(
        "admin/users/form.html",
        user=None,
        roles=[role.value for role in UserRole],
    )


@bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@admin_read_required()
def users_edit(user_id):
    user = User.query.get_or_404(user_id)
    if request.method == "POST":
        _require_super_admin_post()
        return _save_user(user)

    return render_template(
        "admin/users/form.html",
        user=user,
        roles=[role.value for role in UserRole],
    )


@bp.post("/users/<int:user_id>/deactivate")
@super_admin_required()
def users_deactivate(user_id):
    user = User.query.get_or_404(user_id)
    old_values = {"is_active": user.is_active}
    user.is_active = False
    audit("user.deactivate", "User", user.id, old_values, {"is_active": user.is_active})
    db.session.commit()
    flash("Đã vô hiệu hóa người dùng.", "success")
    return redirect(url_for("admin.users_index"))


@bp.post("/users/<int:user_id>/activate")
@super_admin_required()
def users_activate(user_id):
    user = User.query.get_or_404(user_id)
    old_values = {"is_active": user.is_active}
    user.is_active = True
    audit("user.activate", "User", user.id, old_values, {"is_active": user.is_active})
    db.session.commit()
    flash("Đã kích hoạt người dùng.", "success")
    return redirect(url_for("admin.users_index"))


@bp.post("/users/<int:user_id>/reset-password")
@super_admin_required()
def users_reset_password(user_id):
    user = User.query.get_or_404(user_id)
    password = temporary_password()
    user.password_hash = generate_password_hash(password)
    audit("user.reset_password", "User", user.id, new_values={"username": user.username})
    db.session.commit()
    flash(f"Mật khẩu tạm cho {user.username}: {password}", "warning")
    return redirect(url_for("admin.users_index"))


@bp.get("/projects")
@admin_read_required()
def projects_index():
    projects = Project.query.order_by(Project.code.asc()).all()
    return render_template("admin/projects/index.html", projects=projects)


@bp.route("/projects/new", methods=["GET", "POST"])
@admin_read_required()
def projects_new():
    if request.method == "POST":
        _require_super_admin_post()
        return _save_project()

    return render_template(
        "admin/projects/form.html",
        project=None,
        statuses=[status.value for status in ProjectStatus],
    )


@bp.route("/projects/<int:project_id>/edit", methods=["GET", "POST"])
@admin_read_required()
def projects_edit(project_id):
    project = Project.query.get_or_404(project_id)
    if request.method == "POST":
        _require_super_admin_post()
        return _save_project(project)

    return render_template(
        "admin/projects/form.html",
        project=project,
        statuses=[status.value for status in ProjectStatus],
    )


@bp.post("/projects/<int:project_id>/archive")
@super_admin_required()
def projects_archive(project_id):
    project = Project.query.get_or_404(project_id)
    old_values = {"status": project.status}
    project.status = ProjectStatus.ARCHIVED.value
    audit("project.archive", "Project", project.id, old_values, {"status": project.status})
    db.session.commit()
    flash("Đã lưu trữ dự án.", "success")
    return redirect(url_for("admin.projects_index"))


@bp.route("/projects/<int:project_id>/reporters", methods=["GET", "POST"])
@admin_read_required()
def projects_reporters(project_id):
    project = Project.query.get_or_404(project_id)
    reporters = (
        User.query.filter(
            User.role.in_([UserRole.REPORTER.value, UserRole.PROJECT_MANAGER.value]),
            User.is_active.is_(True),
        )
        .order_by(User.full_name.asc())
        .all()
    )

    if request.method == "POST":
        _require_super_admin_post()
        allowed_ids = {reporter.id for reporter in reporters}
        reporter_ids = {
            int(user_id)
            for user_id in request.form.getlist("reporter_ids")
            if user_id.isdigit() and int(user_id) in allowed_ids
        }
        added_ids, removed_ids = replace_project_reporters(project, reporter_ids)
        db.session.commit()
        flash(
            f"Đã cập nhật phân quyền dự án. Thêm {len(added_ids)}, gỡ {len(removed_ids)}.",
            "success",
        )
        return redirect(url_for("admin.projects_reporters", project_id=project.id))

    assigned_ids = {assignment.user_id for assignment in project.user_assignments}
    return render_template(
        "admin/projects/reporters.html",
        project=project,
        reporters=reporters,
        assigned_ids=assigned_ids,
    )


@bp.route("/projects/<int:project_id>/categories", methods=["GET", "POST"])
def categories_index(project_id):
    project = Project.query.get_or_404(project_id)
    _require_can_view_categories(project.id)
    if request.method == "POST":
        _require_can_manage_categories(project.id)
        return _save_category(project)

    categories = (
        ReportCategory.query.filter(
            ReportCategory.project_id == project.id,
            ReportCategory.deleted_at.is_(None),
        )
        .order_by(ReportCategory.sort_order.asc(), ReportCategory.name.asc())
        .all()
    )
    return render_template(
        "admin/categories/index.html",
        project=project,
        categories=categories,
        can_manage=can_manage_categories_for_project(project.id),
    )


@bp.route("/projects/<int:project_id>/categories/<int:category_id>/edit", methods=["GET", "POST"])
def categories_edit(project_id, category_id):
    project = Project.query.get_or_404(project_id)
    _require_can_view_categories(project.id)
    category = ReportCategory.query.filter(
        ReportCategory.id == category_id,
        ReportCategory.project_id == project.id,
        ReportCategory.deleted_at.is_(None),
    ).first_or_404()
    if request.method == "POST":
        _require_can_manage_categories(project.id)
        return _save_category(project, category)

    categories = (
        ReportCategory.query.filter(
            ReportCategory.project_id == project.id,
            ReportCategory.deleted_at.is_(None),
        )
        .order_by(ReportCategory.sort_order.asc(), ReportCategory.name.asc())
        .all()
    )
    return render_template(
        "admin/categories/index.html",
        project=project,
        categories=categories,
        edit_category=category,
        can_manage=can_manage_categories_for_project(project.id),
    )


@bp.post("/projects/<int:project_id>/categories/<int:category_id>/deactivate")
def categories_deactivate(project_id, category_id):
    category = _category_for_project(project_id, category_id)
    _require_can_manage_categories(category.project_id)
    old_values = {"is_active": category.is_active}
    category.is_active = False
    audit(
        "category.deactivate",
        "ReportCategory",
        category.id,
        old_values,
        {"is_active": category.is_active},
    )
    db.session.commit()
    flash("Đã vô hiệu hóa hạng mục.", "success")
    return redirect(url_for("admin.categories_index", project_id=project_id))


@bp.post("/projects/<int:project_id>/categories/<int:category_id>/activate")
def categories_activate(project_id, category_id):
    category = _category_for_project(project_id, category_id)
    _require_can_manage_categories(category.project_id)
    old_values = {"is_active": category.is_active}
    category.is_active = True
    audit(
        "category.activate",
        "ReportCategory",
        category.id,
        old_values,
        {"is_active": category.is_active},
    )
    db.session.commit()
    flash("Đã kích hoạt hạng mục.", "success")
    return redirect(url_for("admin.categories_index", project_id=project_id))


@bp.post("/projects/<int:project_id>/categories/<int:category_id>/delete")
def categories_delete(project_id, category_id):
    category = _category_for_project(project_id, category_id)
    _require_can_manage_categories(category.project_id)
    old_values = _category_snapshot(category)
    category.deleted_at = db.func.now()
    audit("category.delete", "ReportCategory", category.id, old_values, {"deleted_at": True})
    db.session.commit()
    flash("Đã xóa hạng mục.", "success")
    return redirect(url_for("admin.categories_index", project_id=project_id))


def _save_user(user=None):
    is_new = user is None
    full_name = request.form.get("full_name", "").strip()
    username = request.form.get("username", "").strip()
    email = optional_text("email")
    role = request.form.get("role", "").strip()
    is_active = form_bool("is_active")
    password = request.form.get("password", "")

    errors = []
    if not full_name:
        errors.append("Họ tên là bắt buộc.")
    if not username:
        errors.append("Tên đăng nhập là bắt buộc.")
    if role not in [role.value for role in UserRole]:
        errors.append("Vai trò không hợp lệ.")
    if is_new and len(password) < 8:
        errors.append("Mật khẩu phải có ít nhất 8 ký tự.")
    errors.extend(validate_unique_user(username, email, user.id if user else None))

    if errors:
        for error in errors:
            flash(error, "danger")
        return render_template(
            "admin/users/form.html",
            user=user,
            roles=[role.value for role in UserRole],
        ), 400

    old_values = _user_snapshot(user) if user else None
    if is_new:
        user = User(password_hash=generate_password_hash(password))
        add_with_sqlite_id(user)
    user.full_name = full_name
    user.username = username
    user.email = email
    user.role = role
    user.is_active = is_active

    db.session.flush()
    audit(
        "user.create" if is_new else "user.update",
        "User",
        user.id,
        old_values,
        _user_snapshot(user),
    )
    db.session.commit()
    flash("Đã lưu người dùng.", "success")
    return redirect(url_for("admin.users_index"))


def _save_project(project=None):
    is_new = project is None
    code = request.form.get("code", "").strip()
    name = request.form.get("name", "").strip()
    status = request.form.get("status", "").strip()

    errors = []
    if not code:
        errors.append("Mã dự án là bắt buộc.")
    if not name:
        errors.append("Tên dự án là bắt buộc.")
    if status not in [status.value for status in ProjectStatus]:
        errors.append("Trạng thái dự án không hợp lệ.")
    if code and not validate_unique_project_code(Project, code, project.id if project else None):
        errors.append("Mã dự án đã tồn tại.")

    try:
        start_date = parse_date(request.form.get("start_date"))
        expected_end_date = parse_date(request.form.get("expected_end_date"))
    except ValueError:
        errors.append("Ngày phải đúng định dạng YYYY-MM-DD.")
        start_date = None
        expected_end_date = None

    if errors:
        for error in errors:
            flash(error, "danger")
        return render_template(
            "admin/projects/form.html",
            project=project,
            statuses=[status.value for status in ProjectStatus],
        ), 400

    old_values = _project_snapshot(project) if project else None
    if is_new:
        project = Project()
        add_with_sqlite_id(project)
    project.code = code
    project.name = name
    project.description = optional_text("description")
    project.status = status
    project.start_date = start_date
    project.expected_end_date = expected_end_date

    db.session.flush()
    audit(
        "project.create" if is_new else "project.update",
        "Project",
        project.id,
        old_values,
        _project_snapshot(project),
    )
    db.session.commit()
    flash("Đã lưu dự án.", "success")
    return redirect(url_for("admin.projects_index"))


def _save_category(project, category=None):
    is_new = category is None
    name = request.form.get("name", "").strip()
    sort_order_raw = request.form.get("sort_order", "0").strip() or "0"
    errors = []
    if not name:
        errors.append("Tên hạng mục là bắt buộc.")
    if name and not validate_unique_category_name(project.id, name, category.id if category else None):
        errors.append("Tên hạng mục đã tồn tại trong dự án này.")
    try:
        sort_order = int(sort_order_raw)
    except ValueError:
        errors.append("Thứ tự phải là số.")
        sort_order = 0

    if errors:
        for error in errors:
            flash(error, "danger")
        categories = (
            ReportCategory.query.filter(
                ReportCategory.project_id == project.id,
                ReportCategory.deleted_at.is_(None),
            )
            .order_by(ReportCategory.sort_order.asc(), ReportCategory.name.asc())
            .all()
        )
        return render_template(
            "admin/categories/index.html",
            project=project,
            categories=categories,
            edit_category=category,
            can_manage=can_manage_categories_for_project(project.id),
        ), 400

    old_values = _category_snapshot(category) if category else None
    if is_new:
        category = ReportCategory(project_id=project.id)
        add_with_sqlite_id(category)
    category.name = name
    category.description = optional_text("description")
    category.icon = optional_text("icon")
    category.sort_order = sort_order
    category.is_active = form_bool("is_active")
    category.is_required = form_bool("is_required")

    db.session.flush()
    audit(
        "category.create" if is_new else "category.update",
        "ReportCategory",
        category.id,
        old_values,
        _category_snapshot(category),
    )
    db.session.commit()
    flash("Đã lưu hạng mục.", "success")
    return redirect(url_for("admin.categories_index", project_id=project.id))


def _require_super_admin_post():
    if current_user.role != UserRole.SUPER_ADMIN.value:
        abort(403)


def _require_can_view_categories(project_id):
    if current_user.role in {UserRole.SUPER_ADMIN.value, UserRole.VIEWER_ADMIN.value}:
        return
    if can_manage_categories_for_project(project_id):
        return
    abort(403)


def _require_can_manage_categories(project_id):
    if not can_manage_categories_for_project(project_id):
        abort(403)


def _category_for_project(project_id, category_id):
    return ReportCategory.query.filter(
        ReportCategory.id == category_id,
        ReportCategory.project_id == project_id,
        ReportCategory.deleted_at.is_(None),
    ).first_or_404()


def _user_snapshot(user):
    if not user:
        return None
    return {
        "full_name": user.full_name,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
    }


def _project_snapshot(project):
    if not project:
        return None
    return {
        "code": project.code,
        "name": project.name,
        "description": project.description,
        "status": project.status,
        "start_date": project.start_date.isoformat() if project.start_date else None,
        "expected_end_date": project.expected_end_date.isoformat()
        if project.expected_end_date
        else None,
    }


def _category_snapshot(category):
    if not category:
        return None
    return {
        "project_id": category.project_id,
        "name": category.name,
        "description": category.description,
        "icon": category.icon,
        "sort_order": category.sort_order,
        "is_active": category.is_active,
        "is_required": category.is_required,
    }
