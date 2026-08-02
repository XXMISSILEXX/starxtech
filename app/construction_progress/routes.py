import re

from flask import abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user

from app.auth.permissions import can_create_progress_entry, can_edit_progress_entry, can_manage_progress_structure, progress_entry_required, progress_read_required, progress_structure_required
from app.extensions import db
from app.models import ProgressEntry, ProgressGroup, ProgressItem, ProgressType, Project
from app.construction_progress import bp
from app.construction_progress import services


def _project(project_id):
    return Project.query.filter_by(id=project_id).first_or_404()


def _type(project_id, type_id):
    return ProgressType.query.filter_by(id=type_id, project_id=project_id).first_or_404()


def _group(project_id, group_id):
    return ProgressGroup.query.filter_by(id=group_id, project_id=project_id).first_or_404()


def _item(project_id, item_id):
    return ProgressItem.query.filter_by(id=item_id, project_id=project_id).first_or_404()


def _entry(project_id, entry_id):
    return ProgressEntry.query.filter_by(id=entry_id, project_id=project_id).first_or_404()


def _batch_rows_from_form():
    rows = {}
    pattern = re.compile(r"^items-(\d+)-(id|name|unit|decimal_places|planned_quantity|opening_quantity|delete)$")
    for key, value in request.form.items():
        match = pattern.match(key)
        if match:
            rows.setdefault(int(match.group(1)), {})[match.group(2)] = value
    return [rows[index] for index in sorted(rows)]


def _entry_batch_rows_from_form():
    rows = {}
    pattern = re.compile(r"^entries-(\d+)-(group_id|item_id|quantity|note)$")
    for key, value in request.form.items():
        match = pattern.match(key)
        if match:
            rows.setdefault(int(match.group(1)), {})[match.group(2)] = value
    return [rows[index] for index in sorted(rows)]


def _type_detail_response(project, value, *, batch_form=None, entry_batch_form=None, overlay_errors=None, open_modal=None, status=200):
    tree = services.progress_tree(project, value)
    delete_summaries = {
        "type": services.deletion_summary_for_type(value),
        "groups": {group["group"].id: services.deletion_summary_for_group(group["group"]) for node in tree for group in node["groups"]},
        "items": {line["item"].id: services.deletion_summary_for_item(line["item"]) for node in tree for group in node["groups"] for line in group["items"]},
    }
    return render_template(
        "construction_progress/type_detail.html", project=project, progress_type=value,
        tree=tree, types=ProgressType.query.filter_by(project_id=project.id).all(),
        type_percent=services.type_percent(value), can_manage=can_manage_progress_structure(project.id),
        can_create=can_create_progress_entry(project.id),
        delete_summaries=delete_summaries, batch_form=batch_form,
        entry_batch_form=entry_batch_form, overlay_errors=overlay_errors or {"form": {}, "rows": {}},
        open_modal=open_modal, today=services.local_today(),
    ), status


@bp.get("/projects/<int:project_id>/progress")
@progress_read_required()
def project_progress(project_id):
    project = _project(project_id)
    return render_template("construction_progress/index.html", project=project, tree=services.progress_tree(project), can_manage=can_manage_progress_structure(project.id))


@bp.post("/projects/<int:project_id>/progress/types")
@progress_structure_required()
def create_type(project_id):
    value = services.create_type(project=_project(project_id), name=request.form.get("name", ""), value_mode=request.form.get("value_mode", "quantity"), actor_id=current_user.id)
    db.session.commit()
    flash("Đã tạo loại tiến độ.", "success")
    return redirect(url_for("construction_progress.project_progress", project_id=project_id))


@bp.post("/projects/<int:project_id>/progress/types/<int:type_id>/edit")
@progress_structure_required()
def edit_type(project_id, type_id):
    value = services.update_type(_type(project_id, type_id), name=request.form.get("name", ""), value_mode=request.form.get("value_mode", "quantity"), actor_id=current_user.id)
    db.session.commit()
    flash("Đã cập nhật loại tiến độ.", "success")
    return redirect(url_for("construction_progress.project_progress", project_id=project_id))


@bp.post("/projects/<int:project_id>/progress/types/<int:type_id>/delete")
@progress_structure_required()
def delete_type(project_id, type_id):
    try:
        services.delete_type(_type(project_id, type_id), confirm_name=request.form.get("confirm_name"), actor_id=current_user.id)
    except services.ConfirmationNameError as exc:
        abort(400, description=str(exc))
    db.session.commit()
    flash("Đã xoá vĩnh viễn loại tiến độ và dữ liệu bên trong.", "success")
    return redirect(url_for("construction_progress.project_progress", project_id=project_id))


@bp.get("/projects/<int:project_id>/progress/types/<int:type_id>")
@progress_read_required()
def type_detail(project_id, type_id):
    project = _project(project_id)
    value = _type(project_id, type_id)
    return _type_detail_response(project, value)


@bp.post("/projects/<int:project_id>/progress/types/<int:type_id>/groups/batch")
@progress_structure_required()
def create_group_batch(project_id, type_id):
    project, progress_type, rows = _project(project_id), _type(project_id, type_id), _batch_rows_from_form()
    batch_form = {"mode": "create", "group_name": request.form.get("name", ""), "rows": rows}
    try:
        services.create_group_batch(progress_type=progress_type, name=batch_form["group_name"], rows=rows, actor_id=current_user.id)
        db.session.commit()
    except services.BatchItemNotFoundError:
        db.session.rollback()
        abort(404)
    except ValueError as exc:
        db.session.rollback()
        errors = exc.errors if isinstance(exc, services.BatchValidationError) else {"form": {"_form": str(exc)}, "rows": {}}
        return _type_detail_response(project, progress_type, batch_form=batch_form, overlay_errors=errors, open_modal="createGroup", status=400)
    flash("Đã tạo khu vực và các hạng mục.", "success")
    return redirect(url_for("construction_progress.type_detail", project_id=project_id, type_id=type_id))


@bp.post("/projects/<int:project_id>/progress/groups/<int:group_id>/batch")
@progress_structure_required()
def update_group_batch(project_id, group_id):
    project, group, rows = _project(project_id), _group(project_id, group_id), _batch_rows_from_form()
    batch_form = {
        "mode": "edit", "group_id": group.id, "group_name": request.form.get("name", ""),
        "rows": rows, "confirm_deletions": request.form.get("confirm_deletions") == "on",
    }
    try:
        services.update_group_batch(group=group, name=batch_form["group_name"], rows=rows, confirm_deletions=batch_form["confirm_deletions"], actor_id=current_user.id)
        db.session.commit()
    except services.BatchItemNotFoundError:
        db.session.rollback()
        abort(404)
    except ValueError as exc:
        db.session.rollback()
        errors = exc.errors if isinstance(exc, services.BatchValidationError) else {"form": {"_form": str(exc)}, "rows": {}}
        return _type_detail_response(project, _type(project_id, group.progress_type_id), batch_form=batch_form, overlay_errors=errors, open_modal=f"editGroup-{group.id}", status=400)
    flash("Đã cập nhật khu vực và hạng mục.", "success")
    return redirect(url_for("construction_progress.type_detail", project_id=project_id, type_id=group.progress_type_id))


@bp.post("/projects/<int:project_id>/progress/types/<int:type_id>/entries/batch")
@progress_entry_required()
def create_entries_batch(project_id, type_id):
    project, progress_type, rows = _project(project_id), _type(project_id, type_id), _entry_batch_rows_from_form()
    entry_batch_form = {"report_date": request.form.get("report_date", ""), "rows": rows}
    try:
        services.create_entries_batch(progress_type=progress_type, report_date=entry_batch_form["report_date"], rows=rows, actor_id=current_user.id)
        db.session.commit()
    except services.BatchItemNotFoundError:
        db.session.rollback()
        abort(404)
    except ValueError as exc:
        db.session.rollback()
        errors = exc.errors if isinstance(exc, services.BatchValidationError) else {"form": {"_form": str(exc)}, "rows": {}}
        return _type_detail_response(project, progress_type, entry_batch_form=entry_batch_form, overlay_errors=errors, open_modal="createEntries", status=400)
    flash("Đã tạo các phiếu cập nhật ngày.", "success")
    return redirect(url_for("construction_progress.type_detail", project_id=project_id, type_id=type_id))


@bp.post("/projects/<int:project_id>/progress/types/<int:type_id>/groups")
@progress_structure_required()
def create_group(project_id, type_id):
    value = services.create_group(progress_type=_type(project_id, type_id), name=request.form.get("name", ""), actor_id=current_user.id)
    db.session.commit()
    flash("Đã tạo khu vực.", "success")
    return redirect(url_for("construction_progress.type_detail", project_id=project_id, type_id=type_id))


@bp.post("/projects/<int:project_id>/progress/groups/<int:group_id>/<action>")
@progress_structure_required()
def change_group(project_id, group_id, action):
    group = _group(project_id, group_id)
    if action == "edit": services.update_group(group, name=request.form.get("name", ""), actor_id=current_user.id)
    else: abort(404)
    db.session.commit()
    flash("Đã cập nhật khu vực.", "success")
    return redirect(url_for("construction_progress.type_detail", project_id=project_id, type_id=group.progress_type_id))


@bp.post("/projects/<int:project_id>/progress/groups/<int:group_id>/delete")
@progress_structure_required()
def delete_group(project_id, group_id):
    group = _group(project_id, group_id)
    try:
        services.delete_group(group, confirm_name=request.form.get("confirm_name"), actor_id=current_user.id)
    except services.ConfirmationNameError as exc:
        abort(400, description=str(exc))
    db.session.commit()
    flash("Đã xoá vĩnh viễn khu vực và dữ liệu bên trong.", "success")
    return redirect(url_for("construction_progress.type_detail", project_id=project_id, type_id=group.progress_type_id))


@bp.post("/projects/<int:project_id>/progress/groups/<int:group_id>/items")
@progress_structure_required()
def create_item(project_id, group_id):
    group = _group(project_id, group_id)
    try:
        services.create_item(group=group, name=request.form.get("name", ""), unit=request.form.get("unit", ""), planned_quantity=request.form.get("planned_quantity", 0), opening_quantity=request.form.get("opening_quantity", 0), decimal_places=request.form.get("decimal_places", 0), actor_id=current_user.id)
    except ValueError as exc:
        flash(str(exc), "warning")
        return redirect(url_for("construction_progress.type_detail", project_id=project_id, type_id=group.progress_type_id))
    db.session.commit()
    flash("Đã tạo hạng mục.", "success")
    return redirect(url_for("construction_progress.type_detail", project_id=project_id, type_id=_group(project_id, group_id).progress_type_id))


@bp.post("/projects/<int:project_id>/progress/items/<int:item_id>/<action>")
@progress_structure_required()
def change_item(project_id, item_id, action):
    item = _item(project_id, item_id)
    if action == "edit":
        try:
            services.update_item(item, name=request.form.get("name", ""), unit=request.form.get("unit", ""), planned_quantity=request.form.get("planned_quantity", 0), opening_quantity=request.form.get("opening_quantity", 0), decimal_places=request.form.get("decimal_places", 0), actor_id=current_user.id)
        except ValueError as exc:
            flash(str(exc), "warning")
            return redirect(url_for("construction_progress.type_detail", project_id=project_id, type_id=item.progress_group.progress_type_id))
    else: abort(404)
    db.session.commit()
    flash("Đã cập nhật hạng mục.", "success")
    return redirect(url_for("construction_progress.type_detail", project_id=project_id, type_id=item.progress_group.progress_type_id))


@bp.post("/projects/<int:project_id>/progress/items/<int:item_id>/delete")
@progress_structure_required()
def delete_item(project_id, item_id):
    item = _item(project_id, item_id)
    type_id = item.progress_group.progress_type_id
    try:
        services.delete_item(item, confirm_name=request.form.get("confirm_name"), actor_id=current_user.id)
    except services.ConfirmationNameError as exc:
        abort(400, description=str(exc))
    db.session.commit()
    flash("Đã xoá vĩnh viễn hạng mục và phiếu cập nhật.", "success")
    return redirect(url_for("construction_progress.type_detail", project_id=project_id, type_id=type_id))


@bp.get("/projects/<int:project_id>/progress/items/<int:item_id>")
@progress_read_required()
def item_detail(project_id, item_id):
    project = _project(project_id)
    item = _item(project_id, item_id)
    entries = sorted(item.entries, key=lambda entry: entry.report_date, reverse=True)
    return render_template("construction_progress/item_detail.html", project=project, item=item, entries=entries, entry_dates={entry.report_date.isoformat() for entry in entries}, item_percent=services.item_percent(item), can_create=can_create_progress_entry(project.id), today=services.local_today())


@bp.post("/projects/<int:project_id>/progress/items/<int:item_id>/entries")
@progress_entry_required()
def create_entry(project_id, item_id):
    item = _item(project_id, item_id)
    try:
        value = services.create_entry(item=item, report_date=request.form.get("report_date"), quantity=request.form.get("quantity"), note=request.form.get("note"), actor_id=current_user.id)
    except ValueError as exc:
        flash(str(exc), "warning")
        return redirect(url_for("construction_progress.item_detail", project_id=project_id, item_id=item.id))
    db.session.commit()
    flash("Đã tạo phiếu cập nhật tiến độ.", "success")
    return redirect(url_for("construction_progress.item_detail", project_id=project_id, item_id=item.id))


@bp.post("/projects/<int:project_id>/progress/entries/<int:entry_id>/<action>")
@progress_entry_required()
def change_entry(project_id, entry_id, action):
    entry = _entry(project_id, entry_id)
    if not can_edit_progress_entry(entry): abort(403)
    item_id = entry.progress_item_id
    if action == "edit":
        try:
            services.update_entry(entry, report_date=request.form.get("report_date"), quantity=request.form.get("quantity"), note=request.form.get("note"), actor_id=current_user.id)
        except ValueError as exc:
            flash(str(exc), "warning")
            return redirect(url_for("construction_progress.item_detail", project_id=project_id, item_id=item_id))
    elif action == "delete": services.delete_entry(entry, actor_id=current_user.id)
    else: abort(404)
    db.session.commit()
    flash("Đã cập nhật phiếu tiến độ." if action == "edit" else "Đã xóa phiếu tiến độ.", "success")
    return redirect(url_for("construction_progress.item_detail", project_id=project_id, item_id=item_id))


@bp.get("/projects/<int:project_id>/progress/types/<int:type_id>/chart-data")
@progress_read_required()
def chart_data(project_id, type_id):
    value = _type(project_id, type_id)
    groups = list(value.groups)
    payload = {
        "labels": [group.name for group in groups],
        "percentages": [round(float(services.group_percent(group, value.value_mode) or 0), 1) for group in groups],
        "overall_percent": round(float(services.type_percent(value) or 0), 1),
    }
    if value.value_mode == "money":
        payload["completed"] = [float(sum((item.completed_quantity for item in group.items), 0)) for group in groups]
        payload["remaining"] = [float(max(sum((item.planned_quantity - item.completed_quantity for item in group.items), 0), 0)) for group in groups]
    return jsonify(payload)
