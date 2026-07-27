"""Strict, locale-independent dates for HTML forms.

Database values and API contracts remain ISO dates.  This module is only for
human-facing form input and display, which is consistently DD/MM/YYYY.
"""

from datetime import date, datetime
import re


VN_DATE_FORMAT = "%d/%m/%Y"
_VN_DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")


def format_vn_date(value):
    """Return a date suitable for a visible Vietnamese form field."""
    if not value:
        return ""
    if isinstance(value, str):
        value = value.strip()
        if _VN_DATE_RE.fullmatch(value):
            return value
        try:
            value = date.fromisoformat(value)
        except ValueError:
            return value
    return value.strftime(VN_DATE_FORMAT)


def parse_vn_date(value, *, field_label="Ngày", allow_empty=True, allow_iso=True):
    """Parse DD/MM/YYYY; ISO remains accepted for compatible non-UI callers."""
    value = (value or "").strip()
    if not value:
        if allow_empty:
            return None
        raise ValueError(f"Vui lòng nhập {field_label.lower()}.")
    if not _VN_DATE_RE.fullmatch(value):
        if allow_iso:
            try:
                return date.fromisoformat(value)
            except ValueError:
                pass
        raise ValueError(f"{field_label} phải theo định dạng DD/MM/YYYY.")
    try:
        return datetime.strptime(value, VN_DATE_FORMAT).date()
    except ValueError as exc:
        raise ValueError(f"{field_label} không hợp lệ.") from exc
