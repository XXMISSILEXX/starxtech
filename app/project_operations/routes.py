from datetime import date

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.auth.permissions import can_read_project
from app.date_utils import format_vn_date, parse_vn_date
from app.extensions import db
from sqlalchemy import func, or_
from sqlalchemy.orm import contains_eager, joinedload
from app.models import (
    Project,
    ProjectContractor,
    ProjectContractorAssignment,
    ProjectContractorAssignmentStatus,
    ProjectContractorRole,
    ProjectUpdate,
    ProjectUpdateType,
    Customer,
    DailyReport,
)
from app.project_memberships import accessible_project_ids
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
    create_project_update,
    edit_project_update,
    soft_delete_project_update,
    updates_query,
)


ROLE_PATHS = {
    "construction": ProjectContractorRole.CONSTRUCTION.value,
    "solution": ProjectContractorRole.SOLUTION.value,
}


@bp.get("/project-operations")
def operations_index():
    _permission_required("project_operations.view")
    project_ids = accessible_project_ids(current_user, ("can_view_project",))
    # The explicit outer join is required for the customer sort.  Loader
    # options alone use their own alias and do not put ``customers`` in FROM.
    query = Project.query.outerjoin(Customer, Project.customer_id == Customer.id).options(
        contains_eager(Project.customer)
    ).filter(Project.deleted_at.is_(None))
    if project_ids is not None:
        query = query.filter(Project.id.in_(project_ids or [0]))
    search = request.args.get("q", "").strip()
    if search:
        query = query.filter(or_(Project.code.ilike(f"%{search}%"), Project.name.ilike(f"%{search}%"), Customer.name.ilike(f"%{search}%")))
    projects = query.order_by(Customer.name.asc().nulls_last(), Project.name.asc(), Project.id.asc()).all()
    ids = [project.id for project in projects]
    today = date.today()
    role_counts = {(row[0], row[1]): row[2] for row in db.session.query(ProjectContractorAssignment.project_id, ProjectContractorAssignment.role, func.count(ProjectContractorAssignment.id)).filter(ProjectContractorAssignment.project_id.in_(ids or [0]), ProjectContractorAssignment.status != "ENDED").group_by(ProjectContractorAssignment.project_id, ProjectContractorAssignment.role).all()}
    submitted = {row[0] for row in db.session.query(DailyReport.project_id).filter(DailyReport.project_id.in_(ids or [0]), DailyReport.report_date == today)}
    groups = {}
    for project in projects:
        customer = project.customer
        key = customer.id if customer else 0
        groups.setdefault(key, {"customer": customer, "projects": []})["projects"].append({"project": project, "submitted": project.id in submitted, "construction": role_counts.get((project.id, "CONSTRUCTION"), 0), "solution": role_counts.get((project.id, "SOLUTION"), 0)})
    return render_template("project_operations/index.html", groups=list(groups.values()), search=search)


def _permission_required(code):
    if not current_user.can(code):
        abort(403)


def _contractor_or_404(contractor_id):
    return ProjectContractor.query.filter_by(id=contractor_id).first_or_404()


def _project_or_404(project_id):
    return Project.query.filter(Project.id == project_id, Project.deleted_at.is_(None)).first_or_404()


def _assignment_or_404(assignment_id):
    assignment = db.session.get(ProjectContractorAssignment, assignment_id)
    if assignment is None:
        abort(404)
    return assignment


@bp.get("/projects/<int:project_id>/workspace")
def project_workspace(project_id):
    project = _project_or_404(project_id)
    if not can_read_project(project.id):
        abort(403)
    cards = [
        ("overview", "Tổng quan", "Xem tình trạng và số liệu tổng hợp của dự án.", "bi-speedometer2", "dashboards.project.view", url_for("projects.dashboard", project_id=project.id)),
        ("reports", "Báo cáo ngày", "Xem lịch sử và tạo báo cáo theo ngày.", "bi-journal-text", "reports.view", url_for("projects.reports", project_id=project.id)),
        ("updates", "Báo cáo xuyên suốt", "Ghi nhận tiến độ, bàn giao và các cập nhật dài hạn.", "bi-clock-history", "project_updates.view", url_for("project_operations.project_updates", project_id=project.id)),
        ("issues", "Vấn đề tồn đọng", "Quản lý các vấn đề cần tiếp tục theo dõi.", "bi-exclamation-diamond", "issues.view", url_for("projects.issues", project_id=project.id)),
        ("construction", "Đối tác thi công", "Quản lý các đơn vị thi công đang tham gia dự án.", "bi-cone-striped", "contractor_assignments.view", url_for("project_operations.project_contractors", project_id=project.id, role_path="construction")),
        ("solution", "Đối tác giải pháp", "Quản lý các đơn vị cung cấp giải pháp cho dự án.", "bi-lightbulb", "contractor_assignments.view", url_for("project_operations.project_contractors", project_id=project.id, role_path="solution")),
    ]
    report_count = DailyReport.query.filter_by(project_id=project.id).count()
    update_count = ProjectUpdate.query.filter(ProjectUpdate.project_id == project.id, ProjectUpdate.deleted_at.is_(None)).count()
    assignment_counts = dict(db.session.query(ProjectContractorAssignment.role, func.count(ProjectContractorAssignment.id)).filter(ProjectContractorAssignment.project_id == project.id, ProjectContractorAssignment.status != "ENDED").group_by(ProjectContractorAssignment.role).all())
    summaries = {"reports": f"{report_count} báo cáo", "updates": f"{update_count} cập nhật", "construction": f"{assignment_counts.get('CONSTRUCTION', 0)} đối tác", "solution": f"{assignment_counts.get('SOLUTION', 0)} đối tác"}
    visible_cards = [(*card, summaries.get(card[0], "")) for card in cards if current_user.can(card[4])]
    return render_template("project_operations/workspace.html", project=project, cards=visible_cards)


def _date_from_form(field):
    return parse_vn_date(request.form.get(field), field_label="Ngày")


def _assignments_for_project(project, role, status=None):
    query = ProjectContractorAssignment.query.filter_by(project_id=project.id, role=role)
    if status and status != "ALL":
        query = query.filter(ProjectContractorAssignment.status == status)
    return query.order_by(
        ProjectContractorAssignment.status != ProjectContractorAssignmentStatus.ENDED.value,
        ProjectContractorAssignment.created_at.desc(),
    ).all()


def _render_project_role(project, role, *, form_values=None, form_error=None, open_add_modal=False, edit_assignment_id=None, open_end_modal_id=None):
    selected_status = request.args.get("status", "")
    if selected_status not in {"", "ALL", *[item.value for item in ProjectContractorAssignmentStatus]}:
        abort(400)
    return render_template(
        "project_operations/project_assignments.html",
        project=project,
        role=role,
        assignments=_assignments_for_project(project, role, selected_status),
        contractors=accessible_contractors_query(current_user).order_by(ProjectContractor.name.asc()).all(),
        statuses=ProjectContractorAssignmentStatus,
        can_manage=current_user.can("contractor_assignments.manage"),
        can_end=current_user.can("contractor_assignments.end"),
        active_count=active_assignment_count(project.id, role),
        selected_status=selected_status,
        form_values=form_values or {},
        form_error=form_error,
        open_add_modal=open_add_modal,
        edit_assignment_id=edit_assignment_id,
        open_end_modal_id=open_end_modal_id,
        today_vn=format_vn_date(date.today()),
        can_contractor_dashboard=current_user.can("dashboards.contractor.view"),
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
        can_dashboard=current_user.can("dashboards.contractor.view"),
    )


@bp.route("/project-operations/contractors/new", methods=["GET", "POST"])
def contractor_create():
    _permission_required("project_contractors.create")
    if request.method == "GET":
        return render_template("project_operations/contractors/form.html", contractor=None)
    name = request.form.get("name", "").strip()
    if not name or not contractor_name_is_available(name):
        flash("Tên đối tác là bắt buộc và không được trùng.", "danger")
        return render_template("project_operations/contractors/form.html", contractor=None), 400
    contractor = create_or_update_contractor(
        None, name=name, short_name=request.form.get("short_name"), description=request.form.get("description"),
        phone=request.form.get("phone"), email=request.form.get("email"), address=request.form.get("address"), actor_id=current_user.id,
    )
    db.session.commit()
    flash("Đã tạo đối tác.", "success")
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
        flash("Tên đối tác là bắt buộc và không được trùng.", "danger")
        return render_template("project_operations/contractors/form.html", contractor=contractor), 400
    create_or_update_contractor(
        contractor, name=name, short_name=request.form.get("short_name"), description=request.form.get("description"),
        phone=request.form.get("phone"), email=request.form.get("email"), address=request.form.get("address"), actor_id=current_user.id,
    )
    db.session.commit()
    flash("Đã cập nhật đối tác.", "success")
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
    flash("Đã lưu trữ đối tác. Lịch sử liên kết được giữ nguyên.", "success")
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
    flash("Đã khôi phục đối tác.", "success")
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
        assign_contractor(
            project=project, contractor=contractor, role=role,
            status=status,
            started_on=_date_from_form("started_on"), note=request.form.get("note"), actor_id=current_user.id,
        )
        db.session.commit()
    except (ValueError, TypeError) as error:
        db.session.rollback()
        return _render_project_role(
            project, role, form_values=request.form.to_dict(), form_error=str(error), open_add_modal=True
        ), 400
    else:
        flash("Đã thêm đối tác vào dự án.", "success")
    return redirect(url_for("project_operations.project_contractors", project_id=project.id, role_path=role_path))


@bp.post("/project-operations/assignments/<int:assignment_id>/update")
def assignment_update(assignment_id):
    _permission_required("contractor_assignments.manage")
    assignment = _assignment_or_404(assignment_id)
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
        return _render_project_role(
            assignment.project,
            assignment.role,
            form_values=request.form.to_dict(),
            form_error=str(error),
            edit_assignment_id=assignment.id,
        ), 400
    else:
        flash("Đã cập nhật đối tác.", "success")
    return redirect(url_for("project_operations.project_contractors", project_id=assignment.project_id, role_path=assignment.role.lower()))


@bp.post("/project-operations/assignments/<int:assignment_id>/end")
def assignment_end(assignment_id):
    _permission_required("contractor_assignments.end")
    assignment = _assignment_or_404(assignment_id)
    if not can_read_project(assignment.project_id):
        abort(403)
    try:
        end_assignment(assignment, ended_on=_date_from_form("ended_on"), actor_id=current_user.id)
        db.session.commit()
    except (ValueError, TypeError) as error:
        db.session.rollback()
        return _render_project_role(
            assignment.project,
            assignment.role,
            form_values=request.form.to_dict(),
            form_error=str(error),
            open_end_modal_id=assignment.id,
        ), 400
    else:
        flash("Đã gỡ đối tác khỏi dự án; lịch sử vẫn được giữ.", "success")
    return redirect(url_for("project_operations.project_contractors", project_id=assignment.project_id, role_path=assignment.role.lower()))


def _update_or_404(update_id):
    return ProjectUpdate.query.filter_by(id=update_id).first_or_404()


def _can_edit_update(update):
    return current_user.can("project_updates.edit_all") or (
        current_user.can("project_updates.edit") and update.created_by_id == current_user.id
    )


def _update_form(project, update=None, assignment=None, *, form_values=None, form_error=None):
    assignments = ProjectContractorAssignment.query.filter(
        ProjectContractorAssignment.project_id == project.id,
        ProjectContractorAssignment.status != ProjectContractorAssignmentStatus.ENDED.value,
    ).order_by(ProjectContractorAssignment.role, ProjectContractorAssignment.id).all()
    values = form_values or {
        "update_type": update.update_type if update else ProjectUpdateType.GENERAL.value,
        "contractor_assignment_id": assignment.id if assignment else "",
        "update_date": format_vn_date(update.update_date) if update else "",
        "title": update.title if update else "",
        "content": update.content if update else "",
    }
    return render_template("project_operations/updates/form.html", project=project, update=update,
                           locked_assignment=assignment, assignments=assignments, types=ProjectUpdateType,
                           form_values=values, form_error=form_error)


@bp.get("/projects/<int:project_id>/updates")
def project_updates(project_id):
    _permission_required("project_updates.view")
    project = _project_or_404(project_id)
    if not can_read_project(project.id):
        abort(403)
    update_type = request.args.get("type") or None
    return render_template("project_operations/updates/index.html", project=project,
                           updates=updates_query(project_id=project.id, update_type=update_type).all(),
                           types=ProjectUpdateType, selected_type=update_type,
                           can_create=current_user.can("project_updates.create"))


@bp.get("/project-operations/updates")
def project_updates_index():
    _permission_required("project_updates.view")
    project_ids = accessible_project_ids(current_user, ("can_view_project",))
    query = ProjectUpdate.query.options(joinedload(ProjectUpdate.project)).join(Project).filter(ProjectUpdate.deleted_at.is_(None))
    if project_ids is not None:
        query = query.filter(Project.id.in_(project_ids or [0]))
    customer_id = request.args.get("customer_id", type=int)
    contractor_id = request.args.get("contractor_id", type=int)
    if customer_id:
        query = query.filter(Project.customer_id == customer_id)
    if contractor_id:
        query = query.join(ProjectContractorAssignment, ProjectUpdate.contractor_assignment_id == ProjectContractorAssignment.id).filter(ProjectContractorAssignment.contractor_id == contractor_id)
    return render_template("project_operations/updates/all.html", updates=query.order_by(ProjectUpdate.update_date.desc(), ProjectUpdate.created_at.desc(), ProjectUpdate.id.desc()).all())


@bp.get("/projects/<int:project_id>/updates/new")
def project_update_new(project_id):
    _permission_required("project_updates.create")
    project = _project_or_404(project_id)
    if not can_read_project(project.id):
        abort(403)
    assignment_id = request.args.get("assignment_id", type=int)
    assignment = _assignment_or_404(assignment_id) if assignment_id else None
    if assignment is not None and assignment.project_id != project.id:
        abort(403)
    return _update_form(project, assignment=assignment)


@bp.post("/projects/<int:project_id>/updates")
def project_update_create(project_id):
    _permission_required("project_updates.create")
    project = _project_or_404(project_id)
    if not can_read_project(project.id):
        abort(403)
    assignment_id = request.form.get("contractor_assignment_id", type=int)
    assignment = _assignment_or_404(assignment_id) if assignment_id else None
    try:
        update = create_project_update(project=project, assignment=assignment,
            update_type=request.form.get("update_type", "GENERAL"), title=request.form.get("title", ""),
            content=request.form.get("content", ""), update_date=_date_from_form("update_date"), actor_id=current_user.id)
        db.session.commit()
    except (ValueError, TypeError) as error:
        db.session.rollback(); flash(str(error), "danger")
        return _update_form(project, assignment=assignment, form_values=request.form.to_dict(), form_error=str(error)), 400
    flash("Đã thêm cập nhật dự án.", "success")
    return redirect(url_for("project_operations.project_updates", project_id=update.project_id))


@bp.route("/project-updates/<int:update_id>/edit", methods=["GET", "POST"])
def project_update_edit(update_id):
    update = _update_or_404(update_id)
    if not can_read_project(update.project_id) or not _can_edit_update(update):
        abort(403)
    if request.method == "GET":
        return _update_form(update.project, update=update, assignment=update.contractor_assignment)
    try:
        edit_project_update(update, update_type=request.form.get("update_type", update.update_type),
            title=request.form.get("title", ""), content=request.form.get("content", ""),
            update_date=_date_from_form("update_date"), actor_id=current_user.id)
        db.session.commit()
    except (ValueError, TypeError) as error:
        db.session.rollback(); flash(str(error), "danger")
        return _update_form(update.project, update=update, assignment=update.contractor_assignment, form_values=request.form.to_dict(), form_error=str(error)), 400
    flash("Đã chỉnh sửa cập nhật dự án.", "success")
    return redirect(url_for("project_operations.project_updates", project_id=update.project_id))


@bp.post("/project-updates/<int:update_id>/delete")
def project_update_delete(update_id):
    _permission_required("project_updates.delete")
    update = _update_or_404(update_id)
    if not can_read_project(update.project_id):
        abort(403)
    soft_delete_project_update(update, actor_id=current_user.id)
    db.session.commit()
    flash("Đã xóa mềm cập nhật. Audit được giữ lại.", "success")
    return redirect(url_for("project_operations.project_updates", project_id=update.project_id))


@bp.get("/project-assignments/<int:assignment_id>/updates")
def assignment_updates(assignment_id):
    _permission_required("project_updates.view")
    assignment = _assignment_or_404(assignment_id)
    if not can_read_project(assignment.project_id):
        abort(403)
    return render_template("project_operations/updates/index.html", project=assignment.project,
                           assignment=assignment, updates=updates_query(assignment_id=assignment.id).all(),
                           types=ProjectUpdateType, selected_type=None,
                           can_create=current_user.can("project_updates.create"))
