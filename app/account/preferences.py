"""Validation and persistence for a user's personal interface preferences."""

from collections.abc import Mapping

from app.models.user import DEFAULT_UI_PREFERENCES

APPEARANCE_OPTIONS = ("system", "light", "dark")
ACCENT_OPTIONS = ("blue", "green", "purple", "orange")


def normalized_ui_preferences(value) -> dict[str, str]:
    """Return a safe, complete preference object for a database or request value."""
    source = value if isinstance(value, Mapping) else {}
    appearance = source.get("appearance")
    accent = source.get("accent")
    return {
        "appearance": appearance if appearance in APPEARANCE_OPTIONS else DEFAULT_UI_PREFERENCES["appearance"],
        "accent": accent if accent in ACCENT_OPTIONS else DEFAULT_UI_PREFERENCES["accent"],
    }


def validate_ui_preferences(appearance, accent) -> tuple[dict[str, str] | None, dict[str, str]]:
    errors = {}
    if appearance not in APPEARANCE_OPTIONS:
        errors["appearance"] = "Giao diện không hợp lệ."
    if accent not in ACCENT_OPTIONS:
        errors["accent"] = "Màu nhấn không hợp lệ."
    if errors:
        return None, errors
    return {"appearance": appearance, "accent": accent}, {}
