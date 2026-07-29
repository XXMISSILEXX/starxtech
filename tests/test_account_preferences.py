from app.extensions import db
from app.models import User


def login(client, username):
    return client.post("/login", data={"username_or_email": username, "password": "password123"})


def save_preferences(client, appearance, accent):
    return client.post(
        "/account/preferences",
        data={"appearance": appearance, "accent": accent},
        headers={"Accept": "application/json"},
    )


def test_ui_preferences_default_and_html_attributes(client):
    login(client, "reporter")
    response = client.get("/account/")

    assert response.status_code == 200
    assert b'data-appearance="system"' in response.data
    assert b'data-resolved-theme="light"' in response.data
    assert b'data-accent="blue"' in response.data
    assert b'data-theme-storage-key="starx.ui-preferences.3"' in response.data


def test_save_ui_preferences_is_validated_and_persists_across_login(client, app):
    login(client, "reporter")
    response = save_preferences(client, "dark", "purple")

    assert response.status_code == 200
    assert response.get_json()["preferences"] == {"appearance": "dark", "accent": "purple"}
    with app.app_context():
        db.session.expire_all()
        assert db.session.get(User, 3).ui_preferences == {"appearance": "dark", "accent": "purple"}

    client.post("/logout")
    login(client, "reporter")
    page = client.get("/account/")
    assert b'data-appearance="dark"' in page.data
    assert b'data-accent="purple"' in page.data


def test_ui_preferences_reject_invalid_values_without_mutating_database(client, app):
    login(client, "reporter")
    response = save_preferences(client, "neon", "red")

    assert response.status_code == 400
    assert set(response.get_json()["errors"]) == {"appearance", "accent"}
    with app.app_context():
        db.session.expire_all()
        assert db.session.get(User, 3).ui_preferences == {"appearance": "system", "accent": "blue"}


def test_ui_preferences_require_authentication_and_are_user_isolated(client, app):
    anonymous = save_preferences(client, "dark", "orange")
    assert anonymous.status_code == 302
    assert "/login?next=/account/preferences" in anonymous.headers["Location"]

    login(client, "reporter")
    assert save_preferences(client, "dark", "orange").status_code == 200
    client.post("/logout")
    login(client, "viewer")
    page = client.get("/account/")
    assert b'data-appearance="system"' in page.data
    assert b'data-accent="blue"' in page.data
    with app.app_context():
        assert db.session.get(User, 3).ui_preferences == {"appearance": "dark", "accent": "orange"}
        assert db.session.get(User, 2).ui_preferences == {"appearance": "system", "accent": "blue"}


def test_ui_preferences_migration_has_a_json_default_and_current_head():
    """Keep the migration deployable from the previous production head."""
    from importlib import import_module

    migration = import_module("migrations.versions.20260729_0027_add_user_ui_preferences")
    assert migration.down_revision == ("20260725_0026", "c4d2e980f617")
    assert migration.DEFAULT_PREFERENCES == '{"appearance":"system","accent":"blue"}'
