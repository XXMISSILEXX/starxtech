# Deferred Daily Report hardening

Category presentation snapshots (`DailyReportSection.category_name_snapshot` and icon) and required-category enforcement are intentionally deferred from STEP 9.6. They are not a Phase 9.6 blocker.

The affected source includes `app/models/daily_report.py`, V2 payload validation/finalization in `app/reports/services.py`, create/edit templates and legacy report rendering. A change must preserve old rows through relationship fallback and make preflight, upload-session handling, finalize, retry/idempotency and duplicate-date handling agree.

Before implementation, perform a full source audit and migration rehearsal on populated data. The principal risk is a new validation/snapshot write changing direct-upload ordering or breaking finalize retry/idempotency; no S3, HEIC or Celery behavior may be altered as an incidental effect.
