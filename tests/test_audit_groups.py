import pytest

from app.audit import (
    AUDIT_GROUP_AUTHORITY,
    AUDIT_GROUP_DESTRUCTIVE,
    AUDIT_GROUP_DISCLOSURE,
    AUDIT_GROUP_MUTATION,
    AUDIT_GROUP_RETAIN_FOREVER,
    AUDIT_GROUP_SECURITY,
    audit_group_for_action,
)


@pytest.mark.parametrize(
    ("action", "expected_group"),
    [
        ("account.ui_preferences.updated", AUDIT_GROUP_MUTATION),
        ("attachment.create", AUDIT_GROUP_MUTATION),
        ("attachment.delete", AUDIT_GROUP_DESTRUCTIVE),
        ("auth.login_failed", AUDIT_GROUP_SECURITY),
        ("category.create", AUDIT_GROUP_MUTATION),
        ("company.archive", AUDIT_GROUP_DESTRUCTIVE),
        ("company.restore", AUDIT_GROUP_DESTRUCTIVE),
        ("company_media.album.archive", AUDIT_GROUP_DESTRUCTIVE),
        ("company_media.album.cover", AUDIT_GROUP_MUTATION),
        ("company_media.album.create", AUDIT_GROUP_MUTATION),
        ("company_media.album.rename", AUDIT_GROUP_MUTATION),
        ("company_media.album.restore", AUDIT_GROUP_DESTRUCTIVE),
        ("company_media.file.create", AUDIT_GROUP_MUTATION),
        ("company_media.file.delete", AUDIT_GROUP_DESTRUCTIVE),
        ("construction_progress.entry.create", AUDIT_GROUP_MUTATION),
        ("construction_progress.entry.delete", AUDIT_GROUP_DESTRUCTIVE),
        ("construction_progress.entry.update", AUDIT_GROUP_MUTATION),
        ("construction_progress.group.archive", AUDIT_GROUP_DESTRUCTIVE),
        ("construction_progress.group.create", AUDIT_GROUP_MUTATION),
        ("construction_progress.group.delete", AUDIT_GROUP_DESTRUCTIVE),
        ("construction_progress.group.update", AUDIT_GROUP_MUTATION),
        ("construction_progress.item.create", AUDIT_GROUP_MUTATION),
        ("construction_progress.item.update", AUDIT_GROUP_MUTATION),
        ("construction_progress.type.archive", AUDIT_GROUP_DESTRUCTIVE),
        ("construction_progress.type.create", AUDIT_GROUP_MUTATION),
        ("construction_progress.type.delete", AUDIT_GROUP_DESTRUCTIVE),
        ("construction_progress.type.update", AUDIT_GROUP_MUTATION),
        ("customer.archive", AUDIT_GROUP_DESTRUCTIVE),
        ("customer.create", AUDIT_GROUP_MUTATION),
        ("customer.update", AUDIT_GROUP_MUTATION),
        ("document.custom_root.create", AUDIT_GROUP_MUTATION),
        ("document.file.archive", AUDIT_GROUP_DESTRUCTIVE),
        ("document.file.create", AUDIT_GROUP_MUTATION),
        ("document.file.download", AUDIT_GROUP_DISCLOSURE),
        ("document.file.rename", AUDIT_GROUP_MUTATION),
        ("document.file.restore", AUDIT_GROUP_DESTRUCTIVE),
        ("document.folder.archive", AUDIT_GROUP_DESTRUCTIVE),
        ("document.folder.create", AUDIT_GROUP_MUTATION),
        ("document.folder.move", AUDIT_GROUP_MUTATION),
        ("document.folder.rename", AUDIT_GROUP_MUTATION),
        ("document.folder.restore", AUDIT_GROUP_DESTRUCTIVE),
        ("document.folder.revoke", AUDIT_GROUP_AUTHORITY),
        ("document.folder.share", AUDIT_GROUP_AUTHORITY),
        ("issue.create", AUDIT_GROUP_MUTATION),
        ("issue.update", AUDIT_GROUP_MUTATION),
        ("partner.archive", AUDIT_GROUP_DESTRUCTIVE),
        ("partner.create", AUDIT_GROUP_MUTATION),
        ("partner.deactivate", AUDIT_GROUP_DESTRUCTIVE),
        ("partner.restore", AUDIT_GROUP_DESTRUCTIVE),
        ("partner.update", AUDIT_GROUP_MUTATION),
        ("partner_company.create", AUDIT_GROUP_MUTATION),
        ("partner_company.update", AUDIT_GROUP_MUTATION),
        ("partner_department.create", AUDIT_GROUP_MUTATION),
        ("partner_department.update", AUDIT_GROUP_MUTATION),
        ("partner_field_collection.create", AUDIT_GROUP_MUTATION),
        ("project.archive", AUDIT_GROUP_DESTRUCTIVE),
        ("project.create", AUDIT_GROUP_MUTATION),
        ("project.customer.move", AUDIT_GROUP_MUTATION),
        ("project.update", AUDIT_GROUP_MUTATION),
        ("project_contractor.create", AUDIT_GROUP_MUTATION),
        ("project_contractor_assignment.create", AUDIT_GROUP_MUTATION),
        ("project_contractor_assignment.end", AUDIT_GROUP_MUTATION),
        ("project_membership.assign", AUDIT_GROUP_AUTHORITY),
        ("project_membership.deactivate", AUDIT_GROUP_AUTHORITY),
        ("project_membership.update", AUDIT_GROUP_AUTHORITY),
        ("project_update.create", AUDIT_GROUP_MUTATION),
        ("project_update.delete", AUDIT_GROUP_DESTRUCTIVE),
        ("project_update.update", AUDIT_GROUP_MUTATION),
        ("project_user.assign", AUDIT_GROUP_AUTHORITY),
        ("project_user.remove", AUDIT_GROUP_AUTHORITY),
        ("report.create", AUDIT_GROUP_MUTATION),
        ("report.delete", AUDIT_GROUP_DESTRUCTIVE),
        ("report.update", AUDIT_GROUP_MUTATION),
        ("role.create", AUDIT_GROUP_AUTHORITY),
        ("role.permissions.update", AUDIT_GROUP_AUTHORITY),
        ("user.create", AUDIT_GROUP_AUTHORITY),
        ("user.reset_password", AUDIT_GROUP_AUTHORITY),
        ("user.seed_admin", AUDIT_GROUP_SECURITY),
        ("user.seed_admin.update", AUDIT_GROUP_SECURITY),
        ("user.update", AUDIT_GROUP_AUTHORITY),
    ],
)
def test_known_audit_actions_are_explicitly_classified(action, expected_group):
    assert audit_group_for_action(action) == expected_group
    assert audit_group_for_action(action) != AUDIT_GROUP_RETAIN_FOREVER


def test_unknown_audit_action_is_retained_safely():
    assert audit_group_for_action("future_module.unrecognized_action") == AUDIT_GROUP_RETAIN_FOREVER


def test_explicit_authority_exceptions_win_over_suffix_rules():
    assert audit_group_for_action("project_membership.deactivate") == AUDIT_GROUP_AUTHORITY
    assert audit_group_for_action("project_membership.update") == AUDIT_GROUP_AUTHORITY


@pytest.mark.parametrize(
    ("action", "expected_group"),
    [
        ("bulk_download.create", AUDIT_GROUP_DISCLOSURE),
        ("issue.delete", AUDIT_GROUP_DESTRUCTIVE),
        ("issue.close", AUDIT_GROUP_MUTATION),
        ("issue.reopen", AUDIT_GROUP_MUTATION),
        ("issue.section.close", AUDIT_GROUP_MUTATION),
        ("issue.section.reopen", AUDIT_GROUP_MUTATION),
        ("issue.section.update", AUDIT_GROUP_MUTATION),
        ("issue.section.delete", AUDIT_GROUP_DESTRUCTIVE),
    ],
)
def test_mapped_future_audit_actions(action, expected_group):
    assert audit_group_for_action(action) == expected_group
