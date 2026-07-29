from pathlib import Path

from flask import abort, current_app, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user
from markupsafe import Markup

from app.extensions import db
from app.models import Project, ProjectDocumentFolder, ProjectDocumentFolderPermission, Role, StorageDerivative, User
from app.project_documents import bp
from app.project_documents.permissions import (can_access_project_documents, can_create_project_document_folder,
    can_delete_project_document_folder, can_edit_project_document_folder, can_restore_project_document_folder, can_share_project_document_folder,
    can_view_project_document_folder, can_upload_project_document_folder, can_download_project_document_file,
    can_edit_project_document_file, can_delete_project_document_file, can_restore_project_document_file,
    can_view_project_document_file, can_create_custom_root, can_provision_project_document_root)
from app.project_documents.services import (DocumentValidationError, archive_folder, build_breadcrumb, create_folder,
    find_project_root_folder, provision_project_root_folder, list_accessible_projects, list_folder_children, list_folder_files, list_move_destinations, move_folder,
    remove_folder_permission, rename_folder, restore_folder, set_folder_permission, presign_folder_upload_batch,
    complete_folder_upload_item, create_file_download_url, create_file_preview_url, rename_file, archive_file, restore_file, file_payload,
    bulk_archive_files, bulk_restore_files, bulk_file_download_urls, create_custom_root_folder)
from app.storage.exceptions import StorageNotFoundError, StorageValidationError, StorageAuthorizationError
from app.storage.services import create_upload_selection_session, finalize_upload_selection_session
from app.bulk_downloads.services import (BulkDownloadError, parse_file_ids, preflight_document_download,
    request_document_download, stream_zip_download, serialize_job)
from app.models import BulkDownloadJob


@bp.before_request
def require_module():
    if not can_access_project_documents(current_user): abort(403, description="Bạn không có quyền truy cập Hồ sơ tài liệu.")


@bp.get("")
@bp.get("/")
def index():
    custom_roots = [item for item in ProjectDocumentFolder.query.filter_by(project_id=None, is_root=True, root_type="custom").filter(ProjectDocumentFolder.deleted_at.is_(None)).all() if can_view_project_document_folder(current_user, item)]
    projects = list_accessible_projects(current_user)
    roots_by_project_id = {project.id: find_project_root_folder(project) for project in projects}
    return render_template("project_documents/index.html", projects=projects, roots_by_project_id=roots_by_project_id,
        can_provision_by_project_id={project.id: can_provision_project_document_root(current_user, project) for project in projects},
        custom_roots=custom_roots, can_create_custom_root=can_create_custom_root(current_user))

@bp.post("/custom-roots")
def custom_root_create():
    if not can_create_custom_root(current_user): abort(403)
    try: root = create_custom_root_folder(current_user, request.form.get("name"), request.form.get("description"), request.form.get("is_restricted") == "1")
    except (DocumentValidationError, BulkDownloadError) as exc:
        flash(str(exc), "danger"); return redirect(url_for("project_documents.index"))
    flash("Đã tạo mục hồ sơ tài liệu.", "success")
    return redirect(url_for("project_documents.folder", folder_id=root.id))


@bp.get("/projects/<int:project_id>")
def project_root(project_id):
    project = Project.query.filter_by(id=project_id, deleted_at=None).first_or_404()
    if project not in list_accessible_projects(current_user): abort(403)
    root = find_project_root_folder(project)
    if root is None:
        abort(404)
    if not can_view_project_document_folder(current_user, root): abort(403)
    return redirect(url_for("project_documents.folder", folder_id=root.id))


@bp.post("/projects/<int:project_id>/provision-root")
def provision_project_root(project_id):
    project = Project.query.filter_by(id=project_id, deleted_at=None).first_or_404()
    if not can_provision_project_document_root(current_user, project):
        abort(403)
    root, created = provision_project_root_folder(project, current_user)
    flash("Đã tạo thư mục gốc hồ sơ dự án." if created else "Thư mục gốc hồ sơ dự án đã tồn tại.", "success")
    return redirect(url_for("project_documents.folder", folder_id=root.id))


def _folder_context(source=None):
    source = source or request.values
    folder_status = (source.get("folder_status", "active") or "active").strip().lower()
    file_status = (source.get("file_status", "active") or "active").strip().lower()
    return {
        "q": (source.get("q", "") or "").strip(),
        "folder_status": folder_status if folder_status in {"active", "archived", "all"} else "active",
        "file_status": file_status if file_status in {"active", "archived", "all"} else "active",
    }


def _folder_url(folder_id, *, folder_status=None, source=None):
    context = _folder_context(source)
    if folder_status is not None:
        context["folder_status"] = folder_status
    return url_for("project_documents.folder", folder_id=folder_id, **context)


@bp.get("/folders/<int:folder_id>")
def folder(folder_id):
    target = db.get_or_404(ProjectDocumentFolder, folder_id)
    if not can_view_project_document_folder(current_user, target, include_archived=True): abort(403)
    context = _folder_context(request.args)
    children = list_folder_children(current_user, target, context["folder_status"], context["q"])
    files = list_folder_files(current_user, target, context["file_status"], context["q"])
    active_target = target.is_active and target.deleted_at is None
    can_edit_by_child = {child.id: can_edit_project_document_folder(current_user, child) for child in children if child.is_active and child.deleted_at is None}
    move_destinations_by_child = {child.id: list_move_destinations(current_user, child) for child in children if can_edit_by_child.get(child.id)}
    move_destination_options_by_child = {
        child_id: [{"id": destination.id, "name": destination.name} for destination in destinations]
        for child_id, destinations in move_destinations_by_child.items()
    }
    return render_template("project_documents/folder.html", folder=target, breadcrumb=build_breadcrumb(current_user, target),
        children=children, files=files, **context,
        can_create=can_create_project_document_folder(current_user, target), can_edit=can_edit_project_document_folder(current_user, target),
        can_delete=can_delete_project_document_folder(current_user, target), can_restore=can_restore_project_document_folder(current_user, target),
        can_share=can_share_project_document_folder(current_user, target, include_archived=not active_target),
        can_upload=can_upload_project_document_folder(current_user, target), active_target=active_target,
        can_edit_by_child=can_edit_by_child, can_share_by_child={child.id: can_share_project_document_folder(current_user, child, include_archived=not (child.is_active and child.deleted_at is None)) for child in children},
        move_destinations_by_child=move_destinations_by_child, move_destination_options_by_child=move_destination_options_by_child,
        can_delete_by_child={child.id: can_delete_project_document_folder(current_user, child) for child in children if child.is_active and child.deleted_at is None},
        can_restore_by_child={child.id: can_restore_project_document_folder(current_user, child) for child in children if not child.is_active or child.deleted_at},
        can_any_edit_folder=(active_target and not target.is_root and can_edit_project_document_folder(current_user, target)) or any(can_edit_by_child.values()),
        can_edit_file_by_id={item.id: can_edit_project_document_file(current_user, item) for item in files if item.is_active},
        can_delete_file_by_id={item.id: can_delete_project_document_file(current_user, item) for item in files if item.is_active},
        can_restore_file_by_id={item.id: can_restore_project_document_file(current_user, item) for item in files if not item.is_active or item.deleted_at},
        can_download_file_by_id={item.id: can_download_project_document_file(current_user, item) for item in files if item.is_active},
        can_bulk_archive=any(can_delete_project_document_file(current_user, item) for item in files if item.is_active),
        can_bulk_restore=any(can_restore_project_document_file(current_user, item) for item in files if not item.is_active or item.deleted_at),
        can_bulk_download=any(can_download_project_document_file(current_user, item) for item in files if item.is_active),
        thumbnail_version_by_file=_thumbnail_versions(files),
        can_any_edit_file=any(can_edit_project_document_file(current_user, item) for item in files if item.is_active))


def _document_file_or_404(file_id):
    from app.models import ProjectDocumentFile
    return db.get_or_404(ProjectDocumentFile, file_id)


@bp.post("/folders/<int:folder_id>/files/presign-batch")
def presign_batch(folder_id):
    folder = _folder_or_404(folder_id)
    if not can_upload_project_document_folder(current_user, folder): abort(403)
    payload = request.get_json(silent=True) or {}
    try: result = presign_folder_upload_batch(current_user, folder, payload.get("files", []), payload.get("selection_session_id"))
    except StorageAuthorizationError: abort(403)
    except (DocumentValidationError, StorageValidationError) as exc: return jsonify(error=str(exc)), 400
    return jsonify(result)

@bp.post("/folders/<int:folder_id>/files/upload-selection-sessions")
def create_selection_session(folder_id):
    folder = _folder_or_404(folder_id)
    if not can_upload_project_document_folder(current_user, folder): abort(403)
    payload = request.get_json(silent=True) or {}
    try: return jsonify(create_upload_selection_session(user=current_user, module_type="project_documents", target_type="folder", target_id=folder.id, declared_files=payload.get("file_count"), declared_size_bytes=payload.get("total_size_bytes")))
    except StorageValidationError as exc: return jsonify(error=str(exc)), 400

@bp.post("/folders/<int:folder_id>/files/upload-selection-sessions/<int:session_id>/finalize")
def finalize_selection_session(folder_id, session_id):
    folder = _folder_or_404(folder_id)
    if not can_upload_project_document_folder(current_user, folder): abort(403)
    payload = request.get_json(silent=True) or {}
    try: return jsonify(finalize_upload_selection_session(user=current_user, selection_session_id=session_id, module_type="project_documents", target_type="folder", target_id=folder.id, failed_upload_batch_item_ids=payload.get("failed_upload_batch_item_ids")))
    except StorageAuthorizationError: abort(403)
    except StorageValidationError as exc: return jsonify(error=str(exc)), 400


@bp.post("/folders/<int:folder_id>/files/complete-upload")
def complete_upload(folder_id):
    folder = _folder_or_404(folder_id)
    if not can_upload_project_document_folder(current_user, folder): abort(403)
    payload = request.get_json(silent=True) or request.form
    try: upload_batch_item_id = int(payload.get("upload_batch_item_id"))
    except (TypeError, ValueError): return jsonify(error="upload_batch_item_id không hợp lệ."), 400
    try: result = complete_folder_upload_item(current_user, folder, upload_batch_item_id, payload)
    except StorageAuthorizationError: abort(403)
    except (DocumentValidationError, StorageValidationError, StorageNotFoundError) as exc: return jsonify(error=str(exc)), 400
    return jsonify(result)


@bp.post("/files/<int:file_id>/signed-download")
def signed_download(file_id):
    document_file = _document_file_or_404(file_id)
    if not can_download_project_document_file(current_user, document_file): abort(403)
    try: return jsonify(create_file_download_url(current_user, document_file))
    except DocumentValidationError as exc: return jsonify(error=str(exc)), 400


@bp.post("/files/<int:file_id>/signed-preview")
def signed_preview(file_id):
    document_file = _document_file_or_404(file_id)
    if not can_view_project_document_file(current_user, document_file): abort(403)
    payload = request.get_json(silent=True) or {}
    try: return jsonify(create_file_preview_url(current_user, document_file, variant=payload.get("variant")))
    except DocumentValidationError as exc: return jsonify(error=str(exc)), 400


@bp.get("/files/<int:file_id>/thumbnail")
def thumbnail(file_id):
    document_file = _document_file_or_404(file_id)
    if not can_view_project_document_file(current_user, document_file):
        abort(403)
    derivative = _thumbnail_derivative(document_file)
    if derivative is None:
        return _thumbnail_placeholder()
    if not current_app.config["MEDIA_CACHE_ENABLED"]:
        from app.storage.providers import get_storage_provider
        return redirect(get_storage_provider().create_presigned_download(
            derivative.bucket, derivative.object_key, current_app.config["STORAGE_DOWNLOAD_URL_TTL_SECONDS"],
            "inline", document_file.display_name)["url"])
    from app.storage.cache import CacheSource, MediaCacheSourceMissing, serve_cached_source
    source = CacheSource(category="project-document-thumbnail", object_id=document_file.id,
        derivative_type=derivative.derivative_type, immutable_key=derivative.object_key, version_id=derivative.id,
        extension=derivative.file_ext, mime_type=derivative.mime_type, file_size=derivative.file_size,
        bucket=derivative.bucket)
    cache_control = "private, max-age=3600" if request.args.get("v") == str(derivative.id) else "private, max-age=0, must-revalidate"
    try:
        return serve_cached_source(source, cache_control=cache_control)
    except MediaCacheSourceMissing:
        abort(404)


def _thumbnail_derivative(document_file):
    object_ = document_file.storage_object
    if not object_ or object_.upload_status != "active" or object_.deleted_at is not None:
        return None
    kinds = ("thumbnail",) if object_.mime_type.startswith("image/") else ("poster",) if object_.mime_type.startswith("video/") else ()
    if not kinds:
        return None
    return StorageDerivative.query.filter(
        StorageDerivative.storage_object_id == object_.id, StorageDerivative.derivative_type.in_(kinds),
        StorageDerivative.deleted_at.is_(None), StorageDerivative.object_key.is_not(None), StorageDerivative.object_key != "",
    ).first()


def _thumbnail_versions(files):
    object_to_file = {file.storage_object_id: file.id for file in files if file.is_active and file.deleted_at is None}
    if not object_to_file:
        return {}
    rows = StorageDerivative.query.filter(
        StorageDerivative.storage_object_id.in_(object_to_file), StorageDerivative.derivative_type.in_(("thumbnail", "poster")),
        StorageDerivative.deleted_at.is_(None), StorageDerivative.object_key.is_not(None), StorageDerivative.object_key != "",
    ).all()
    return {object_to_file[row.storage_object_id]: row.id for row in rows}


def _thumbnail_placeholder():
    response = send_file(Path(current_app.static_folder) / "img" / "attachment-processing.svg", mimetype="image/svg+xml", max_age=0)
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@bp.post("/files/<int:file_id>/rename")
def file_rename(file_id):
    document_file = _document_file_or_404(file_id)
    if not can_edit_project_document_file(current_user, document_file): abort(403)
    try: rename_file(current_user, document_file, request.form.get("display_name"))
    except DocumentValidationError as exc: return _fail(exc, _folder_url(document_file.folder_id, source=request.form))
    flash("Đã đổi tên tệp.", "success"); return redirect(_folder_url(document_file.folder_id, source=request.form))


@bp.post("/files/<int:file_id>/archive")
def file_archive(file_id):
    document_file = _document_file_or_404(file_id)
    if not can_delete_project_document_file(current_user, document_file): abort(403)
    archive_file(current_user, document_file); flash("Đã lưu trữ tệp.", "success")
    return redirect(_folder_url(document_file.folder_id, source=request.form))


@bp.post("/files/<int:file_id>/restore")
def file_restore(file_id):
    document_file = _document_file_or_404(file_id)
    if not can_restore_project_document_file(current_user, document_file): abort(403)
    try: restore_file(current_user, document_file)
    except DocumentValidationError as exc: return _fail(exc, _folder_url(document_file.folder_id, source=request.form))
    flash("Đã khôi phục tệp.", "success"); return redirect(_folder_url(document_file.folder_id, source=request.form))


def _bulk_payload_file_ids():
    return parse_file_ids(request)


def _bulk_folder_or_403(folder_id):
    folder = _folder_or_404(folder_id)
    if not can_view_project_document_folder(current_user, folder):
        abort(403)
    return folder


def _bulk_response(summary, action):
    changed = summary.get(action, 0)
    if not changed and summary.get("forbidden", 0):
        abort(403)
    return jsonify({"ok": True, **summary})


@bp.post("/folders/<int:folder_id>/files/bulk-archive")
def bulk_archive(folder_id):
    folder = _bulk_folder_or_403(folder_id)
    try:
        return _bulk_response(bulk_archive_files(current_user, folder, _bulk_payload_file_ids()), "archived")
    except (DocumentValidationError, BulkDownloadError) as exc:
        return jsonify(error=str(exc)), 400


@bp.post("/folders/<int:folder_id>/files/bulk-restore")
def bulk_restore(folder_id):
    folder = _bulk_folder_or_403(folder_id)
    try:
        return _bulk_response(bulk_restore_files(current_user, folder, _bulk_payload_file_ids()), "restored")
    except (DocumentValidationError, BulkDownloadError) as exc:
        return jsonify(error=str(exc)), 400


@bp.post("/folders/<int:folder_id>/files/bulk-signed-download")
def bulk_signed_download(folder_id):
    folder = _bulk_folder_or_403(folder_id)
    try:
        result = request_document_download(current_user, folder, _bulk_payload_file_ids())
        return stream_zip_download(current_user, result) if result["kind"] == "zip" else jsonify(ok=True, **result)
    except PermissionError:
        abort(403)
    except (DocumentValidationError, BulkDownloadError) as exc:
        return jsonify(error=str(exc)), 400


@bp.post("/folders/<int:folder_id>/files/bulk-download-validate")
def bulk_download_validate(folder_id):
    folder = _bulk_folder_or_403(folder_id)
    try:
        return jsonify(ok=True, **preflight_document_download(current_user, folder, _bulk_payload_file_ids()))
    except PermissionError:
        abort(403)
    except (DocumentValidationError, BulkDownloadError) as exc:
        return jsonify(error=str(exc)), 400


@bp.get("/bulk-download-jobs/<int:job_id>")
def bulk_download_status(job_id):
    job = db.get_or_404(BulkDownloadJob, job_id)
    try:
        return jsonify(ok=True, **serialize_job(current_user, job))
    except PermissionError:
        abort(403)


def _folder_or_404(folder_id): return db.get_or_404(ProjectDocumentFolder, folder_id)
def _fail(exc, redirect_to):
    flash(str(exc), "danger"); return redirect(redirect_to)


@bp.post("/folders/new")
def new_folder():
    parent = _folder_or_404(request.form.get("parent_id", type=int))
    if not can_create_project_document_folder(current_user, parent): abort(403)
    try: create_folder(current_user, parent, request.form.get("name"), request.form.get("description"), request.form.get("is_restricted") == "1")
    except DocumentValidationError as exc: return _fail(exc, _folder_url(parent.id, source=request.form))
    flash("Đã tạo thư mục.", "success"); return redirect(_folder_url(parent.id, source=request.form))


@bp.post("/folders/<int:folder_id>/rename")
def rename(folder_id):
    target = _folder_or_404(folder_id)
    if not can_edit_project_document_folder(current_user, target): abort(403)
    try: rename_folder(current_user, target, request.form.get("name"))
    except DocumentValidationError as exc: return _fail(exc, _folder_url(target.parent_id or target.id, source=request.form))
    flash("Đã đổi tên thư mục.", "success"); return redirect(_folder_url(target.parent_id or target.id, source=request.form))


@bp.post("/folders/<int:folder_id>/move")
def move(folder_id):
    target = _folder_or_404(folder_id); destination = _folder_or_404(request.form.get("parent_id", type=int))
    if not can_edit_project_document_folder(current_user, target) or not can_create_project_document_folder(current_user, destination): abort(403)
    try: move_folder(current_user, target, destination)
    except DocumentValidationError as exc: return _fail(exc, _folder_url(target.parent_id or target.id, source=request.form))
    flash("Đã di chuyển thư mục.", "success"); return redirect(_folder_url(destination.id, source=request.form))


@bp.post("/folders/<int:folder_id>/archive")
def archive(folder_id):
    target = _folder_or_404(folder_id)
    if not can_delete_project_document_folder(current_user, target): abort(403)
    parent_id = target.parent_id
    try: archive_folder(current_user, target)
    except DocumentValidationError as exc: return _fail(exc, _folder_url(target.id, source=request.form))
    archived_url = _folder_url(parent_id, folder_status="archived", source=request.form)
    flash(Markup(f'Đã lưu trữ thư mục. <a class="alert-link" href="{archived_url}">Xem thư mục đã lưu trữ</a>.'), "success")
    return redirect(_folder_url(parent_id, folder_status="active", source=request.form))


@bp.post("/folders/<int:folder_id>/restore")
def restore(folder_id):
    target = _folder_or_404(folder_id)
    if not can_restore_project_document_folder(current_user, target): abort(403)
    try: restore_folder(current_user, target)
    except DocumentValidationError as exc: return _fail(exc, _folder_url(target.parent_id or target.id, source=request.form))
    flash("Đã khôi phục thư mục.", "success"); return redirect(_folder_url(target.parent_id, folder_status="active", source=request.form))


@bp.route("/folders/<int:folder_id>/permissions", methods=["GET", "POST"])
def permissions(folder_id):
    target = _folder_or_404(folder_id)
    if not can_share_project_document_folder(current_user, target, include_archived=not (target.is_active and target.deleted_at is None)): abort(403)
    if request.method == "POST":
        try:
            if request.form.get("remove_id"): remove_folder_permission(current_user, target, request.form.get("remove_id", type=int))
            else: set_folder_permission(current_user, target, request.form.get("principal_type"), request.form.get("principal_id"), request.form)
        except DocumentValidationError as exc: flash(str(exc), "danger")
        else: flash("Đã cập nhật quyền chia sẻ.", "success")
        return redirect(url_for("project_documents.permissions", folder_id=target.id))
    users = User.query.filter_by(is_active=True).order_by(User.full_name, User.username).all()
    roles = Role.query.order_by(Role.name).all()
    principal_options = [
        {"type": "user", "id": item.id, "name": item.full_name, "username": item.username,
         "email": item.email, "role": item.role.name if item.role else item.role_code}
        for item in users
    ] + [
        {"type": "role", "id": item.id, "name": item.name, "code": item.code,
         "description": item.description or ""}
        for item in roles
    ]
    entries = ProjectDocumentFolderPermission.query.filter_by(folder_id=target.id).order_by(
        ProjectDocumentFolderPermission.principal_type, ProjectDocumentFolderPermission.id).all()
    return render_template("project_documents/permissions.html", folder=target, entries=entries,
        principal_options=principal_options)
