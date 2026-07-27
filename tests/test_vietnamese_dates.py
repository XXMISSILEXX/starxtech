from datetime import date

import pytest

from app.date_utils import format_vn_date, parse_vn_date


def test_vietnamese_date_parser_is_strict_and_does_not_swap_day_month():
    assert parse_vn_date("07/08/2026") == date(2026, 8, 7)
    assert format_vn_date(date(2026, 7, 27)) == "27/07/2026"
    for value in ("31/02/2026", "00/07/2026", "07/08/26", "text"):
        with pytest.raises(ValueError):
            parse_vn_date(value, allow_iso=False)


def test_vietnamese_date_parser_keeps_iso_for_technical_backwards_compatibility():
    assert parse_vn_date("2026-07-27") == date(2026, 7, 27)
