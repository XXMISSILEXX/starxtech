# Phase 2 implementation report — Company Media config and upload contract

## Scope completed

Company Media now resolves its own upload limits from one public helper:
`app.storage.limits.get_company_media_upload_limits()`. The same resolved
payload drives Company Media backend validation and the album template. It does
not contain storage credentials, object keys, bucket names, or signed URLs.

The dedicated settings are:

| Setting | Default effective value | Fallback when unset |
|---|---:|---|
| `COMPANY_MEDIA_MAX_SELECTION_FILES` | 500 | `UPLOAD_SELECTION_MAX_FILES` |
| `COMPANY_MEDIA_MAX_SELECTION_BYTES` | 2,147,483,648 | `UPLOAD_SELECTION_MAX_BYTES` |
| `COMPANY_MEDIA_MAX_FILES_PER_BATCH` | 50 | `STORAGE_MAX_FILES_PER_BATCH` |
| `COMPANY_MEDIA_MAX_PRESIGN_BATCH_BYTES` | 536,870,912 | `STORAGE_MAX_BATCH_SIZE_MB * 1024 * 1024` |
| `COMPANY_MEDIA_MAX_FILE_BYTES` | 314,572,800 | `UPLOAD_SINGLE_FILE_MAX_BYTES` |
| `COMPANY_MEDIA_MAX_IMAGE_BYTES` | 52,428,800 | `STORAGE_MAX_IMAGE_SIZE_MB * 1024 * 1024` |
| `COMPANY_MEDIA_MAX_VIDEO_BYTES` | 314,572,800 | `min(STORAGE_MAX_VIDEO_SIZE_MB * 1024 * 1024, UPLOAD_SINGLE_FILE_MAX_BYTES)` |
| `COMPANY_MEDIA_UPLOAD_CONCURRENCY` | 3 | 3 |
| `COMPANY_MEDIA_UPLOAD_SESSION_TTL_SECONDS` | 7,200 | `UPLOAD_SELECTION_TTL_SECONDS` |

Explicit values must be positive integers. Invalid zero, negative, and
non-integer values are rejected; they are never silently treated as a fallback.
Image/video values are clamped by the absolute Company Media file ceiling, so
the rendered payload remains the effective server limit.

## Resolved payload and backend use

The album upload section carries a safe JSON `data-company-media-upload-limits`
payload with:

```json
{
  "max_selection_files": 500,
  "max_selection_bytes": 2147483648,
  "max_files_per_batch": 50,
  "max_batch_bytes": 536870912,
  "max_file_bytes": 314572800,
  "max_image_bytes": 52428800,
  "max_video_bytes": 314572800,
  "upload_concurrency": 3,
  "session_ttl_seconds": 7200
}
```

Backend enforcement uses it for selection count/bytes/TTL, presign batch
count/bytes, absolute per-file size, and image/video effective caps. Project
Documents and Daily Report retain their existing shared or module-specific
validation paths.

## Structured upload errors

Company Media application errors use:

```json
{"ok": false, "error": {"code": "…", "message": "…", "details": {}, "retryable": false}}
```

Implemented codes are `invalid_selection_file_count`,
`selection_file_count_exceeded`, `invalid_selection_total_bytes`,
`selection_total_bytes_exceeded`, `empty_presign_batch`,
`presign_batch_file_count_exceeded`, `presign_batch_bytes_exceeded`,
`file_size_exceeded`, `image_size_exceeded`, `video_size_exceeded`,
`selection_declared_file_quota_exceeded`,
`selection_declared_byte_quota_exceeded`, `selection_session_expired`,
`selection_session_target_mismatch`, `head_verification_failed`, and
`presign_unavailable`. `s3_upload_failed` and `idempotency_conflict` remain
separate client-/future-lifecycle contract codes. Direct browser-to-provider
POST failures now map locally to `s3_upload_failed` with a safe Vietnamese
message and no raw XML/provider body; retry eligibility retains the existing
HTTP/status policy. `idempotency_conflict` is reserved only; Phase 2 does not
implement idempotency.

Selection and batch validation errors return HTTP 422; declared quota errors
return 409; an expired session returns 410; target mismatch returns 403 without
target metadata; presign unavailability returns 502 and is retryable. HEAD
verification failure returns 422 and is retryable. Provider XML, raw provider
responses, signed URLs, bucket names, and object keys are not reflected.

Partial presign rejection retains compatibility with old clients using the
temporary `error_message` string. New clients receive an `error` object:

```json
{"client_file_id":"…","accepted":false,"error":{"code":"image_size_exceeded","message":"…","details":{"actual_bytes":60000000,"max_bytes":52428800},"retryable":false},"error_message":"…"}
```

`error_message` is deprecated and should be removed only after all clients use
the structured object.

## Frontend and deployment changes

`company-media-upload.js` reads positive `max_files_per_batch` and
`upload_concurrency` from the server payload. Missing or malformed payloads
safely retain the prior 50-file/3-worker behavior. It parses both structured
and legacy string errors and continues to map provider POST XML to safe local
messages rather than displaying raw XML. It intentionally does not add the
selected/max UI or alter retry/session behavior. `STATIC_ASSET_VERSION` is
bumped to `20260730-8302`.

The environment template and Compose anchor expose every Company Media setting.
No migration, schema/data change, storage-object change, deployment, commit,
or push is included.

## Tests and remaining work

Added `tests/test_company_media_upload_limits.py` and extended the Company
Media JS contract test. Coverage includes defaults/fallbacks/overrides,
invalid settings, selection and batch boundaries, separate count/bytes codes,
image/video/absolute caps, partial rejection, declared quotas, expiry/target
mismatch, template payload, and JS fallback/structured-error parsing.

Phase 3 remains: selected/max accessible UI, client-side aggregate feedback,
and an approved session/retry idempotency design. A database migration is only
needed if that future design requires race-safe selection-session/client-ID
uniqueness; none was created for Phase 2.

Final local verification completed successfully:

```text
python -m compileall app                 # passed
pytest -q                                # 459 passed in 296.53s
node --test tests_js/*.test.js           # 7 passed
git diff --check                         # passed
```
