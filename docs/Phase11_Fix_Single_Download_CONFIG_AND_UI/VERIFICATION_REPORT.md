# Verification report

## Executive summary

This is an independent, read-only verification of the prior audit. Two previously stated defects are **CONFIRMED** by code and safe runtime evidence:

1. Company Media's menu single-download POST returns a valid signed-URL shape without `ok: true`, while its shared browser helper rejects every response without `data.ok`. The helper throws before `window.location.assign(result.url)`. Therefore the normal code path emits no signed-storage GET after the successful POST.
2. Repeating Company Media presign with the same selection session and client file ID creates a new batch, pending object, and accepted item; the selection's presigned count/bytes increase again.

Project Documents has the same route response shape and uses the same download handler, so its menu single-download is also **CONFIRMED** to have the same client-side contract defect. Its bulk-one-file action follows a different contract and is unaffected.

HEIC/HEIF is **RULED OUT** as the cause of the original-download defect. It remains a **CONFIRMED** independent preview risk because preview requires generated WebP derivatives and decoder/pipeline failure marks that processing failed while leaving the original active.

No production logs were supplied, and no production/local live storage request was made. Provider-specific behavior after a browser actually reaches a signed GET remains unverified.

## Single-download verification

### Exact Company Media flow

```text
Album menu button (data-signed-download/data-download-url)
→ project-document-preview.js click listener
→ requestJson(): POST with X-CSRFToken
→ company_media.routes.download()
→ company_media.services.signed_download()
→ provider.create_presigned_download(..., attachment, display_name)
→ JSON {url, expires_at}
→ requestJson rejects because data.ok is absent
→ catch → window.alert("Không thể tải preview.")
→ no window.location.assign()
→ no signed-storage GET on this code path
```

The safe runtime check independently observed `single_has_url: true` and `single_has_ok: false` from `company_media.services.signed_download()` with FakeStorage. It did not print a URL, bucket, key, credential, or object identifier.

### Endpoint, CSRF, and authorization

- Endpoint: `POST /company-media/files/<file_id>/signed-download`.
- Browser handler sends JSON and `X-CSRFToken`; Flask-WTF global CSRF applies to POST routes in normal runtime.
- The route requires `company_media.permissions.download_file(current_user, file)`. That helper requires an active/non-archived file and album download capability.
- The backend success schema is provider output: `{url, expires_at}`. The error schema is normally `{error: "..."}` with HTTP 400; it is not a common success/error envelope.
- The helper reads `result.url` (top-level), not `download_url` and not `data.url`.

### Why HTTP 200 does not download

`requestJson()` succeeds only when both HTTP status is OK and `data.ok` is truthy. Company Media's single signer does not add `ok`, so the helper throws the fallback string "Không thể tải preview." The navigation statement is later in the same `try` block and is unreachable. This is a direct causal chain, not an inference from HEIC, CSP, or storage behavior.

### Competing hypotheses

| Hypothesis | New verification | Result |
|---|---|---|
| Top-level URL field mismatch | Both provider result and JS use `url` | RULED OUT |
| Nested `data.url` mismatch | No nested success response exists | RULED OUT |
| Missing `ok: true` | Helper requires it; single response omits it | CONFIRMED |
| Popup blocker | Uses `window.location.assign`, not asynchronous `window.open` | RULED OUT for this path |
| Cross-origin anchor/download attribute | No anchor is created by the handler | RULED OUT for this path |
| Browser downloads JSON | Fetch parses JSON and never navigates | RULED OUT |
| CSP blocks the GET | Code never initiates GET; CSP allows configured storage origin for media/connect | RULED OUT as primary cause |
| Signed URL expiry/provider error | No GET is reached in the broken path | UNVERIFIED secondary risk |
| Unicode Content-Disposition | Provider constructs a response-disposition override, but no provider/browser test was run | UNVERIFIED |
| Archived/deleted media | Permission returns 403 before signing, not the observed 200 | RULED OUT for observed symptom |
| Derivative used for original | Single signer targets `StorageObject`; derivative is only preview/thumbnail | RULED OUT |
| X-Accel intercepts original | X-Accel is only reached by cache derivative delivery | RULED OUT |

## Project Documents verification

Project Documents' menu endpoint is `POST /project-documents/files/<file_id>/signed-download`. Its service returns the same provider shape `{url, expires_at}` without `ok`; its template registers the same `data-signed-download` controls, and `project-document-preview.js` handles both modules.

Therefore the Project Documents **menu single-download has the same defect**. This is confirmed by direct code-path equivalence; a browser test has not yet been added.

Project Documents' bulk-one-file action is separate: it expects `{kind: "direct", download: {url}}` and immediately calls `window.location.assign(result.download.url)`. It does not call `requestJson()` and is not affected by this mismatch.

## Daily Report comparison

Daily Report original download is `GET /attachments/<id>/download`. It authorizes the attachment, validates active storage state, then returns an HTTP 302 to the signed original URL. Its UI uses a normal route/navigation rather than this JSON helper. That difference explains why it continues to work despite the Company Media defect.

## Company Media bulk comparison

- Bulk one file: `POST /company-media/albums/<id>/files/bulk-signed-download` returns `{ok: true, kind: "direct", download: {url, expires_at}}`; JS recognizes this exact contract and navigates.
- Bulk multiple: the same endpoint streams an `application/zip` response after a native POST form submission. It does not use a signed single-download response.

These paths explain why bulk works while the menu's single-download does not.

| Module/path | Endpoint | Method | Success response | Frontend behavior | Status |
|---|---|---|---|---|---|
| Company Media menu one file | `/company-media/files/<id>/signed-download` | POST | `{url, expires_at}` | Shared helper requires `ok`, then would navigate to `url` | Broken — CONFIRMED |
| Project Documents menu one file | `/project-documents/files/<id>/signed-download` | POST | `{url, expires_at}` | Same shared helper | Broken — CONFIRMED |
| Company Media bulk one file | `/company-media/albums/<id>/files/bulk-signed-download` | POST | `{ok, kind:"direct", download:{url}}` | Navigate to `download.url` | Working path |
| Company Media bulk many | same | POST form | ZIP response | Native browser download | Working path |
| Daily Report original | `/attachments/<id>/download` | GET | 302 Location to signed original | Native navigation | Working path |

## Preview and HEIC verification

### Flow

```text
CompanyMediaFile → StorageObject original (active)
→ enqueue media job → image/video pipeline
→ WebP thumbnail + preview (or poster)
→ authorized thumbnail/preview route
→ signed derivative URL or local derivative cache
→ browser image/video presentation
```

### Findings

- Original download does not query derivatives and does not depend on `processing_status` in its current service method. HEIC decoder state therefore cannot cause the confirmed client-contract failure.
- `signed_preview()` validates original active state, selects only image `thumbnail`/`preview` or video `poster` derivatives, and returns `ok: true` only when a derivative exists. It deliberately does not sign an original as preview.
- The worker imports `pillow_heif` and registers its opener. `requirements.txt` pins `pillow-heif==0.18.0`; this establishes source/dependency intent, but it does not prove a running production worker image has successfully installed/loaded the decoder.
- Pipeline exceptions set the media job and `StorageObject.processing_status` to `failed`; the original remains active. Tests cover this behavior.
- Ready image/video preview returns a signed inline derivative URL. Processing/missing returns an `ok:false` status/message; failed image derivative returns unavailable.
- Media cache delivery uses `send_file` or `X-Accel-Redirect` from an authorized `CacheSource`; the cache route is called only with derivative sources.

### HEIC conclusion

- Original download: **RULED OUT** as an HEIC-dependent path.
- Preview: **CONFIRMED** as HEIC-dependent when the original needs decoder-based derivative generation. A decode/dependency/worker failure can make preview unavailable.
- Runtime information still needed: sanitized job status/error-code aggregates for HEIC items, worker dependency health, and a staging HEIC sample with a generated derivative. Do not requeue production jobs for this verification.

## Upload-limits verification

All Company Media limits currently resolve from shared storage/upload settings. There is no `COMPANY_MEDIA_*` setting in config, `.env.example`, or Compose.

| Limit | Config key | Default / observed local config | Effective Company Media value | Frontend knows | Hard-code |
|---|---|---:|---:|---|---|
| Selection files | `UPLOAD_SELECTION_MAX_FILES` | 500 | 500 | No | No |
| Selection bytes | `UPLOAD_SELECTION_MAX_BYTES` | 2 GiB | 2 GiB | No | No |
| Selection TTL | `UPLOAD_SELECTION_TTL_SECONDS` | 7,200 s | 7,200 s | No | No |
| Files per presign batch | `STORAGE_MAX_FILES_PER_BATCH` | 50 | 50 | Implicitly | JS slices at 50 |
| Batch bytes | `STORAGE_MAX_BATCH_SIZE_MB` | 512 MiB | 512 MiB | No | No |
| Absolute file cap | `UPLOAD_SINGLE_FILE_MAX_BYTES` | 300 MiB | 300 MiB ceiling | No | Error text says 300 MB |
| Image type cap | `STORAGE_MAX_IMAGE_SIZE_MB` | 50 MiB | 50 MiB | No | No |
| Video type cap | `STORAGE_MAX_VIDEO_SIZE_MB` | 500 MiB | min(500, 300) = 300 MiB | No | No |
| Upload concurrency | none | n/a | 3 | Yes, behavior only | `const concurrency = 3` |
| Upload URL TTL | `STORAGE_UPLOAD_URL_TTL_SECONDS` | 300 s | 300 s | Returned per item only | No |
| Download URL TTL | `STORAGE_DOWNLOAD_URL_TTL_SECONDS` | 300 s config | Company/Document single services currently pass literal `300` | No | Service literal |

The direct S3 POST file body bypasses Flask `MAX_CONTENT_LENGTH` and Nginx `client_max_body_size`; those limits can affect the small application JSON calls but not browser-to-storage file body. Provider POST policy enforces the per-file category cap plus configured multipart overhead, and Flask HEAD verification checks actual object size/content type after upload.

Accepted Company Media extensions are the image/video subset of the document policy, including JPG/JPEG, PNG, WebP, GIF, HEIC/HEIF, MP4, WebM, MOV, and M4V. The template accepts broad `image/*`, `video/*`, `.heic`, `.heif`; the backend policy is authoritative.

## Session-accounting verification

### Scope and lifecycle

Selection lookup requires matching actor, module type, target type, target ID, `pending` state, and unexpired time. Company Media calls it with `company_media`, `album`, and the requested album ID. A mismatch returns authorization failure; an expired/completed session returns a validation string.

### Accounting

- Count/bytes are declared at session creation.
- Presign checks declared quota before creating the batch.
- After the batch, `presigned_files` and `presigned_size_bytes` increase only for accepted items.
- Rejected items do not increase these counters.
- Failed HEAD verification marks the item failed but does not decrement session presigned counters. It therefore consumes declared-session quota; global active-storage usage is a separate calculation.
- Completion itself is idempotent only when the same item is already completed/active.

### Retry verification

The model has only `UNIQUE(upload_batch_id, client_file_id)`. There is no unique constraint or lookup over selection session plus client file ID.

The isolated in-memory runtime check issued two equivalent Company Media presign calls with the same session and client ID. Result: distinct batch IDs, 2 accepted items, 2 pending objects, `presigned_files=2`, `presigned_size_bytes=10`, and 2 batches. This **confirms** selection-session-level retry is non-idempotent and can consume quota twice.

There is no server concept of retrying “the same batch”: every presign call creates a new `UploadBatch`. Duplicate IDs are rejected only inside the one request payload.

### Browser session state and cancellation

- `company-media-upload.js` has no `sessionStorage` or `localStorage` usage. A reload cannot reuse an ID persisted by this JS.
- The current JS creates a new selection session for each upload invocation. A changed in-memory selection is normally submitted as a new session, but the server does not fingerprint or reconcile selections.
- No Company Media cancel endpoint exists.
- Generic `cleanup_pending_uploads()` exists with a 24-hour default and is dry-run by default, but repository scheduling shown here only explicitly wires Daily Report session cleanup. This is **PARTIALLY CONFIRMED**: generic cleanup logic exists; automatic Company Media session/object cleanup scheduling is not established by the inspected evidence.

### Migration assessment

The defect needs a fix; an application-only lookup can prevent ordinary duplicates but is not race-safe across concurrent requests. A migration is needed only if the approved design requires database-enforced selection-session/client-ID uniqueness. No migration is needed for the single-download contract, config separation, errors, or UI display.

## Error-contract verification

Current Company Media upload errors are predominantly HTTP 400 with `{error: "Vietnamese string"}`. They do not carry stable semantic codes, actual/max values, or retryability. The one unexpected presign exception path returns HTTP 502 with `{error, code:"CM-PRESIGN-001"}` and logs only stable context.

| Condition | Current source/result | HTTP/schema | Frontend outcome | Classification |
|---|---|---|---|---|
| Invalid/exceeded selection count or bytes | session creation combines both | 400 `{error}` | Generic thrown error | Grouped |
| Empty / >50 batch | presign validation | 400 `{error}` | Generic thrown error | String only |
| >512 MiB batch | presign validation | 400 `{error}` | Generic thrown error | String only |
| >300 MiB absolute file | presign validation | 400 `{error}` | Generic thrown error | String only |
| Type/category cap | item validation becomes `accepted:false,error` | 200 item-level string | Per-file “Bị chặn” | String only |
| Declared session quota count/bytes | one combined condition | 400 `{error}` | Generic thrown error | Grouped |
| Expired/completed session | selection lookup | 400 `{error}` | Generic thrown error | String only |
| Target/actor mismatch | selection lookup raises authorization | 403 abort | Generic browser failure | String/HTML depends handler |
| Idempotency conflict | no dedicated detection | n/a | n/a | Missing |
| S3 POST failure | XHR parses provider XML | no app API response | Per-file safe message/retry policy | Client-side only |
| HEAD verification failure | completion validation | 400 `{error}` | Per-file failure after upload | String only |

Provider exception handling is sanitized for the presign catch-all. The single-download route catches only `CompanyMediaError`; unexpected provider failures are not normalized by that route and need a future safe error boundary. No live exception was invoked.

## UI verification

- The Company Media template shows upload controls, a queue, and a result modal, but no selected/max count, byte quota, per-file cap, batch cap, or concurrency statement.
- The upload queue uses `aria-live="polite"`; the modal enumerates blocked/failed entries, so partial failure is visible per file.
- `formatSize()` only renders KB/MB, not B/KiB/MiB/GiB.
- There is no aggregate count/byte or per-file prevalidation before API calls.
- Batch slicing is hard-coded to `50`; concurrency is hard-coded to `3`.
- No resolved limits are rendered into the Company Media DOM.
- The upload button is disabled only when no pending item exists, not when a selection is invalid. Backend remains the effective enforcement.
- Existing Bootstrap classes make the modal/grid responsive at a basic level, but there is no dedicated mobile/limit-state behavior to verify.

## Security verification

| Area | Verification |
|---|---|
| Client bucket/key input | Browser sends file ID or upload metadata; server derives bucket/key. CONFIRMED. |
| File/album authorization | Single and bulk routes authorize server-side; bulk validates every selected file. CONFIRMED. |
| Archived file | Company Media permission denies inactive/deleted file before signing. CONFIRMED. |
| StorageObject state before single signing | Company Media signer does **not** check `upload_status`/`deleted_at`; Project Documents and Daily Report do. NEW FINDING. |
| Preview original disclosure | Preview selects derivatives only; original remains on separate download authority. CONFIRMED. |
| CSRF | JS uses `X-CSRFToken` on POST and app initializes CSRF. CONFIRMED. |
| CSP | Configured storage origin is appended to image/media/connect/frame sources. No evidence that CSP causes this fault. CONFIRMED/RULED OUT. |
| X-Accel | Internal Nginx location and cache API deliver validated relative derivative paths. CONFIRMED. |
| Signed URL TTL | Config defines 300 seconds; Company/Project Document single signer uses literal 300. NEW FINDING. |

## Confirmed vs unverified findings

### CONFIRMED

- Missing `ok:true` is the Company Media single-download root cause.
- Project Documents menu single-download shares the same mismatch.
- The broken browser code path does not initiate a signed-storage GET after POST 200.
- Bulk one-file/multi-file and Daily Report use different, working response/navigation contracts.
- HEIC is not on original-download code path; it can cause derivative preview failure.
- Effective shared limits are 500 files, 2 GiB selection, 7,200-second selection TTL, 50 files/512 MiB batch, 50 MiB image cap, 300 MiB effective video/absolute cap, and 3 hard-coded concurrent uploads.
- Company Media presign retry is non-idempotent at selection-session level and consumes declared-session counters again.
- Company Media has no cancel endpoint and no persisted browser session state.

### UNVERIFIED

- Provider signed GET returns 2xx after the client mismatch is fixed.
- CloudFly handling of Unicode response-content-disposition and expiry behavior.
- Production worker actually has a usable HEIC decoder and observed failed-job rate.
- Automatic operational cleanup of Company Media pending sessions/objects.

## Final recommendations

1. Repair the signed-download success contract and shared helper as one atomic frontend/backend release; retain top-level `url` for compatibility and include `ok:true`.
2. Add a browser-level regression test proving POST 200 is followed by navigation to the signed URL, for both Company Media and Project Documents.
3. Add explicit active/non-deleted `StorageObject` validation and safe provider-error normalization to Company Media's single signer.
4. Add Company Media-specific resolved limit settings with current shared values as fallbacks; publish them to the UI and replace hard-coded 50/3.
5. Define structured upload errors before changing UI messaging.
6. Decide whether race-safe retry idempotency is required. If yes, use a DB-enforced selection-session/client-ID design and migration; otherwise document the residual concurrent-retry risk.

## Audit conclusion table

| Finding | Audit cũ | Xác minh mới | Confidence | Hành động đề xuất |
|---|---|---|---|---|
| Missing `ok:true` blocks Company Media single download | Hypothesis | CONFIRMED | Confirmed by code + isolated runtime | Fix success contract/helper together |
| Project Documents has same defect | Hypothesis | CONFIRMED | Same route shape + shared handler | Include in Phase 1 regression fix |
| Daily Report works through GET/302 | Claim | CONFIRMED | Direct route/UI comparison | Preserve behavior |
| Company Media bulk works through separate contract | Claim | CONFIRMED | Route + JS comparison | Preserve regression coverage |
| HEIC causes original failure | Not asserted as fact | RULED OUT | Original signer does not use derivatives | Do not diagnose download as HEIC |
| HEIC can cause preview failure | Claim | CONFIRMED | Pipeline/status/test evidence | Add staging decoder/derivative checks |
| Shared limits/no Company config | Claim | CONFIRMED | Config/env/JS evidence | Introduce Company-specific fallbacks |
| Presign retry is non-idempotent | Hypothesis | CONFIRMED | Code + isolated runtime | Design explicit idempotency; assess migration |
| No Company cancel endpoint | Claim | CONFIRMED | Route/JS inventory | Decide lifecycle UX |
| Company signer skips storage active/deleted check | Not in old audit | NEW FINDING | Service comparison | Fix in same download hardening phase |
