# Data model impact

## Migration need

No migration is needed merely to implement Partner/Company archive and restore:
both already have `is_active` and `deleted_at`. Relationship also has both;
Department has `is_active` and can support a first lifecycle without schema
change. New `*.restore` permissions require registry synchronization, not a
schema migration if the permissions table is already migratable.

A migration is recommended only if product requires: (1) `archived_at`
distinct from generic soft-delete timestamp, (2) archive reason/actor on the
entity rather than AuditLog, or (3) a dedicated Department resource model/
permission convention. Do not add it speculatively.

## Query contract

- `active`: `is_active = true AND deleted_at IS NULL` for soft-delete entities;
  `is_active = true` for Department.
- `archived`: `is_active = false OR deleted_at IS NOT NULL`; normalize legacy
  inconsistent rows in query/service rather than silently omitting them.
- `all`: no lifecycle filter, while preserving tenant/company scope.

Use one lifecycle query helper per entity, and make detail lookup status-aware
for view/restore; edit/archive only operate on the expected lifecycle state.
Avoid Company archive cascade. Maintain Partner `company_id` and Department
`department_id` history. Relationship/tree active queries should also exclude
inactive partners/departments by default.

## Backfill and integrity

Before release, report rows where `deleted_at IS NOT NULL` but `is_active=true`
or inverse; normalize under an approved migration/maintenance plan, with audit.
Existing Company deactivation writes both fields; Department only writes
`is_active`. Check database FK/cascade behavior before any hard-delete
administration is contemplated; business UI should never invoke hard delete.
