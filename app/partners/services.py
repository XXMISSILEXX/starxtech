import re
from decimal import Decimal, InvalidOperation

from flask_login import current_user
from sqlalchemy import func, or_

from app.date_utils import format_vn_date as format_shared_vn_date, parse_iso_date
from app.extensions import db
from app.models import Company, CompanyDepartment, Partner, PartnerFieldCollection, PartnerFieldDefinition, PartnerFieldValue


FIELD_TYPES = [
    "text",
    "textarea",
    "number",
    "date",
    "boolean",
    "select",
    "multi_select",
    "url",
    "email",
    "phone",
]


class PartnerValidationError(ValueError):
    def __init__(self, message, errors=None):
        super().__init__(message)
        self.errors = errors or {}


def active_field_definitions():
    return (
        PartnerFieldDefinition.query.filter(PartnerFieldDefinition.is_active.is_(True))
        .order_by(PartnerFieldDefinition.sort_order.asc(), PartnerFieldDefinition.label.asc())
        .all()
    )


def active_field_collections():
    return (
        PartnerFieldCollection.query.filter(PartnerFieldCollection.is_active.is_(True))
        .order_by(PartnerFieldCollection.sort_order.asc(), PartnerFieldCollection.name.asc())
        .all()
    )


def partners_query(include_inactive=False):
    query = Partner.query.outerjoin(Company).outerjoin(CompanyDepartment, Partner.department_id == CompanyDepartment.id)
    if not include_inactive:
        query = query.filter(Partner.deleted_at.is_(None), Partner.is_active.is_(True))
    return query


def apply_partner_filters(query, args):
    search = args.get("q", "").strip()
    company_id = args.get("company_id", "").strip()
    industry = args.get("industry", "").strip()
    department = args.get("department", "").strip()
    position = args.get("position", "").strip()
    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                Partner.full_name.ilike(like),
                Partner.phone.ilike(like),
                Partner.email.ilike(like),
                Company.name.ilike(like),
            )
        )
    if company_id.isdigit():
        query = query.filter(Partner.company_id == int(company_id))
    if industry:
        query = query.filter(Company.industry == industry)
    if department:
        query = query.filter(Partner.department_id == int(department) if department.isdigit() else CompanyDepartment.name == department)
    if position:
        query = query.filter(Partner.position == position)
    return query


def save_partner(form, partner=None):
    is_new = partner is None
    form_data = build_partner_form_data(form, partner)
    errors = _validate_partner_data(form_data, partner)
    field_rows = build_field_value_rows(form)
    field_errors = _validate_field_value_rows(field_rows)
    errors.update(field_errors)
    if errors:
        raise PartnerValidationError("Vui lòng kiểm tra lại thông tin đối tác.", errors)

    if is_new:
        partner = Partner(created_by_user_id=current_user.id)
        _add_with_sqlite_id(partner)

    partner.full_name = form_data["full_name"]
    partner.company_id = form_data["company_id"]
    partner.department_id = form_data["department_id"]
    partner.department = _department_name(form_data["department_id"])
    partner.position = form_data["position"]
    partner.is_department_head = form_data["is_department_head"]
    partner.phone = form_data["phone"]
    partner.email = form_data["email"]
    partner.birth_date = form_data["birth_date"]
    partner.address = form_data["address"]
    partner.notes = form_data["notes"]
    partner.updated_by_user_id = current_user.id

    partner.field_values[:] = []
    db.session.flush()
    for row in field_rows:
        value = PartnerFieldValue(partner_id=partner.id)
        _add_with_sqlite_id(value)
        _populate_field_value(value, row)
        partner.field_values.append(value)
    return partner


def build_partner_form_data(form, partner=None):
    if form:
        return {
            "full_name": form.get("full_name", "").strip(),
            "company_id": _optional_int(form.get("company_id")),
            "department_id": _optional_int(form.get("department_id")),
            "department": None,
            "position": _optional_text(form.get("position")),
            "is_department_head": form.get("is_department_head") == "on" if "is_department_head" in form else (partner.is_department_head if partner else False),
            "phone": _optional_text(form.get("phone")),
            "email": _optional_text(form.get("email")),
            "birth_date": _parse_iso_date_or_none(form.get("birth_date")),
            "birth_date_raw": form.get("birth_date", "").strip(),
            "address": _optional_text(form.get("address")),
            "notes": _optional_text(form.get("notes")),
        }
    if not partner:
        return {}
    return {
        "full_name": partner.full_name,
        "company_id": partner.company_id,
        "department_id": partner.department_id,
        "department": partner.department,
        "position": partner.position,
        "is_department_head": partner.is_department_head,
        "phone": partner.phone,
        "email": partner.email,
        "birth_date": partner.birth_date,
        "birth_date_raw": partner.birth_date.isoformat() if partner.birth_date else "",
        "address": partner.address,
        "notes": partner.notes,
    }


def build_field_form_rows(form=None, partner=None):
    if form:
        return build_field_value_rows(form, keep_empty=True)
    if not partner:
        return []
    rows = []
    for value in partner.field_values:
        rows.append(
            {
                "field_definition_id": value.field_definition_id,
                "label": value.field_label_snapshot,
                "field_type": value.field_type_snapshot,
                "group_name": value.group_name_snapshot,
                "value": form_field_value(value),
                "options": _options_for_value(value),
                "sort_order": value.sort_order,
            }
        )
    return rows


def build_field_value_rows(form, keep_empty=False):
    indexes = sorted(
        {
            key.split("[", 1)[1].split("]", 1)[0]
            for key in form.keys()
            if key.startswith("fields[") and "][" in key
        },
        key=lambda item: int(item) if item.isdigit() else item,
    )
    rows = []
    for sort_order, index in enumerate(indexes):
        definition_id = _optional_int(form.get(f"fields[{index}][field_definition_id]"))
        if not definition_id:
            continue
        definition = db.session.get(PartnerFieldDefinition, definition_id)
        if not definition:
            continue
        label = definition.label.strip()
        field_type = definition.field_type.strip()
        group_name = definition.group_name
        value = _field_posted_value(form, index, field_type)
        if not keep_empty and not _has_value(value, field_type):
            continue
        if not label or field_type not in FIELD_TYPES:
            continue
        rows.append(
            {
                "field_definition_id": definition.id,
                "label": label,
                "field_key": definition.field_key,
                "field_type": field_type,
                "group_name": group_name,
                "value": value,
                "options": definition.options_json,
                "sort_order": sort_order,
            }
        )
    return rows


def save_field_definition(form, field=None):
    is_new = field is None
    label = form.get("label", "").strip()
    field_type = form.get("field_type", "").strip()
    field_key = form.get("field_key", "").strip() or _slugify(label)
    errors = []
    if not label:
        errors.append("Tên trường là bắt buộc.")
    if field_type not in FIELD_TYPES:
        errors.append("Kiểu dữ liệu không hợp lệ.")
    existing = PartnerFieldDefinition.query.filter(PartnerFieldDefinition.field_key == field_key)
    if field:
        existing = existing.filter(PartnerFieldDefinition.id != field.id)
    if field_key and existing.first():
        errors.append("Mã trường đã tồn tại.")
    try:
        sort_order = int(form.get("sort_order", "0") or "0")
    except ValueError:
        sort_order = 0
        errors.append("Thứ tự phải là số.")
    if errors:
        raise PartnerValidationError(errors[0], {"form": errors})

    if is_new:
        field = PartnerFieldDefinition()
        _add_with_sqlite_id(field)
    field.label = label
    field.field_key = field_key
    field.field_type = field_type
    field.group_name = _optional_text(form.get("group_name"))
    field.options_json = normalize_options(form.get("options", ""))
    field.sort_order = sort_order
    field.is_required = form.get("is_required") == "on"
    field.is_active = form.get("is_active") == "on"
    return field


def normalize_options(raw):
    options = []
    seen = set()
    for line in (raw or "").splitlines():
        value = line.strip()
        if value and value.lower() not in seen:
            options.append(value)
            seen.add(value.lower())
    return options


def display_field_value(value):
    field_type = value.field_type_snapshot
    if field_type in {"text", "textarea", "url", "email", "phone", "select"}:
        return value.value_text or ""
    if field_type == "number":
        return "" if value.value_number is None else str(value.value_number.normalize())
    if field_type == "date":
        return format_vn_date(value.value_date)
    if field_type == "boolean":
        return "Có" if value.value_boolean else "Không"
    if field_type == "multi_select":
        return ", ".join(value.value_json or [])
    return value.value_text or ""


def form_field_value(value):
    """Return native form values; readable views continue to use vn_date."""
    if value.field_type_snapshot == "date":
        return value.value_date.isoformat() if value.value_date else ""
    return display_field_value(value)


def _populate_field_value(value, row):
    value.field_definition_id = row["field_definition_id"]
    value.field_label_snapshot = row["label"]
    value.field_key_snapshot = row["field_key"]
    value.field_type_snapshot = row["field_type"]
    value.group_name_snapshot = row["group_name"]
    value.sort_order = row["sort_order"]
    _assign_typed_value(value, row["field_type"], row["value"])


def _assign_typed_value(value, field_type, raw_value):
    value.value_text = None
    value.value_number = None
    value.value_date = None
    value.value_boolean = None
    value.value_json = None
    if field_type in {"text", "textarea", "url", "email", "phone", "select"}:
        value.value_text = str(raw_value or "").strip()
    elif field_type == "number":
        try:
            value.value_number = Decimal(str(raw_value).strip())
        except (InvalidOperation, ValueError):
            value.value_number = None
    elif field_type == "date":
        value.value_date = _parse_iso_date_or_none(raw_value)
    elif field_type == "boolean":
        value.value_boolean = raw_value in {True, "on", "1", "true", "yes"}
    elif field_type == "multi_select":
        value.value_json = [item.strip() for item in (raw_value or []) if item.strip()]


def _field_posted_value(form, index, field_type):
    key = f"fields[{index}][value]"
    if field_type == "multi_select":
        return form.getlist(key)
    if field_type == "boolean":
        return form.get(key)
    return form.get(key, "")


def _validate_partner_data(data, partner=None):
    errors = {}
    if not data["full_name"]:
        errors["full_name"] = "Họ tên là bắt buộc."
    if not data["company_id"]:
        errors["company_id"] = "Vui lòng chọn công ty."
    if not data["department_id"]:
        errors["department_id"] = "Vui lòng chọn phòng ban."
    if data["birth_date_raw"] and data["birth_date"] is None:
        errors["birth_date"] = "Ngày sinh phải có định dạng YYYY-MM-DD."
    company = db.session.get(Company, data["company_id"]) if data["company_id"] else None
    if data["company_id"] and not company:
        errors["company_id"] = "Công ty không hợp lệ."
    elif company and (company.deleted_at is not None or not company.is_active) and data["company_id"] != (partner.company_id if partner else None):
        errors["company_id"] = "Không thể chọn công ty đã lưu trữ."
    if data["department_id"]:
        department = db.session.get(CompanyDepartment, data["department_id"])
        is_current_department = partner is not None and department and department.id == partner.department_id
        if not department or department.company_id != data["company_id"]:
            errors["department_id"] = "Phòng ban không hợp lệ."
        elif not department.is_active and not is_current_department:
            errors["department_id"] = "Không thể chọn phòng ban đã lưu trữ."
        elif department.is_special_department:
            data["is_department_head"] = False
        elif data["is_department_head"]:
            data["position"] = "Trưởng phòng"
    if not data["position"]:
        errors["position"] = "Vui lòng nhập vị trí."
    return errors


def _department_name(department_id):
    department = db.session.get(CompanyDepartment, department_id) if department_id else None
    return department.name if department else None


def _validate_field_value_rows(rows):
    errors = {}
    for row in rows:
        if row["field_type"] == "date" and row["value"] and _parse_iso_date_or_none(row["value"]) is None:
            errors[f"field_{row['field_definition_id']}"] = "Ngày không hợp lệ, vui lòng nhập theo định dạng YYYY-MM-DD."
    return errors


def _parse_date_or_none(value):
    value = (value or "").strip()
    if not value:
        return None


def _parse_iso_date_or_none(value):
    try:
        return parse_iso_date(value)
    except ValueError:
        return None


def format_vn_date(value):
    return format_shared_vn_date(value)


def _optional_text(value):
    value = (value or "").strip()
    return value or None


def _optional_int(value):
    value = (value or "").strip()
    return int(value) if value.isdigit() else None


def _slugify(value):
    slug = re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower())
    return slug.strip("_")[:120] or "custom_field"


def _has_value(value, field_type):
    if field_type == "boolean":
        return value is not None
    if field_type == "multi_select":
        return any(item.strip() for item in value or [])
    return bool(str(value or "").strip())


def _options_for_value(value):
    if value.field_definition and value.field_definition.options_json:
        return value.field_definition.options_json
    return []


def _add_with_sqlite_id(instance):
    if getattr(instance, "id", None) is None and db.engine.name == "sqlite":
        max_id = db.session.query(func.max(type(instance).id)).scalar() or 0
        instance.id = max_id + 1
    db.session.add(instance)
