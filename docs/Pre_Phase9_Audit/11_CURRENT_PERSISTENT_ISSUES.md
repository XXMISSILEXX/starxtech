# Persistent Issues

**VERIFIED.** `PersistentIssue` (`app/models/issue.py`) belongs to `Project`, has title/description, severity, status, opened/due/closed dates, optional owner user, creator, timestamps and soft delete. It has no category, DailyReportSection, contractor, first-observed, or latest-observed relation. `app/issues/services.py` writes audit records; routes create/edit/close/reopen/delete through capability helpers.

Capabilities: view=`can_view_issues`; create=`can_create_issues`; edit/delete=`can_edit_issues`; close/reopen=`can_close_reopen_issues`. PM/Reporter global role labels confer nothing by themselves. Dashboard uses non-deleted open/processing issues and critical severity; aging is not calculated in the model/service—only dates are stored. No active issue rows were found in runtime profile.

**Recommendation (TARGET):** PersistentIssue can be the cross-report source of truth, add nullable `report_category_id`, `first_report_section_id`, `latest_report_section_id`, and `assigned_project_contractor_id` only after decisions on automatic issue creation and contractor roles. Current evidence: isolated project issue. Gap: no traceability/responsibility. Migration/RBAC/test/compatibility impact: additive nullable FKs, backfill none, new permissions/audit and regressions for report flows; preserve existing unlinked issues.
