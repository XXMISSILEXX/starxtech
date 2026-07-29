# CloudFly direct-upload manual test checklist

Run on staging or local development configured with a non-production private
CloudFly bucket. Do not use a production bucket, credentials, or real business
media for these checks.

## Before testing

- Browser origin is present explicitly in the bucket CORS allow-list.
- CORS permits `POST`, `PUT`, and `HEAD`, plus `Content-Type` and
  `x-amz-meta-sha256` request headers. Do not use a wildcard origin.
- Worker, Redis, and a non-production S3-compatible bucket are healthy.
- Browser DevTools Network is open with request bodies and query strings
  redacted before sharing screenshots/logs.

## Company Media POST upload

For each case, wait for the result overlay and close it manually only after
checking the summary. Confirm the grid refreshes after close, not before.

| Case | Files | Expected result |
| --- | --- | --- |
| Small images | PNG a few KB, JPEG about 20 KB, GIF about 200 KB | S3 POST returns 2xx; all complete and derivative jobs are queued. |
| Medium images | JPEG 1–3 MB, HEIC 1–3 MB | S3 POST returns 2xx; HEIC safely shows processing/preview state. |
| CloudFly regression sizes | JPEG about 5.8 MB, 6.9 MB, 8.5 MB | No `EntityTooSmall`; each POST policy allows multipart overhead and HEAD reports the exact original file size. |
| Batch scale | 1, 5, then 20–25 files | At most three browser requests upload simultaneously; overall and per-file progress move correctly. |
| Duplicate names | Two files with exactly the same filename | Each result belongs to its own `client_file_id`; both can succeed independently. |
| Blocked middle item | One unsupported file between allowed images | Overlay lists it as **Bị chặn** with a reason; it is not counted as an S3 failure. |
| Simulated S3 error | Make one POST return 5xx/network failure | Remaining files continue; overlay lists only that file as failed. |
| Retry | Click **Thử lại file lỗi** | A fresh presign/session is requested; no old signed form is reused; a successful retry creates no duplicate media row. |

Inspect only safe diagnostics: client file ID, filename, byte count, HTTP
status, provider error code/request ID, elapsed time, and retry count. Never
copy a presigned URL, policy, signature, access key, or secret into tickets.

## Other direct-upload regression

- Project Documents: upload a small PDF and an image; verify POST success,
  exact HEAD validation, authorized file creation, and worker enqueue only for
  the image.
- Daily Report attachments: upload an allowed image through the existing PUT
  flow; verify all item completion before report finalization and derivative
  processing after the report commits.
- Partner photos, account avatar, and system branding: upload one image each;
  these are backend-mediated and must keep their existing private storage path.
- Try a zero-byte file and a file one byte above its category limit. Presign
  must reject them before object-storage upload.
- For a controlled test object, make HEAD report one byte too small, one byte
  too large, or missing. Complete must fail, object metadata must not become
  active, and no derivative job may be enqueued.
