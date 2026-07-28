"""Safe rendering primitives for spreadsheet-oriented CSV exports."""


_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
# Tabs and carriage returns are themselves dangerous prefixes, so retain them
# for the prefix test while ignoring other leading whitespace/control chars.
_LEADING_IGNORED = " \n\v\f"


def safe_csv_cell(value):
    """Return a CSV cell that spreadsheets render as text when required.

    This only changes the export representation.  It never writes back to the
    source model and leaves numeric values untouched for normal CSV consumers.
    """
    if not isinstance(value, str):
        return value
    candidate = value.lstrip(_LEADING_IGNORED)
    return "'" + value if candidate.startswith(_FORMULA_PREFIXES) else value
