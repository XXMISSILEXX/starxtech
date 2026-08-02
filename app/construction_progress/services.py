"""Construction-progress calculations and transactional mutations."""

from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app.audit import log_audit
from app.date_utils import local_today, parse_iso_date
from app.extensions import db
from app.models import ProgressEntry, ProgressGroup, ProgressItem, ProgressType


class DuplicateEntryError(ValueError):
    pass


class FutureDateError(ValueError):
    pass


class InvalidQuantityError(ValueError):
    pass


class InvalidDecimalPlacesError(ValueError):
    pass


def item_percent(item):
    planned = Decimal(item.planned_quantity or 0)
    return None if planned <= 0 else Decimal(item.completed_quantity or 0) / planned * 100


def group_percent(group, value_mode):
    items = [item for item in group.items if item.is_active]
    if value_mode == "money":
        planned = sum((Decimal(item.planned_quantity or 0) for item in items), Decimal())
        return None if planned <= 0 else sum((Decimal(item.completed_quantity or 0) for item in items), Decimal()) / planned * 100
    values = [item_percent(item) for item in items]
    values = [value for value in values if value is not None]
    return sum(values, Decimal()) / len(values) if values else None


def type_percent(progress_type):
    groups = [group for group in progress_type.groups if group.is_active]
    if progress_type.value_mode == "money":
        items = [item for group in groups for item in group.items]
        planned = sum((Decimal(item.planned_quantity or 0) for item in items), Decimal())
        return None if planned <= 0 else sum((Decimal(item.completed_quantity or 0) for item in items), Decimal()) / planned * 100
    values = [group_percent(group, "quantity") for group in groups]
    values = [value for value in values if value is not None]
    return sum(values, Decimal()) / len(values) if values else None


def progress_tree(project, progress_type=None):
    query = ProgressType.query.filter_by(project_id=project.id, is_active=True).options(joinedload(ProgressType.groups).joinedload(ProgressGroup.items))
    if progress_type is not None:
        query = query.filter_by(id=progress_type.id)
    types = query.order_by(ProgressType.display_order, ProgressType.id).all()
    return [{"type": value, "percent": type_percent(value), "groups": [
        {"group": group, "percent": group_percent(group, value.value_mode), "items": [
            {"item": item, "percent": item_percent(item)} for item in group.items if item.is_active
        ]} for group in value.groups if group.is_active
    ]} for value in types]


def recalculate_item_completed(item):
    if db.engine.dialect.name == "postgresql":
        item = ProgressItem.query.filter_by(id=item.id).with_for_update().one()
    total = db.session.query(func.coalesce(func.sum(ProgressEntry.quantity), 0)).filter_by(progress_item_id=item.id).scalar()
    item.completed_quantity = Decimal(item.opening_quantity or 0) + Decimal(total or 0)
    return item


def _entry_values(entry):
    return {"report_date": entry.report_date.isoformat(), "quantity": str(entry.quantity), "note": entry.note}


def _report_date(value):
    result = parse_iso_date(value, field_label="Ngày", allow_empty=False) if isinstance(value, str) else value
    if result > local_today():
        raise FutureDateError("Không thể tạo phiếu cho ngày trong tương lai.")
    return result


def _quantity(value):
    try:
        value = Decimal(str(value))
    except Exception as exc:
        raise InvalidQuantityError("Khối lượng phải lớn hơn 0.") from exc
    if value <= 0:
        raise InvalidQuantityError("Khối lượng phải lớn hơn 0.")
    return value


def _nonnegative_quantity(value):
    try:
        result = Decimal(str(value))
    except Exception as exc:
        raise InvalidQuantityError("Khối lượng kế hoạch và mang sang không hợp lệ.") from exc
    if result < 0:
        raise InvalidQuantityError("Khối lượng kế hoạch và mang sang không được âm.")
    return result


def _decimal_places(value):
    try:
        result = int(str(value))
    except (TypeError, ValueError) as exc:
        raise InvalidDecimalPlacesError("Số chữ số thập phân phải từ 0 đến 3.") from exc
    if not 0 <= result <= 3:
        raise InvalidDecimalPlacesError("Số chữ số thập phân phải từ 0 đến 3.")
    return result


def _has_decimal_precision(value, decimal_places):
    return Decimal(value).quantize(Decimal(1).scaleb(-decimal_places)) == Decimal(value)


def _validate_decimal_precision(value, decimal_places, field_label):
    if not _has_decimal_precision(value, decimal_places):
        raise InvalidDecimalPlacesError(
            f"{field_label} chỉ được có tối đa {decimal_places} chữ số thập phân."
        )


def _decimal_value_label(value):
    text = format(Decimal(value), "f").rstrip("0").rstrip(".")
    return text.replace(".", ",")


def _validate_existing_item_precision(item, decimal_places):
    candidates = [
        ("khối lượng kế hoạch", item.planned_quantity),
        ("khối lượng mang sang", item.opening_quantity),
    ]
    candidates.extend(
        (f"phiếu ngày {entry.report_date:%d/%m/%Y} có khối lượng", entry.quantity)
        for entry in item.entries
    )
    for label, value in candidates:
        if not _has_decimal_precision(value, decimal_places):
            raise InvalidDecimalPlacesError(
                f"Không thể hạ xuống {decimal_places} chữ số thập phân vì {label} "
                f"{_decimal_value_label(value)} cần độ chính xác cao hơn."
            )


def create_entry(*, item, report_date, quantity, note=None, actor_id=None):
    report_date, quantity = _report_date(report_date), _quantity(quantity)
    _validate_decimal_precision(quantity, item.decimal_places, "Khối lượng")
    entry = ProgressEntry(project_id=item.project_id, progress_item_id=item.id, report_date=report_date, quantity=quantity, note=(note or "").strip() or None, created_by_id=actor_id, updated_by_id=actor_id)
    try:
        with db.session.begin_nested():
            db.session.add(entry)
            db.session.flush()
    except IntegrityError as exc:
        raise DuplicateEntryError(f"Ngày {report_date:%d/%m/%Y} đã có phiếu cho hạng mục này. Hãy mở phiếu đó để sửa.") from exc
    recalculate_item_completed(item)
    log_audit("construction_progress.entry.create", "ProgressEntry", entry.id, new_values=_entry_values(entry))
    return entry


def update_entry(entry, *, report_date, quantity, note=None, actor_id=None):
    old_values = _entry_values(entry)
    report_date, quantity = _report_date(report_date), _quantity(quantity)
    _validate_decimal_precision(quantity, entry.progress_item.decimal_places, "Khối lượng")
    entry.report_date, entry.quantity, entry.note, entry.updated_by_id = report_date, quantity, (note or "").strip() or None, actor_id
    try:
        with db.session.begin_nested():
            db.session.flush()
    except IntegrityError as exc:
        raise DuplicateEntryError(f"Ngày {entry.report_date:%d/%m/%Y} đã có phiếu cho hạng mục này. Hãy mở phiếu đó để sửa.") from exc
    recalculate_item_completed(entry.progress_item)
    log_audit("construction_progress.entry.update", "ProgressEntry", entry.id, old_values=old_values, new_values=_entry_values(entry))
    return entry


def delete_entry(entry, *, actor_id=None):
    old_values, item = _entry_values(entry), entry.progress_item
    db.session.delete(entry)
    db.session.flush()
    recalculate_item_completed(item)
    log_audit("construction_progress.entry.delete", "ProgressEntry", entry.id, old_values=old_values)


def create_type(*, project, name, value_mode="quantity", description=None, display_order=0, actor_id=None):
    if value_mode not in {"quantity", "money"}:
        raise ValueError("Chế độ giá trị không hợp lệ.")
    value = ProgressType(project_id=project.id, name=name.strip(), value_mode=value_mode, description=(description or "").strip() or None, display_order=display_order, created_by_id=actor_id, updated_by_id=actor_id)
    db.session.add(value); db.session.flush(); log_audit("construction_progress.type.create", "ProgressType", value.id, new_values={"name": value.name}); return value


def create_group(*, progress_type, name, note=None, display_order=0, actor_id=None):
    value = ProgressGroup(project_id=progress_type.project_id, progress_type_id=progress_type.id, name=name.strip(), note=(note or "").strip() or None, display_order=display_order, created_by_id=actor_id, updated_by_id=actor_id)
    db.session.add(value); db.session.flush(); log_audit("construction_progress.group.create", "ProgressGroup", value.id, new_values={"name": value.name}); return value


def create_item(*, group, name, unit, planned_quantity=0, opening_quantity=0, decimal_places=0, assignee_user_id=None, note=None, display_order=0, actor_id=None):
    planned, opening = _nonnegative_quantity(planned_quantity), _nonnegative_quantity(opening_quantity)
    decimal_places = 0 if group.progress_type.value_mode == "money" else _decimal_places(decimal_places)
    _validate_decimal_precision(planned, decimal_places, "Khối lượng kế hoạch")
    _validate_decimal_precision(opening, decimal_places, "Khối lượng mang sang")
    value = ProgressItem(project_id=group.project_id, progress_group_id=group.id, name=name.strip(), unit="VNĐ" if group.progress_type.value_mode == "money" else unit.strip(), decimal_places=decimal_places, planned_quantity=planned, opening_quantity=opening, assignee_user_id=assignee_user_id, note=(note or "").strip() or None, display_order=display_order, created_by_id=actor_id, updated_by_id=actor_id)
    db.session.add(value); db.session.flush(); recalculate_item_completed(value); log_audit("construction_progress.item.create", "ProgressItem", value.id, new_values={"name": value.name}); return value


def archive_type(progress_type, *, actor_id=None):
    progress_type.is_active = False; progress_type.updated_by_id = actor_id; log_audit("construction_progress.type.archive", "ProgressType", progress_type.id, new_values={"is_active": False}); return progress_type


def archive_group(group, *, actor_id=None):
    group.is_active = False; group.updated_by_id = actor_id; log_audit("construction_progress.group.archive", "ProgressGroup", group.id, new_values={"is_active": False}); return group


def archive_item(item, *, actor_id=None):
    item.is_active = False; item.updated_by_id = actor_id; log_audit("construction_progress.item.archive", "ProgressItem", item.id, new_values={"is_active": False}); return item


def update_type(progress_type, *, name, value_mode, description=None, display_order=0, actor_id=None):
    old = {"name": progress_type.name, "value_mode": progress_type.value_mode, "description": progress_type.description}
    if value_mode not in {"quantity", "money"}:
        raise ValueError("Chế độ giá trị không hợp lệ.")
    progress_type.name, progress_type.value_mode, progress_type.description, progress_type.display_order, progress_type.updated_by_id = name.strip(), value_mode, (description or "").strip() or None, display_order, actor_id
    log_audit("construction_progress.type.update", "ProgressType", progress_type.id, old_values=old, new_values={"name": progress_type.name, "value_mode": progress_type.value_mode, "description": progress_type.description})
    return progress_type


def update_group(group, *, name, note=None, display_order=0, actor_id=None):
    old = {"name": group.name, "note": group.note}
    group.name, group.note, group.display_order, group.updated_by_id = name.strip(), (note or "").strip() or None, display_order, actor_id
    log_audit("construction_progress.group.update", "ProgressGroup", group.id, old_values=old, new_values={"name": group.name, "note": group.note})
    return group


def update_item(item, *, name, unit, planned_quantity, opening_quantity, decimal_places=0, assignee_user_id=None, note=None, display_order=0, actor_id=None):
    planned, opening = _nonnegative_quantity(planned_quantity), _nonnegative_quantity(opening_quantity)
    decimal_places = 0 if item.progress_group.progress_type.value_mode == "money" else _decimal_places(decimal_places)
    _validate_decimal_precision(planned, decimal_places, "Khối lượng kế hoạch")
    _validate_decimal_precision(opening, decimal_places, "Khối lượng mang sang")
    _validate_existing_item_precision(item, decimal_places)
    old = {"name": item.name, "planned_quantity": str(item.planned_quantity), "opening_quantity": str(item.opening_quantity), "decimal_places": item.decimal_places}
    item.name, item.unit, item.decimal_places, item.planned_quantity, item.opening_quantity = name.strip(), "VNĐ" if item.progress_group.progress_type.value_mode == "money" else unit.strip(), decimal_places, planned, opening
    item.assignee_user_id, item.note, item.display_order, item.updated_by_id = assignee_user_id, (note or "").strip() or None, display_order, actor_id
    recalculate_item_completed(item)
    log_audit("construction_progress.item.update", "ProgressItem", item.id, old_values=old, new_values={"name": item.name, "planned_quantity": str(item.planned_quantity), "opening_quantity": str(item.opening_quantity), "decimal_places": item.decimal_places})
    return item
