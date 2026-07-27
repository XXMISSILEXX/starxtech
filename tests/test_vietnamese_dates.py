from datetime import date

import pytest

from app.date_utils import format_vn_date, parse_iso_date


def test_native_date_parser_is_strict_and_readonly_values_remain_vietnamese():
    assert parse_iso_date("2026-08-07") == date(2026, 8, 7)
    assert format_vn_date(date(2026, 7, 27)) == "27/07/2026"
    for value in ("31/02/2026", "07/08/2026", "2026/08/07", "text"):
        with pytest.raises(ValueError):
            parse_iso_date(value, allow_empty=False)
