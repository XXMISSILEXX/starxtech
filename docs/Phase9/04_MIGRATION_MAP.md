# Migration map and compatibility

Current revision is `20260725_0026` and no migration is created in Step 9.0.

| Planned migration | Additive change | Compatibility rule |
| --- | --- | --- |
| M1 Customer | `customers`, nullable `projects.customer_id`, indexes, `Khách hàng chưa phân loại` backfill | Old null customer renders safely until backfill completes. |
| M2 Contractor | contractor/assignment tables, role/status checks/indexes | No Partner FK; ended assignments preserve history. |
| M3 ProjectUpdate | update table, nullable assignment FK, project/date/assignment indexes | No update attachment or workflow. |
| M4 (Step 9.6 only) | nullable section category name/icon snapshots | Existing relationship remains fallback; no status migration. |

Before the first schema migration: backup, PostgreSQL rehearsal, dry-run/backfill report, validation, then constraints only after data is clean. Rollback disables feature code/routes while retaining additive tables and nullable columns; never delete Phase 9 data automatically.
