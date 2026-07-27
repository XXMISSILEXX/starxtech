# Phase 9 migration rehearsal runbook

This is an additive-only rehearsal procedure for the Customer, project-contractor,
assignment and ProjectUpdate migrations. It must be run against a restored PostgreSQL
copy, never production without owner approval.

## Current migration evidence

- Alembic current: `c4d2e980f617`.
- Alembic head: `c4d2e980f617`.
- The runtime database reachable for the release audit contains one Customer and no
  live Projects, reports, contractors, assignments or updates. It is therefore not a
  populated-copy rehearsal.

## Required rehearsal

1. Ask the database owner for a backup/restore window and create a protected custom
   `pg_dump`; never commit the dump or credentials.
2. Restore it to a separately named rehearsal database.
3. Record the baseline Alembic revision, run `flask db upgrade`, record elapsed time,
   then verify `flask db current` equals `flask db heads`.
4. Run read-only profile queries for Customer classification, duplicate non-ENDED
   assignments, cross-project ProjectUpdate assignment mismatch, orphan rows,
   duplicate daily reports, section/category mismatches and active attachment/storage
   integrity.
5. Run the full gate and smoke Daily Report V2, private attachment authorization,
   direct S3/HEIC, finalize/idempotency and Celery derivatives against the copy.
6. Revert application code only as the rollback rehearsal. Keep additive schema/data;
   do not run destructive downgrade on production.

## Status

**Pending.** Backup, restore, baseline-to-head timing, populated-data validation and
rollback evidence require a database owner and a populated copy.
