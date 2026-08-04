from decimal import Decimal

import pytest

from app.ui import vn_number


@pytest.mark.parametrize(
    ("value", "places", "expected"),
    [
        (None, 0, "—"),
        (0, 0, "0"),
        (1000, 0, "1.000"),
        (Decimal("1234.5"), 1, "1.234,5"),
        (Decimal("937"), 2, "937,00"),
        (Decimal("1.234"), 3, "1,234"),
        (Decimal("33.33333333333333333333333333"), 1, "33,3"),
        (Decimal("-1234.5"), 1, "-1.234,5"),
    ],
)
def test_vn_number_formats_none_thousands_and_decimal_places(value, places, expected):
    assert vn_number(value, places=places) == expected
