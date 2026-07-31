# Phase 4 audit — Safe, race-resistant and idempotent Company Media upload

## Purpose and safety

This is a read-only audit of the Company Media direct-upload lifecycle. It records the current implementation and an implementation decision proposal; it does **not** implement Phase 4. No application code, configuration, test, migration, database, or S3 object was changed. The only artefacts created are the Markdown files in this directory.

## Current status

Phase 4 is implemented locally (not deployed). The browser flow now uses the
selection-scoped key `(selection_session_id, client_file_id)`, persisted directly
on `UploadBatchItem` and protected by a database unique constraint. Company Media
presign is create-or-replay; complete and selection finalize are idempotent.
Details, test evidence, remaining manual checks, rollout and rollback are in
[PHASE4_IMPLEMENTATION_REPORT.md](PHASE4_IMPLEMENTATION_REPORT.md).

The decisive confirmed defect is `F-001`: no database constraint protects `(selection_session_id, client_file_id)`. See [FINDINGS.md](FINDINGS.md) and [SCHEMA_AND_CONSTRAINT_AUDIT.md](SCHEMA_AND_CONSTRAINT_AUDIT.md).

## Scope and non-goals

Covered: Company Media frontend, routes, generic storage services, models, migrations, quota/accounting, media-job enqueue, tests, configuration, and PostgreSQL deployment wiring. Shared direct-upload code is reviewed because it is called by Company Media; Daily Reports are not proposed for a behavior change.

Excluded: cancellation, orphan-object cleanup, persistent resume, browser file hashing, multipart resume, cross-device recovery, content deduplication, and automatic new sessions. The full list is in [PROPOSED_PHASE4_SCOPE.md](PROPOSED_PHASE4_SCOPE.md).

## Document index

| Document | Contents |
| --- | --- |
| [CURRENT_FLOW.md](CURRENT_FLOW.md) | Verified browser → DB/S3 lifecycle and sequence diagram. |
| [FINDINGS.md](FINDINGS.md) | Confirmed findings, impact, and evidence. |
| [SCHEMA_AND_CONSTRAINT_AUDIT.md](SCHEMA_AND_CONSTRAINT_AUDIT.md) | Tables, keys, relationships, and preflight SQL. |
| [TRANSACTION_AND_IDEMPOTENCY_DESIGN.md](TRANSACTION_AND_IDEMPOTENCY_DESIGN.md) | Recommended create-or-replay design and contracts. |
| [MIGRATION_PLAN.md](MIGRATION_PLAN.md) | Additive migration and PostgreSQL rollout plan. |
| [TEST_AND_VERIFICATION_PLAN.md](TEST_AND_VERIFICATION_PLAN.md) | Future test matrix and acceptance criteria. |
| [IMPLEMENTATION_OPTIONS.md](IMPLEMENTATION_OPTIONS.md) | Options considered and recommendation. |
| [PROPOSED_PHASE4_SCOPE.md](PROPOSED_PHASE4_SCOPE.md) | Must implement, exclusions, and approval decisions. |
| [AUDIT_COMMANDS_AND_RESULTS.md](AUDIT_COMMANDS_AND_RESULTS.md) | Commands, isolated test results, and Git safety checks. |

## Historical decision gate

The implementation follows the approved narrow solution: a unique constraint on
`upload_batch_items` after adding `selection_session_id`, plus a PostgreSQL-safe
replay path. Production still requires its own read-only preflight result before
deployment; no production database was queried or migrated for this work.

Source baseline: `CLAUDE.md` audit rules and storage lifecycle guidance; `AUDIT_RUNBOOK.md`; `docs/Phase11_Fix_Single_Download_CONFIG_AND_UI/README.md`, `VERIFICATION_REPORT.md`, `EVIDENCE_MAP.md`, `PROPOSED_FIX_PLAN.md`, `TEST_AND_ROLLOUT_PLAN.md`, `PHASE2_IMPLEMENTATION_REPORT.md`, and `PHASE3A_IMPLEMENTATION_REPORT.md` were all present and read. Phase 2/3A state that idempotency was deliberately left for a later approved design.
