# Findings — Report upload flows

## Summary

- Primary paths read in full: `app/reports/create_v2.py` and `app/reports/direct_uploads.py`. Legacy project upload routes, shared report creation/finalization, storage/quota/provider, and media-processing functions directly reached by the flows were also traced.
- V2 improves retry behavior for a single `client_file_id` and does not repeat the legacy route’s global cleanup-on-cancel defect. It still inherits direct-to-S3 PUT’s lack of byte-level type verification and check-then-act quota/session accounting.
- PRE-011 is a defense-in-depth gap, not a practical bypass today. Every V2 route invokes `_project()` before parsing payloads, sessions, or provider work; `can_create_report` implies `can_access_reports_module` under the present predicates.
- Findings: one High and two Medium. The concurrent `client_request_id` idempotency defect is documented in 3a as REPORTS-005 and is not duplicated here.

## V2 versus legacy comparison

| Control | Legacy route/file:line | V2 route/file:line | Equivalent? | Consequence |
|---|---|---|---|---|
| Authentication | Global `require_login`; `projects.*` | Global `require_login`; `daily_report_create_v2.*` | Yes | Both require an active Flask-Login session before the handler. |
| Reports-module gate | Global endpoint-prefix gate includes `projects.` (`app/__init__.py:179-189`) | Prefix does not include `daily_report_create_v2.`; no blueprint hook | No | Defense-in-depth drift; PRE-011 is not bypassable today because all routes next require `can_create_report`. |
| Project existence / soft-delete | `_project_or_404()` at `projects/routes.py:139,150,160,170,182` | `_project()` at `create_v2.py:29-35` | Yes | Both reject a missing/soft-deleted target before payload/session work. Neither rejects archived status. |
| Project capability | `can_create_report` before each stage (`projects/routes.py:140,151,161,171,183`) | `_project()` invokes it before each stage (`create_v2.py:33`) | Yes | Creation authority is re-checked on every request, including state/cancel/complete/finalize. |
| User/session ownership | `_session()` (`direct_uploads.py:41-49`) | Same `_session()` | Yes | Requires creator, module type, target type, target ID, valid status/expiry. |
| Project/session association | URL project passed to `_session()` | URL project passed to `_session()` | Yes | Swapping a session ID across projects/users raises authorization error. |
| CSRF | Global `CSRFProtect` | Global `CSRFProtect` | Yes | POSTs are covered; no `csrf.exempt` found in these flows. |
| Input schema / coercion | JSON defaults to `{}`; session numbers coerced in service; legacy complete manually `int()`-coerces item ID | `_payload()` requires JSON object; V2 complete IDs are URL ints | Mostly | V2 returns structured JSON errors for most invalid payloads; finalize’s `int(session_id)` is covered by 3a’s service review. |
| Filename / declared MIME | `validate_file_metadata()` in `presign()` (`direct_uploads.py:82-89`) | Same in `v2_presign()` (`131-138`) and V2 preflight (`services.py:125-135`) | Yes | Extension/MIME pair is validated, but bytes are not content-sniffed (UPLOAD-001). |
| Size / count limits | Per-request plus `min(declared, configured cap)` (`direct_uploads.py:73,90-93`) | Session-declared count/bytes plus per-file cap (`v2_presign():118-152`) | Not fully | Both are race-prone; V2 creates one batch per file and has no lock around session accounting (UPLOAD-003). |
| Quota reservation | `ensure_storage_capacity(total)` before object rows | `ensure_storage_capacity(meta["file_size"])` per new item | No | Both are check-then-act and count only active objects; V2 cancellation makes abandoned bytes particularly easy to accumulate (UPLOAD-002/003). |
| Presigned key generation | `build_original_key(..., uuid4().hex, ...)` (`98-103`) | Same (`156-163`) | Yes | Opaque, fresh keys; no client-controlled object key. |
| Completion verification | `complete()` → provider HEAD and `_validate_head()` | Same `complete()` | Yes | Server verifies declared size, signed Content-Type, and optional checksum; it does not inspect bytes. |
| Storage-object transition | `pending` → `uploaded` in `complete()` → `active` at legacy report edit attach | Same `pending` → `uploaded` → `active` in V2 finalize (`services.py:199-204`) | Yes | Objects are not servable as report attachments until finalization. |
| Attachment / category binding | Legacy edit manifest binds items to submitted section IDs; report service validates categories | V2 validates target-project categories and locks/compares item section IDs (`services.py:111-113,182-203`) | Yes | Cross-project category and cross-session/item substitution are blocked. |
| Finalize idempotency | Legacy report creation POST is rejected; edit consumes a session once | UUID request id plus session/item locks in `finalize_daily_report_create_v2()` | Improved, but incomplete | Sequential retry returns the existing report; concurrent same-request retries can 500 (REPORTS-005). |
| Project/date uniqueness | No live legacy create route | Pre-check plus DB unique `(project_id, report_date)` | V2-only | V2 returns 409 for detected/date-constraint duplicates. |
| Cancel authorization | Project capability + creator/project/session binding | Same capability + `_session()` binding | Yes | Neither permits cancellation of another user’s session. |
| Cleanup scope | Cancel invokes global `cleanup_expired_sessions()` (`projects/routes.py:185-189`) | Cancel only marks its session cancelled (`create_v2.py:119-123`) | No | Legacy cross-project cleanup is REPORTS-001; V2 avoids it but leaves abandoned objects until external cleanup (UPLOAD-002). |
| Retry behavior | `presign()` mints new object/item rows on repeated client file IDs | `v2_presign()` reuses an existing same-session `client_file_id` item (`139-148`) | Improved | V2 avoids ordinary retry duplicates, but not races before either request sees the other’s item (UPLOAD-003). |
| Celery enqueue | Legacy edit stages jobs, commits, then dispatches | V2 finalize stages jobs, commits, then dispatches (`services.py:205-215`) | Yes | Durable pending jobs precede broker work; broker failure does not roll back report ownership. |
| Partial-failure rollback | Presigned URL is generated before the DB commit | Same ordering in `v2_presign()` (`155-166`) | Yes | A provider/commit failure can leave an issued URL/object without durable metadata; no attacker-controlled trigger was proven. |
| Audit logging | No upload-session create/presign/complete/cancel audit | Same; V2 finalize audits attachment/report create | Mostly | Report evidence creation is audited; session lifecycle and abandoned uploads are not. |
| Rate limiting | Create/presign/complete: 30/60/120 per minute; no state/cancel limit | Same plus preflight 30 and finalize 20; no state/cancel limit | V2 stronger | Limits reduce but do not remove parallel session/accounting races. |

## Findings

### UPLOAD-001 — Direct-upload flows trust a signed Content-Type instead of verifying uploaded bytes before Pillow processing

- **Severity:** High
- **Confidence:** High
- **CWE:** CWE-434
- **Location:** `app/storage/providers.py:84-88`; `app/storage/services.py:159-168`; `app/media_processing/pipeline.py:53-67`
- **Reachability:** Any authenticated user with `can_create_reports` for a non-deleted project can use either legacy or V2 presign, PUT arbitrary bytes using the signed `image/*` Content-Type, complete, and finalize a report. The V2 capability check runs first.
- **Exact code quote:**
  ```python
  params = {"Bucket": bucket, "Key": object_key, "ContentType": mime_type}
  return {"method": "PUT", "url": self.client.generate_presigned_url("put_object", Params=params, ExpiresIn=expires_in, HttpMethod="PUT"),
  ```
  ```python
  if int(head.get("size", -1)) != storage_object.file_size:
      raise StorageValidationError("Kích thước object không khớp.")
  content_type = (head.get("content_type") or "").lower()
  if content_type and content_type != storage_object.mime_type:
      raise StorageValidationError("MIME type object không khớp.")
  ```
  ```python
  with Image.open(source) as original:
      original.verify()
  with Image.open(source) as source_image:
      with ImageOps.exif_transpose(source_image) as transposed:
  ```
- **Full guard chain:** Login → (legacy only) global Reports-module gate → project lookup excluding `deleted_at` → `can_create_report` → session owner/project binding → declared filename/MIME/size validation → presigned PUT with declared Content-Type → HEAD size/Content-Type/optional checksum comparison → item/session finalize checks → `upload_status="active"` → durable media job → Pillow decodes the uploaded bytes.
- **Object-scope evidence:** IDs are correctly bound to the actor/session/project. The missing check is byte identity: PUT signing constrains headers, and `_validate_head()` compares provider metadata, but neither path opens/sniffs/re-encodes the object before it is classified as an image and passed to `Image.open()`.
- **Resulting write/read/delete:** Attacker-controlled bytes become an active `StorageObject`, `ReportAttachment`, and image-derivative job; the worker downloads and parses the bytes.
- **Concrete impact:** A permitted reporter can disguise an arbitrary Pillow-decodable payload as JPEG/PNG/WebP by using a valid declared MIME and matching size. This exposes the media worker to malicious image parsers and decompression/CPU pressure; Foundation-B identifies content validation as absent and the installed Pillow surface as relevant to image decoding.
- **Remediation direction:** Verify the actual uploaded bytes after HEAD and before activation (strict allowed decoder formats plus full decode/pixel limits, then re-encode or quarantine). Do not rely on extension, Content-Type, or optional client checksum as a content-type control.

### UPLOAD-002 — V2 cancellation leaves uploaded objects uncounted and unscheduled for cleanup

- **Severity:** Medium
- **Confidence:** High
- **CWE:** CWE-400
- **Location:** `app/reports/create_v2.py:114-123`; `app/reports/direct_uploads.py:170-186`; `app/storage/quota.py:6-24`
- **Reachability:** A user with create capability can presign, upload, complete, then cancel their own V2 session repeatedly. V2 cancellation runs only after project/capability/session ownership checks.
- **Exact code quote:**
  ```python
  session = direct_uploads._session(current_user, project.id, session_id)
  session.status = "cancelled"
  ...
  db.session.commit()
  return _ok(upload_session_id=session.id, status=session.status)
  ```
  ```python
  item.status = "completed"; item.storage_object.upload_status = "uploaded"; item.storage_object.completed_at = _now()
  ```
  ```python
  originals = db.session.query(func.coalesce(func.sum(StorageObject.file_size), 0)).filter(StorageObject.upload_status == "active", StorageObject.deleted_at.is_(None)).scalar()
  ```
- **Full guard chain:** Login → V2 `_project()` soft-delete lookup → `can_create_report` → `_session()` actor/project/scope binding. The cancel handler then writes only the session status and performs no cleanup, storage-status transition, or audit event.
- **Object-scope evidence:** Completed objects remain associated with the cancelled session as `upload_status="uploaded"`. Storage quota counts only `active` originals, while the only direct-upload session cleanup is a separately callable task/CLI routine, not invoked by V2 cancel or scheduled in-repo.
- **Resulting write/read/delete:** A cancelled V2 session retains uploaded bytes and DB metadata without an attachable report. They are neither active/quota-accounted nor deleted by the route.
- **Concrete impact:** An authorized reporter can consume object storage outside the application quota by repeatedly completing then cancelling sessions. In normal failure/retry use, abandoned bytes also persist until an operator runs cleanup; storage cost and cleanup backlog can grow without bound over time.
- **Remediation direction:** Make cancellation enqueue a scoped asynchronous cleanup, or mark associated objects for a scheduled cleanup that accounts for reserved bytes. Include pending/uploaded-but-unfinalized objects in a reservation/quota model and audit cancellation/cleanup outcomes.

### UPLOAD-003 — Concurrent V2 presign requests can exceed session limits and create duplicate upload items

- **Severity:** Medium
- **Confidence:** High
- **CWE:** CWE-362, CWE-400
- **Location:** `app/reports/direct_uploads.py:116-167`; `app/storage/quota.py:20-24`
- **Reachability:** A permitted V2 uploader can send parallel presign requests against one owned session, using different UUID client file IDs (or the same ID before either request commits). The endpoint is rate-limited but admits concurrent requests.
- **Exact code quote:**
  ```python
  existing = {item.client_file_id: item for item in UploadBatchItem.query.join(UploadBatch).filter(
      UploadBatch.selection_session_id == session.id).all()}
  if len(existing) + len([file_id for file_id in ids if file_id not in existing]) > session.declared_files:
      raise StorageValidationError("Ảnh vượt quá giới hạn của phiên tải.")
  ```
  ```python
  if session.presigned_size_bytes + meta["file_size"] > session.declared_size_bytes:
      raise StorageValidationError("Ảnh vượt quá giới hạn của phiên tải.")
  ensure_storage_capacity(meta["file_size"])
  ```
  ```python
  session.presigned_files += 1; session.presigned_size_bytes += meta["file_size"]
  ```
- **Full guard chain:** Login → V2 `_project()` checks soft-delete and `can_create_report` → `_session()` binds actor/project/session and validates status → metadata validation → count/size/quota checks → object/item insertion and presigned PUT issuance. Neither the session nor quota aggregate is locked during the read-check-write sequence.
- **Object-scope evidence:** Each request is correctly owned by the same actor/session/project; the defect is temporal. Two requests can each read the same `existing` set and counters, pass independently, create separate `UploadBatch`/`StorageObject`/`UploadBatchItem` rows, then increment stale session counters. The DB unique key is only `(upload_batch_id, client_file_id)`, so it cannot prevent same-session duplicates across the one-batch-per-file V2 design.
- **Resulting write/read/delete:** More presigned objects/items than `declared_files` or `declared_size_bytes` allow can be committed. Finalize requires the full resulting item set and can attach duplicated file submissions if they otherwise meet report-level limits; abandoned items also amplify UPLOAD-002.
- **Concrete impact:** A reporter can exceed per-session limits and drive uncounted direct-storage allocation despite normal rate limits. It also weakens V2’s promised idempotent presign behavior under real concurrent browser retries.
- **Remediation direction:** Lock the `UploadSelectionSession` row (`FOR UPDATE`) before calculating capacity and reserve counters atomically; add a uniqueness constraint for `(selection_session_id, client_file_id)` (or a session-level item table); use atomic quota reservation rather than aggregate check-then-act.

## Explicitly checked and found clean

- PRE-011 verdict: **defense-in-depth gap / Info, not a practical authorization bypass today.** `can_access_reports_module()` returns true for a project admin/viewer-admin or anyone with any `can_view_reports`/`can_create_reports` membership; `can_create_report()` requires `can_create_reports` for the specific project. Therefore a caller that passes `_project()`’s `can_create_report` check necessarily satisfies the current module-access predicate. All six V2 handlers call `_project()` before payload parsing, session lookup, provider work, completion, cancellation, or finalization. Existing sessions do not survive loss of that capability because state, presign, complete, cancel, and finalize all call `_project()` first.
- V2 and legacy both bind `session_id` to creator, daily-report scope, target type, and URL project; `item_id` completion is re-bound to the session through `UploadBatch.selection_session_id`. Swapping user/project/session/item/storage IDs does not reach another user’s object.
- Completed item retry is idempotent (`item.status == "completed"` plus `upload_status == "uploaded"`), and V2 finalization locks session/items, requires every session item exactly once, checks `finalized_at`, and changes the session to `finalized`; double-finalize does not duplicate attachments.
- Finalize rejects cancelled/expired/non-ready sessions and re-validates every category against the target project, section/item binding, report date, statuses, attachment count, and total size.
- V2 stages media jobs in the report transaction and dispatches only after `db.session.commit()`. Broker failure is logged and leaves a durable pending job for later reconciliation.
- Session-state responses disclose only the caller’s own, project-bound item IDs/statuses/filenames after the capability and `_session()` checks; no horizontal session-state disclosure was found.
- V2 cancel intentionally avoids the legacy global cleanup route that caused REPORTS-001; that difference is safe for cross-project authorization but creates UPLOAD-002’s lifecycle debt.

## Needs verification

- Add PostgreSQL concurrency tests for parallel V2 presign calls with the same and different `client_file_id` values, and for same-client-request finalization (cross-reference REPORTS-005).
- Induce provider URL-generation and database commit failures. Both flows issue presigned URLs before committing their metadata; source proves a non-atomic external/DB boundary, but no attacker-controlled provider-failure path was established.
- Verify the production scheduler actually invokes `reports.cleanup_expired_upload_sessions` and/or pending-object cleanup. The repository defines task/CLI entry points but no schedule.
- Decide whether `archived`, `paused`, and `completed` projects should permit uploads. Both paths reject only soft-deleted projects.
