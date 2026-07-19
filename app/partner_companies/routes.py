from flask import abort, flash, redirect, render_template, request, url_for
from sqlalchemy import func, or_

from app.auth.permissions import can_access_partners_module
from app.audit import audit
from app.permissions.services import permission_required
from app.extensions import db
from app.models import Company, CompanyDepartment, Partner, PartnerRelationship
from app.partner_companies import bp
from app.partners.services import _add_with_sqlite_id


@bp.before_request
def require_partner_module():
    if not can_access_partners_module():
        abort(403, description="Bạn không có quyền truy cập phân hệ Quản lý đối tác.")


@bp.get("/")
@permission_required("partner_companies.view")
def index():
    query = Company.query.filter(Company.deleted_at.is_(None))
    search = request.args.get("q", "").strip()
    industry = request.args.get("industry", "").strip()
    if search:
        like = f"%{search}%"
        query = query.filter(or_(Company.name.ilike(like), Company.phone.ilike(like), Company.email.ilike(like)))
    if industry:
        query = query.filter(Company.industry == industry)
    companies = query.order_by(Company.name.asc()).all()
    industries = [
        row[0]
        for row in db.session.query(Company.industry)
        .filter(Company.industry.isnot(None), Company.deleted_at.is_(None))
        .distinct()
        .order_by(Company.industry.asc())
    ]
    return render_template("partner_companies/index.html", companies=companies, industries=industries, filters=request.args, can_create=_can("partner_companies.create"))


@bp.route("/new", methods=["GET", "POST"])
@permission_required("partner_companies.create")
def new():
    if request.method == "POST":
        company = Company()
        _add_with_sqlite_id(company)
        return _save_company(company, is_new=True)
    return render_template("partner_companies/form.html", company=None, errors={})


@bp.get("/<int:company_id>")
@permission_required("partner_companies.view")
def detail(company_id):
    company = _company_or_404(company_id)
    partners = (
        Partner.query.filter(Partner.company_id == company.id, Partner.deleted_at.is_(None))
        .outerjoin(CompanyDepartment, Partner.department_id == CompanyDepartment.id)
        .order_by(CompanyDepartment.display_order.asc(), CompanyDepartment.name.asc(), Partner.full_name.asc())
        .all()
    )
    partner_ids = [partner.id for partner in partners]
    relationships = []
    if partner_ids:
        relationships = (
            PartnerRelationship.query.filter(
                PartnerRelationship.company_id == company.id,
                PartnerRelationship.parent_partner_id.isnot(None),
                PartnerRelationship.deleted_at.is_(None),
                PartnerRelationship.is_active.is_(True),
            )
            .order_by(PartnerRelationship.department.asc(), PartnerRelationship.display_order.asc())
            .all()
        )
    grouped = {}
    for partner in partners:
        grouped.setdefault(_partner_department_name(partner), []).append(partner)
    return render_template(
        "partner_companies/detail.html",
        company=company,
        departments=_company_departments(company.id),
        grouped_partners=grouped,
        relationships=relationships,
        can_edit=_can("partner_companies.edit"), can_create_department=_can("partner_companies.create"),
    )


@bp.get("/<int:company_id>/departments")
@permission_required("partner_companies.view")
def departments(company_id):
    company = _company_or_404(company_id)
    search = request.args.get("q", "").strip()
    parent_id = request.args.get("parent_department_id", "").strip()
    active = request.args.get("active", "").strip()
    query = CompanyDepartment.query.filter(CompanyDepartment.company_id == company.id)
    if search:
        query = query.filter(CompanyDepartment.name.ilike(f"%{search}%"))
    if parent_id.isdigit():
        query = query.filter(CompanyDepartment.parent_department_id == int(parent_id))
    if active == "1":
        query = query.filter(CompanyDepartment.is_active.is_(True))
    elif active == "0":
        query = query.filter(CompanyDepartment.is_active.is_(False))
    rows = query.order_by(CompanyDepartment.display_order.asc(), CompanyDepartment.name.asc()).all()
    return render_template(
        "partner_companies/departments.html",
        company=company,
        departments=rows,
        parent_options=_company_departments(company.id),
        filters=request.args,
        can_create=_can("partner_companies.create"), can_edit=_can("partner_companies.edit"), can_delete=_can("partner_companies.delete"),
    )


@bp.route("/<int:company_id>/departments/new", methods=["GET", "POST"])
@permission_required("partner_companies.create")
def departments_new(company_id):
    company = _company_or_404(company_id)
    department = CompanyDepartment(company_id=company.id, is_active=True)
    if request.method == "POST":
        return _save_department(company, department)
    return _render_department_form(company, department, {})


@bp.route("/<int:company_id>/departments/<int:department_id>/edit", methods=["GET", "POST"])
@permission_required("partner_companies.edit")
def departments_edit(company_id, department_id):
    company = _company_or_404(company_id)
    department = _department_or_404(company.id, department_id)
    if request.method == "POST":
        return _save_department(company, department)
    return _render_department_form(company, department, {})


@bp.post("/<int:company_id>/departments/<int:department_id>/delete")
@permission_required("partner_companies.delete")
def departments_delete(company_id, department_id):
    company = _company_or_404(company_id)
    department = _department_or_404(company.id, department_id)
    old_values = _department_snapshot(department)
    department.is_active = False
    audit("partner_department.deactivate", "CompanyDepartment", department.id, old_values, {"is_active": False})
    db.session.commit()
    flash("Đã vô hiệu hóa phòng ban.", "success")
    return redirect(url_for("partner_companies.departments", company_id=company.id))


@bp.route("/<int:company_id>/edit", methods=["GET", "POST"])
@permission_required("partner_companies.edit")
def edit(company_id):
    company = _company_or_404(company_id)
    if request.method == "POST":
        return _save_company(company)
    return render_template("partner_companies/form.html", company=company, errors={})


@bp.post("/<int:company_id>/deactivate")
@permission_required("partner_companies.delete")
def deactivate(company_id):
    company = _company_or_404(company_id)
    old_values = _company_snapshot(company)
    company.is_active = False
    company.deleted_at = func.now()
    audit("partner_company.deactivate", "Company", company.id, old_values, {"is_active": False, "deleted_at": True})
    db.session.commit()
    flash("Đã vô hiệu hóa công ty.", "success")
    return redirect(url_for("partner_companies.index"))


def _save_company(company, is_new=False):
    old_values = None if is_new else _company_snapshot(company)
    errors = {}
    name = request.form.get("name", "").strip()
    if not name:
        errors["name"] = "Tên công ty là bắt buộc."
    if errors:
        return render_template("partner_companies/form.html", company=company, errors=errors), 400
    company.name = name
    company.industry = _text("industry")
    company.phone = _text("phone")
    company.email = _text("email")
    company.website = _text("website")
    company.address = _text("address")
    company.notes = _text("notes")
    company.is_active = request.form.get("is_active", "on") == "on"
    audit("partner_company.create" if is_new else "partner_company.update", "Company", company.id, old_values, _company_snapshot(company))
    db.session.commit()
    flash("Đã lưu công ty.", "success")
    return redirect(url_for("partner_companies.detail", company_id=company.id))


def _company_or_404(company_id):
    return Company.query.filter(Company.id == company_id, Company.deleted_at.is_(None)).first_or_404()


def _department_or_404(company_id, department_id):
    return CompanyDepartment.query.filter(
        CompanyDepartment.id == department_id,
        CompanyDepartment.company_id == company_id,
    ).first_or_404()


def _company_departments(company_id, include_inactive=False):
    query = CompanyDepartment.query.filter(CompanyDepartment.company_id == company_id)
    if not include_inactive:
        query = query.filter(CompanyDepartment.is_active.is_(True))
    return query.order_by(CompanyDepartment.display_order.asc(), CompanyDepartment.name.asc()).all()


def _render_department_form(company, department, errors):
    parent_options = [item for item in _company_departments(company.id, include_inactive=True) if item.id != department.id]
    return render_template(
        "partner_companies/department_form.html",
        company=company,
        department=department,
        parent_options=parent_options,
        errors=errors,
    )


def _save_department(company, department):
    is_new = department.id is None
    old_values = None if is_new else _department_snapshot(department)
    errors = {}
    name = request.form.get("name", "").strip()
    parent_id = _optional_int(request.form.get("parent_department_id"))
    if not name:
        errors["name"] = "Tên phòng ban là bắt buộc."
    if parent_id == department.id:
        errors["parent_department_id"] = "Phòng ban không thể là cấp trên của chính nó."
    elif parent_id and _department_cycle(company.id, department.id, parent_id):
        errors["parent_department_id"] = "Không thể tạo vòng lặp phòng ban."
    existing = CompanyDepartment.query.filter(CompanyDepartment.company_id == company.id, CompanyDepartment.name == name)
    if department.id:
        existing = existing.filter(CompanyDepartment.id != department.id)
    if name and existing.first():
        errors["name"] = "Tên phòng ban đã tồn tại trong công ty."
    if errors:
        return _render_department_form(company, department, errors), 400
    if department.id is None:
        _add_with_sqlite_id(department)
    department.company_id = company.id
    department.name = name
    department.parent_department_id = parent_id
    department.description = _text("description")
    department.display_order = _int_or_zero(request.form.get("display_order"))
    department.is_active = request.form.get("is_active", "on") == "on"
    department.is_special_department = request.form.get("is_special_department") == "on"
    audit("partner_department.create" if is_new else "partner_department.update", "CompanyDepartment", department.id, old_values, _department_snapshot(department))
    db.session.commit()
    flash("Đã lưu phòng ban.", "success")
    return redirect(url_for("partner_companies.departments", company_id=company.id))


def _department_cycle(company_id, department_id, parent_id):
    if department_id is None:
        return False
    current = parent_id
    seen = {department_id}
    while current:
        if current in seen:
            return True
        seen.add(current)
        parent = CompanyDepartment.query.filter_by(id=current, company_id=company_id).first()
        current = parent.parent_department_id if parent else None
    return False


def _partner_department_name(partner):
    return partner.company_department.name if partner.company_department else (partner.department or "Chưa có phòng ban")


def _optional_int(value):
    value = (value or "").strip()
    return int(value) if value.isdigit() else None


def _int_or_zero(value):
    try:
        return int(value or 0)
    except ValueError:
        return 0


def _text(name):
    value = request.form.get(name, "").strip()
    return value or None


def _can(code):
    from flask_login import current_user
    return current_user.can(code)


def _company_snapshot(company):
    return {"name": company.name, "industry": company.industry, "is_active": company.is_active}


def _department_snapshot(department):
    return {"company_id": department.company_id, "name": department.name, "parent_department_id": department.parent_department_id, "is_active": department.is_active, "is_special_department": department.is_special_department}
