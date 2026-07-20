from datetime import date, datetime, time

from flask import abort, flash, redirect, render_template, request, url_for
from sqlalchemy import func

from app.auth.permissions import (
    can_create_partner,
    can_delete_partner,
    can_edit_partner,
    can_manage_partner_fields,
    can_view_partner,
)
from app.audit import audit
from app.permissions.services import permission_required
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
from app.partners.lifecycle import active_record_query, apply_lifecycle_scope, archived_record_query, lifecycle_status


@bp.before_request
def require_partner_module():
    from app.auth.permissions import can_access_partners_module, PARTNER_MODULE_DENY_MESSAGE
    if not can_access_partners_module():
        abort(403, description=PARTNER_MODULE_DENY_MESSAGE)


@bp.get("/dashboard")
@permission_required("partners.view")
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
        can_create_company=request_user_can("partner_companies.create"),
        can_view_relations=request_user_can("partner_relations.view"),
    )


@bp.get("/")
@permission_required("partners.view")
def index():
    status = lifecycle_status(request.args)
    query = apply_partner_filters(apply_lifecycle_scope(partners_query(include_inactive=True), Partner, status), request.args)
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
        filters=request.args, status=status,
        can_create=can_create_partner(),
        can_edit_by_partner={partner.id: can_edit_partner(partner) and _is_active(partner) for partner in partners},
        can_delete_by_partner={partner.id: can_delete_partner(partner) for partner in partners},
        can_restore_by_partner={partner.id: request_user_can("partners.restore") for partner in partners},
    )


@bp.route("/new", methods=["GET", "POST"])
@permission_required("partners.create")
def new():
    if request.method == "POST":
        _require_head_permission_if_changed(None)
        try:
            partner = save_partner(request.form)
            audit("partner.create", "Partner", partner.id, new_values=_partner_snapshot(partner))
            db.session.commit()
        except PartnerValidationError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
            return _render_form(form_errors=exc.errors, form=request.form), 400
        flash("Đã tạo đối tác.", "success")
        return redirect(url_for("partners.detail", partner_id=partner.id))
    return _render_form()


@bp.get("/<int:partner_id>")
@permission_required("partners.view")
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
        can_edit=can_edit_partner(partner) and _is_active(partner),
        can_delete=can_delete_partner(partner) and _is_active(partner),
        can_restore=request_user_can("partners.restore") and not _is_active(partner),
    )


@bp.route("/<int:partner_id>/edit", methods=["GET", "POST"])
@permission_required("partners.edit")
def edit(partner_id):
    partner = _active_partner_or_404(partner_id)
    if not can_edit_partner(partner):
        abort(403)
    if request.method == "POST":
        _require_head_permission_if_changed(partner)
        old_values = _partner_snapshot(partner)
        try:
            save_partner(request.form, partner)
            audit("partner.update", "Partner", partner.id, old_values, _partner_snapshot(partner))
            db.session.commit()
        except PartnerValidationError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
            return _render_form(partner=partner, form_errors=exc.errors, form=request.form), 400
        flash("Đã cập nhật đối tác.", "success")
        return redirect(url_for("partners.detail", partner_id=partner.id))
    return _render_form(partner=partner)


@bp.post("/<int:partner_id>/archive")
@permission_required("partners.delete")
def archive(partner_id):
    partner = _active_partner_or_404(partner_id)
    if not can_delete_partner(partner):
        abort(403)
    old_values = _partner_snapshot(partner)
    partner.is_active = False
    partner.deleted_at = func.now()
    audit("partner.archive", "Partner", partner.id, old_values, _lifecycle_snapshot(partner))
    db.session.commit()
    flash("Đã lưu trữ đối tác.", "success")
    return redirect(url_for("partners.index"))


@bp.post("/<int:partner_id>/deactivate")
@permission_required("partners.delete")
def deactivate(partner_id):
    return archive(partner_id)


@bp.post("/<int:partner_id>/restore")
@permission_required("partners.restore")
def restore(partner_id):
    partner = archived_record_query(Partner).filter(Partner.id == partner_id).first_or_404()
    old_values = _lifecycle_snapshot(partner)
    partner.is_active = True
    partner.deleted_at = None
    audit("partner.restore", "Partner", partner.id, old_values, _lifecycle_snapshot(partner))
    db.session.commit()
    flash("Đã khôi phục đối tác.", "success")
    return redirect(url_for("partners.detail", partner_id=partner.id))


def _render_form(partner=None, form_errors=None, form=None):
    companies = Company.query.filter(Company.deleted_at.is_(None), Company.is_active.is_(True)).order_by(Company.name.asc()).all()
    departments = (
        CompanyDepartment.query.filter(CompanyDepartment.is_active.is_(True))
        .order_by(CompanyDepartment.company_id.asc(), CompanyDepartment.display_order.asc(), CompanyDepartment.name.asc())
        .all()
    )
    if partner and partner.company and partner.company not in companies:
        companies.append(partner.company)
        companies.sort(key=lambda item: item.name.lower())
    if partner and partner.company_department and partner.company_department not in departments:
        departments.append(partner.company_department)
        departments.sort(key=lambda item: (item.company_id, item.display_order, item.name.lower()))
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
        can_manage_department_head=request_user_can("partner_relations.manage"),
    )


def _partner_or_404(partner_id):
    return Partner.query.filter(Partner.id == partner_id).first_or_404()


def _active_partner_or_404(partner_id):
    return active_record_query(Partner).filter(Partner.id == partner_id).first_or_404()


def _is_active(partner):
    return partner.deleted_at is None and partner.is_active


def request_user_can(code):
    from flask_login import current_user
    return current_user.can(code)


def _require_head_permission_if_changed(partner):
    if "is_department_head" not in request.form:
        return
    requested = request.form.get("is_department_head") == "on"
    if requested != (partner.is_department_head if partner else False) and not request_user_can("partner_relations.manage"):
        abort(403)


def _partner_snapshot(partner):
    return {"full_name": partner.full_name, "company_id": partner.company_id,
            "department_id": partner.department_id, "position": partner.position,
            "is_department_head": partner.is_department_head, "is_active": partner.is_active}


def _lifecycle_snapshot(partner):
    return {"id": partner.id, "type": "partner", "full_name": partner.full_name, "is_active": partner.is_active,
            "deleted_at": partner.deleted_at is not None}
