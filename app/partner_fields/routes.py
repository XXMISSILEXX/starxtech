from flask import abort, flash, redirect, render_template, request, url_for
from sqlalchemy import or_

from app.auth.permissions import can_access_partners_module, can_manage_partner_fields
from app.extensions import db
from app.models import PartnerFieldDefinition
from app.partner_fields import bp
from app.partners.services import FIELD_TYPES, PartnerValidationError, save_field_definition


@bp.before_request
def require_partner_module():
    if not can_access_partners_module():
        abort(403)


@bp.get("/")
def index():
    if not can_manage_partner_fields():
        abort(403)
    query = PartnerFieldDefinition.query
    search = request.args.get("q", "").strip()
    field_type = request.args.get("field_type", "").strip()
    group_name = request.args.get("group_name", "").strip()
    active = request.args.get("active", "").strip()
    if search:
        like = f"%{search}%"
        query = query.filter(or_(PartnerFieldDefinition.label.ilike(like), PartnerFieldDefinition.field_key.ilike(like)))
    if field_type:
        query = query.filter(PartnerFieldDefinition.field_type == field_type)
    if group_name:
        query = query.filter(PartnerFieldDefinition.group_name == group_name)
    if active == "1":
        query = query.filter(PartnerFieldDefinition.is_active.is_(True))
    elif active == "0":
        query = query.filter(PartnerFieldDefinition.is_active.is_(False))
    fields = query.order_by(PartnerFieldDefinition.sort_order.asc(), PartnerFieldDefinition.label.asc()).all()
    group_names = [
        row[0]
        for row in db.session.query(PartnerFieldDefinition.group_name)
        .filter(PartnerFieldDefinition.group_name.isnot(None))
        .distinct()
        .order_by(PartnerFieldDefinition.group_name.asc())
    ]
    return render_template(
        "partner_fields/index.html",
        fields=fields,
        field=None,
        field_types=FIELD_TYPES,
        group_names=group_names,
        filters=request.args,
        errors={},
    )


@bp.route("/new", methods=["GET", "POST"])
def new():
    if not can_manage_partner_fields():
        abort(403)
    if request.method == "POST":
        try:
            field = save_field_definition(request.form)
            db.session.commit()
        except PartnerValidationError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
            return render_template("partner_fields/form.html", field=None, field_types=FIELD_TYPES, errors=exc.errors), 400
        flash("Đã tạo trường dữ liệu.", "success")
        return redirect(url_for("partner_fields.index"))
    return render_template("partner_fields/form.html", field=None, field_types=FIELD_TYPES, errors={})


@bp.route("/<int:field_id>/edit", methods=["GET", "POST"])
def edit(field_id):
    if not can_manage_partner_fields():
        abort(403)
    field = PartnerFieldDefinition.query.get_or_404(field_id)
    if request.method == "POST":
        try:
            save_field_definition(request.form, field)
            db.session.commit()
        except PartnerValidationError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
            return render_template("partner_fields/form.html", field=field, field_types=FIELD_TYPES, errors=exc.errors), 400
        flash("Đã cập nhật trường dữ liệu.", "success")
        return redirect(url_for("partner_fields.index"))
    return render_template("partner_fields/form.html", field=field, field_types=FIELD_TYPES, errors={})


@bp.post("/<int:field_id>/deactivate")
def deactivate(field_id):
    if not can_manage_partner_fields():
        abort(403)
    field = PartnerFieldDefinition.query.get_or_404(field_id)
    field.is_active = False
    db.session.commit()
    flash("Đã vô hiệu hóa trường dữ liệu.", "success")
    return redirect(url_for("partner_fields.index"))


@bp.post("/reorder")
def reorder():
    if not can_manage_partner_fields():
        abort(403)
    for field in PartnerFieldDefinition.query.all():
        raw = request.form.get(f"sort_order_{field.id}")
        if raw and raw.strip().lstrip("-").isdigit():
            field.sort_order = int(raw)
    db.session.commit()
    flash("Đã cập nhật thứ tự trường dữ liệu.", "success")
    return redirect(url_for("partner_fields.index"))
