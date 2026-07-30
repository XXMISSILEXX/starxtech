# Test and rollout plan

## Phase 2 local result

Phase 2 adds SQLite/FakeStorage and Node static-contract coverage for resolved
limits, structured selection/batch/session errors, partial rejection, and the
server-rendered JS limits payload. The full repository verification commands
and their final results are recorded in `PHASE2_IMPLEMENTATION_REPORT.md`.
No real provider request, migration, deployment, or production smoke test is
part of Phase 2.

## Test matrix

| Area | Required tests |
|---|---|
| Company Media single download | JPG, PNG, WebP, HEIC; active/archived; authorized/unauthorized; missing/inactive storage object; provider exception; missing URL; `ok:true`; POST followed by navigation request |
| Project Documents single download | Same response contract/navigation cases; ensure bulk-one remains working |
| Daily Report regression | GET original download remains 302 to signed URL; unauthorized remains denied |
| Company Media bulk | One direct response, multi-file ZIP, authorization per file, missing source, count/byte bulk limits |
| Preview | Ready thumbnail/preview/poster, processing, failed, missing derivative, HEIC with WebP, HEIC without WebP, no original URL for view-only actor |
| Cache/CSP | Cache disabled redirect, cache hit/miss, X-Accel relative-path header, storage-origin CSP sources |
| Limits | 499/500/501 selection files; just below/equal/above 2 GiB; 49/50/51 batch files; just below/equal/above 512 MiB; 50 MiB image and 300 MiB effective video boundaries |
| Sessions | Same-ID repeated presign, same-ID concurrent requests, failed HEAD retry, selected change, session expiry, album mismatch, partial success, finalization, cancel if added |
| UI/accessibility | Add/remove/drop count/byte updates, invalid disabled state, actual/max text, B/KiB/MiB/GiB formatting, aria-live, keyboard dropzone, mobile layout, retryable/non-retryable errors |

## Local verification after implementation

Use only repository tests with SQLite in-memory and FakeStorage. Add an explicit browser-capable test or minimal DOM test for the actual `requestJson`/navigation contract; server route tests alone cannot detect this defect.

Suggested checks:

```bash
pytest -q tests/test_company_media_permissions_ux.py \
  tests/test_storage_namespace_bulk_download.py \
  tests/test_media_processing_foundation.py \
  tests/test_project_documents_upload.py
node --test <new-browser-contract-test>
git status --short
```

Do not invoke real presign/upload endpoints as part of local verification.

## Staging verification

Use a dedicated non-production bucket and disposable test files. Do not paste signed URLs into tickets or logs.

1. Confirm a Company Media menu click gets POST 200 and exactly one browser navigation/GET to storage.
2. Confirm Content-Disposition downloads the expected ASCII, space-containing, and Unicode filenames.
3. Confirm signed URL works before expiry and fails predictably after expiry.
4. Confirm direct upload CORS for exact staging origin, POST/HEAD, and required headers.
5. Upload a valid HEIC fixture, wait for worker completion, then verify generated WebP preview and original download separately.
6. Use a deliberately unsupported/corrupt HEIC fixture only in staging; confirm original stays downloadable and preview displays safe unavailable state.
7. Exercise configured boundaries without exceeding staging quota.

## Production smoke test

Run only after staging passes, with a pre-approved non-sensitive Company Media item and an authorized operator:

1. Open the album and use menu single download.
2. In browser DevTools, confirm POST success followed by navigation to storage; do not export/copy the signed URL.
3. Confirm a standard image preview and one existing HEIC preview state.
4. Check stable application event/error codes and worker health counters only.
5. Verify Project Documents menu single download and Daily Report original download as regressions.

## Observability

Record only: module, endpoint/event code, actor ID, file ID, HTTP status, provider status class, response contract state, selection count/bytes, and retry outcome. Exclude signed URLs, object keys, bucket names, credentials, file bytes, and provider response bodies.

Useful measures after release:

- single-download POST successes vs browser-navigation failures;
- provider GET 2xx/4xx/5xx class counts where available;
- upload error code counts and actual/max distributions;
- duplicate/reused presign item rate;
- derivative queued/succeeded/failed counts by normalized MIME type.

## Rollout order

1. Merge tests first with no behavior change where practical.
2. Release Phase 1 backend and static asset version as one unit.
3. Run staging and production smoke test.
4. Release Phase 2 config/error contract with defaults matching current limits.
5. Release Phase 3 UX/session lifecycle.
6. If approved, deploy additive idempotency migration before the code that relies on it.

## Rollback

- Roll back matched backend/frontend artifacts together for the single-download contract.
- Keep Company Media config fallback to shared settings so new environment variables can be unset safely.
- Do not drop an additive idempotency schema during an incident rollback.
- Preserve only sanitized diagnostic identifiers needed for post-incident analysis.
