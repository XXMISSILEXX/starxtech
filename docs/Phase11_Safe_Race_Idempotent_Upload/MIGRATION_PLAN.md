# Migration plan

Implemented locally as `20260730_0028_company_media_selection_item_idempotency`.
It was exercised only against disposable SQLite and PostgreSQL 16.11 databases.

## Baseline and proposal

The parent is `20260729_0027`, a merge with parents `20260725_0026` and
`c4d2e980f617` (`migrations/versions/20260729_0027_add_user_ui_preferences.py:3-17`).
The implemented revision is:

```text
20260730_0028
down_revision = "20260729_0027"
```

It adds nullable `upload_batch_items.selection_session_id` FK, backfills from
each parent batch, creates index `ix_upload_batch_items_selection_session_id`,
and unique constraint `uq_upload_batch_items_selection_client_file` on
`(selection_session_id, client_file_id)`. It preserves NULL in legacy/non-session
rows. No object key rewrite, row deletion, S3 operation, cancel/cleanup/hash/
resume field, or automatic deduplication occurs.

## Upgrade and rollout

1. Run preflight SQL in [SCHEMA_AND_CONSTRAINT_AUDIT.md](SCHEMA_AND_CONSTRAINT_AUDIT.md) against production under a controlled release. Any duplicate is fail-fast/review, not auto-remediation.
2. Add nullable column/FK, backfill only relationally derivable value, add named unique key.
3. Deploy/verify migration before application code depending on it. Compose has one migration service before web/worker (`docker-compose.yml:79-117`).
4. Deploy code, run PostgreSQL race test/staging smoke, then monitor safe replay/conflict counters.

## PostgreSQL availability

`batch_alter_table` is current migration convention for SQLite compatibility (`20260724_0024_daily_report_direct_uploads.py:15-35`). On PostgreSQL, adding a unique constraint scans/locks `upload_batch_items`; table size is unknown because no production query was run. For large live table, assess `pg_class` size and maintenance window; possibly create unique index concurrently in a separate autocommit operation and attach it as constraint if version/policy allow. For small table, normal named constraint is simplest. SQLite cannot prove lock/isolation behavior.

## Downgrade and failure plan

Downgrade removes this constraint/index then nullable FK column; it never recreates prevented duplicates or changes S3. During incident code rollback, prefer retaining additive schema if old code tolerates it, consistent with prior Phase 11 rollout guidance. If preflight/migration fails, stop deployment and report aggregates to approved operator; do not perform destructive cleanup.
