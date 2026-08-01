import inspect
from datetime import date

from app import register_auth_guard
from app.auth.permissions import can_edit_progress_entry, can_view_project_progress
from app.extensions import db
from app.models import ProgressEntry, ProgressGroup, ProgressItem, ProgressType, User
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


def _login(client, username):
    return client.post("/login", data={"username_or_email": username, "password": "password123"})


def _type_for_project(project_id):
    value = ProgressType(project_id=project_id, name=f"Loại {project_id}", created_by_id=1)
    db.session.add(value)
    db.session.commit()
    return value


def test_progress_routes_enforce_read_structure_and_project_scope(client, app):
    with app.app_context():
        first = _type_for_project(1)
        second = _type_for_project(2)
        first_id, second_id = first.id, second.id

    assert client.get("/projects/1/progress").status_code == 302
    _login(client, "reporter")
    assert client.get("/projects/1/progress").status_code == 200
    assert client.post("/projects/1/progress/types", data={"name": "Không được tạo"}).status_code == 403
    assert client.get(f"/projects/1/progress/types/{second_id}").status_code == 404

    client.post("/logout")
    _login(client, "pm")
    response = client.post("/projects/1/progress/types", data={"name": "Được tạo"})
    assert response.status_code == 201
    assert client.post(f"/projects/1/progress/types/{first_id}/groups", data={"name": "Khu vực"}).status_code == 201


def test_progress_entry_creator_cannot_edit_another_users_entry(client, app):
    with app.app_context():
        progress_type = _type_for_project(1)
        group = ProgressGroup(project_id=1, progress_type_id=progress_type.id, name="Khu vực", created_by_id=1)
        db.session.add(group)
        db.session.flush()
        item = ProgressItem(project_id=1, progress_group_id=group.id, name="Hạng mục", unit="m", planned_quantity=10, created_by_id=1)
        db.session.add(item)
        db.session.flush()
        entry = ProgressEntry(project_id=1, progress_item_id=item.id, report_date=date(2026, 1, 1), quantity=1, created_by_id=5)
        db.session.add(entry)
        db.session.flush()
        entry_id = entry.id
        db.session.commit()

    _login(client, "reporter")
    assert client.post(f"/projects/1/progress/entries/{entry_id}/edit", data={"report_date": "2026-01-01", "quantity": "2"}).status_code == 403
