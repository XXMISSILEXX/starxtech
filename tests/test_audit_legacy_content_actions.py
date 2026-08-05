from app.audit import AUDIT_ACTION_GROUPS, LEGACY_CONTENT_CREATE_ACTIONS


def test_legacy_content_create_actions_are_complete_and_do_not_hide_live_creation_audits():
    still_emitted = {
        "category.create",
        "partner_company.create",
        "partner_department.create",
        "partner_field.create",
        "partner_field_collection.create",
        "partner_relationship.create",
        "project.create",
    }
    create_actions = {action for action in AUDIT_ACTION_GROUPS if action.endswith(".create")}
    excluded_non_content_creates = {"bulk_download.create", "user.create", "role.create"}

    assert LEGACY_CONTENT_CREATE_ACTIONS.isdisjoint(still_emitted)
    assert LEGACY_CONTENT_CREATE_ACTIONS | still_emitted == create_actions - excluded_non_content_creates
