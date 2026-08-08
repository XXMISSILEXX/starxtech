"""Date helpers shared by HTML forms, APIs, and readable UI values."""

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo


VN_DATE_FORMAT = "%d/%m/%Y"
APP_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")


def utc_to_vietnam_time(value):
    """Convert a UTC datetime, naive or aware, to Vietnam time.

    Naive values are treated as UTC because they are persisted that way by the
    login flow.  ``None`` stays ``None`` so templates can retain their normal
    empty-value presentation.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(APP_TIMEZONE)


def format_vn_date(value):
    """Return a DD/MM/YYYY value for read-only Vietnamese UI text."""
    if not value:
        return ""
    if isinstance(value, str):
        value = value.strip()
        try:
            value = date.fromisoformat(value)
        except ValueError:
            return value
    return value.strftime(VN_DATE_FORMAT)


def local_today():
    """Today's calendar date in the application's Vietnamese timezone."""
    return datetime.now(APP_TIMEZONE).date()


def parse_iso_date(value, *, field_label="Ngày", allow_empty=True):
    """Parse the native HTML ``input[type=date]`` ISO contract."""
    value = (value or "").strip()
    if not value:
        if allow_empty:
            return None
        raise ValueError(f"Vui lòng nhập {field_label.lower()}.")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_label} phải theo định dạng YYYY-MM-DD.") from exc
