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
    return jsonify({"id": value.id}), 201


@bp.post("/projects/<int:project_id>/progress/types/<int:type_id>/edit")
@progress_structure_required()
def edit_type(project_id, type_id):
    value = services.update_type(_type(project_id, type_id), name=request.form.get("name", ""), value_mode=request.form.get("value_mode", "quantity"), actor_id=current_user.id)
    db.session.commit()
    return jsonify({"id": value.id})


@bp.post("/projects/<int:project_id>/progress/types/<int:type_id>/archive")
@progress_structure_required()
def archive_type(project_id, type_id):
    services.archive_type(_type(project_id, type_id), actor_id=current_user.id)
    db.session.commit()
    return "", 204


@bp.get("/projects/<int:project_id>/progress/types/<int:type_id>")
@progress_read_required()
def type_detail(project_id, type_id):
    project = _project(project_id)
    value = _type(project_id, type_id)
    return render_template("construction_progress/type_detail.html", project=project, progress_type=value, tree=services.progress_tree(project, value), types=ProgressType.query.filter_by(project_id=project.id, is_active=True).all(), type_percent=services.type_percent(value), can_manage=can_manage_progress_structure(project.id))


@bp.post("/projects/<int:project_id>/progress/types/<int:type_id>/groups")
@progress_structure_required()
def create_group(project_id, type_id):
    value = services.create_group(progress_type=_type(project_id, type_id), name=request.form.get("name", ""), actor_id=current_user.id)
    db.session.commit()
    return jsonify({"id": value.id}), 201


@bp.post("/projects/<int:project_id>/progress/groups/<int:group_id>/<action>")
@progress_structure_required()
def change_group(project_id, group_id, action):
    group = _group(project_id, group_id)
    if action == "edit": services.update_group(group, name=request.form.get("name", ""), actor_id=current_user.id)
    elif action == "archive": services.archive_group(group, actor_id=current_user.id)
    else: abort(404)
    db.session.commit()
    return "", 204


@bp.post("/projects/<int:project_id>/progress/groups/<int:group_id>/items")
@progress_structure_required()
def create_item(project_id, group_id):
    value = services.create_item(group=_group(project_id, group_id), name=request.form.get("name", ""), unit=request.form.get("unit", ""), planned_quantity=request.form.get("planned_quantity", 0), opening_quantity=request.form.get("opening_quantity", 0), actor_id=current_user.id)
    db.session.commit()
    return jsonify({"id": value.id}), 201


@bp.post("/projects/<int:project_id>/progress/items/<int:item_id>/<action>")
@progress_structure_required()
def change_item(project_id, item_id, action):
    item = _item(project_id, item_id)
    if action == "edit": services.update_item(item, name=request.form.get("name", ""), unit=request.form.get("unit", ""), planned_quantity=request.form.get("planned_quantity", 0), opening_quantity=request.form.get("opening_quantity", 0), actor_id=current_user.id)
    elif action == "archive": services.archive_item(item, actor_id=current_user.id)
    else: abort(404)
    db.session.commit()
    return "", 204


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
    return jsonify({"id": value.id}), 201


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
    return "", 204


@bp.get("/projects/<int:project_id>/progress/types/<int:type_id>/chart-data")
@progress_read_required()
def chart_data(project_id, type_id):
    value = _type(project_id, type_id)
    groups = [group for group in value.groups if group.is_active]
    payload = {
        "labels": [group.name for group in groups],
        "percentages": [round(float(services.group_percent(group, value.value_mode) or 0), 1) for group in groups],
        "overall_percent": round(float(services.type_percent(value) or 0), 1),
    }
    if value.value_mode == "money":
        payload["completed"] = [float(sum((item.completed_quantity for item in group.items if item.is_active), 0)) for group in groups]
        payload["remaining"] = [float(max(sum((item.planned_quantity - item.completed_quantity for item in group.items if item.is_active), 0), 0)) for group in groups]
    return jsonify(payload)
