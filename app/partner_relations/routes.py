from flask import abort, flash, redirect, render_template, request, url_for
from sqlalchemy import func, or_

from app.auth.permissions import can_access_partners_module, can_edit_partner
from app.extensions import db
from app.models import Company, CompanyDepartment, Partner, PartnerRelationship
from app.partner_relations import bp
from app.partners.services import _add_with_sqlite_id


RELATIONSHIP_TYPES = {
    "none": "Không có",
    "direct_report": "Báo cáo trực tiếp",
    "manager": "Quản lý",
    "collaborates": "Phối hợp",
    "advisor": "Tham vấn",
    "primary_contact": "Liên hệ chính",
}


@bp.before_request
def require_partner_module():
    if not can_access_partners_module():
        abort(403)


@bp.get("/")
def index():
    company_id = request.args.get("company_id", "").strip()
    search = request.args.get("q", "").strip()
    department = request.args.get("department", "").strip()
    if company_id.isdigit():
        return redirect(url_for("partner_relations.company", company_id=int(company_id), q=search, department=department))

    query = Company.query.filter(Company.deleted_at.is_(None))
    if search or department:
        query = query.join(Partner, Partner.company_id == Company.id)
    if search:
        like = f"%{search}%"
        query = query.filter(or_(Partner.full_name.ilike(like), Company.name.ilike(like)))
    if department:
        query = query.outerjoin(PartnerRelationship, PartnerRelationship.company_id == Company.id).filter(
            PartnerRelationship.department_id == int(department) if department.isdigit() else Partner.department == department
        )
    companies = query.distinct().order_by(Company.name.asc()).all()
    all_companies = Company.query.filter(Company.deleted_at.is_(None)).order_by(Company.name.asc()).all()
    departments = _department_options()
    partners_without_company = (
        Partner.query.filter(Partner.company_id.is_(None), Partner.deleted_at.is_(None))
        .order_by(Partner.full_name.asc())
        .all()
    )
    return render_template(
        "partner_relations/index.html",
        companies=companies,
        all_companies=all_companies,
        departments=departments,
        filters=request.args,
        partners_without_company=partners_without_company,
        can_edit=can_edit_partner(),
    )


@bp.get("/company/<int:company_id>")
def company(company_id):
    company = _company_or_404(company_id)
    relationships = _relationship_rows(company.id, request.args.get("q", ""), request.args.get("department", ""))
    return render_template(
        "partner_relations/company.html",
        company=company,
        relationships=relationships,
        grouped_relationships=_group_relationships(relationships),
        filters=request.args,
        can_edit=can_edit_partner(),
        relationship_type_labels=RELATIONSHIP_TYPES,
        departments=_company_departments(company.id),
    )


@bp.route("/company/<int:company_id>/manage", methods=["GET", "POST"])
def manage_company(company_id):
    if not can_edit_partner():
        abort(403)
    company = _company_or_404(company_id)
    partners = _company_partners(company.id)
    relationship = None
    errors = {}
    form_data = {}
    if request.method == "POST":
        relationship = PartnerRelationship()
        errors, form_data = _relationship_form_data(company, partners)
        if not errors:
            _save_relationship(relationship, company, form_data)
            db.session.commit()
            flash("Đã thêm quan hệ.", "success")
            return redirect(url_for("partner_relations.manage_company", company_id=company.id))
        flash("Vui lòng kiểm tra lại thông tin quan hệ.", "danger")
        return _render_manage(company, partners, relationship, errors, form_data), 400
    return _render_manage(company, partners, relationship, errors, form_data)


@bp.route("/company/<int:company_id>/relationships/<int:relationship_id>/edit", methods=["GET", "POST"])
def edit_relationship(company_id, relationship_id):
    if not can_edit_partner():
        abort(403)
    company = _company_or_404(company_id)
    partners = _company_partners(company.id)
    relationship = _relationship_or_404(company.id, relationship_id)
    errors = {}
    form_data = _relationship_to_form_data(relationship)
    if request.method == "POST":
        errors, form_data = _relationship_form_data(company, partners, relationship)
        if not errors:
            _save_relationship(relationship, company, form_data)
            db.session.commit()
            flash("Đã cập nhật quan hệ.", "success")
            return redirect(url_for("partner_relations.manage_company", company_id=company.id))
        flash("Vui lòng kiểm tra lại thông tin quan hệ.", "danger")
        return _render_manage(company, partners, relationship, errors, form_data), 400
    return _render_manage(company, partners, relationship, errors, form_data)


@bp.post("/company/<int:company_id>/relationships/<int:relationship_id>/delete")
def delete_relationship(company_id, relationship_id):
    if not can_edit_partner():
        abort(403)
    company = _company_or_404(company_id)
    relationship = _relationship_or_404(company.id, relationship_id)
    relationship.deleted_at = func.now()
    relationship.is_active = False
    db.session.commit()
    flash("Đã xóa quan hệ.", "success")
    return redirect(url_for("partner_relations.manage_company", company_id=company.id))


@bp.get("/company/<int:company_id>/tree")
def tree(company_id):
    company = _company_or_404(company_id)
    relationships = _relationship_rows(company.id, request.args.get("q", ""), request.args.get("department", ""))
    tree_data = _build_department_tree(company.id, request.args.get("q", ""), request.args.get("department", ""))
    return render_template(
        "partner_relations/tree.html",
        company=company,
        tree_data=tree_data,
        relationships=relationships,
        filters=request.args,
        can_edit=can_edit_partner(),
        relationship_type_labels=RELATIONSHIP_TYPES,
        departments=_company_departments(company.id),
    )


@bp.get("/departments/<int:department_id>/summary")
def department_summary(department_id):
    department = (
        CompanyDepartment.query.join(Company)
        .filter(
            CompanyDepartment.id == department_id,
            CompanyDepartment.is_active.is_(True),
            Company.deleted_at.is_(None),
        )
        .first_or_404()
    )
    members = _department_members(department.id)
    relationships = _department_relationships(department.company_id, department.id)
    return render_template(
        "partner_relations/_department_summary.html",
        department=department,
        company=department.company,
        head=_department_head(members),
        members=members,
        relationships=relationships,
        relationships_by_partner=_relationships_by_partner(relationships),
        relationship_type_labels=RELATIONSHIP_TYPES,
        child_departments=sorted(
            [item for item in department.child_departments if item.is_active],
            key=lambda item: (item.display_order, item.name),
        ),
    )


@bp.route("/company/<int:company_id>/edit", methods=["GET", "POST"])
def edit_company(company_id):
    return redirect(url_for("partner_relations.manage_company", company_id=company_id))


def _render_manage(company, partners, relationship, errors, form_data):
    relationships = _relationship_rows(company.id)
    return render_template(
        "partner_relations/manage.html",
        company=company,
        partners=partners,
        relationships=relationships,
        relationship=relationship,
        relationship_types=RELATIONSHIP_TYPES,
        departments=_company_departments(company.id),
        errors=errors,
        form_data=form_data,
    )


def _relationship_form_data(company, partners, current_relationship=None):
    errors = {}
    partner_ids = {partner.id for partner in partners}
    partner_id = _optional_int(request.form.get("partner_id"))
    parent_partner_id = _optional_int(request.form.get("parent_partner_id"))
    relationship_type = request.form.get("relationship_type", "direct_report").strip()
    partner = next((item for item in partners if item.id == partner_id), None)

    if not partner_id or partner_id not in partner_ids:
        errors["partner_id"] = "Vui lòng chọn đối tác."
    elif not partner or not partner.department_id:
        errors["partner_id"] = "Đối tác phải có phòng ban hợp lệ."
    elif not partner.position:
        errors["partner_id"] = "Đối tác phải có vị trí hợp lệ."
    if parent_partner_id and parent_partner_id == partner_id:
        errors["parent_partner_id"] = "Đối tác không thể báo cáo cho chính mình."
    if parent_partner_id and parent_partner_id not in partner_ids:
        errors["parent_partner_id"] = "Cấp trên không hợp lệ."
    if relationship_type not in RELATIONSHIP_TYPES:
        relationship_type = "direct_report"
    if relationship_type == "none":
        parent_partner_id = None

    form_data = {
        "partner_id": partner_id,
        "department_id": partner.department_id if partner else None,
        "department": partner.company_department.name if partner and partner.company_department else "",
        "position_title": partner.position if partner else "",
        "parent_partner_id": parent_partner_id,
        "relationship_type": relationship_type,
        "display_order": _int_or_zero(request.form.get("display_order")),
        "note": request.form.get("note", "").strip(),
    }
    if not errors and _creates_cycle(company.id, partner_id, parent_partner_id, current_relationship):
        errors["parent_partner_id"] = "Không thể tạo quan hệ vòng lặp."
    return errors, form_data


def _save_relationship(relationship, company, data):
    if relationship.id is None:
        _add_with_sqlite_id(relationship)
    partner_id = data["partner_id"]
    parent_partner_id = data["parent_partner_id"]
    relationship.company_id = company.id
    relationship.partner_id = partner_id
    partner = db.session.get(Partner, partner_id)
    relationship.from_partner_id = parent_partner_id or partner_id
    relationship.to_partner_id = partner_id
    relationship.department_id = partner.department_id if partner else None
    relationship.department = partner.company_department.name if partner and partner.company_department else None
    relationship.position_title = partner.position if partner else None
    relationship.parent_partner_id = parent_partner_id
    relationship.relationship_type = data["relationship_type"]
    relationship.is_department_head = False
    relationship.display_order = data["display_order"]
    relationship.note = data["note"] or None
    relationship.notes = relationship.note
    relationship.is_active = True
    relationship.deleted_at = None


def _relationship_to_form_data(relationship):
    return {
        "partner_id": relationship.partner_id or relationship.to_partner_id,
        "department": relationship.department or "",
        "department_id": relationship.department_id,
        "position_title": relationship.position_title or "",
        "parent_partner_id": relationship.parent_partner_id,
        "relationship_type": relationship.relationship_type or "direct_report",
        "display_order": relationship.display_order or 0,
        "note": relationship.note or relationship.notes or "",
    }


def _relationship_or_404(company_id, relationship_id):
    return PartnerRelationship.query.filter(
        PartnerRelationship.id == relationship_id,
        PartnerRelationship.company_id == company_id,
        PartnerRelationship.deleted_at.is_(None),
    ).first_or_404()


def _relationship_rows(company_id, search="", department=""):
    query = (
        PartnerRelationship.query.join(Partner, Partner.id == PartnerRelationship.partner_id)
        .filter(
            PartnerRelationship.company_id == company_id,
            PartnerRelationship.deleted_at.is_(None),
            PartnerRelationship.is_active.is_(True),
        )
    )
    search = (search or "").strip()
    department = (department or "").strip()
    if search:
        query = query.filter(Partner.full_name.ilike(f"%{search}%"))
    if department:
        query = query.filter(PartnerRelationship.department_id == int(department) if department.isdigit() else PartnerRelationship.department == department)
    return query.order_by(
        PartnerRelationship.department.asc(),
        PartnerRelationship.display_order.asc(),
        Partner.full_name.asc(),
        PartnerRelationship.id.asc(),
    ).all()


def _build_department_tree(company_id, search="", department_filter=""):
    departments = _company_departments(company_id)
    relationships = _relationship_rows(company_id)
    members_by_department = _members_by_department(company_id)
    rows_by_department_id = {}
    for row in relationships:
        rows_by_department_id.setdefault(row.department_id, []).append(row)
    by_parent = {}
    for department in departments:
        by_parent.setdefault(department.parent_department_id, []).append(department)

    visible_department_ids = _visible_department_ids(departments, members_by_department, search, department_filter)
    if visible_department_ids is not None:
        by_parent = {
            parent_id: [department for department in rows if department.id in visible_department_ids]
            for parent_id, rows in by_parent.items()
        }

    def build_department(department):
        rows = rows_by_department_id.get(department.id, [])
        members = members_by_department.get(department.id, [])
        return {
            "department": department,
            "head": _department_head(members),
            "members": _filter_members_for_search(members, search),
            "is_match": _department_matches_search(department, members, search),
            "children": [build_department(child) for child in sorted(by_parent.get(department.id, []), key=lambda item: (item.display_order, item.name))],
        }

    if department_filter and department_filter.isdigit():
        selected = next((department for department in departments if department.id == int(department_filter)), None)
        return [build_department(selected)] if selected and (visible_department_ids is None or selected.id in visible_department_ids) else []
    return [build_department(dept) for dept in sorted(by_parent.get(None, []), key=lambda item: (item.display_order, item.name))]


def _visible_department_ids(departments, members_by_department, search="", department_filter=""):
    selected_ids = None
    if department_filter and department_filter.isdigit():
        selected = next((department for department in departments if department.id == int(department_filter)), None)
        selected_ids = _department_subtree_ids(departments, selected.id) if selected else set()
    search = (search or "").strip().lower()
    if not search:
        return selected_ids

    by_id = {department.id: department for department in departments}
    matching_ids = set()
    for department in departments:
        members = members_by_department.get(department.id, [])
        if _department_matches_search(department, members, search):
            matching_ids.add(department.id)
            current = department.parent_department_id
            while current:
                matching_ids.add(current)
                parent = by_id.get(current)
                current = parent.parent_department_id if parent else None
    return matching_ids if selected_ids is None else matching_ids & selected_ids


def _department_subtree_ids(departments, root_id):
    by_parent = {}
    for department in departments:
        by_parent.setdefault(department.parent_department_id, []).append(department)
    result = {root_id}
    pending = [root_id]
    while pending:
        current = pending.pop()
        for child in by_parent.get(current, []):
            result.add(child.id)
            pending.append(child.id)
    return result


def _department_matches_search(department, members, search):
    search = (search or "").strip().lower()
    if not search:
        return False
    if search in (department.name or "").lower():
        return True
    return any(search in (member.full_name or "").lower() for member in members)


def _filter_members_for_search(members, search):
    search = (search or "").strip().lower()
    if not search:
        return members
    filtered = [member for member in members if search in (member.full_name or "").lower()]
    return filtered or members


def _parent_in_department(parent_partner_id, rows):
    return any(row.partner_id == parent_partner_id for row in rows)


def _group_relationships(relationships):
    grouped = {}
    for relationship in relationships:
        grouped.setdefault(relationship.department or "Chưa có phòng ban", []).append(relationship)
    return grouped


def _relationship_sort_key(relationship):
    return (
        0 if relationship.is_department_head else 1,
        relationship.display_order or 0,
        relationship.partner.full_name if relationship.partner else "",
        relationship.id or 0,
    )


def _members_by_department(company_id):
    members = (
        Partner.query.filter(
            Partner.company_id == company_id,
            Partner.department_id.isnot(None),
            Partner.deleted_at.is_(None),
            Partner.is_active.is_(True),
        )
        .order_by(Partner.full_name.asc())
        .all()
    )
    grouped = {}
    for member in members:
        grouped.setdefault(member.department_id, []).append(member)
    return grouped


def _department_members(department_id):
    return (
        Partner.query.filter(
            Partner.department_id == department_id,
            Partner.deleted_at.is_(None),
            Partner.is_active.is_(True),
        )
        .order_by(Partner.full_name.asc())
        .all()
    )


def _department_relationships(company_id, department_id):
    return (
        PartnerRelationship.query.filter(
            PartnerRelationship.company_id == company_id,
            PartnerRelationship.department_id == department_id,
            PartnerRelationship.deleted_at.is_(None),
            PartnerRelationship.is_active.is_(True),
        )
        .order_by(
            PartnerRelationship.display_order.asc(),
            PartnerRelationship.id.asc(),
        )
        .all()
    )


def _department_head(members):
    heads = [member for member in members if member.is_department_head]
    return sorted(heads, key=lambda item: (item.full_name or "", item.id or 0))[0] if heads else None


def _relationships_by_partner(relationships):
    grouped = {}
    for relationship in relationships:
        partner_id = relationship.partner_id or relationship.to_partner_id
        grouped.setdefault(partner_id, []).append(relationship)
    return grouped


def _creates_cycle(company_id, partner_id, parent_partner_id, current_relationship=None):
    if not parent_partner_id:
        return False
    parent_by_partner = {}
    for row in _relationship_rows(company_id):
        if current_relationship and row.id == current_relationship.id:
            continue
        if row.parent_partner_id:
            parent_by_partner.setdefault(row.partner_id, row.parent_partner_id)
    parent_by_partner[partner_id] = parent_partner_id
    seen = {partner_id}
    current = parent_partner_id
    while current:
        if current in seen:
            return True
        seen.add(current)
        current = parent_by_partner.get(current)
    return False


def _company_or_404(company_id):
    return Company.query.filter(Company.id == company_id, Company.deleted_at.is_(None)).first_or_404()


def _company_partners(company_id):
    return (
        Partner.query.filter(Partner.company_id == company_id, Partner.deleted_at.is_(None))
        .order_by(Partner.full_name.asc())
        .all()
    )


def _department_options():
    return CompanyDepartment.query.filter(CompanyDepartment.is_active.is_(True)).order_by(CompanyDepartment.name.asc()).all()


def _company_departments(company_id):
    return (
        CompanyDepartment.query.filter(CompanyDepartment.company_id == company_id, CompanyDepartment.is_active.is_(True))
        .order_by(CompanyDepartment.display_order.asc(), CompanyDepartment.name.asc())
        .all()
    )


def _optional_int(value):
    value = (value or "").strip()
    return int(value) if value.isdigit() else None


def _int_or_zero(value):
    try:
        return int(value or 0)
    except ValueError:
        return 0
