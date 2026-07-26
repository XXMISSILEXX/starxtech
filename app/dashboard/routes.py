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
    project_section_status_payload,
)
from app.auth.permissions import can_access_reports_module
from app.auth.permissions import can_read_project
from app.models import Customer, Project, ProjectContractor
from datetime import datetime


@bp.get("/system")
def system_dashboard():
    _require_dashboard_scope("dashboards.system.view")
    return render_template(
        "dashboard/scoped.html",
        dashboard_title="Dashboard toàn hệ thống",
        dashboard_kind="system",
        dashboard_api=url_for("dashboard_api.system_dashboard_payload"),
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
    return render_template("dashboard/contractor.html", **context)


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
