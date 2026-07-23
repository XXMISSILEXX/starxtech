import csv
from io import StringIO

from flask import Response, flash, render_template, request
from flask_login import current_user

from app.admin_storage import bp
from app.admin_storage.services import StorageDashboardFilterError, dashboard_context, parse_filters
from app.extensions import limiter
from app.permissions.services import permission_required


def _filters():
    try:
        return parse_filters(request.args)
    except StorageDashboardFilterError as exc:
        flash(str(exc), "danger")
        return parse_filters({})


@bp.get("")
@bp.get("/")
@permission_required("storage.dashboard.view")
def index():
    return render_template("admin_storage/index.html", **dashboard_context(_filters()))


@bp.get("/export.csv")
@permission_required("storage.dashboard.export")
@limiter.limit(lambda: __import__("flask").current_app.config.get("RATELIMIT_EXPORT_LIMIT", "10 per hour"))
def export_csv():
    data = dashboard_context(_filters())
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["section", "label", "bytes", "count", "storage_egress_bytes", "client_egress_bytes"])
    writer.writerow(["overview", "originals", data["originals"], "", "", ""])
    writer.writerow(["overview", "derivatives", data["derivatives"], "", "", ""])
    writer.writerow(["overview", "legacy_zip", data["zips"], "", "", ""])
    for row in data["usage_by_module"]: writer.writerow(["storage_module", row["label"], row["total"], "", "", ""])
    for row in data["module_breakdown"]: writer.writerow(["bandwidth_module", row.label, "", row.count, row.storage_bytes, row.client_bytes])
    for row in data["source_breakdown"]: writer.writerow(["bandwidth_source", row.label, "", row.count, row.storage_bytes, row.client_bytes])
    for row in data["top_users"]: writer.writerow(["top_user", row.full_name or row.username, row.bytes, row.count, "", row.bytes])
    for row in data["top_objects"]: writer.writerow(["top_object", row.original_filename or "Không còn metadata", row.bytes, row.count, "", row.bytes])
    return Response("\ufeff" + output.getvalue(), mimetype="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=storage-dashboard.csv"})
