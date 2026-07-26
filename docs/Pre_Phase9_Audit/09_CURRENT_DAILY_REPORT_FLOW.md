# Daily Report V2 flow

**VERIFIED** from `projects.routes::reports_create`, `reports.create_v2`, `reports.direct_uploads`, `reports.services`, templates and `test_daily_report_create_v2.py`.

```mermaid
sequenceDiagram
 Browser->>Flask: GET /projects/:id/reports/create
 Browser->>Flask: POST V2 /preflight (read-only)
 Browser->>Flask: POST upload-sessions
 Browser->>Flask: POST presign metadata/client UUIDs
 Browser->>S3: direct PUT each file
 Browser->>Flask: POST complete (HEAD + checksum verify)
 Browser->>Flask: POST finalize (client_request_id)
 Flask->>Postgres: lock session/items; create report/sections/attachments
 Flask->>Postgres: mark objects active, audit, commit
 Flask->>Celery: enqueue derivatives after commit
 Browser->>Flask: GET report detail
```

Create GET requires only project read and renders `can_write`; API requires `can_create_report`. Legacy create POST returns JSON 405. V2 requires UUID `client_request_id` and UUID client section/file IDs, validates category/project, section category uniqueness, attachment mapping and maximum 3 files/section (30/300MB report). Files are session-owned, presigned direct to S3, completed after HEAD/checksum verification, then locked/finalized atomically. `(project_id,report_date)` and IntegrityError conversion protect races; `(project_id,client_request_id)` returns existing report on retry, avoiding re-upload after a lost finalize response.

Overall status is selected by user and not computed from section statuses. V2 does not check project `status`, so paused/completed/archived create policy is UNKNOWN/product gap. Edit remains legacy HTML controller with direct-upload attachment manifest support; delete calls hard-delete/storage cleanup (`reports.services::delete_report`). Immutable Phase 9 invariants: browser validation, preflight no mutation, mapping, direct PUT, HEAD, idempotent finalize, derivative dispatch-after-commit, private authorization, and HEIC client preview.
