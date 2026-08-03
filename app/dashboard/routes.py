from flask import abort, jsonify, render_template, request, url_for
from flask_login import current_user

from app.dashboard import api_bp, bp
from app.dashboard.services import (
    DashboardScope,
    DashboardFilterError,
    dashboard_scope_context,
    dashboard_scope_payload,
    contractor_dashboard_context,
    contractor_dashboard_payload,
    contractor_is_visible,
    parse_contractor_dashboard_filters,
    progress_dashboard_context,
    project_section_status_payload,
)
from app.auth.permissions import can_access_reports_module
from app.auth.permissions import can_read_project
from app.models import Customer, Project, ProjectContractor, ProjectStatus
from app.models import ProjectContractorAssignment
from datetime import datetime


@bp.get("/system")
def system_dashboard():
    _require_dashboard_scope("dashboards.system.view")
    return render_template(
        "dashboard/scoped.html",
        dashboard_title="Dashboard toàn hệ thống",
        dashboard_kind="system",
        dashboard_api=url_for("dashboard_api.system_dashboard_payload"),
        **dashboard_navigation_context("system"),
        **dashboard_scope_context(DashboardScope.system()),
    )


@bp.get("/customers/<int:customer_id>")
def customer_dashboard(customer_id):
    _require_dashboard_scope("dashboards.customer.view")
    # Authorize before loading the resource so users without global scope
    # cannot use this endpoint to enumerate Customer identifiers.
    customer = Customer.query.filter_by(id=customer_id, is_active=True).first_or_404()
    return render_template(
        "dashboard/scoped.html",
        dashboard_title=f"Dashboard khách hàng · {customer.name}",
        dashboard_kind="customer",
        customer=customer,
        dashboard_api=url_for("dashboard_api.customer_dashboard_payload", customer_id=customer.id),
        **dashboard_navigation_context("customer", customer_id=customer.id),
        **dashboard_scope_context(DashboardScope.customer(customer.id)),
    )


@bp.get("/contractors/<int:contractor_id>")
def contractor_dashboard(contractor_id):
    _require_contractor_dashboard()
    contractor = _contractor_or_404(contractor_id)
    filters = _contractor_filters_or_400()
    try:
        context = contractor_dashboard_context(contractor, filters)
    except DashboardFilterError as exc:
        abort(404, str(exc))
    context["dashboard_kind"] = "contractor"
    return render_template("dashboard/contractor.html", **context, **dashboard_navigation_context("contractor", contractor_id=contractor.id))


@bp.get("/progress")
def progress_dashboard():
    if not can_access_reports_module(current_user) or not current_user.can("dashboards.progress.view"):
        abort(403)
    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        abort(400, "page phải là số nguyên dương")
    return render_template(
        "dashboard/progress.html",
        dashboard_kind="progress",
        **progress_dashboard_context(page=page),
        **dashboard_navigation_context("progress"),
    )


@api_bp.get("/projects/<int:project_id>/section-status")
def project_section_status(project_id):
    if not can_access_reports_module(current_user) or not current_user.can("dashboards.project.view"):
        abort(403)
    project = Project.query.filter_by(id=project_id, deleted_at=None).first_or_404()
    if not can_read_project(project.id):
        abort(403)
    raw_date = request.args.get("selected_date", "")
    try:
        selected_date = datetime.strptime(raw_date, "%Y-%m-%d").date() if raw_date else None
    except ValueError:
        abort(400, "selected_date phải theo YYYY-MM-DD")
    return jsonify(project_section_status_payload(project, selected_date=selected_date))


@api_bp.get("/system/overview")
def system_dashboard_payload():
    _require_dashboard_scope("dashboards.system.view")
    return jsonify(dashboard_scope_payload(DashboardScope.system()))


@api_bp.get("/customers/<int:customer_id>/overview")
def customer_dashboard_payload(customer_id):
    _require_dashboard_scope("dashboards.customer.view")
    customer = Customer.query.filter_by(id=customer_id, is_active=True).first_or_404()
    return jsonify(dashboard_scope_payload(DashboardScope.customer(customer.id)))


@api_bp.get("/contractors/<int:contractor_id>/overview")
def contractor_dashboard_payload_api(contractor_id):
    _require_contractor_dashboard()
    contractor = _contractor_or_404(contractor_id)
    filters = _contractor_filters_or_400()
    try:
        return jsonify(contractor_dashboard_payload(contractor, filters))
    except DashboardFilterError as exc:
        abort(404, str(exc))


def _contractor_filters_or_400():
    try:
        return parse_contractor_dashboard_filters(request.args)
    except DashboardFilterError as exc:
        abort(400, str(exc))


def _contractor_or_404(contractor_id):
    contractor = ProjectContractor.query.filter_by(id=contractor_id).first_or_404()
    if not contractor_is_visible(contractor.id):
        abort(404)
    return contractor


def _require_contractor_dashboard():
    if not can_access_reports_module(current_user) or not current_user.can("dashboards.contractor.view"):
        abort(403)


def _require_dashboard_scope(permission):
    if (
        not can_access_reports_module(current_user)
        or not current_user.can(permission)
        or not current_user.can("projects.scope_all")
    ):
        abort(403)


def dashboard_navigation_context(kind, *, customer_id=None, project_id=None, contractor_id=None):
    """Permission-aware canonical dashboard navigation without resource leakage."""
    can_system = current_user.can("dashboards.system.view") and current_user.can("projects.scope_all")
    can_customer = current_user.can("dashboards.customer.view") and current_user.can("projects.scope_all")
    can_project = current_user.can("dashboards.project.view")
    can_contractor = current_user.can("dashboards.contractor.view")
    can_progress = current_user.can("dashboards.progress.view")
    visible_project_ids = DashboardScope.system().projects_query().with_entities(Project.id)
    customers = (
        Customer.query.join(Project, Project.customer_id == Customer.id)
        .filter(Customer.is_active.is_(True), Project.id.in_(visible_project_ids))
        .distinct().order_by(Customer.normalized_name.asc(), Customer.id.asc()).all() if can_customer else []
    )
    projects = (
        Project.query.filter(Project.id.in_(visible_project_ids))
        .order_by(Project.status != ProjectStatus.ACTIVE.value, Project.code.asc(), Project.name.asc(), Project.id.asc()).all()
        if can_project else []
    )
    contractors = (
        ProjectContractor.query.join(ProjectContractorAssignment)
        .join(Project, Project.id == ProjectContractorAssignment.project_id)
        .filter(Project.id.in_(visible_project_ids)).distinct().order_by(ProjectContractor.normalized_name.asc(), ProjectContractor.id.asc()).all()
        if can_contractor else []
    )
    cards = [
        {"kind": "system", "label": "Dashboard toàn hệ thống", "description": "Theo dõi tình hình tổng hợp của các dự án.", "icon": "bi-grid-1x2", "href": url_for("dashboard.system_dashboard") if can_system else None, "enabled": can_system},
        {"kind": "customer", "label": "Dashboard khách hàng", "description": "Theo dõi các dự án theo từng khách hàng.", "icon": "bi-people", "href": url_for("dashboard.customer_dashboard", customer_id=customers[0].id) if customers else None, "enabled": bool(customers)},
        {"kind": "project", "label": "Dashboard dự án", "description": "Xem số liệu và tiến độ của một dự án.", "icon": "bi-kanban", "href": url_for("projects.dashboard", project_id=projects[0].id) if projects else None, "enabled": bool(projects)},
        {"kind": "contractor", "label": "Dashboard đối tác", "description": "Theo dõi đối tác trong phạm vi dự án được cấp quyền.", "icon": "bi-buildings", "href": url_for("dashboard.contractor_dashboard", contractor_id=contractors[0].id) if contractors else None, "enabled": bool(contractors)},
        *([{"kind": "progress", "label": "Dashboard tiến độ thi công", "description": "Theo dõi các giai đoạn thi công trong dự án được cấp quyền.", "icon": "bi-bar-chart-steps", "href": url_for("dashboard.progress_dashboard"), "enabled": True}] if can_progress else []),
    ]
    return {
        "dashboard_navigation": cards,
        "dashboard_customers": customers,
        "dashboard_projects": projects,
        "dashboard_contractors": contractors,
        "selected_dashboard_customer_id": customer_id,
        "selected_dashboard_project_id": project_id,
        "selected_dashboard_contractor_id": contractor_id,
        "can_customer_dashboard": can_customer,
        "can_project_dashboard": can_project,
        "can_contractor_dashboard": can_contractor,
        "can_progress_dashboard": can_progress,
    }
