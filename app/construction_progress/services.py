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
    items = list(group.items)
    if value_mode == "money":
        planned = sum((Decimal(item.planned_quantity or 0) for item in items), Decimal())
        return None if planned <= 0 else sum((Decimal(item.completed_quantity or 0) for item in items), Decimal()) / planned * 100
    values = [item_percent(item) for item in items]
    values = [value for value in values if value is not None]
    return sum(values, Decimal()) / len(values) if values else None


def type_percent(progress_type):
    groups = list(progress_type.groups)
    if progress_type.value_mode == "money":
        items = [item for group in groups for item in group.items]
        planned = sum((Decimal(item.planned_quantity or 0) for item in items), Decimal())
        return None if planned <= 0 else sum((Decimal(item.completed_quantity or 0) for item in items), Decimal()) / planned * 100
    values = [group_percent(group, "quantity") for group in groups]
    values = [value for value in values if value is not None]
    return sum(values, Decimal()) / len(values) if values else None


def progress_tree(project, progress_type=None):
    query = ProgressType.query.filter_by(project_id=project.id).options(joinedload(ProgressType.groups).joinedload(ProgressGroup.items))
    if progress_type is not None:
        query = query.filter_by(id=progress_type.id)
    types = query.order_by(ProgressType.display_order, ProgressType.id).all()
    return [{"type": value, "percent": type_percent(value), "groups": [
        {"group": group, "percent": group_percent(group, value.value_mode), "items": [
            {"item": item, "percent": item_percent(item)} for item in group.items
        ]} for group in value.groups
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


class ConfirmationNameError(ValueError):
    pass


def _user_values(user):
    return None if user is None else {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
    }


def _entry_values_for_delete(entry):
    return {
        "id": entry.id,
        "report_date": entry.report_date.isoformat(),
        "quantity": str(entry.quantity),
        "note": entry.note,
        "created_by": _user_values(entry.created_by),
    }


def _item_values_for_delete(item):
    return {
        "id": item.id,
        "name": item.name,
        "unit": item.unit,
        "decimal_places": item.decimal_places,
        "planned_quantity": str(item.planned_quantity),
        "opening_quantity": str(item.opening_quantity),
        "completed_quantity": str(item.completed_quantity),
        "note": item.note,
        "entries": [_entry_values_for_delete(entry) for entry in sorted(item.entries, key=lambda entry: entry.id)],
    }


def _group_values_for_delete(group):
    return {
        "id": group.id,
        "name": group.name,
        "note": group.note,
        "items": [_item_values_for_delete(item) for item in sorted(group.items, key=lambda item: item.id)],
    }


def _deletion_context(*, progress_type, groups):
    groups = sorted(groups, key=lambda group: group.id)
    items = [item for group in groups for item in sorted(group.items, key=lambda item: item.id)]
    entries = [entry for item in items for entry in sorted(item.entries, key=lambda entry: entry.id)]
    return {
        "progress_type": {
            "id": progress_type.id,
            "name": progress_type.name,
            "value_mode": progress_type.value_mode,
            "description": progress_type.description,
        },
        "groups": [_group_values_for_delete(group) for group in groups],
        "counts": {"groups": len(groups), "items": len(items), "entries": len(entries)},
    }, groups, items, entries


def deletion_summary_for_type(progress_type):
    return _deletion_context(progress_type=progress_type, groups=list(progress_type.groups))[0]["counts"]


def deletion_summary_for_group(group):
    return _deletion_context(progress_type=group.progress_type, groups=[group])[0]["counts"]


def deletion_summary_for_item(item):
    return _deletion_context(progress_type=item.progress_group.progress_type, groups=[item.progress_group])[0]["counts"] | {"items": 1, "entries": len(item.entries)}


def _confirm_structure_delete(name, confirm_name):
    if confirm_name != name:
        raise ConfirmationNameError("Tên xác nhận không khớp. Chưa xoá dữ liệu nào.")


def _hard_delete_structure(*, action, entity_type, entity, progress_type, groups, confirm_name):
    _confirm_structure_delete(entity.name, confirm_name)
    old_values, groups, items, entries = _deletion_context(progress_type=progress_type, groups=groups)
    with db.session.begin_nested():
        log_audit(action, entity_type, entity.id, old_values=old_values)
        db.session.flush()
        for entry in entries:
            db.session.delete(entry)
        db.session.flush()
        for item in items:
            db.session.delete(item)
        db.session.flush()
        for group in groups:
            db.session.delete(group)
        db.session.flush()
        if entity_type == "ProgressType":
            db.session.delete(entity)
            db.session.flush()
    return old_values["counts"]


def delete_type(progress_type, *, confirm_name, actor_id=None):
    return _hard_delete_structure(
        action="construction_progress.type.delete",
        entity_type="ProgressType",
        entity=progress_type,
        progress_type=progress_type,
        groups=list(progress_type.groups),
        confirm_name=confirm_name,
    )


def delete_group(group, *, confirm_name, actor_id=None):
    return _hard_delete_structure(
        action="construction_progress.group.delete",
        entity_type="ProgressGroup",
        entity=group,
        progress_type=group.progress_type,
        groups=[group],
        confirm_name=confirm_name,
    )


def delete_item(item, *, confirm_name, actor_id=None):
    _confirm_structure_delete(item.name, confirm_name)
    item_values = _item_values_for_delete(item)
    old_values = {
        "progress_type": {
            "id": item.progress_group.progress_type.id,
            "name": item.progress_group.progress_type.name,
            "value_mode": item.progress_group.progress_type.value_mode,
            "description": item.progress_group.progress_type.description,
        },
        "groups": [{
            "id": item.progress_group.id,
            "name": item.progress_group.name,
            "items": [item_values],
        }],
        "counts": {"groups": 0, "items": 1, "entries": len(item.entries)},
    }
    with db.session.begin_nested():
        log_audit("construction_progress.item.delete", "ProgressItem", item.id, old_values=old_values)
        db.session.flush()
        for entry in item.entries:
            db.session.delete(entry)
        db.session.flush()
        db.session.delete(item)
        db.session.flush()
    return old_values["counts"]


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
