from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.models import Project, ProjectDocumentFolder, ProjectDocumentFolderPermission, Role, User
from app.project_documents import bp
from app.project_documents.permissions import (can_access_project_documents, can_create_project_document_folder,
    can_delete_project_document_folder, can_edit_project_document_folder, can_restore_project_document_folder, can_share_project_document_folder,
    can_view_project_document_folder)
from app.project_documents.services import (DocumentValidationError, archive_folder, build_breadcrumb, create_folder,
    get_or_create_project_root_folder, list_accessible_projects, list_folder_children, list_folder_files, list_move_destinations, move_folder,
    remove_folder_permission, rename_folder, restore_folder, set_folder_permission)


@bp.before_request
def require_module():
    if not can_access_project_documents(current_user): abort(403, description="Bạn không có quyền truy cập Hồ sơ dự án.")


@bp.get("")
@bp.get("/")
def index():
    return render_template("project_documents/index.html", projects=list_accessible_projects(current_user))


@bp.get("/projects/<int:project_id>")
def project_root(project_id):
    project = Project.query.filter_by(id=project_id, deleted_at=None).first_or_404()
    if project not in list_accessible_projects(current_user): abort(403)
    root = get_or_create_project_root_folder(project, current_user)
    if not can_view_project_document_folder(current_user, root): abort(403)
    return redirect(url_for("project_documents.folder", folder_id=root.id))


@bp.get("/folders/<int:folder_id>")
def folder(folder_id):
    target = ProjectDocumentFolder.query.get_or_404(folder_id)
    if not can_view_project_document_folder(current_user, target): abort(403)
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "active").strip().lower()
    if status not in {"active", "archived", "all"}:
        status = "active"
    children = list_folder_children(current_user, target, status, q)
    return render_template("project_documents/folder.html", folder=target, breadcrumb=build_breadcrumb(current_user, target),
        children=children, files=list_folder_files(current_user, target, status, q), q=q, status=status,
        can_create=can_create_project_document_folder(current_user, target), can_edit=can_edit_project_document_folder(current_user, target),
        can_delete=can_delete_project_document_folder(current_user, target), can_share=can_share_project_document_folder(current_user, target),
        move_destinations_by_child={child.id: list_move_destinations(current_user, child) for child in children if child.is_active and can_edit_project_document_folder(current_user, child)},
        can_delete_by_child={child.id: can_delete_project_document_folder(current_user, child) for child in children if child.is_active},
        can_restore_by_child={child.id: can_restore_project_document_folder(current_user, child) for child in children if not child.is_active or child.deleted_at})


def _folder_or_404(folder_id): return ProjectDocumentFolder.query.get_or_404(folder_id)
def _fail(exc, redirect_to):
    flash(str(exc), "danger"); return redirect(redirect_to)


@bp.post("/folders/new")
def new_folder():
    parent = _folder_or_404(request.form.get("parent_id", type=int))
    if not can_create_project_document_folder(current_user, parent): abort(403)
    try: create_folder(current_user, parent, request.form.get("name"), request.form.get("description"), request.form.get("is_restricted") == "1")
    except DocumentValidationError as exc: return _fail(exc, url_for("project_documents.folder", folder_id=parent.id))
    flash("Đã tạo thư mục.", "success"); return redirect(url_for("project_documents.folder", folder_id=parent.id))


@bp.post("/folders/<int:folder_id>/rename")
def rename(folder_id):
    target = _folder_or_404(folder_id)
    if not can_edit_project_document_folder(current_user, target): abort(403)
    try: rename_folder(current_user, target, request.form.get("name"))
    except DocumentValidationError as exc: return _fail(exc, url_for("project_documents.folder", folder_id=target.parent_id or target.id))
    flash("Đã đổi tên thư mục.", "success"); return redirect(url_for("project_documents.folder", folder_id=target.parent_id or target.id))


@bp.post("/folders/<int:folder_id>/move")
def move(folder_id):
    target = _folder_or_404(folder_id); destination = _folder_or_404(request.form.get("parent_id", type=int))
    if not can_edit_project_document_folder(current_user, target) or not can_create_project_document_folder(current_user, destination): abort(403)
    try: move_folder(current_user, target, destination)
    except DocumentValidationError as exc: return _fail(exc, url_for("project_documents.folder", folder_id=target.parent_id or target.id))
    flash("Đã di chuyển thư mục.", "success"); return redirect(url_for("project_documents.folder", folder_id=destination.id))


@bp.post("/folders/<int:folder_id>/archive")
def archive(folder_id):
    target = _folder_or_404(folder_id)
    if not can_delete_project_document_folder(current_user, target): abort(403)
    parent_id = target.parent_id
    try: archive_folder(current_user, target)
    except DocumentValidationError as exc: return _fail(exc, url_for("project_documents.folder", folder_id=target.id))
    flash("Đã lưu trữ thư mục.", "success"); return redirect(url_for("project_documents.folder", folder_id=parent_id))


@bp.post("/folders/<int:folder_id>/restore")
def restore(folder_id):
    target = _folder_or_404(folder_id)
    if not can_restore_project_document_folder(current_user, target): abort(403)
    try: restore_folder(current_user, target)
    except DocumentValidationError as exc: return _fail(exc, url_for("project_documents.folder", folder_id=target.parent_id or target.id))
    flash("Đã khôi phục thư mục.", "success"); return redirect(url_for("project_documents.folder", folder_id=target.parent_id, status="active"))


@bp.route("/folders/<int:folder_id>/permissions", methods=["GET", "POST"])
def permissions(folder_id):
    target = _folder_or_404(folder_id)
    if not can_share_project_document_folder(current_user, target): abort(403)
    if request.method == "POST":
        try:
            if request.form.get("remove_id"): remove_folder_permission(current_user, target, request.form.get("remove_id", type=int))
            else: set_folder_permission(current_user, target, request.form.get("principal_type"), request.form.get("principal_id"), request.form)
        except DocumentValidationError as exc: flash(str(exc), "danger")
        else: flash("Đã cập nhật quyền chia sẻ.", "success")
        return redirect(url_for("project_documents.permissions", folder_id=target.id))
    return render_template("project_documents/permissions.html", folder=target,
        entries=ProjectDocumentFolderPermission.query.filter_by(folder_id=target.id).all(), users=User.query.filter_by(is_active=True).order_by(User.full_name).all(), roles=Role.query.order_by(Role.name).all())
