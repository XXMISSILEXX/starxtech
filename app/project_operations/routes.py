from datetime import date

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.auth.permissions import can_read_project
from app.extensions import db
from app.models import (
    Project,
    ProjectContractor,
    ProjectContractorAssignment,
    ProjectContractorAssignmentStatus,
    ProjectContractorRole,
)
from app.project_operations import bp
from app.project_operations.services import (
    accessible_contractors_query,
    active_assignment_count,
    archive_contractor,
    assign_contractor,
    can_access_contractor,
    can_manage_contractor,
    contractor_name_is_available,
    create_or_update_contractor,
    end_assignment,
    restore_contractor,
    update_assignment,
)


ROLE_PATHS = {
    "construction": ProjectContractorRole.CONSTRUCTION.value,
    "solution": ProjectContractorRole.SOLUTION.value,
}


def _permission_required(code):
    if not current_user.can(code):
        abort(403)


def _contractor_or_404(contractor_id):
    return ProjectContractor.query.filter_by(id=contractor_id).first_or_404()


def _project_or_404(project_id):
    return Project.query.filter(Project.id == project_id, Project.deleted_at.is_(None)).first_or_404()


def _date_from_form(field):
    value = request.form.get(field, "").strip()
    return date.fromisoformat(value) if value else None


def _assignments_for_project(project, role):
    return ProjectContractorAssignment.query.filter_by(project_id=project.id, role=role).order_by(
        ProjectContractorAssignment.status != ProjectContractorAssignmentStatus.ENDED.value,
        ProjectContractorAssignment.created_at.desc(),
    ).all()


def _render_project_role(project, role):
    return render_template(
        "project_operations/project_assignments.html",
        project=project,
        role=role,
        assignments=_assignments_for_project(project, role),
        contractors=accessible_contractors_query(current_user).order_by(ProjectContractor.name.asc()).all(),
        statuses=ProjectContractorAssignmentStatus,
        can_manage=current_user.can("contractor_assignments.manage"),
        can_end=current_user.can("contractor_assignments.end"),
        active_count=active_assignment_count(project.id, role),
    )


@bp.get("/project-operations/contractors")
def contractors_index():
    _permission_required("project_contractors.view")
    query = accessible_contractors_query(current_user, include_archived=request.args.get("archived") == "1")
    search = request.args.get("q", "").strip()
    if search:
        query = query.filter(ProjectContractor.name.ilike(f"%{search}%"))
    return render_template("project_operations/contractors/index.html", contractors=query.order_by(ProjectContractor.is_active.desc(), ProjectContractor.name.asc()).all(), search=search)


@bp.get("/project-operations/contractors/<int:contractor_id>")
def contractor_detail(contractor_id):
    _permission_required("project_contractors.view")
    contractor = _contractor_or_404(contractor_id)
    if not can_access_contractor(current_user, contractor):
        abort(403)
    visible_project_ids = {assignment.project_id for assignment in contractor.assignments if can_read_project(assignment.project_id)}
    assignments = [assignment for assignment in contractor.assignments if assignment.project_id in visible_project_ids]
    return render_template(
        "project_operations/contractors/detail.html",
        contractor=contractor,
        assignments=assignments,
        can_edit=current_user.can("project_contractors.edit") and can_manage_contractor(current_user, contractor),
        can_archive=current_user.can("project_contractors.archive") and can_manage_contractor(current_user, contractor),
    )


@bp.route("/project-operations/contractors/new", methods=["GET", "POST"])
def contractor_create():
    _permission_required("project_contractors.create")
    if request.method == "GET":
        return render_template("project_operations/contractors/form.html", contractor=None)
    name = request.form.get("name", "").strip()
    if not name or not contractor_name_is_available(name):
        flash("Tên nhà thầu là bắt buộc và không được trùng.", "danger")
        return render_template("project_operations/contractors/form.html", contractor=None), 400
    contractor = create_or_update_contractor(
        None, name=name, short_name=request.form.get("short_name"), description=request.form.get("description"),
        phone=request.form.get("phone"), email=request.form.get("email"), address=request.form.get("address"), actor_id=current_user.id,
    )
    db.session.commit()
    flash("Đã tạo nhà thầu.", "success")
    return redirect(url_for("project_operations.contractor_detail", contractor_id=contractor.id))


@bp.route("/project-operations/contractors/<int:contractor_id>/edit", methods=["GET", "POST"])
def contractor_edit(contractor_id):
    _permission_required("project_contractors.edit")
    contractor = _contractor_or_404(contractor_id)
    if not can_access_contractor(current_user, contractor) or not can_manage_contractor(current_user, contractor):
        abort(403)
    if request.method == "GET":
        return render_template("project_operations/contractors/form.html", contractor=contractor)
    name = request.form.get("name", "").strip()
    if not name or not contractor_name_is_available(name, contractor.id):
        flash("Tên nhà thầu là bắt buộc và không được trùng.", "danger")
        return render_template("project_operations/contractors/form.html", contractor=contractor), 400
    create_or_update_contractor(
        contractor, name=name, short_name=request.form.get("short_name"), description=request.form.get("description"),
        phone=request.form.get("phone"), email=request.form.get("email"), address=request.form.get("address"), actor_id=current_user.id,
    )
    db.session.commit()
    flash("Đã cập nhật nhà thầu.", "success")
    return redirect(url_for("project_operations.contractor_detail", contractor_id=contractor.id))


@bp.post("/project-operations/contractors/<int:contractor_id>/archive")
def contractor_archive(contractor_id):
    _permission_required("project_contractors.archive")
    contractor = _contractor_or_404(contractor_id)
    if not can_access_contractor(current_user, contractor) or not can_manage_contractor(current_user, contractor):
        abort(403)
    try:
        archive_contractor(contractor, actor_id=current_user.id)
    except ValueError as error:
        flash(str(error), "danger")
        return redirect(url_for("project_operations.contractor_detail", contractor_id=contractor.id))
    db.session.commit()
    flash("Đã lưu trữ nhà thầu. Lịch sử assignment được giữ nguyên.", "success")
    return redirect(url_for("project_operations.contractors_index", archived="1"))


@bp.post("/project-operations/contractors/<int:contractor_id>/restore")
def contractor_restore(contractor_id):
    _permission_required("project_contractors.archive")
    contractor = _contractor_or_404(contractor_id)
    if not can_access_contractor(current_user, contractor) or not can_manage_contractor(current_user, contractor):
        abort(403)
    try:
        restore_contractor(contractor, actor_id=current_user.id)
    except ValueError as error:
        flash(str(error), "danger")
        return redirect(url_for("project_operations.contractor_detail", contractor_id=contractor.id))
    db.session.commit()
    flash("Đã khôi phục nhà thầu.", "success")
    return redirect(url_for("project_operations.contractor_detail", contractor_id=contractor.id))


@bp.route("/projects/<int:project_id>/contractors/<role_path>", methods=["GET", "POST"])
def project_contractors(project_id, role_path):
    _permission_required("contractor_assignments.view")
    role = ROLE_PATHS.get(role_path)
    if role is None:
        abort(404)
    project = _project_or_404(project_id)
    if not can_read_project(project.id):
        abort(403)
    if request.method == "GET":
        return _render_project_role(project, role)
    _permission_required("contractor_assignments.manage")
    contractor = _contractor_or_404(request.form.get("contractor_id", type=int))
    try:
        status = request.form.get("status", ProjectContractorAssignmentStatus.ACTIVE.value)
        if status == ProjectContractorAssignmentStatus.ENDED.value:
            raise ValueError("Assignment mới không thể ở trạng thái ENDED.")
        assign_contractor(
            project=project, contractor=contractor, role=role,
            status=status,
            started_on=_date_from_form("started_on"), note=request.form.get("note"), actor_id=current_user.id,
        )
        db.session.commit()
    except (ValueError, TypeError) as error:
        db.session.rollback()
        flash(str(error), "danger")
    else:
        flash("Đã gán nhà thầu cho dự án.", "success")
    return redirect(url_for("project_operations.project_contractors", project_id=project.id, role_path=role_path))


@bp.post("/project-operations/assignments/<int:assignment_id>/update")
def assignment_update(assignment_id):
    _permission_required("contractor_assignments.manage")
    assignment = ProjectContractorAssignment.query.get_or_404(assignment_id)
    if not can_read_project(assignment.project_id):
        abort(403)
    try:
        update_assignment(
            assignment, status=request.form.get("status", assignment.status), started_on=_date_from_form("started_on"),
            ended_on=_date_from_form("ended_on"), note=request.form.get("note"), actor_id=current_user.id,
        )
        db.session.commit()
    except (ValueError, TypeError) as error:
        db.session.rollback()
        flash(str(error), "danger")
    else:
        flash("Đã cập nhật assignment.", "success")
    return redirect(url_for("project_operations.project_contractors", project_id=assignment.project_id, role_path=assignment.role.lower()))


@bp.post("/project-operations/assignments/<int:assignment_id>/end")
def assignment_end(assignment_id):
    _permission_required("contractor_assignments.end")
    assignment = ProjectContractorAssignment.query.get_or_404(assignment_id)
    if not can_read_project(assignment.project_id):
        abort(403)
    try:
        end_assignment(assignment, ended_on=_date_from_form("ended_on"), actor_id=current_user.id)
        db.session.commit()
    except (ValueError, TypeError) as error:
        db.session.rollback()
        flash(str(error), "danger")
    else:
        flash("Đã kết thúc assignment; lịch sử vẫn được giữ.", "success")
    return redirect(url_for("project_operations.project_contractors", project_id=assignment.project_id, role_path=assignment.role.lower()))
