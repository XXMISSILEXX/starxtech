# Database schema and data profile

**VERIFIED read-only PostgreSQL.** Current=head is `20260725_0026`; detailed columns, FKs, constraints and indexes are in [schema evidence](evidence/database_schema_summary.txt), and aggregate profile in [profile evidence](evidence/database_profile_summary.txt). No credentials or report content are stored.

Exact aggregate queries found 2 projects (one active, one archived), 12 daily reports dated 2026-06-08–2026-09-29, 22 active sections, 55 active/completed attachments, and zero active issues. No duplicate `(project_id,report_date)`, no orphan section categories, and no used inactive category were returned. One active project had no active user assignment; one project had no categories. Category flags show 12 active/non-required categories. Reports use UPDATED 7, GOOD 2, PROCESSING 2, ATTENTION 1; sections INFO 12, GOOD 6, PROCESSING 4.

**Verified compatibility debt:** `pg_stat_user_tables.n_live_tup` reports zero for several populated tables, while direct aggregate queries return rows. It is stale statistics and must not be used for planning capacity until ANALYZE is operationally approved. Actual role data contains legacy/custom codes including `005`, `PARTNER`, and `PROJECT_STAFF`; role grants also contain `PROJECT_MANAGER`/`REPORTER`, unlike the registry's system-role defaults.

Migration chain 0001–0026 includes canonical RBAC, S3 transitions, hard report deletion, direct uploads, finalize jobs, and idempotency. Additive migrations only are appropriate for Phase 9.
