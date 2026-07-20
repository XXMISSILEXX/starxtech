# Implementation phases

## Phase A — contract preparation

Define lifecycle helpers and status query contract; add `*.restore` registry
metadata/default grants after approval. Add audit snapshot convention including
`name`, `is_active`, `deleted_at`, target type/id. No data migration unless
integrity audit identifies inconsistent legacy rows.

## Phase B — Company lifecycle

Expose existing archive safely under canonical route/UI, add restore, list
status filter/detail archived view, and inactive Company form guards. Preserve
Partner links; do not cascade.

## Phase C — Partner lifecycle

Add status filter, archived detail/read policy, canonical archive/restore and
Company archived badge/current-inactive edit behavior.

## Phase D — Department and Relationship policy

Block Company-inactive mutations. Implement Department restore only if approved.
Keep Relationship archived UI deferred unless the business needs it; prepare
restore/admin access and active-tree semantics first.

## Phase E — UI, audit and tests

Replace destructive wording, finish badges/flash messages, test RBAC/CSRF and
full regression. Run normal local verification only after a reviewed change:

```bash
python -m compileall app tests
pytest -q
flask sync-permissions
```

Run `flask sync-permissions` only against the intended migrated local database;
do not use reset or migration commands as a substitute for a rollout plan.

## Rollback notes

Deploy routes/UI before removing compatibility POST aliases. Rollback is code
rollback; archived rows remain business data. Never rollback by hard deleting
records. If a migration is later approved, use tested forward/backward scripts
and database backup/change-window procedures.
