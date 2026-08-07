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
        db.session.add_all((audit_role, document_role, media_role))
        db.session.flush()

        audit_user = _user(201, "sidebar-audit", audit_role)
        document_user = _user(202, "sidebar-documents", document_role)
        media_user = _user(203, "sidebar-media", media_role)
        db.session.add_all((audit_user, document_user, media_user))
        db.session.flush()

        audit_permission = Permission.query.filter_by(code="audit_logs.view").one()
        db.session.add(RolePermission(role_id=audit_role.id, permission_id=audit_permission.id))
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
