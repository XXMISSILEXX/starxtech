from flask import abort, flash, jsonify, render_template, request
from flask_login import current_user

from app.dashboard import api_bp, bp
from app.dashboard.services import (
    DashboardFilterError,
    dashboard_context,
    parse_filters,
    report_count_chart_data,
    status_chart_data,
)


@bp.get("")
@bp.get("/")
def index():
    if not current_user.can("reports.view"):
        abort(403)
    try:
        filters = parse_filters(request.args)
    except DashboardFilterError as exc:
        flash(str(exc), "danger")
        filters = parse_filters({})
    return render_template("dashboard/index.html", **dashboard_context(filters))


@api_bp.get("/status-chart")
def status_chart():
    if not current_user.can("reports.view"):
        abort(403)
    filters = _filters_or_400()
    return jsonify(status_chart_data(filters))


@api_bp.get("/report-count-chart")
def report_count_chart():
    if not current_user.can("reports.view"):
        abort(403)
    filters = _filters_or_400()
    return jsonify(report_count_chart_data(filters))


def _filters_or_400():
    try:
        return parse_filters(request.args)
    except DashboardFilterError as exc:
        abort(400, str(exc))
