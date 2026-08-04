from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash

from app.admin import bp
from app.admin.services import (
    add_with_sqlite_id,
    audit,
    can_assign_role,
    can_manage_role_permissions,
    can_manage_target_user,
    form_bool,
    optional_text,
    parse_date,
    save_project_memberships,
    temporary_password,
    validate_unique_category_name,
    validate_unique_project_code,
    validate_unique_user,
)
from app.auth.permissions import (
    can_manage_categories_for_project, can_view_categories_for_project,
)
from app.customers.services import (
    active_manageable_customer_choices,
    can_access_customer,
    can_manage_customer,
)
from app.permissions.services import permission_required
from app.permissions.registry import DEFAULTS, PERMISSIONS
from app.extensions import db
from app.models import Customer, Permission, Project, ProjectDocumentFolder, ProjectStatus, ProjectUser, ReportCategory, Role, RolePermission, User, UserRole
from app.project_memberships import (CAPABILITY_FIELDS, CAPABILITY_LABELS, PROJECT_ROLE_LABELS,
    PROJECT_ROLE_LEVELS, PROJECT_ROLE_PRESETS, can_manage_project_memberships,
    is_owner_equivalent_membership, is_super_admin, manageable_project_capabilities,
    manageable_project_role_level, membership_capability_labels, membership_summary)
from app.security import password_policy_errors


REGISTRY_PERMISSION_CODES = frozenset(permission["code"] for permission in PERMISSIONS)

DEPRECATED_GLOBAL_ROLE_CODES = ("PROJECT_MANAGER", "REPORTER")


@bp.get("/")
@permission_required("users.view")
def index():
    return redirect(url_for("admin.users_index"))


@bp.get("/users")
@permission_required("users.view")
def users_index():
    users = User.query.order_by(User.full_name.asc()).all()
    return render_template("admin/users/index.html", users=users)


@bp.route("/users/new", methods=["GET", "POST"])
@permission_required("users.view")
def users_new():
    if request.method == "POST":
        _require_users_manage()
        return _save_user()

    return render_template(
        "admin/users/form.html",
        user=None,
        roles=Role.query.filter(~Role.code.in_(DEPRECATED_GLOBAL_ROLE_CODES)).order_by(Role.is_system.desc(), Role.name).all(),
    )


@bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@permission_required("users.view")
def users_edit(user_id):
    user = db.get_or_404(User, user_id)
    if request.method == "POST":
        _require_users_manage()
        return _save_user(user)

    return render_template(
        "admin/users/form.html",
        user=user,
        roles=Role.query.filter(~Role.code.in_(DEPRECATED_GLOBAL_ROLE_CODES)).order_by(Role.is_system.desc(), Role.name).all(),
    )


@bp.post("/users/<int:user_id>/deactivate")
@permission_required("users.manage")
def users_deactivate(user_id):
    user = db.get_or_404(User, user_id)
    _require_target_user_management(user, "deactivate")
    ensure_not_last_active_super_admin(user, new_is_active=False)
    old_values = {"is_active": user.is_active}
    user.is_active = False
    audit("user.deactivate", "User", user.id, old_values, {"is_active": user.is_active})
    db.session.commit()
    flash("Đã vô hiệu hóa người dùng.", "success")
    return redirect(url_for("admin.users_index"))


@bp.post("/users/<int:user_id>/activate")
@permission_required("users.manage")
def users_activate(user_id):
    user = db.get_or_404(User, user_id)
    _require_target_user_management(user, "activate")
    old_values = {"is_active": user.is_active}
    user.is_active = True
    audit("user.activate", "User", user.id, old_values, {"is_active": user.is_active})
    db.session.commit()
    flash("Đã kích hoạt người dùng.", "success")
    return redirect(url_for("admin.users_index"))


@bp.get("/roles")
@permission_required("roles.view")
def roles_index():
    return render_template("admin/roles/index.html", roles=Role.query.filter(~Role.code.in_(DEPRECATED_GLOBAL_ROLE_CODES)).order_by(Role.id).all())


@bp.route("/roles/new", methods=["GET", "POST"])
@permission_required("roles.manage")
def roles_new():
    if request.method == "POST":
        code = request.form.get("code", "").strip().upper()
        name = request.form.get("name", "").strip()
        if not code or not code.replace("_", "").isalnum() or Role.query.filter_by(code=code).first():
            flash("Mã vai trò phải duy nhất, chỉ gồm chữ, số và dấu gạch dưới.", "danger")
        elif not name:
            flash("Tên vai trò là bắt buộc.", "danger")
        else:
            role = Role(code=code, name=name, description=optional_text("description"), is_system=False)
            add_with_sqlite_id(role); db.session.flush()
            audit("role.create", "Role", role.id, new_values={"code": role.code, "name": role.name})
            db.session.commit(); flash("Đã tạo vai trò tùy chỉnh.", "success")
            return redirect(url_for("admin.role_permissions", role_id=role.id))
    return render_template("admin/roles/form.html", role=None)


@bp.route("/roles/<int:role_id>/edit", methods=["GET", "POST"])
@permission_required("roles.manage")
def roles_edit(role_id):
    role = db.get_or_404(Role, role_id)
    if role.is_system:
        abort(403)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Tên vai trò là bắt buộc.", "danger")
        else:
            old = {"name": role.name, "description": role.description}
            role.name, role.description = name, optional_text("description")
            audit("role.update", "Role", role.id, old, {"name": role.name, "description": role.description})
            db.session.commit(); flash("Đã cập nhật vai trò.", "success")
            return redirect(url_for("admin.roles_index"))
    return render_template("admin/roles/form.html", role=role)


@bp.route("/roles/<int:role_id>/permissions", methods=["GET", "POST"])
@permission_required("roles.view")
def role_permissions(role_id):
    role = db.get_or_404(Role, role_id)
    if request.method == "POST":
        selected_permissions = _requested_permissions()
        if not can_manage_role_permissions(current_user, role, selected_permissions):
            abort(403)
        selected = {permission.id for permission in selected_permissions}
        old = {item.permission_id for item in role.role_permissions}
        RolePermission.query.filter_by(role_id=role.id).delete()
        for permission in selected_permissions:
            db.session.add(RolePermission(role_id=role.id, permission_id=permission.id))
        audit("role.permissions.update", "Role", role.id, {"permission_ids": sorted(old)}, {"permission_ids": sorted(selected)})
        db.session.commit(); flash("Đã cập nhật phân quyền.", "success")
        return redirect(url_for("admin.role_permissions", role_id=role.id))
    group_labels = {
        "modules": "Phân hệ", "users": "Người dùng/Vai trò", "roles": "Người dùng/Vai trò",
        "security": "Quản trị hệ thống", "system": "Quản trị hệ thống", "project_assignments": "Quản lý dự án / cấu hình dự án",
        "projects": "Quản lý dự án / cấu hình dự án", "categories": "Quản lý dự án / cấu hình dự án",
        "reports": "Quản lý dự án", "attachments": "Quản lý dự án", "report_attachments": "Quản lý dự án", "issues": "Quản lý dự án",
        "project_documents": "Hồ sơ dự án", "project_document_folders": "Hồ sơ dự án", "project_document_files": "Hồ sơ dự án",
        "company_media": "Thư viện ảnh/video công ty", "company_media_albums": "Thư viện ảnh/video công ty", "company_media_files": "Thư viện ảnh/video công ty",
        "partners": "Quản lý đối tác", "partner_companies": "Quản lý đối tác", "partner_fields": "Quản lý đối tác", "partner_field_collections": "Quản lý đối tác", "partner_relations": "Quản lý đối tác",
        "project_operations": "Điều hướng Reports", "customers": "Khách hàng", "project_contractors": "Nhà thầu dự án",
        "contractor_assignments": "Assignment", "project_updates": "Báo cáo xuyên suốt", "dashboards": "Dashboard",
    }
    phase9_group_labels = {
        "reports.today.view": "Điều hướng Reports",
        "reports.configuration.view": "Điều hướng Reports",
        "projects.scope_all": "Dashboard",
    }
    grouped = {}
    for permission in Permission.query.filter(Permission.code.in_(REGISTRY_PERMISSION_CODES)).order_by(
            Permission.module, Permission.sort_order, Permission.code).all():
        group = phase9_group_labels.get(permission.code, group_labels.get(permission.module, permission.group_name))
        grouped.setdefault(group, []).append(permission)
    return render_template("admin/roles/permissions.html", role=role, grouped=grouped,
                           selected_ids={item.permission_id for item in role.role_permissions}, can_manage=current_user.can("roles.manage"))


@bp.post("/roles/<int:role_id>/permissions/reset-defaults")
@permission_required("roles.manage")
def role_permissions_reset_defaults(role_id):
    role = db.get_or_404(Role, role_id)
    wanted = DEFAULTS.get(role.code, set())
    permissions = Permission.query.filter(
        Permission.code.in_(wanted), Permission.code.in_(REGISTRY_PERMISSION_CODES)
    ).all()
    if len(permissions) != len(wanted) or not can_manage_role_permissions(current_user, role, permissions):
        abort(403)
    old = {item.permission_id for item in role.role_permissions}
    RolePermission.query.filter_by(role_id=role.id).delete()
    db.session.add_all([RolePermission(role_id=role.id, permission_id=item.id) for item in permissions])
    audit("role.permissions.reset_defaults", "Role", role.id, {"permission_ids": sorted(old)}, {"permission_ids": sorted(item.id for item in permissions)})
    db.session.commit(); flash("Đã khôi phục quyền mặc định.", "success")
    return redirect(url_for("admin.role_permissions", role_id=role.id))


@bp.post("/users/<int:user_id>/reset-password")
@permission_required("users.manage")
def users_reset_password(user_id):
    user = db.get_or_404(User, user_id)
    _require_target_user_management(user, "reset_password")
    password = temporary_password()
    user.password_hash = generate_password_hash(password)
    audit("user.reset_password", "User", user.id, new_values={"username": user.username})
    db.session.commit()
    flash(f"Mật khẩu tạm cho {user.username}: {password}", "warning")
    return redirect(url_for("admin.users_index"))


@bp.get("/projects")
@permission_required("projects.view")
def projects_index():
    projects = Project.query.order_by(Project.code.asc()).all()
    return render_template("admin/projects/index.html", projects=projects)


@bp.route("/projects/new", methods=["GET", "POST"])
@permission_required("projects.manage")
def projects_new():
    if request.method == "POST":
        return _save_project()

    return _render_project_form()


@bp.route("/projects/<int:project_id>/edit", methods=["GET", "POST"])
@permission_required("projects.manage")
def projects_edit(project_id):
    project = db.get_or_404(Project, project_id)
    if request.method == "POST":
        return _save_project(project)

    return _render_project_form(project)


@bp.post("/projects/<int:project_id>/archive")
@permission_required("projects.manage")
def projects_archive(project_id):
    project = db.get_or_404(Project, project_id)
    old_values = _project_snapshot(project)
    project.status = ProjectStatus.ARCHIVED.value
    audit("project.archive", "Project", project.id, old_values, {"status": project.status})
    db.session.commit()
    flash("Đã lưu trữ dự án.", "success")
    return redirect(url_for("admin.projects_index"))


@bp.get("/projects/<int:project_id>/reporters")
@bp.get("/projects/<int:project_id>/memberships")
def projects_reporters(project_id):
    if not current_user.can("projects.view"):
        abort(403)
    project = db.get_or_404(Project, project_id)
    memberships = (ProjectUser.query.join(User).filter(ProjectUser.project_id == project.id,
        ProjectUser.is_active.is_(True)).order_by(User.full_name.asc()).all())
    assigned_ids = {item.user_id for item in memberships}
    available_users = User.query.filter(User.is_active.is_(True), User.deleted_at.is_(None), ~User.id.in_(assigned_ids or [0])).order_by(User.full_name.asc()).all()

    return render_template(
        "admin/projects/reporters.html",
        project=project,
        memberships=memberships,
        available_users=available_users,
        available_user_payload=[{"id": user.id, "name": user.full_name, "username": user.username,
                                 "email": user.email or "", "role": user.role.name} for user in available_users],
        presets={code: sorted(flags) for code, flags in PROJECT_ROLE_PRESETS.items()},
        capability_fields=CAPABILITY_FIELDS,
        capability_labels=CAPABILITY_LABELS,
        project_role_labels=PROJECT_ROLE_LABELS,
        membership_capability_labels=membership_capability_labels,
        membership_summary=membership_summary,
    )


@bp.post("/projects/<int:project_id>/memberships")
@permission_required("project_assignments.manage")
def memberships_create(project_id):
    project = db.get_or_404(Project, project_id)
    _require_project_membership_management(project)
    user_id = _membership_user_id()
    user = db.session.get(User, user_id)
    if not user or not user.is_active or user.deleted_at is not None:
        abort(400)
    code, enabled = _membership_form_values()
    membership = ProjectUser.query.filter_by(project_id=project.id, user_id=user.id).first()
    if membership and membership.is_active:
        flash("Người dùng đã có trong dự án.", "warning")
        return redirect(url_for("admin.projects_reporters", project_id=project.id))
    _validate_membership_grant(project, code, enabled, existing_membership=membership)
    membership = membership or ProjectUser(project_id=project.id, user_id=user.id)
    if membership.id is None:
        add_with_sqlite_id(membership)
    _apply_membership_values(membership, code, enabled)
    membership.is_active = True
    audit("project_membership.assign", "ProjectUser", membership.id, new_values={"project_id": project.id, "user_id": user.id})
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("Người dùng đã có trong dự án.", "warning")
        return redirect(url_for("admin.projects_reporters", project_id=project.id))
    flash("Đã thêm thành viên dự án.", "success")
    return redirect(url_for("admin.projects_reporters", project_id=project.id))


@bp.post("/projects/<int:project_id>/memberships/<int:membership_id>")
@permission_required("project_assignments.manage")
def memberships_update(project_id, membership_id):
    project = db.get_or_404(Project, project_id)
    _require_project_membership_management(project)
    membership = ProjectUser.query.filter_by(id=membership_id, project_id=project_id, is_active=True).first_or_404()
    code, enabled = _membership_form_values()
    _validate_membership_grant(project, code, enabled, existing_membership=membership)
    _apply_membership_values(membership, code, enabled)
    audit("project_membership.update", "ProjectUser", membership.id)
    db.session.commit(); flash("Đã lưu thay đổi.", "success")
    return redirect(url_for("admin.projects_reporters", project_id=project_id))


@bp.post("/projects/<int:project_id>/memberships/<int:membership_id>/deactivate")
@permission_required("project_assignments.manage")
def memberships_deactivate(project_id, membership_id):
    project = db.get_or_404(Project, project_id)
    _require_project_membership_management(project)
    membership = ProjectUser.query.filter_by(id=membership_id, project_id=project_id, is_active=True).first_or_404()
    _validate_membership_target(project, membership)
    membership.is_active = False
    audit("project_membership.deactivate", "ProjectUser", membership.id, new_values={"is_active": False})
    db.session.commit(); flash("Đã ngừng phân quyền thành viên.", "success")
    return redirect(url_for("admin.projects_reporters", project_id=project_id))


def _membership_user_id():
    values = request.form.getlist("user_id")
    if len(values) != 1 or not values[0].isdigit() or int(values[0]) <= 0:
        abort(400)
    return int(values[0])


def _membership_form_values():
    role_values = request.form.getlist("project_role_code")
    if len(role_values) != 1 or role_values[0] not in PROJECT_ROLE_LEVELS:
        abort(400)
    unknown_capability_fields = {
        name for name in request.form.keys()
        if name.startswith("can_") and name not in CAPABILITY_FIELDS
    }
    if unknown_capability_fields:
        abort(400)

    enabled = set()
    for field in CAPABILITY_FIELDS:
        values = request.form.getlist(field)
        if not values:
            continue
        if values != ["1"]:
            abort(400)
        enabled.add(field)
    if not enabled:
        flash("Vui lòng chọn ít nhất một quyền hoặc dùng nút Bỏ khỏi dự án.", "danger")
        abort(400)
    return role_values[0], enabled


def _require_project_membership_management(project):
    if not can_manage_project_memberships(current_user, project):
        abort(403, description="Không có quyền quản lý thành viên của dự án này.")


def _validate_membership_target(project, membership):
    if not is_super_admin(current_user) and is_owner_equivalent_membership(
        membership.project_role_code,
        {field for field in CAPABILITY_FIELDS if getattr(membership, field)},
    ):
        abort(403, description="Chỉ SUPER_ADMIN được quản lý thành viên chủ trì dự án.")
    if PROJECT_ROLE_LEVELS.get(membership_summary(membership), -1) > manageable_project_role_level(current_user, project):
        abort(403, description="Vai trò thành viên vượt quá phạm vi quản lý.")


def _validate_membership_grant(project, code, enabled, *, existing_membership=None):
    if existing_membership is not None:
        _validate_membership_target(project, existing_membership)
    if not enabled.issubset(manageable_project_capabilities(current_user, project)):
        abort(403, description="Quyền dự án được cấp vượt quá phạm vi của bạn.")
    if PROJECT_ROLE_LEVELS[code] > manageable_project_role_level(current_user, project):
        abort(403, description="Vai trò dự án được cấp vượt quá phạm vi của bạn.")
    # Product policy: creating or managing owner-equivalent memberships is a
    # SUPER_ADMIN responsibility.  Project owners may manage subordinates.
    if not is_super_admin(current_user) and is_owner_equivalent_membership(code, enabled):
        abort(403, description="Chỉ SUPER_ADMIN được cấp vai trò chủ trì dự án.")


def _apply_membership_values(membership, code, enabled):
    membership.project_role_code = code
    for field in CAPABILITY_FIELDS:
        setattr(membership, field, field in enabled)


@bp.route("/projects/<int:project_id>/categories", methods=["GET", "POST"])
def categories_index(project_id):
    project = db.get_or_404(Project, project_id)
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
    project = db.get_or_404(Project, project_id)
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
    role_id = request.form.get("role_id", "").strip()
    legacy_role_code = request.form.get("role", "").strip()
    is_active = form_bool("is_active")
    password = request.form.get("password", "")

    errors = []
    if not full_name:
        errors.append("Họ tên là bắt buộc.")
    if not username:
        errors.append("Tên đăng nhập là bắt buộc.")
    # role_id is canonical. Keep accepting the legacy role code during Phase 1
    # because older forms and integrations still submit `role=REPORTER`.
    role = db.session.get(Role, int(role_id)) if role_id.isdigit() else None
    if role_id and not role_id.isdigit():
        errors.append("Vai trò không hợp lệ.")
    if role is None and not role_id and legacy_role_code:
        role = Role.query.filter_by(code=legacy_role_code).first()
        if role is None:
            errors.append("Vai trò được chọn chưa tồn tại trong hệ thống.")
    if role is None and not errors:
        errors.append("Vui lòng chọn vai trò hợp lệ.")
    if is_new:
        errors.extend(password_policy_errors(password))
    errors.extend(validate_unique_user(username, email, user.id if user else None))

    if errors:
        for error in errors:
            flash(error, "danger")
        return render_template(
            "admin/users/form.html",
            user=user,
            roles=Role.query.filter(~Role.code.in_(DEPRECATED_GLOBAL_ROLE_CODES)).order_by(Role.is_system.desc(), Role.name).all(),
        ), 400

    if not is_new:
        _require_target_user_management(user, "edit")
        if is_active != user.is_active:
            _require_target_user_management(user, "activate" if is_active else "deactivate")
    if not can_assign_role(current_user, user, role):
        _reject_role_assignment(user)

    old_values = _user_snapshot(user) if user else None
    if is_new:
        user = User(password_hash=generate_password_hash(password))
        add_with_sqlite_id(user)
    user.full_name = full_name
    user.username = username
    user.email = email
    if not is_new:
        ensure_not_last_active_super_admin(user, new_role=role, new_is_active=is_active)
    user.role = role
    user.role_id = role.id
    user.legacy_role = role.code
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
    raw_customer_id = request.form.get("customer_id", "").strip()

    errors = []
    form_errors = {}
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

    current_customer_id = project.customer_id if project else None
    requested_customer_id = None
    if raw_customer_id:
        try:
            requested_customer_id = int(raw_customer_id)
        except ValueError:
            form_errors["customer_id"] = "Khách hàng không hợp lệ."
        else:
            if requested_customer_id < 1:
                form_errors["customer_id"] = "Khách hàng không hợp lệ."

    if not form_errors and requested_customer_id != current_customer_id:
        # Project management is already gated by the route.  Changing the
        # customer additionally requires customer mutation authority.
        if not current_user.can("customers.edit"):
            abort(403)
        if current_customer_id is not None:
            current_customer = db.session.get(Customer, current_customer_id)
            if (
                current_customer is None
                or not can_access_customer(current_user, current_customer)
                or not can_manage_customer(current_user, current_customer)
            ):
                abort(403)
        if requested_customer_id is not None:
            customer = db.session.get(Customer, requested_customer_id)
            if (
                customer is None
                or not customer.is_active
                or customer.archived_at is not None
                or not can_access_customer(current_user, customer)
                or not can_manage_customer(current_user, customer)
            ):
                form_errors["customer_id"] = "Khách hàng không tồn tại, đã lưu trữ hoặc ngoài phạm vi quản lý."

    if errors or form_errors:
        for error in errors:
            flash(error, "danger")
        return _render_project_form(project, form_errors=form_errors), 400

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
    project.customer_id = requested_customer_id

    db.session.flush()
    if is_new:
        root = ProjectDocumentFolder(project_id=project.id, name="__ROOT__", is_root=True, root_type="project", created_by_id=current_user.id)
        add_with_sqlite_id(root)
        db.session.flush()
    if is_new:
        # Retain project.create: Project has created_by_user_id, but this
        # creation path does not assign it, so audit is the only provenance.
        audit("project.create", "Project", project.id, old_values, _project_snapshot(project))
    else:
        audit("project.update", "Project", project.id, old_values, _project_snapshot(project))
    db.session.commit()
    flash("Đã lưu dự án.", "success")
    return redirect(url_for("admin.projects_index"))


def _render_project_form(project=None, *, form_errors=None):
    """Render a project form without ever exposing arbitrary customer IDs."""
    customer_choices = active_manageable_customer_choices(current_user)
    current_customer = project.customer if project else None
    if current_customer and all(choice.id != current_customer.id for choice in customer_choices):
        # An archived historical customer may be retained while other fields
        # are edited, but it is not an eligible new choice.
        customer_choices.append(current_customer)
    return render_template(
        "admin/projects/form.html",
        project=project,
        statuses=[status.value for status in ProjectStatus],
        customer_choices=customer_choices,
        form_errors=form_errors or {},
    )


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
    if is_new:
        # Retain category.create: ReportCategory has no creator column.
        audit("category.create", "ReportCategory", category.id, old_values, _category_snapshot(category))
    else:
        audit("category.update", "ReportCategory", category.id, old_values, _category_snapshot(category))
    db.session.commit()
    flash("Đã lưu hạng mục.", "success")
    return redirect(url_for("admin.categories_index", project_id=project.id))


def _require_users_manage():
    if not current_user.can("users.manage"):
        abort(403)


def _require_target_user_management(user, action):
    if can_manage_target_user(current_user, user, action):
        return
    # A self-targeted security mutation is a safe validation rejection.  Keep
    # the historic 400 response for the sole-SUPER_ADMIN flow while still
    # rejecting before any state change.
    if current_user.is_authenticated and current_user.id == user.id:
        abort(400)
    abort(403)


def _reject_role_assignment(user):
    if user is not None and current_user.is_authenticated and current_user.id == user.id:
        abort(400)
    abort(403)


def _requested_permissions():
    """Load an exact, canonical requested permission set or reject it whole."""
    values = request.form.getlist("permission_ids")
    if any(not value.isdigit() for value in values):
        abort(400)
    permission_ids = [int(value) for value in values]
    if len(permission_ids) != len(set(permission_ids)):
        abort(400)
    permissions = Permission.query.filter(Permission.id.in_(permission_ids)).all() if permission_ids else []
    if len(permissions) != len(permission_ids):
        abort(400)
    return [permission for permission in permissions if permission.code in REGISTRY_PERMISSION_CODES]


def _require_can_view_categories(project_id):
    if can_view_categories_for_project(project_id):
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
        "role": user.role_code,
        "is_active": user.is_active,
    }


def count_active_super_admins(exclude_user_id=None):
    query = User.query.join(Role).filter(Role.code == UserRole.SUPER_ADMIN.value, User.is_active.is_(True))
    if exclude_user_id is not None:
        query = query.filter(User.id != exclude_user_id)
    return query.count()


def ensure_not_last_active_super_admin(user, new_role=None, new_is_active=None):
    will_remain = (new_role or user.role).code == UserRole.SUPER_ADMIN.value and (user.is_active if new_is_active is None else new_is_active)
    if user.has_role(UserRole.SUPER_ADMIN.value) and user.is_active and not will_remain and count_active_super_admins(user.id) == 0:
        flash("Không thể thay đổi vì hệ thống phải luôn có ít nhất một Quản trị tổng đang hoạt động.", "danger")
        abort(400)


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
        "customer_id": project.customer_id,
        "customer": None if project.customer is None else {
            "id": project.customer.id,
            "name": project.customer.name,
        },
        "created_by_id": project.created_by_user_id,
        "created_at": project.created_at.isoformat() if project.created_at else None,
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


@bp.route("/branding", methods=["GET", "POST"])
def branding():
    from flask_login import current_user
    from app.display_images import (DisplayImageCleanupError, DisplayImageError,
                                    finalize_display_image_change, remove_display_image,
                                    replace_display_image)
    from app.models import SystemSetting
    if not current_user.can("settings.branding.view"):
        abort(403)
    setting = db.session.get(SystemSetting, "branding") or SystemSetting(key="branding")
    if request.method == "POST":
        if not current_user.can("settings.branding.manage"):
            abort(403)
        try:
            change = None
            if request.form.get("remove_logo"):
                change = remove_display_image(setting, attribute="brand_logo_storage_object")
            elif request.files.get("logo") and request.files["logo"].filename:
                change = replace_display_image(setting, request.files["logo"], attribute="brand_logo_storage_object", scope="branding", user=current_user)
            if db.session.get(SystemSetting, "branding") is None:
                db.session.add(setting)
            db.session.commit()
        except DisplayImageError as exc:
            db.session.rollback(); flash(str(exc), "danger")
        else:
            try:
                if change:
                    finalize_display_image_change(change)
            except DisplayImageCleanupError:
                db.session.rollback()
                flash("Đã cập nhật nhận diện; ảnh cũ đang chờ dọn dẹp.", "warning")
            else:
                flash("Đã cập nhật nhận diện hệ thống.", "success")
        return redirect(url_for("admin.branding"))
    return render_template("admin/branding.html", setting=setting, can_manage=current_user.can("settings.branding.manage"))
