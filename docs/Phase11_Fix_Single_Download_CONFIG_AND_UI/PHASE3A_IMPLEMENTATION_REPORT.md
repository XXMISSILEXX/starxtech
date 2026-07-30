# Phase 3A implementation report — Company Media upload UI

## Scope

Phase 3A implements the Company Media upload selection UX only. It reads the
resolved public limit payload rendered by Phase 2 and keeps the backend as the
authoritative validator. It does not change selection-session accounting,
retry/idempotency behavior, models, migrations, backend limits, Project
Documents, Daily Report, storage providers, deployment, commits, or pushes.

## Files changed

- `app/templates/company_media/album.html`
- `app/static/js/company-media-upload.js`
- `app/static/css/app.css`
- `app/company_media/routes.py` (safe initial byte labels for the server-rendered UI)
- `app/config.py`, `app/__init__.py`, `.env.example` (one static asset version bump)
- `tests/test_company_media_upload_limits.py`
- `tests/test_signed_download_contract.py`
- `tests_js/company-media-upload.test.js`
- this directory's `README.md` and `TEST_AND_ROLLOUT_PLAN.md`

## DOM contract and UI states

The upload card retains `data-company-media-upload` and
`data-company-media-upload-limits`; the latter contains the safe resolved
Phase 2 payload. It adds explicit selected count/maximum, selected bytes/
maximum, valid count, blocked count, batch estimate, validation alert, queue,
clear action, and result modal markers. The static labels are rendered from the
payload by JavaScript: image cap, video cap, batch file/byte cap, and
concurrency.

`data-company-media-upload-state` identifies normal, near-limit, partial,
invalid, and uploading states. Near-limit begins at 80% of count or byte
capacity and includes a text indicator through the validation/summary state;
exceeded selection presents text plus an alert and disables upload.

## Pre-validation and partial acceptance

The browser validates empty selections, aggregate count and bytes, the
absolute cap, image cap, video cap, unsupported extension, and a single file
that cannot fit in a presign batch. It uses one binary `formatBytes` helper for
B, KiB, MiB, and GiB. A malformed/missing payload retains only the historic
safe 50-file/3-concurrency fallback and disables upload until server limits are
available; it never invents higher selection/file/byte limits.

Blocked files remain visible with their reason, but are not included in
selection-session `file_count`, `total_size_bytes`, or presign metadata.
Consequently `declared_files` and `declared_size_bytes` always describe only
the valid files intended for upload. A partial selection remains uploadable
when at least one valid file exists and neither aggregate selection cap is
exceeded.

## Batch builder and errors

`buildBatches()` is the single slicing helper for both batch estimate and
presign flow. It closes a batch when either `max_files_per_batch` or
`max_batch_bytes` would be exceeded; a file larger than the batch cap is
reported safely rather than included.

`formatUploadError()` handles Phase 2 structured objects, legacy strings, and
the compatibility `error_message`. For all supported Phase 2 codes it renders
actual/max values when details are supplied. XML/provider bodies, signed URLs,
and other unsafe markup are discarded in favor of safe messages. Browser S3
POST failures remain the existing safe `s3_upload_failed` flow and retain the
existing retry policy.

## Accessibility and mobile

Summary updates use `aria-live="polite"`; aggregate validation uses
`role="alert"`; file-level errors are connected to their queue row; buttons use
their actual disabled state and aria-disabled state. The dropzone supports
keyboard picker activation, and result-modal close restores focus to its
trigger. The queue uses readable status text rather than color alone.

Narrow-screen rules at the 320–430px target range collapse limit columns,
allow filenames to wrap, retain 38px remove targets, constrain the modal to
the viewport, and stack chooser/clear/upload actions. A standard picker button
remains available, so mobile does not depend on drag/drop.

## Static asset version

`STATIC_ASSET_VERSION` changed once from `20260730-8302` to
`20260730-8303` in the normal config, test default, and `.env.example`.

## Tests and manual verification

Added Node coverage for valid/malformed payloads, byte formatting, selection
summary/remove, partial acceptance metadata, count/byte boundaries, image/video
boundaries, batch count/byte splitting, oversized batch item, structured/legacy
error rendering, XML sanitization, double-submit guard, and accessibility
markers. Python coverage verifies the server payload, UI markers, absence of
secret setting names, initial binary limit labels, and the versioned asset.

Completed local commands:

```text
python -m compileall app                                      # passed
pytest -q tests/test_company_media_upload_limits.py \
  tests/test_company_media_permissions_ux.py \
  tests/test_signed_download_contract.py                       # 40 passed
node --test tests_js/*.test.js                                 # 7 passed
git diff --check                                               # passed
```

`pytest -q` was invoked twice (including once outside the sandbox), but the
execution harness terminated it after roughly 30 seconds while it was still
printing progress dots and before it returned an exit summary. It therefore
cannot be reported as a completed full-suite result in this environment; the
targeted Python coverage and full JavaScript suite above completed.

Manual browser checks still required: desktop plus 320/375/390/430px, 3 small
media files, blocked 50MiB+ image, remove/clear, 100-file batch estimate,
byte-driven batch estimate, offline S3 POST error, and keyboard/focus flow.
No real storage/provider request was made by automated local verification.

## Remaining Phase 3B work

The confirmed selection-session retry/idempotency issue remains untouched.
Phase 3B must decide retry reuse, concurrent-tab semantics, cancellation, and
whether database-enforced uniqueness requires an additive migration. No
migration was created in Phase 3A.
