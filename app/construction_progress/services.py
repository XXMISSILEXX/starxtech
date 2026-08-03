"""Construction-progress calculations and transactional mutations."""

from calendar import monthrange
from datetime import timedelta
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


class InvalidNumberFormatError(ValueError):
    pass


class BatchValidationError(ValueError):
    def __init__(self, message=None, *, form_errors=None, row_errors=None):
        self.form_errors = form_errors or ({"_form": message} if message else {})
        self.row_errors = row_errors or {}
        super().__init__(message or next(iter(self.form_errors.values()), "Dữ liệu không hợp lệ."))

    @property
    def errors(self):
        return {"form": self.form_errors, "rows": self.row_errors}


def _batch_row_error(position, field, message):
    return BatchValidationError(row_errors={position - 1: {field: message}})


class BatchItemNotFoundError(ValueError):
    pass


_UNSET = object()


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


def item_gantt_timeline(item, entries=()):
    """Derive one item's planned and actual timeline without database access."""
    entry_dates = sorted(
        entry.report_date if hasattr(entry, "report_date") else entry
        for entry in entries
    )
    planned_start, planned_end = item.planned_start_date, item.planned_end_date
    is_scheduled = planned_start is not None and planned_end is not None
    actual_starts = [value for value in (item.actual_start_date, entry_dates[0] if entry_dates else None) if value is not None]
    actual_start = min(actual_starts) if actual_starts else None
    actual_end = entry_dates[-1] if entry_dates else actual_start
    return {
        "item": item,
        "planned_start": planned_start if is_scheduled else None,
        "planned_end": planned_end if is_scheduled else None,
        "actual_start": actual_start,
        "actual_end": actual_end,
        "actual_is_point": actual_start is not None and not entry_dates,
        "has_opening_actual_start_reminder": Decimal(item.opening_quantity or 0) > 0 and item.actual_start_date is None,
        "percent": item_percent(item),
    }


def group_gantt_timeline(group, item_timelines):
    """Derive one group's ranges from only its scheduled item timelines."""
    scheduled_items = [timeline for timeline in item_timelines if timeline["planned_start"] is not None]
    if not scheduled_items:
        return None
    scheduled_items.sort(key=lambda timeline: (timeline["planned_start"], timeline["item"].name.casefold()))
    actual_items = [timeline for timeline in scheduled_items if timeline["actual_start"] is not None]
    return {
        "group": group,
        "items": scheduled_items,
        "planned_start": min(timeline["planned_start"] for timeline in scheduled_items),
        "planned_end": max(timeline["planned_end"] for timeline in scheduled_items),
        "actual_start": min((timeline["actual_start"] for timeline in actual_items), default=None),
        "actual_end": max((timeline["actual_end"] for timeline in actual_items), default=None),
    }


def gantt_timeline_for_type(progress_type, entries_by_item_id=None):
    """Build Gantt-ready groups and excluded items from already-loaded model data."""
    entries_by_item_id = entries_by_item_id or {}
    groups, excluded_items = [], []
    for group in progress_type.groups:
        item_timelines = [
            item_gantt_timeline(item, entries_by_item_id.get(item.id, ()))
            for item in group.items
        ]
        excluded_items.extend(
            timeline["item"] for timeline in item_timelines if timeline["planned_start"] is None
        )
        timeline = group_gantt_timeline(group, item_timelines)
        if timeline is not None:
            groups.append(timeline)
    groups.sort(key=lambda timeline: (timeline["planned_start"], timeline["group"].name.casefold()))
    return {"groups": groups, "excluded_items": excluded_items}


def type_progress_summary(progress_type, entries_by_item_id=None, *, today=None):
    """Derive one type's dashboard summary from already-loaded model data."""
    today = today or local_today()
    entries_by_item_id = entries_by_item_id or {}
    timeline = gantt_timeline_for_type(progress_type, entries_by_item_id)
    scheduled_groups = timeline["groups"]
    planned_start = min((group["planned_start"] for group in scheduled_groups), default=None)
    planned_end = max((group["planned_end"] for group in scheduled_groups), default=None)
    percent = type_percent(progress_type)
    scheduled_items = [item for group in scheduled_groups for item in group["items"]]
    overdue_items = sum(
        1
        for item in scheduled_items
        if item["planned_end"] < today and item["percent"] is not None and item["percent"] < 100
    )
    entry_dates = [
        entry.report_date if hasattr(entry, "report_date") else entry
        for group in progress_type.groups
        for item in group.items
        for entry in entries_by_item_id.get(item.id, ())
    ]
    if percent is None or not scheduled_groups:
        status = "not_started"
    elif percent >= 100:
        status = "done"
    elif planned_end < today and percent < 100:
        status = "overdue"
    elif planned_start <= today:
        status = "in_progress"
    else:
        status = "not_started"
    return {
        "progress_type": progress_type,
        "percent": percent,
        "planned_start": planned_start,
        "planned_end": planned_end,
        "days": (planned_end - planned_start).days + 1 if planned_start is not None else None,
        "status": status,
        "overdue_items": overdue_items,
        "undated_items": len(timeline["excluded_items"]),
        "last_entry_date": max(entry_dates, default=None),
    }


def gantt_axis_for_dates(first_date, last_date, *, today=None):
    """Return an outward-rounded Gantt axis and Vietnamese-calendar tick dates."""
    today = today or local_today()
    first_date, last_date = min(first_date, today), max(last_date, today)
    span_days = (last_date - first_date).days + 1
    if span_days <= 31:
        unit, axis_start, axis_end = "day", first_date, last_date
    elif span_days <= 26 * 7:
        unit = "week"
        axis_start = first_date - timedelta(days=first_date.weekday())
        axis_end = last_date + timedelta(days=6 - last_date.weekday())
    else:
        unit = "month"
        axis_start = first_date.replace(day=1)
        axis_end = last_date.replace(day=monthrange(last_date.year, last_date.month)[1])
    total_days = max((axis_end - axis_start).days, 1)
    ticks, tick_date = [], axis_start
    while tick_date <= axis_end:
        ticks.append({"date": tick_date, "left": (tick_date - axis_start).days / total_days * 100})
        if unit == "day":
            tick_date += timedelta(days=1)
        elif unit == "week":
            tick_date += timedelta(days=7)
        elif tick_date.month == 12:
            tick_date = tick_date.replace(year=tick_date.year + 1, month=1, day=1)
        else:
            tick_date = tick_date.replace(month=tick_date.month + 1, day=1)
    return {"start": axis_start, "end": axis_end, "unit": unit, "ticks": ticks, "total_days": total_days}


def _gantt_bar(start, end, axis, *, is_point=False):
    if start is None:
        return None
    return {
        "start": start,
        "end": end,
        "left": (start - axis["start"]).days / axis["total_days"] * 100,
        "width": (end - start).days / axis["total_days"] * 100,
        "is_point": is_point,
        "is_single_day": start == end,
    }


def gantt_chart_for_type(progress_type, entries_by_item_id=None, *, today=None):
    """Enrich a pure type timeline with axis-relative CSS bar positions."""
    today = today or local_today()
    timeline = gantt_timeline_for_type(progress_type, entries_by_item_id)
    dates = [
        value
        for group in timeline["groups"]
        for value in (group["planned_start"], group["planned_end"], group["actual_start"], group["actual_end"])
        if value is not None
    ]
    if not dates:
        return {**timeline, "axis": None, "today_left": None}
    axis = gantt_axis_for_dates(min(dates), max(dates), today=today)
    for group in timeline["groups"]:
        group["planned_bar"] = _gantt_bar(group["planned_start"], group["planned_end"], axis)
        group["actual_bar"] = _gantt_bar(group["actual_start"], group["actual_end"], axis)
        for item in group["items"]:
            item["planned_bar"] = _gantt_bar(item["planned_start"], item["planned_end"], axis)
            item["actual_bar"] = _gantt_bar(
                item["actual_start"],
                item["actual_end"],
                axis,
                is_point=item["actual_is_point"],
            )
            item["is_overdue"] = item["planned_end"] < today and (item["percent"] is None or item["percent"] < 100)
    return {
        **timeline,
        "axis": axis,
        "today_left": (today - axis["start"]).days / axis["total_days"] * 100,
    }


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


def progress_entries_page(*, project, progress_type, date_from=None, date_to=None, group_id=None, page=1, per_page=20):
    """Fetch one SQL-paginated page of entries scoped to one progress type."""
    query = ProgressEntry.query.join(ProgressItem).join(ProgressGroup).filter(
        ProgressEntry.project_id == project.id,
        ProgressItem.project_id == project.id,
        ProgressGroup.project_id == project.id,
        ProgressGroup.progress_type_id == progress_type.id,
    )
    if date_from is not None:
        query = query.filter(ProgressEntry.report_date >= date_from)
    if date_to is not None:
        query = query.filter(ProgressEntry.report_date <= date_to)
    if group_id is not None:
        query = query.filter(ProgressGroup.id == group_id)
    total = query.order_by(None).count()
    entries = query.options(
        joinedload(ProgressEntry.progress_item).joinedload(ProgressItem.progress_group),
        joinedload(ProgressEntry.created_by),
    ).order_by(ProgressEntry.report_date.desc(), ProgressEntry.id.desc()).offset((page - 1) * per_page).limit(per_page).all()
    return entries, total


def recalculate_item_completed(item):
    if db.engine.dialect.name == "postgresql":
        item = ProgressItem.query.filter_by(id=item.id).with_for_update().one()
    total = db.session.query(func.coalesce(func.sum(ProgressEntry.quantity), 0)).filter_by(progress_item_id=item.id).scalar()
    item.completed_quantity = Decimal(item.opening_quantity or 0) + Decimal(total or 0)
    return item


def _entry_values(entry):
    return {"report_date": entry.report_date.isoformat(), "quantity": str(entry.quantity), "note": entry.note, "created_by": _user_values(entry.created_by)}


def _report_date(value):
    result = parse_iso_date(value, field_label="Ngày", allow_empty=False) if isinstance(value, str) else value
    if result > local_today():
        raise FutureDateError("Không thể tạo phiếu cho ngày trong tương lai.")
    return result


def _number_example(decimal_places):
    return {0: "1.280", 1: "1.280,3", 2: "1.280,34", 3: "1.280,345"}[decimal_places]


def parse_vietnamese_number(value, decimal_places):
    """Parse a human-entered number without relying on the host locale."""
    if isinstance(value, Decimal):
        return value
    text = "".join(str(value).replace("\u00a0", " ").split())
    if not text:
        raise InvalidNumberFormatError(
            f"Định dạng số không hợp lệ. Ví dụ với độ chính xác này: {_number_example(decimal_places)}."
        )
    sign, body = (text[:1], text[1:]) if text[:1] in {"+", "-"} else ("", text)
    if not body or any(character not in "0123456789.," for character in body):
        raise InvalidNumberFormatError(
            f"Định dạng số không hợp lệ. Ví dụ với độ chính xác này: {_number_example(decimal_places)}."
        )
    dots, commas = body.count("."), body.count(",")
    if dots and commas:
        decimal_separator = "." if body.rfind(".") > body.rfind(",") else ","
        thousand_separator = "," if decimal_separator == "." else "."
        normalized = body.replace(thousand_separator, "").replace(decimal_separator, ".")
    elif dots or commas:
        separator = "." if dots else ","
        occurrences = dots or commas
        if occurrences > 1:
            normalized = body.replace(separator, "")
        else:
            fraction = body.split(separator, 1)[1]
            if len(fraction) == 3:
                if decimal_places == 3:
                    raise InvalidNumberFormatError(
                        f"'{body}' có thể là 1000 hoặc 1,000. Hãy viết lại rõ ràng; ví dụ: {_number_example(decimal_places)}."
                    )
                normalized = body.replace(separator, "")
            else:
                normalized = body.replace(separator, ".")
    else:
        normalized = body
    try:
        return Decimal(sign + normalized)
    except Exception as exc:
        raise InvalidNumberFormatError(
            f"Định dạng số không hợp lệ. Ví dụ với độ chính xác này: {_number_example(decimal_places)}."
        ) from exc


def _quantity(value, decimal_places):
    try:
        value = parse_vietnamese_number(value, decimal_places)
    except InvalidNumberFormatError:
        raise
    if value <= 0:
        raise InvalidQuantityError("Khối lượng phải lớn hơn 0.")
    return value


def _nonnegative_quantity(value, decimal_places):
    try:
        result = parse_vietnamese_number(value, decimal_places)
    except InvalidNumberFormatError:
        raise
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
    report_date, quantity = _report_date(report_date), _quantity(quantity, item.decimal_places)
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


def create_entries_batch(*, progress_type, report_date, rows, actor_id=None):
    """Create daily entries only after every submitted row has passed validation."""
    try:
        report_date = _report_date(report_date)
    except ValueError as exc:
        raise BatchValidationError(form_errors={"report_date": str(exc)}) from exc
    prepared, seen_item_ids = [], set()
    for position, raw in enumerate(rows, start=1):
        item_id = (raw.get("item_id") or "").strip()
        group_id = (raw.get("group_id") or "").strip()
        quantity = (raw.get("quantity") or "").strip()
        note = (raw.get("note") or "").strip()
        if not any((item_id, group_id, quantity, note)):
            continue
        if not item_id:
            raise _batch_row_error(position, "item_id", "Cần chọn hạng mục.")
        try:
            item_id = int(item_id)
        except (TypeError, ValueError) as exc:
            raise BatchItemNotFoundError("Hạng mục không thuộc loại tiến độ này.") from exc
        item = ProgressItem.query.join(ProgressGroup).filter(
            ProgressItem.id == item_id,
            ProgressItem.project_id == progress_type.project_id,
            ProgressGroup.progress_type_id == progress_type.id,
        ).first()
        if item is None:
            raise BatchItemNotFoundError("Hạng mục không thuộc loại tiến độ này.")
        if item.id in seen_item_ids:
            raise _batch_row_error(position, "item_id", f"Hạng mục '{item.name}' bị trùng trong lượt tạo phiếu.")
        seen_item_ids.add(item.id)
        try:
            quantity_value = _quantity(quantity, item.decimal_places)
            _validate_decimal_precision(quantity_value, item.decimal_places, "Khối lượng")
        except ValueError as exc:
            raise _batch_row_error(position, "quantity", str(exc)) from exc
        if ProgressEntry.query.filter_by(progress_item_id=item.id, report_date=report_date).first() is not None:
            raise _batch_row_error(position, "item_id", f"Hạng mục '{item.name}' đã có phiếu ngày {report_date:%d/%m/%Y}.")
        prepared.append({"item": item, "quantity": quantity_value, "note": note})

    try:
        with db.session.begin_nested():
            for row in prepared:
                create_entry(item=row["item"], report_date=report_date, quantity=row["quantity"], note=row["note"], actor_id=actor_id)
    except DuplicateEntryError as exc:
        raise BatchValidationError(str(exc)) from exc
    return prepared


def update_entry(entry, *, report_date, quantity, note=None, actor_id=None):
    old_values = _entry_values(entry)
    report_date, quantity = _report_date(report_date), _quantity(quantity, entry.progress_item.decimal_places)
    _validate_decimal_precision(quantity, entry.progress_item.decimal_places, "Khối lượng")
    entry.report_date, entry.quantity, entry.note, entry.updated_by_id = report_date, quantity, (note or "").strip() or None, actor_id
    try:
        with db.session.begin_nested():
            db.session.flush()
    except IntegrityError as exc:
        raise DuplicateEntryError(f"Ngày {report_date:%d/%m/%Y} đã có phiếu cho hạng mục này. Hãy mở phiếu đó để sửa.") from exc
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


def create_item(*, group, name, unit, planned_quantity=0, opening_quantity=0, planned_start_date=None, planned_end_date=None, actual_start_date=None, decimal_places=0, assignee_user_id=None, note=None, display_order=0, actor_id=None):
    decimal_places = 0 if group.progress_type.value_mode == "money" else _decimal_places(decimal_places)
    planned, opening = _nonnegative_quantity(planned_quantity, decimal_places), _nonnegative_quantity(opening_quantity, decimal_places)
    _validate_decimal_precision(planned, decimal_places, "Khối lượng kế hoạch")
    _validate_decimal_precision(opening, decimal_places, "Khối lượng mang sang")
    value = ProgressItem(project_id=group.project_id, progress_group_id=group.id, name=name.strip(), unit="VNĐ" if group.progress_type.value_mode == "money" else unit.strip(), decimal_places=decimal_places, planned_quantity=planned, opening_quantity=opening, planned_start_date=planned_start_date, planned_end_date=planned_end_date, actual_start_date=actual_start_date, assignee_user_id=assignee_user_id, note=(note or "").strip() or None, display_order=display_order, created_by_id=actor_id, updated_by_id=actor_id)
    db.session.add(value); db.session.flush(); recalculate_item_completed(value); log_audit("construction_progress.item.create", "ProgressItem", value.id, new_values={"name": value.name}); return value


class ItemDateValidationError(ValueError):
    def __init__(self, field, message):
        self.field = field
        super().__init__(message)


def _item_schedule_dates(values):
    """Parse and validate the three Gantt dates for both group-batch writers."""
    dates = {}
    for field, label in (
        ("planned_start_date", "Ngày bắt đầu kế hoạch"),
        ("planned_end_date", "Ngày kết thúc kế hoạch"),
        ("actual_start_date", "Ngày bắt đầu thực tế"),
    ):
        try:
            dates[field] = parse_iso_date(values[field], field_label=label)
        except ValueError as exc:
            raise ItemDateValidationError(field, str(exc)) from exc
    if (dates["planned_start_date"] is None) != (dates["planned_end_date"] is None):
        raise ItemDateValidationError(
            "planned_start_date",
            "Cần khai cả ngày bắt đầu và ngày kết thúc kế hoạch, hoặc để trống cả hai.",
        )
    if dates["planned_start_date"] and dates["planned_start_date"] > dates["planned_end_date"]:
        raise ItemDateValidationError(
            "planned_start_date",
            "Ngày bắt đầu kế hoạch không được sau ngày kết thúc kế hoạch.",
        )
    if dates["actual_start_date"] and dates["actual_start_date"] > local_today():
        raise ItemDateValidationError(
            "actual_start_date",
            "Ngày bắt đầu thực tế không được sau hôm nay.",
        )
    return dates


def _batch_item_rows(group, rows):
    """Validate an overlay payload before any of its changes are written."""
    existing = {item.id: item for item in group.items}
    prepared, submitted_ids, deleting_ids = [], set(), set()
    for position, raw in enumerate(rows, start=1):
        item_id = raw.get("id")
        if item_id:
            try:
                item_id = int(item_id)
            except (TypeError, ValueError) as exc:
                raise _batch_row_error(position, "id", "Hạng mục không hợp lệ.") from exc
            item = existing.get(item_id)
            if item is None:
                raise BatchItemNotFoundError("Hạng mục không thuộc khu vực này.")
            if item_id in submitted_ids:
                raise _batch_row_error(position, "id", "Hạng mục bị lặp trong biểu mẫu.")
            submitted_ids.add(item_id)
        else:
            item = None

        deleting = str(raw.get("delete", "")).lower() in {"1", "true", "on", "yes"}
        values = {
            "name": (raw.get("name") or "").strip(),
            "unit": (raw.get("unit") or "").strip(),
            "decimal_places": raw.get("decimal_places", "0"),
            "planned_quantity": raw.get("planned_quantity", "0"),
            "opening_quantity": raw.get("opening_quantity", "0"),
            "planned_start_date": raw.get("planned_start_date", ""),
            "planned_end_date": raw.get("planned_end_date", ""),
            "actual_start_date": raw.get("actual_start_date", ""),
        }
        if deleting:
            if item is None:
                raise _batch_row_error(position, "delete", "Chỉ có thể xoá hạng mục đã tồn tại.")
            deleting_ids.add(item.id)
            prepared.append({"position": position, "item": item, "delete": True, **values})
            continue
        if item is None and not values["name"] and not values["unit"] and str(values["planned_quantity"]).strip() in {"", "0", "0.0", "0.00", "0.000"} and str(values["opening_quantity"]).strip() in {"", "0", "0.0", "0.00", "0.000"} and not any(values[field] for field in ("planned_start_date", "planned_end_date", "actual_start_date")):
            continue
        if not values["name"]:
            raise _batch_row_error(position, "name", "Cần nhập tên hạng mục.")
        if group.progress_type.value_mode != "money" and not values["unit"]:
            raise _batch_row_error(position, "unit", "Cần nhập đơn vị.")
        try:
            decimal_places = 0 if group.progress_type.value_mode == "money" else _decimal_places(values["decimal_places"])
        except ValueError as exc:
            raise _batch_row_error(position, "decimal_places", str(exc)) from exc
        try:
            planned = _nonnegative_quantity(values["planned_quantity"], decimal_places)
            _validate_decimal_precision(planned, decimal_places, "Khối lượng kế hoạch")
        except ValueError as exc:
            raise _batch_row_error(position, "planned_quantity", str(exc)) from exc
        try:
            opening = _nonnegative_quantity(values["opening_quantity"], decimal_places)
            _validate_decimal_precision(opening, decimal_places, "Khối lượng mang sang")
        except ValueError as exc:
            raise _batch_row_error(position, "opening_quantity", str(exc)) from exc
        try:
            dates = _item_schedule_dates(values)
        except ItemDateValidationError as exc:
            raise _batch_row_error(position, exc.field, str(exc)) from exc
        if item is not None:
            try:
                _validate_existing_item_precision(item, decimal_places)
            except ValueError as exc:
                raise _batch_row_error(position, "decimal_places", str(exc)) from exc
        prepared.append({
            "position": position, "item": item, "delete": False, "name": values["name"],
            "unit": values["unit"], "decimal_places": decimal_places,
            "planned_quantity": planned, "opening_quantity": opening,
            **dates,
        })

    final_names = {}
    for item in group.items:
        if item.id not in submitted_ids:
            final_names[item.name.casefold()] = item.id
    for row in prepared:
        if row["delete"]:
            continue
        key = row["name"].casefold()
        if key in final_names:
            raise _batch_row_error(row["position"], "name", f"Tên hạng mục '{row['name']}' bị trùng trong khu vực.")
        final_names[key] = row["item"].id if row["item"] is not None else None
    return prepared, deleting_ids


def create_group_batch(*, progress_type, name, rows, actor_id=None):
    name = (name or "").strip()
    if not name:
        raise BatchValidationError(form_errors={"name": "Cần nhập tên khu vực."})
    if ProgressGroup.query.filter_by(progress_type_id=progress_type.id, name=name).first() is not None:
        raise BatchValidationError(form_errors={"name": "Tên khu vực đã tồn tại trong loại tiến độ này."})
    temporary_group = type("BatchGroup", (), {"items": [], "progress_type": progress_type})()
    prepared, _ = _batch_item_rows(temporary_group, rows)
    try:
        with db.session.begin_nested():
            group = create_group(progress_type=progress_type, name=name, actor_id=actor_id)
            for row in prepared:
                create_item(group=group, name=row["name"], unit=row["unit"], decimal_places=row["decimal_places"], planned_quantity=row["planned_quantity"], opening_quantity=row["opening_quantity"], planned_start_date=row["planned_start_date"], planned_end_date=row["planned_end_date"], actual_start_date=row["actual_start_date"], actor_id=actor_id)
    except IntegrityError as exc:
        raise BatchValidationError("Tên khu vực hoặc hạng mục đã tồn tại.") from exc
    return group


def update_group_batch(*, group, name, rows, confirm_deletions=False, actor_id=None):
    name = (name or "").strip()
    if not name:
        raise BatchValidationError(form_errors={"name": "Cần nhập tên khu vực."})
    duplicate_group = ProgressGroup.query.filter(
        ProgressGroup.progress_type_id == group.progress_type_id,
        ProgressGroup.name == name,
        ProgressGroup.id != group.id,
    ).first()
    if duplicate_group is not None:
        raise BatchValidationError(form_errors={"name": "Tên khu vực đã tồn tại trong loại tiến độ này."})
    prepared, deleting_ids = _batch_item_rows(group, rows)
    if deleting_ids and not confirm_deletions:
        raise BatchValidationError(form_errors={"confirm_deletions": "Hãy xác nhận việc xoá các hạng mục đã đánh dấu."})
    try:
        with db.session.begin_nested():
            update_group(group, name=name, actor_id=actor_id)
            for row in prepared:
                if row["delete"]:
                    _delete_item_without_confirmation(row["item"])
                elif row["item"] is None:
                    create_item(group=group, name=row["name"], unit=row["unit"], decimal_places=row["decimal_places"], planned_quantity=row["planned_quantity"], opening_quantity=row["opening_quantity"], planned_start_date=row["planned_start_date"], planned_end_date=row["planned_end_date"], actual_start_date=row["actual_start_date"], actor_id=actor_id)
                else:
                    update_item(row["item"], name=row["name"], unit=row["unit"], decimal_places=row["decimal_places"], planned_quantity=row["planned_quantity"], opening_quantity=row["opening_quantity"], planned_start_date=row["planned_start_date"], planned_end_date=row["planned_end_date"], actual_start_date=row["actual_start_date"], actor_id=actor_id)
    except IntegrityError as exc:
        raise BatchValidationError("Tên khu vực hoặc hạng mục đã tồn tại.") from exc
    return group


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


def _delete_item_without_confirmation(item):
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
    log_audit("construction_progress.item.delete", "ProgressItem", item.id, old_values=old_values)
    db.session.flush()
    for entry in item.entries:
        db.session.delete(entry)
    db.session.flush()
    db.session.delete(item)
    db.session.flush()
    return old_values["counts"]


def delete_item(item, *, confirm_name, actor_id=None):
    _confirm_structure_delete(item.name, confirm_name)
    with db.session.begin_nested():
        return _delete_item_without_confirmation(item)


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


def update_item(item, *, name, unit, planned_quantity, opening_quantity, planned_start_date=_UNSET, planned_end_date=_UNSET, actual_start_date=_UNSET, decimal_places=0, assignee_user_id=None, note=None, display_order=0, actor_id=None):
    decimal_places = 0 if item.progress_group.progress_type.value_mode == "money" else _decimal_places(decimal_places)
    planned, opening = _nonnegative_quantity(planned_quantity, decimal_places), _nonnegative_quantity(opening_quantity, decimal_places)
    _validate_decimal_precision(planned, decimal_places, "Khối lượng kế hoạch")
    _validate_decimal_precision(opening, decimal_places, "Khối lượng mang sang")
    _validate_existing_item_precision(item, decimal_places)
    old = {"name": item.name, "planned_quantity": str(item.planned_quantity), "opening_quantity": str(item.opening_quantity), "decimal_places": item.decimal_places, "planned_start_date": item.planned_start_date.isoformat() if item.planned_start_date else None, "planned_end_date": item.planned_end_date.isoformat() if item.planned_end_date else None, "actual_start_date": item.actual_start_date.isoformat() if item.actual_start_date else None}
    item.name, item.unit, item.decimal_places, item.planned_quantity, item.opening_quantity = name.strip(), "VNĐ" if item.progress_group.progress_type.value_mode == "money" else unit.strip(), decimal_places, planned, opening
    if planned_start_date is not _UNSET:
        item.planned_start_date = planned_start_date
    if planned_end_date is not _UNSET:
        item.planned_end_date = planned_end_date
    if actual_start_date is not _UNSET:
        item.actual_start_date = actual_start_date
    item.assignee_user_id, item.note, item.display_order, item.updated_by_id = assignee_user_id, (note or "").strip() or None, display_order, actor_id
    recalculate_item_completed(item)
    log_audit("construction_progress.item.update", "ProgressItem", item.id, old_values=old, new_values={"name": item.name, "planned_quantity": str(item.planned_quantity), "opening_quantity": str(item.opening_quantity), "decimal_places": item.decimal_places, "planned_start_date": item.planned_start_date.isoformat() if item.planned_start_date else None, "planned_end_date": item.planned_end_date.isoformat() if item.planned_end_date else None, "actual_start_date": item.actual_start_date.isoformat() if item.actual_start_date else None})
    return item
