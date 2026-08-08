from datetime import date, datetime, timedelta, timezone

import pytest

from app.date_utils import APP_TIMEZONE, format_vn_date, parse_iso_date, utc_to_vietnam_time


def test_native_date_parser_is_strict_and_readonly_values_remain_vietnamese():
    assert parse_iso_date("2026-08-07") == date(2026, 8, 7)
    assert format_vn_date(date(2026, 7, 27)) == "27/07/2026"
    for value in ("31/02/2026", "07/08/2026", "2026/08/07", "text"):
        with pytest.raises(ValueError):
            parse_iso_date(value, allow_empty=False)


def test_utc_to_vietnam_time_handles_empty_naive_and_aware_values():
    assert utc_to_vietnam_time(None) is None

    naive_utc = datetime(2026, 8, 6, 14, 38)
    assert utc_to_vietnam_time(naive_utc) == datetime(2026, 8, 6, 21, 38, tzinfo=APP_TIMEZONE)

    aware_value = datetime(2026, 8, 6, 16, 38, tzinfo=timezone(timedelta(hours=2)))
    assert utc_to_vietnam_time(aware_value) == datetime(2026, 8, 6, 21, 38, tzinfo=APP_TIMEZONE)
