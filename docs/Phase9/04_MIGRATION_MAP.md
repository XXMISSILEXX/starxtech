# Migration map and compatibility

Step 9.2 revision is `aa468094da4f` (`add customers and project grouping`). It creates Customer, adds nullable `projects.customer_id`, backfills the deterministic `Khách hàng chưa phân loại` Customer, and does not set the FK NOT NULL.

| Planned migration | Additive change | Compatibility rule |
| --- | --- | --- |
| M1 Customer | `customers`, nullable `projects.customer_id`, indexes, `Khách hàng chưa phân loại` backfill | Old null customer renders safely until backfill completes. |
| M2 Contractor | contractor/assignment tables, role/status checks/indexes | No Partner FK; ended assignments preserve history. |
| M3 ProjectUpdate | update table, nullable assignment FK, project/date/assignment indexes | No update attachment or workflow. |
| M4 (Step 9.6 only) | nullable section category name/icon snapshots | Existing relationship remains fallback; no status migration. |

Before the first schema migration: backup, PostgreSQL rehearsal, dry-run/backfill report, validation, then constraints only after data is clean. Rollback disables feature code/routes while retaining additive tables and nullable columns; never delete Phase 9 data automatically.
# STEP 9.3 — Project contractors and assignments

Migration `b9f1c210e8d4_add_project_contractors_and_assignments.py` follows customer grouping migration `aa468094da4f`.

- Adds independent `project_contractors` catalog. It has no foreign key or import to Partner/Company models.
- Adds `project_contractor_assignments` with `project_id`, `contractor_id`, `role`, status/dates/note and audit actors.
- A partial unique index prevents a second non-`ENDED` assignment for one project, contractor and role while allowing `CONSTRUCTION` and `SOLUTION` together and a replacement after end.
- No Daily Report, PersistentIssue, attachment, storage, Celery or Partner schema changes are included.
