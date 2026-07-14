from datetime import date, datetime, time

from flask import abort, flash, redirect, render_template, request, url_for
from sqlalchemy import func

from app.auth.permissions import (
    can_access_partners_module,
    can_create_partner,
    can_delete_partner,
    can_edit_partner,
    can_manage_partner_fields,
    can_view_partner,
)
from app.extensions import db
from app.models import Company, CompanyDepartment, Partner, PartnerFieldDefinition
from app.partners import bp
from app.partners.services import (
    PartnerValidationError,
    active_field_definitions,
    active_field_collections,
    apply_partner_filters,
    build_field_form_rows,
    build_partner_form_data,
    partners_query,
    save_partner,
)


@bp.before_request
def require_partner_module():
    if not can_access_partners_module():
        abort(403)


@bp.get("/dashboard")
def dashboard():
    start_of_month = date.today().replace(day=1)
    query = apply_partner_filters(partners_query(), request.args)
    created_from = request.args.get("date_from", "").strip()
    created_to = request.args.get("date_to", "").strip()
    if created_from:
        try:
            query = query.filter(Partner.created_at >= datetime.combine(datetime.strptime(created_from, "%Y-%m-%d").date(), time.min))
        except ValueError:
            pass
    if created_to:
        try:
            query = query.filter(Partner.created_at <= datetime.combine(datetime.strptime(created_to, "%Y-%m-%d").date(), time.max))
        except ValueError:
            pass
    recent_partners = (
        query
        .order_by(Partner.created_at.desc(), Partner.id.desc())
        .limit(8)
        .all()
    )
    companies = Company.query.filter(Company.deleted_at.is_(None)).order_by(Company.name.asc()).all()
    industries = [
        row[0]
        for row in db.session.query(Company.industry)
        .filter(Company.industry.isnot(None), Company.deleted_at.is_(None))
        .distinct()
        .order_by(Company.industry.asc())
    ]
    return render_template(
        "partners/dashboard.html",
        total_partners=query.count(),
        total_companies=Company.query.filter(Company.deleted_at.is_(None), Company.is_active.is_(True)).count(),
        new_this_month=query.filter(Partner.created_at >= start_of_month).count(),
        active_fields=PartnerFieldDefinition.query.filter_by(is_active=True).count(),
        recent_partners=recent_partners,
        companies=companies,
        industries=industries,
        filters=request.args,
        can_create=can_create_partner(),
        can_manage_fields=can_manage_partner_fields(),
    )


@bp.get("/")
def index():
    query = apply_partner_filters(partners_query(), request.args)
    partners = query.order_by(Partner.full_name.asc()).all()
    companies = Company.query.filter(Company.deleted_at.is_(None)).order_by(Company.name.asc()).all()
    industries = [
        row[0]
        for row in db.session.query(Company.industry)
        .filter(Company.industry.isnot(None), Company.deleted_at.is_(None))
        .distinct()
        .order_by(Company.industry.asc())
    ]
    departments = [
        row
        for row in CompanyDepartment.query.join(Partner, Partner.department_id == CompanyDepartment.id)
        .filter(Partner.deleted_at.is_(None))
        .distinct()
        .order_by(CompanyDepartment.name.asc())
    ]
    positions = [
        row[0]
        for row in db.session.query(Partner.position)
        .filter(Partner.position.isnot(None), Partner.deleted_at.is_(None))
        .distinct()
        .order_by(Partner.position.asc())
    ]
    return render_template(
        "partners/index.html",
        partners=partners,
        companies=companies,
        industries=industries,
        departments=departments,
        positions=positions,
        filters=request.args,
        can_create=can_create_partner(),
        can_edit_by_partner={partner.id: can_edit_partner(partner) for partner in partners},
        can_delete_by_partner={partner.id: can_delete_partner(partner) for partner in partners},
    )


@bp.route("/new", methods=["GET", "POST"])
def new():
    if not can_create_partner():
        abort(403)
    if request.method == "POST":
        try:
            partner = save_partner(request.form)
            db.session.commit()
        except PartnerValidationError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
            return _render_form(form_errors=exc.errors, form=request.form), 400
        flash("Đã tạo đối tác.", "success")
        return redirect(url_for("partners.detail", partner_id=partner.id))
    return _render_form()


@bp.get("/<int:partner_id>")
def detail(partner_id):
    partner = _partner_or_404(partner_id)
    if not can_view_partner(partner):
        abort(403)
    grouped_fields = {}
    for value in partner.field_values:
        grouped_fields.setdefault(value.group_name_snapshot or "Thông tin mở rộng", []).append(value)
    return render_template(
        "partners/detail.html",
        partner=partner,
        grouped_fields=grouped_fields,
        can_edit=can_edit_partner(partner),
        can_delete=can_delete_partner(partner),
    )


@bp.route("/<int:partner_id>/edit", methods=["GET", "POST"])
def edit(partner_id):
    partner = _partner_or_404(partner_id)
    if not can_edit_partner(partner):
        abort(403)
    if request.method == "POST":
        try:
            save_partner(request.form, partner)
            db.session.commit()
        except PartnerValidationError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
            return _render_form(partner=partner, form_errors=exc.errors, form=request.form), 400
        flash("Đã cập nhật đối tác.", "success")
        return redirect(url_for("partners.detail", partner_id=partner.id))
    return _render_form(partner=partner)


@bp.post("/<int:partner_id>/deactivate")
def deactivate(partner_id):
    partner = _partner_or_404(partner_id)
    if not can_delete_partner(partner):
        abort(403)
    partner.is_active = False
    partner.deleted_at = func.now()
    db.session.commit()
    flash("Đã vô hiệu hóa đối tác.", "success")
    return redirect(url_for("partners.index"))


def _render_form(partner=None, form_errors=None, form=None):
    companies = Company.query.filter(Company.deleted_at.is_(None), Company.is_active.is_(True)).order_by(Company.name.asc()).all()
    departments = (
        CompanyDepartment.query.filter(CompanyDepartment.is_active.is_(True))
        .order_by(CompanyDepartment.company_id.asc(), CompanyDepartment.display_order.asc(), CompanyDepartment.name.asc())
        .all()
    )
    return render_template(
        "partners/form.html",
        partner=partner,
        companies=companies,
        departments=departments,
        field_definitions=active_field_definitions(),
        field_collections=active_field_collections(),
        field_rows=build_field_form_rows(form, partner),
        form_data=build_partner_form_data(form, partner),
        form_errors=form_errors or {},
    )


def _partner_or_404(partner_id):
    return Partner.query.filter(Partner.id == partner_id, Partner.deleted_at.is_(None)).first_or_404()
