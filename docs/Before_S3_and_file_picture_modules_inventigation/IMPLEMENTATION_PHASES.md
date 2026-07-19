# Implementation phases

Production commands are proposals for a future approved deployment only; none were executed during investigation. Back up PostgreSQL/upload data before migration and run commands serially in the `web` container.

## Phase 1 — RBAC foundation

- Goal: roles/permissions tables, registry, `sync-permissions`, `can`, decorators, Vietnamese 403, role change audit and final-super-admin guard.
- Files: new `app/models/role.py`, `app/permissions/*`, migration, CLI, `app/auth/permissions.py`, templates/admin routes, tests.
- Migration: additive roles/permissions/role_permissions only; retain `users.role`.
- Tests: registry idempotency/no-delete, inactive/anonymous/unknown deny, SUPER bypass, last admin guard, CSRF regression.
- Deploy: `docker compose exec web flask db upgrade`; then `docker compose exec web flask sync-permissions`; smoke test. Do not enable automatic migration.
- Rollback: revert code; tables may remain unused. Restore backup only for failed migration; do not downgrade blindly.

## Phase 2 — Protect partner module

- Goal: replace partner helper roles with module/action permissions; make PM read-only by default; gate sidebar/cards/buttons and all routes.
- Files: partner blueprints/services/templates/base/UI, registry, tests.
- Migration: normally none after Phase 1.
- Tests: direct URL and POST deny, role matrix, partner/company/department/relationship audit.
- Deploy: sync registry, assign reviewed mappings, smoke test each role. Rollback mapping to prior defaults; code retains old adapter only during transition.

## Phase 3 — Protect daily reports

- Goal: report/issue/category/dashboard/attachment permissions plus `ProjectUser` resource scope; decide own vs project edit.
- Files: reports/projects/issues/dashboard/attachments routes/services/templates, registry/tests.
- Migration: no schema migration unless audit enrichment is selected.
- Tests: unassigned project denial, viewer write denial, ownership policy, delete, attachment download/delete, dashboard API.
- Deploy/rollback: sync, grant existing equivalent permissions, test per role; restore mapping before reverting code.

## Phase 4 — Prepare document/photo modules

- Goal: private local storage implementation, document/folder/album/photo/tag models, scope helpers and audit from first route.
- Files: new blueprints/models/services/templates/registry/migrations/tests.
- Migration: new module tables and object metadata. Do not touch existing report images initially.
- Tests: MIME/size, authorization vs guessed ID, metadata/download split, soft delete, audit.
- Deploy: migration then sync-permissions then smoke test with local mounted upload root. Rollback disables routes; preserve objects and database rows.

## Phase 5 — S3 integration

- Goal: `StorageService`, S3 backend, private bucket/IAM, controlled local-to-S3 migration and presigned URL/stream policy.
- Files: storage package/config/docs/tests/operations runbook; possibly object metadata migration only if missing fields.
- Tests: local and fake-S3 contracts, failed upload compensation, expiry, no public URL/key disclosure.
- Deploy: provision bucket/IAM/secrets outside repo, deploy code, validate a pilot project, migrate asynchronously with checksums. Never restart Docker solely for an investigation.
- Rollback: switch storage backend to local for new writes; retain object mapping and do not delete remote originals until verified backup/retention window.
