from datetime import date

import pytest
from werkzeug.security import generate_password_hash

from app.auth.permissions import can_edit_progress_entry, can_view_project_progress
from app.extensions import db
from app.models import ProgressEntry, ProgressGroup, ProgressItem, ProgressType, ProjectUser, Role, User
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


def test_construction_progress_module_gate_rejects_user_without_reports_access(client, app):
    with app.app_context():
        role = Role.query.filter_by(code="REPORTER").one()
        user = User(id=99, username="no-progress-module", email="no-progress-module@example.com", full_name="No Module", password_hash=generate_password_hash("password123"), role=role, legacy_role="REPORTER")
        db.session.add(user)
        db.session.commit()

    _login(client, "no-progress-module")
    assert client.get("/projects/1/progress").status_code == 403
    assert client.post("/projects/1/progress/types", data={"name": "Không được tạo"}).status_code == 403


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
    assert response.status_code == 302
    assert client.post(f"/projects/1/progress/types/{first_id}/groups", data={"name": "Khu vực"}).status_code == 302


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
        entry_id, item_id = entry.id, item.id
        db.session.commit()

    _login(client, "reporter")
    page = client.get(f"/projects/1/progress/items/{item_id}").get_data(as_text=True)
    assert "data-entry-edit" not in page
    assert "data-entry-delete" not in page
    assert client.post(f"/projects/1/progress/entries/{entry_id}/edit", data={"report_date": "2026-01-01", "quantity": "2"}).status_code == 403
    assert client.post(f"/projects/1/progress/entries/{entry_id}/delete").status_code == 403
    with app.app_context():
        assert db.session.get(ProgressEntry, entry_id).quantity == 1


def _progress_objects():
    first = _type_for_project(1)
    second = _type_for_project(2)
    group = ProgressGroup(project_id=1, progress_type_id=first.id, name="Khu vực A bí mật", created_by_id=1)
    other_group = ProgressGroup(project_id=2, progress_type_id=second.id, name="Khu vực B bí mật", created_by_id=1)
    db.session.add_all((group, other_group)); db.session.flush()
    item = ProgressItem(project_id=1, progress_group_id=group.id, name="Hạng mục A bí mật", unit="m", planned_quantity=10, created_by_id=1)
    other_item = ProgressItem(project_id=2, progress_group_id=other_group.id, name="Hạng mục B bí mật", unit="m", planned_quantity=10, created_by_id=1)
    db.session.add_all((item, other_item)); db.session.flush()
    entry = ProgressEntry(project_id=2, progress_item_id=other_item.id, report_date=date(2026, 1, 1), quantity=1, created_by_id=1)
    db.session.add(entry); db.session.commit()
    return first.id, second.id, group.id, other_group.id, item.id, other_item.id, entry.id


def test_progress_cross_project_ids_are_not_disclosed(client, app):
    with app.app_context():
        _, other_type, _, other_group, _, other_item, other_entry = _progress_objects()
    _login(client, "pm")
    responses = [
        client.get(f"/projects/1/progress/types/{other_type}"),
        client.post(f"/projects/1/progress/groups/{other_group}/edit", data={"name": "x"}),
        client.get(f"/projects/1/progress/items/{other_item}"),
        client.post(f"/projects/1/progress/entries/{other_entry}/delete"),
    ]
    for response in responses:
        assert response.status_code == 404
        assert "bí mật" not in response.get_data(as_text=True)
    chart = client.get("/projects/1/progress/types/1/chart-data")
    assert chart.status_code == 200
    assert "Loại 2" not in chart.get_data(as_text=True)


@pytest.mark.parametrize("username, expected", [
    (None, (302, 302, 302, 302, 302)),
    ("no-progress-module", (403, 403, 403, 403, 403)),
    ("outsider-progress", (403, 403, 403, 403, 403)),
    ("limited-progress", (403, 403, 403, 403, 403)),
    ("reporter", (200, 403, 200, 200, 200)),
    ("viewer", (200, 403, 200, 200, 200)),
    ("admin", (200, 302, 200, 200, 200)),
    ("super", (200, 302, 200, 200, 200)),
])
def test_progress_route_matrix(client, app, username, expected):
    with app.app_context():
        type_id, _, _, _, item_id, _, _ = _progress_objects()
        if username in {"no-progress-module", "outsider-progress", "limited-progress"}:
            role = Role.query.filter_by(code="REPORTER").one()
            user_id = {"no-progress-module": 99, "outsider-progress": 100, "limited-progress": 101}[username]
            user = User(id=user_id, username=username, email=f"{username}@example.com", full_name=username, password_hash=generate_password_hash("password123"), role=role, legacy_role="REPORTER")
            db.session.add(user); db.session.flush()
            if username != "no-progress-module":
                db.session.add(ProjectUser(id=100 if username.startswith("out") else 101, project_id=2 if username.startswith("out") else 1, user_id=user.id, can_view_reports=True, is_active=True))
            db.session.commit()
    if username:
        _login(client, username)
    with app.app_context():
        before_types = ProgressType.query.count()
        before_entries = ProgressEntry.query.count()
    results = (
        client.get("/projects/1/progress").status_code,
        client.post("/projects/1/progress/types", data={"name": f"Cấu trúc {username}"}).status_code,
        client.get(f"/projects/1/progress/types/{type_id}/chart-data").status_code,
        client.get(f"/projects/1/progress/types/{type_id}?tab=entries").status_code,
        client.get(f"/projects/1/progress/types/{type_id}?tab=gantt").status_code,
    )
    assert results == expected
    if 302 not in expected:
        with app.app_context():
            assert ProgressType.query.count() == before_types
            assert ProgressEntry.query.count() == before_entries
