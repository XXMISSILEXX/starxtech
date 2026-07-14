from flask import abort, flash, redirect, render_template, request, url_for
from sqlalchemy import or_

from app.auth.permissions import can_access_partners_module, can_manage_partner_fields
from app.extensions import db
from app.models import PartnerFieldCollection, PartnerFieldCollectionItem, PartnerFieldDefinition
from app.partner_field_collections import bp
from app.partners.services import _add_with_sqlite_id


@bp.before_request
def require_partner_module():
    if not can_access_partners_module():
        abort(403)
    if not can_manage_partner_fields():
        abort(403)


@bp.get("/")
def index():
    query = PartnerFieldCollection.query
    search = request.args.get("q", "").strip()
    active = request.args.get("active", "").strip()
    if search:
        like = f"%{search}%"
        query = query.filter(or_(PartnerFieldCollection.name.ilike(like), PartnerFieldCollection.description.ilike(like)))
    if active == "1":
        query = query.filter(PartnerFieldCollection.is_active.is_(True))
    elif active == "0":
        query = query.filter(PartnerFieldCollection.is_active.is_(False))
    collections = query.order_by(PartnerFieldCollection.sort_order.asc(), PartnerFieldCollection.name.asc()).all()
    return render_template("partner_field_collections/index.html", collections=collections, filters=request.args)


@bp.route("/new", methods=["GET", "POST"])
def new():
    collection = PartnerFieldCollection(is_active=True)
    if request.method == "POST":
        return _save_collection(collection)
    return _render_form(collection, {})


@bp.route("/<int:collection_id>/edit", methods=["GET", "POST"])
def edit(collection_id):
    collection = PartnerFieldCollection.query.get_or_404(collection_id)
    if request.method == "POST":
        return _save_collection(collection)
    return _render_form(collection, {})


@bp.post("/<int:collection_id>/deactivate")
def deactivate(collection_id):
    collection = PartnerFieldCollection.query.get_or_404(collection_id)
    collection.is_active = False
    db.session.commit()
    flash("Đã vô hiệu hóa bộ trường dữ liệu.", "success")
    return redirect(url_for("partner_field_collections.index"))


def _save_collection(collection):
    errors = {}
    name = request.form.get("name", "").strip()
    if not name:
        errors["name"] = "Tên bộ trường là bắt buộc."
    if errors:
        return _render_form(collection, errors), 400

    if collection.id is None:
        _add_with_sqlite_id(collection)
    collection.name = name
    collection.description = request.form.get("description", "").strip() or None
    collection.sort_order = _int_or_zero(request.form.get("sort_order"))
    collection.is_active = request.form.get("is_active", "on") == "on"
    collection.items[:] = []
    db.session.flush()
    for sort_order, field_id in enumerate(_selected_field_ids(), start=1):
        item = PartnerFieldCollectionItem(
            collection_id=collection.id,
            field_definition_id=field_id,
            sort_order=sort_order,
        )
        _add_with_sqlite_id(item)
        collection.items.append(item)
    db.session.commit()
    flash("Đã lưu bộ trường dữ liệu.", "success")
    return redirect(url_for("partner_field_collections.index"))


def _render_form(collection, errors):
    fields = (
        PartnerFieldDefinition.query.filter(PartnerFieldDefinition.is_active.is_(True))
        .order_by(PartnerFieldDefinition.sort_order.asc(), PartnerFieldDefinition.label.asc())
        .all()
    )
    selected_ids = {item.field_definition_id for item in collection.items}
    return render_template(
        "partner_field_collections/form.html",
        collection=collection,
        fields=fields,
        selected_ids=selected_ids,
        errors=errors,
    )


def _selected_field_ids():
    seen = set()
    result = []
    for raw in request.form.getlist("field_definition_ids"):
        if raw.isdigit():
            field_id = int(raw)
            if field_id not in seen:
                seen.add(field_id)
                result.append(field_id)
    return result


def _int_or_zero(value):
    try:
        return int(value or 0)
    except ValueError:
        return 0
