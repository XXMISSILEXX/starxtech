from flask import abort, flash, jsonify, render_template, request
from flask_login import current_user

from app.dashboard import api_bp, bp
from app.dashboard.services import (
    DashboardFilterError,
    dashboard_context,
    parse_filters,
    report_count_chart_data,
    status_chart_data,
    project_section_status_payload,
)
from app.auth.permissions import can_access_reports_module
from app.auth.permissions import can_read_project
from app.models import Project
from datetime import datetime


@bp.get("")
def index():
    if not can_access_reports_module(current_user):
        abort(403)
    try:
        filters = parse_filters(request.args)
    except DashboardFilterError as exc:
        flash(str(exc), "danger")
        filters = parse_filters({})
    return render_template("dashboard/index.html", **dashboard_context(filters))


@api_bp.get("/status-chart")
def status_chart():
    if not can_access_reports_module(current_user):
        abort(403)
    filters = _filters_or_400()
    return jsonify(status_chart_data(filters))


@api_bp.get("/report-count-chart")
def report_count_chart():
    if not can_access_reports_module(current_user):
        abort(403)
    filters = _filters_or_400()
    return jsonify(report_count_chart_data(filters))


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


def _filters_or_400():
    try:
        return parse_filters(request.args)
    except DashboardFilterError as exc:
        abort(400, str(exc))
