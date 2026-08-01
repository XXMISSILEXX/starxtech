import inspect
from datetime import date

from app import register_auth_guard
from app.auth.permissions import can_edit_progress_entry, can_view_project_progress
from app.models import ProgressEntry, User
from app.permissions.registry import DEFAULTS, PERMISSIONS
from app.project_memberships import CAPABILITY_FIELDS, PROJECT_ROLE_PRESETS, READ_CAPABILITIES


PROGRESS_PERMISSION_CODES = {
    "construction_progress.view",
    "construction_progress.create",
    "construction_progress.edit",
    "construction_progress.edit_all",
    "construction_progress.delete",
    "construction_progress.structure",
}


def test_construction_progress_permissions_have_safe_default_grants():
    permission_codes = {permission["code"] for permission in PERMISSIONS}

    assert PROGRESS_PERMISSION_CODES <= permission_codes
    assert PROGRESS_PERMISSION_CODES <= DEFAULTS["ADMIN"]
    assert "construction_progress.view" in DEFAULTS["VIEWER_ADMIN"]
    assert not (PROGRESS_PERMISSION_CODES - {"construction_progress.view"}) & DEFAULTS["VIEWER_ADMIN"]


def test_progress_capabilities_and_presets_match_the_specification():
    progress_capabilities = {
        "can_view_progress",
        "can_create_progress_entries",
        "can_edit_all_progress_entries",
        "can_manage_progress_structure",
    }

    assert progress_capabilities <= set(CAPABILITY_FIELDS)
    assert "can_view_progress" in READ_CAPABILITIES
    assert progress_capabilities & PROJECT_ROLE_PRESETS["PROJECT_VIEWER"] == {"can_view_progress"}
    assert progress_capabilities & PROJECT_ROLE_PRESETS["PROJECT_REPORTER"] == {
        "can_view_progress", "can_create_progress_entries"
    }
    assert progress_capabilities & PROJECT_ROLE_PRESETS["PROJECT_EDITOR"] == {
        "can_view_progress", "can_create_progress_entries", "can_edit_all_progress_entries"
    }
    assert progress_capabilities & PROJECT_ROLE_PRESETS["PROJECT_DOCUMENT_CONTROLLER"] == {"can_view_progress"}
    assert progress_capabilities & PROJECT_ROLE_PRESETS["PROJECT_ISSUE_COORDINATOR"] == {"can_view_progress"}
    assert progress_capabilities <= PROJECT_ROLE_PRESETS["PROJECT_OWNER"]


def test_construction_progress_endpoint_prefix_is_in_reports_module_gate():
    assert '"construction_progress."' in inspect.getsource(register_auth_guard)


def test_progress_entry_owner_or_editor_may_edit(app):
    with app.app_context():
        reporter = User.query.filter_by(username="reporter").one()
        owner = User.query.filter_by(username="pm").one()
        entry = ProgressEntry(project_id=1, progress_item_id=1, report_date=date(2026, 8, 1), quantity=1, created_by_id=reporter.id)

        assert can_view_project_progress(1, reporter)
        assert can_edit_progress_entry(entry, reporter)
        assert can_edit_progress_entry(entry, owner)
