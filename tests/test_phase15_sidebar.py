from html.parser import HTMLParser
from urllib.parse import urlsplit

import pytest
from flask import render_template_string
from werkzeug.security import generate_password_hash

from app.company_media.services import set_permission
from app.extensions import db
from app.models import (CompanyMediaAlbum, Permission, ProjectUser, Role,
                        RolePermission, User)
from app.navigation import get_sidebar_items


MODULES = ("reports", "partners", "project_documents", "company_media", "admin")


class _ModuleNavParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "a" and "data-module-nav-link" in attributes:
            self.hrefs.append(attributes["href"])


class _ModuleNavStateParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = {}

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "a" and "data-module-nav-link" in attributes:
            self.links[attributes["href"]] = "active" in attributes.get("class", "").split()


class _ModuleOverlayParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.cards = set()
        self.overlays = {}
        self.trigger_targets = set()
        self._overlay_stack = []
        self._current_overlay = None

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if "data-module-card" in attributes:
            self.cards.add(attributes["data-module-card"])
        if "data-module-nav-trigger" in attributes:
            self.trigger_targets.add(attributes["data-bs-target"])
        if tag == "div":
            self._overlay_stack.append(self._current_overlay)
            if "data-module-nav-overlay" in attributes:
                self._current_overlay = attributes["data-module-nav-overlay"]
                self.overlays[self._current_overlay] = []
        if tag == "a" and "data-module-nav-overlay-link" in attributes:
            self.overlays[self._current_overlay].append(attributes["href"])

    def handle_endtag(self, tag):
        if tag == "div" and self._overlay_stack:
            self._current_overlay = self._overlay_stack.pop()


@pytest.fixture
def sidebar_shell(app):
    @app.get("/test/sidebar-shell")
    def render_sidebar_shell():
        return render_template_string('{% extends "base.html" %}{% block content %}{% endblock %}')

    return "/test/sidebar-shell"


@pytest.fixture
def sidebar_users(app):
    with app.app_context():
        audit_role = Role(code="SIDEBAR_AUDIT_ONLY", name="Sidebar audit only", is_system=False)
        document_role = Role(code="SIDEBAR_DOCUMENT_ONLY", name="Sidebar document only", is_system=False)
        media_role = Role(code="SIDEBAR_MEDIA_ACL_ONLY", name="Sidebar media ACL only", is_system=False)
        branding_role = Role(code="SIDEBAR_BRANDING_ONLY", name="Sidebar branding only", is_system=False)
        db.session.add_all((audit_role, document_role, media_role, branding_role))
        db.session.flush()

        audit_user = _user(201, "sidebar-audit", audit_role)
        document_user = _user(202, "sidebar-documents", document_role)
        media_user = _user(203, "sidebar-media", media_role)
        branding_user = _user(204, "sidebar-branding", branding_role)
        db.session.add_all((audit_user, document_user, media_user, branding_user))
        db.session.flush()

        audit_permission = Permission.query.filter_by(code="audit_logs.view").one()
        branding_permission = Permission.query.filter_by(code="settings.branding.view").one()
        db.session.add(RolePermission(role_id=audit_role.id, permission_id=audit_permission.id))
        db.session.add(RolePermission(role_id=branding_role.id, permission_id=branding_permission.id))
        db.session.add(ProjectUser(
            id=201,
            project_id=1,
            user_id=document_user.id,
            project_role_code="CUSTOM",
            can_view_documents=True,
        ))
        album = CompanyMediaAlbum(name="Sidebar ACL album", is_restricted=True, created_by_id=6)
        db.session.add(album)
        db.session.flush()
        set_permission(db.session.get(User, 6), album, "user", media_user.id, {"can_view": "1"})
        db.session.commit()

    return (
        ("super", 1),
        ("admin", 6),
        ("viewer", 2),
        ("audit-only", 201),
        ("project-document-member", 202),
        ("company-media-acl", 203),
        ("branding-only", 204),
    )


def _user(user_id, username, role):
    return User(
        id=user_id,
        username=username,
        email=f"{username}@example.com",
        full_name=username,
        password_hash=generate_password_hash("password123"),
        role=role,
        legacy_role=role.code,
        is_active=True,
    )


def _authenticate(client, user_id):
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def _sidebar_blocks(markup):
    desktop_start = markup.index('<aside class="sidebar')
    desktop_end = markup.index("</aside>", desktop_start) + len("</aside>")
    mobile_start = markup.index('<div class="offcanvas', desktop_end)
    mobile_end = markup.index('<div class="app-content">', mobile_start)
    return markup[desktop_start:desktop_end], markup[mobile_start:mobile_end]


def _rendered_endpoints(app, markup):
    parser = _ModuleNavParser()
    parser.feed(markup)
    adapter = app.url_map.bind("localhost")
    return [adapter.match(urlsplit(href).path, method="GET")[0] for href in parser.hrefs]


def _module_nav_states(app, markup):
    parser = _ModuleNavStateParser()
    parser.feed(markup)
    adapter = app.url_map.bind("localhost")
    return {adapter.match(urlsplit(href).path, method="GET")[0]: active
            for href, active in parser.links.items()}


def _module_overlays(app, markup):
    parser = _ModuleOverlayParser()
    parser.feed(markup)
    adapter = app.url_map.bind("localhost")
    return parser, {
        module: [adapter.match(urlsplit(href).path, method="GET")[0] for href in hrefs]
        for module, hrefs in parser.overlays.items()
    }


def _sidebar_endpoints(app, user_id, module):
    with app.test_request_context("/test/sidebar-shell"):
        user = db.session.get(User, user_id)
        return [item["endpoint"] for item in get_sidebar_items(user, active_module=module)]


def test_module_navigation_matches_sidebar_items_for_every_visible_permission_set(
    client, app, sidebar_shell, sidebar_users):
    for _, user_id in sidebar_users:
        _authenticate(client, user_id)
        for module in MODULES:
            with client.session_transaction() as session:
                session["active_module"] = module
            response = client.get(sidebar_shell)
            assert response.status_code == 200
            desktop, mobile = _sidebar_blocks(response.get_data(as_text=True))
            expected = _sidebar_endpoints(app, user_id, module)
            desktop_endpoints = _rendered_endpoints(app, desktop)
            mobile_endpoints = _rendered_endpoints(app, mobile)

            assert set(desktop_endpoints) == set(expected)
            assert set(mobile_endpoints) == set(expected)
            assert desktop_endpoints == expected
            assert mobile_endpoints == expected


def test_project_document_membership_without_global_permissions_has_navigation_item(
        client, app, sidebar_shell, sidebar_users):
    _authenticate(client, 202)
    with client.session_transaction() as session:
        session["active_module"] = "project_documents"

    response = client.get(sidebar_shell)

    assert response.status_code == 200
    desktop, mobile = _sidebar_blocks(response.get_data(as_text=True))
    assert _rendered_endpoints(app, desktop) == ["project_documents.index"]
    assert _rendered_endpoints(app, mobile) == ["project_documents.index"]


def test_company_media_acl_without_global_permissions_has_navigation_item(
        client, app, sidebar_shell, sidebar_users):
    _authenticate(client, 203)
    with client.session_transaction() as session:
        session["active_module"] = "company_media"

    response = client.get(sidebar_shell)

    assert response.status_code == 200
    desktop, mobile = _sidebar_blocks(response.get_data(as_text=True))
    assert _rendered_endpoints(app, desktop) == ["company_media.index"]
    assert _rendered_endpoints(app, mobile) == ["company_media.index"]


def test_module_card_overlays_match_navigation_items_and_skip_single_destination_modules(
        client, app, sidebar_users):
    _authenticate(client, 1)

    response = client.get("/modules/")

    assert response.status_code == 200
    parser, overlays = _module_overlays(app, response.get_data(as_text=True))
    with app.test_request_context("/modules/"):
        user = db.session.get(User, 1)
        expected = {
            module: [item["endpoint"] for item in get_sidebar_items(user, active_module=module)]
            for module in ("reports", "partners", "admin")
        }
    assert overlays == expected
    assert parser.cards == set(MODULES)
    assert set(parser.trigger_targets) == {"#moduleQuickNav1", "#moduleQuickNav2", "#moduleQuickNav5"}
    assert "project_documents" not in overlays
    assert "company_media" not in overlays
    forbidden = {"modules.index", "account.profile", "auth.logout"}
    assert not forbidden.intersection(endpoint for items in overlays.values() for endpoint in items)


def test_single_module_user_only_receives_its_own_overlay_and_no_other_module_names(
        client, app, sidebar_users):
    _authenticate(client, 201)

    response = client.get("/modules/")

    assert response.status_code == 200
    parser, overlays = _module_overlays(app, response.get_data(as_text=True))
    assert parser.cards == {"admin"}
    assert overlays == {"admin": ["audit_log.index"]}
    markup = response.get_data(as_text=True)
    module_cards = markup[markup.index('<main class="main-content">'):markup.index("</main>")]
    assert "Quản lý dự án" not in module_cards
    assert "Quản lý đối tác" not in module_cards
    assert "Hồ sơ tài liệu" not in module_cards
    assert "Thư viện ảnh/video công ty" not in module_cards


def test_direct_overlay_navigation_uses_the_page_module_not_the_stale_session(client, app, sidebar_users):
    _authenticate(client, 1)
    with client.session_transaction() as session:
        session["active_module"] = "admin"

    response = client.get("/reports/today")

    assert response.status_code == 200
    with client.session_transaction() as session:
        assert session["active_module"] == "admin"
    desktop, mobile = _sidebar_blocks(response.get_data(as_text=True))
    assert "reports.today" in _rendered_endpoints(app, desktop)
    assert "reports.today" in _rendered_endpoints(app, mobile)
    assert "admin.users_index" not in _rendered_endpoints(app, desktop)


def test_new_report_navigation_items_follow_their_route_permissions(app, sidebar_users):
    with app.test_request_context("/modules/"):
        super_admin = db.session.get(User, 1)
        document_member = db.session.get(User, 202)
        super_admin_endpoints = {item["endpoint"] for item in get_sidebar_items(super_admin, "reports")}
        document_member_endpoints = {item["endpoint"] for item in get_sidebar_items(document_member, "reports")}

    assert {"reports.index", "project_operations.project_updates_index"}.issubset(super_admin_endpoints)
    assert "reports.index" not in document_member_endpoints
    assert "project_operations.project_updates_index" not in document_member_endpoints


@pytest.mark.parametrize(("endpoint", "desktop_active", "mobile_active"), (
    ("dashboard.system_dashboard", True, True),
    ("reports.today", True, True),
    ("reports.index", True, True),
    ("project_operations.project_updates_index", True, True),
    ("project_operations.operations_index", True, True),
    ("reports.configuration_hub", True, True),
    ("partners.dashboard", True, True),
    ("partners.index", True, True),
    ("partner_companies.index", True, True),
    ("partner_fields.index", True, True),
    ("partner_field_collections.index", True, True),
    ("partner_relations.index", True, True),
    ("project_documents.index", True, True),
    ("company_media.index", True, True),
    ("admin.users_index", False, True),
    ("admin_storage.index", False, True),
    ("audit_log.index", True, True),
    ("admin.roles_index", True, True),
    ("admin.branding", False, False),
))
def test_module_navigation_keeps_each_link_active_state(client, app, sidebar_users,
                                                         endpoint, desktop_active, mobile_active):
    _authenticate(client, 1)
    with app.test_request_context("/"):
        url = next(
            item["url"]
            for module in MODULES
            for item in get_sidebar_items(db.session.get(User, 1), module)
            if item["endpoint"] == endpoint
        )

    response = client.get(url)

    assert response.status_code == 200
    desktop, mobile = _sidebar_blocks(response.get_data(as_text=True))
    assert _module_nav_states(app, desktop)[endpoint] is desktop_active
    assert _module_nav_states(app, mobile)[endpoint] is mobile_active


def test_project_configuration_page_is_owned_by_configuration_navigation(client, app, sidebar_users):
    _authenticate(client, 1)

    response = client.get("/project-operations/contractors")

    assert response.status_code == 200
    desktop, mobile = _sidebar_blocks(response.get_data(as_text=True))
    for states in (_module_nav_states(app, desktop), _module_nav_states(app, mobile)):
        assert states["reports.configuration_hub"] is True
        assert states["project_operations.operations_index"] is False


@pytest.mark.parametrize("url", (
    "/reports/today",
    "/partners/dashboard",
    "/project-documents/",
    "/company-media/",
    "/admin/roles",
    "/project-operations/updates",
    "/project-operations/contractors",
))
def test_module_navigation_has_at_most_one_active_link_per_sidebar(client, app, sidebar_users, url):
    _authenticate(client, 1)

    response = client.get(url)

    assert response.status_code == 200
    desktop, mobile = _sidebar_blocks(response.get_data(as_text=True))
    assert sum(_module_nav_states(app, desktop).values()) <= 1
    assert sum(_module_nav_states(app, mobile).values()) <= 1
