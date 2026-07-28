from flask import abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func, or_

from app.auth.permissions import can_access_partners_module
from app.audit import audit
from app.permissions.services import permission_required
from app.extensions import db
from app.models import Company, CompanyDepartment, Partner, PartnerRelationship
from app.partner_companies import bp
from app.partners.services import _add_with_sqlite_id
from app.partners.lifecycle import active_record_query, apply_lifecycle_scope, archived_record_query, lifecycle_status


@bp.before_request
def require_partner_module():
    if not can_access_partners_module():
        abort(403, description="Bạn không có quyền truy cập phân hệ Quản lý đối tác.")


@bp.after_request
def private_photo_cache_headers(response):
    if request.endpoint in {"partner_companies.photo_preview", "partner_companies.photo_signed_preview"}:
        response.headers["Cache-Control"] = "no-store, private"
        response.headers["Pragma"] = "no-cache"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@bp.get("/")
@permission_required("partner_companies.view")
def index():
    status = lifecycle_status(request.args)
    query = apply_lifecycle_scope(Company.query, Company, status)
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
        .filter(Company.industry.isnot(None))
        .distinct()
        .order_by(Company.industry.asc())
    ]
    return render_template("partner_companies/index.html", companies=companies, industries=industries, filters=request.args, status=status, can_create=_can("partner_companies.create"), can_archive=_can("partner_companies.delete"), can_restore=_can("partner_companies.restore"))


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
            ).order_by(PartnerRelationship.department.asc(), PartnerRelationship.display_order.asc()).all()
        )
    grouped = {}
    for partner in partners:
        grouped.setdefault(_partner_department_name(partner), []).append(partner)
    return render_template("partner_companies/detail.html", company=company,
        departments=_company_departments(company.id), grouped_partners=grouped, relationships=relationships,
        can_edit=_can("partner_companies.edit") and _is_active(company),
        can_create_department=_can("partner_companies.create") and _is_active(company),
        can_archive=_can("partner_companies.delete") and _is_active(company),
        can_restore=_can("partner_companies.restore") and not _is_active(company))


@bp.post("/<int:company_id>/photo")
@permission_required("partner_companies.edit")
def photo(company_id):
    company = _active_company_or_404(company_id)
    from app.partner_photos import PartnerPhotoError, replace_photo
    try: result = replace_photo(company, request.files.get("photo"), kind="company_photo", user=current_user)
    except (PartnerPhotoError, AttributeError) as exc: flash(str(exc) or "Vui lòng chọn ảnh.", "danger")
    else: flash("Đã cập nhật logo công ty; ảnh cũ đang chờ dọn dẹp." if result["cleanup_pending"] else "Đã cập nhật logo công ty.", "warning" if result["cleanup_pending"] else "success")
    return redirect(url_for("partner_companies.detail", company_id=company.id))


@bp.post("/<int:company_id>/photo/delete")
@permission_required("partner_companies.edit")
def photo_delete(company_id):
    company = _active_company_or_404(company_id)
    from app.partner_photos import delete_photo
    result = delete_photo(company, kind="company_photo")
    flash("Đã xóa logo công ty; ảnh cũ đang chờ dọn dẹp." if result["cleanup_pending"] else "Đã xóa logo công ty.", "warning" if result["cleanup_pending"] else "success")
    return redirect(url_for("partner_companies.detail", company_id=company.id))


@bp.post("/<int:company_id>/photo/signed-preview")
@permission_required("partner_companies.view")
def photo_signed_preview(company_id):
    company = _company_or_404(company_id)
    if not company.company_photo_storage_object or company.company_photo_storage_object.upload_status != "active" or company.company_photo_storage_object.deleted_at is not None:
        return jsonify({"ok": False, "message": "Ảnh chưa sẵn sàng."}), 404
    return jsonify({"ok": True, "url": url_for("partner_companies.photo_preview", company_id=company.id)})


@bp.get("/<int:company_id>/photo/preview")
@permission_required("partner_companies.view")
def photo_preview(company_id):
    company = _company_or_404(company_id)
    from app.partner_photos import PartnerPhotoError, preview_response
    try:
        return preview_response(company, kind="company_photo", user=current_user)
    except PartnerPhotoError:
        abort(404)


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
        can_create=_can("partner_companies.create") and _is_active(company), can_edit=_can("partner_companies.edit") and _is_active(company), can_delete=_can("partner_companies.delete") and _is_active(company),
    )


@bp.route("/<int:company_id>/departments/new", methods=["GET", "POST"])
@permission_required("partner_companies.create")
def departments_new(company_id):
    company = _company_or_404(company_id)
    _require_active_company_for_mutation(company)
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
        _require_active_company_for_mutation(company)
        return _save_department(company, department)
    return _render_department_form(company, department, {})


@bp.post("/<int:company_id>/departments/<int:department_id>/delete")
@permission_required("partner_companies.delete")
def departments_delete(company_id, department_id):
    company = _company_or_404(company_id)
    _require_active_company_for_mutation(company)
    department = _department_or_404(company.id, department_id)
    old_values = _department_snapshot(department)
    department.is_active = False
    audit("partner_department.deactivate", "CompanyDepartment", department.id, old_values, {"is_active": False})
    db.session.commit()
    flash("Đã lưu trữ phòng ban.", "success")
    return redirect(url_for("partner_companies.departments", company_id=company.id))


@bp.route("/<int:company_id>/edit", methods=["GET", "POST"])
@permission_required("partner_companies.edit")
def edit(company_id):
    company = _company_or_404(company_id)
    if request.method == "POST":
        return _save_company(company)
    return render_template("partner_companies/form.html", company=company, errors={})


@bp.post("/<int:company_id>/archive")
@permission_required("partner_companies.delete")
def archive(company_id):
    company = _active_company_or_404(company_id)
    old_values = _company_snapshot(company)
    company.is_active = False
    company.deleted_at = func.now()
    audit("company.archive", "Company", company.id, old_values, _lifecycle_snapshot(company))
    db.session.commit()
    flash("Đã lưu trữ công ty.", "success")
    return redirect(url_for("partner_companies.index"))


@bp.post("/<int:company_id>/deactivate")
@permission_required("partner_companies.delete")
def deactivate(company_id):
    return archive(company_id)


@bp.post("/<int:company_id>/restore")
@permission_required("partner_companies.restore")
def restore(company_id):
    company = archived_record_query(Company).filter(Company.id == company_id).first_or_404()
    old_values = _lifecycle_snapshot(company)
    company.is_active = True
    company.deleted_at = None
    audit("company.restore", "Company", company.id, old_values, _lifecycle_snapshot(company))
    db.session.commit()
    flash("Đã khôi phục công ty.", "success")
    return redirect(url_for("partner_companies.detail", company_id=company.id))


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
    if request.files.get("photo") and request.files["photo"].filename:
        from app.partner_photos import replace_photo
        try:
            replace_photo(company, request.files["photo"], kind="company_photo", user=current_user)
        except Exception as exc:
            flash(str(exc), "warning")
    flash("Đã lưu công ty.", "success")
    return redirect(url_for("partner_companies.detail", company_id=company.id))


def _company_or_404(company_id):
    return Company.query.filter(Company.id == company_id).first_or_404()


def _active_company_or_404(company_id):
    return active_record_query(Company).filter(Company.id == company_id).first_or_404()


def _is_active(company):
    return company.deleted_at is None and company.is_active


def _require_active_company_for_mutation(company):
    if _is_active(company):
        return
    flash("Không thể thay đổi phòng ban khi công ty đã lưu trữ.", "danger")
    abort(400)


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
    excluded_ids = _department_descendant_ids(company.id, department.id)
    if department.id is not None:
        excluded_ids.add(department.id)
    parent_options = [
        item for item in _company_departments(company.id)
        if item.id not in excluded_ids
    ]
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
    try:
        parent_id = _parse_optional_int(request.form.get("parent_department_id"))
    except ValueError:
        parent_id = None
        errors["parent_department_id"] = "Phòng ban cấp trên không hợp lệ."
    if not name:
        errors["name"] = "Tên phòng ban là bắt buộc."
    parent = None
    if parent_id is not None:
        parent = CompanyDepartment.query.filter_by(id=parent_id).first()
        if parent is None:
            errors["parent_department_id"] = "Phòng ban cấp trên không tồn tại."
        elif parent.company_id != company.id:
            errors["parent_department_id"] = "Phòng ban cấp trên phải thuộc cùng công ty."
        elif not parent.is_active:
            errors["parent_department_id"] = "Phòng ban cấp trên phải đang hoạt động."
    if department.id is not None and parent_id == department.id:
        errors["parent_department_id"] = "Phòng ban không thể là cấp trên của chính nó."
    elif department.id is not None and parent_id in _department_descendant_ids(company.id, department.id):
        errors["parent_department_id"] = "Không thể chọn phòng ban con làm phòng ban cấp trên."
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


def _department_descendant_ids(company_id, department_id):
    if department_id is None:
        return set()
    children_by_parent = {}
    for item_id, parent_id in db.session.query(
        CompanyDepartment.id,
        CompanyDepartment.parent_department_id,
    ).filter(CompanyDepartment.company_id == company_id):
        children_by_parent.setdefault(parent_id, []).append(item_id)

    descendants = set()
    pending = list(children_by_parent.get(department_id, []))
    while pending:
        child_id = pending.pop()
        if child_id in descendants:
            continue
        descendants.add(child_id)
        pending.extend(children_by_parent.get(child_id, []))
    return descendants


def _partner_department_name(partner):
    return partner.company_department.name if partner.company_department else (partner.department or "Chưa có phòng ban")


def _parse_optional_int(value):
    normalized = str(value).strip().lower() if value is not None else ""
    if normalized in {"", "0", "none", "null"}:
        return None
    return int(normalized)


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


def _lifecycle_snapshot(company):
    return {"id": company.id, "type": "company", "name": company.name, "is_active": company.is_active,
            "deleted_at": company.deleted_at is not None}


def _department_snapshot(department):
    return {"company_id": department.company_id, "name": department.name, "parent_department_id": department.parent_department_id, "is_active": department.is_active, "is_special_department": department.is_special_department}
