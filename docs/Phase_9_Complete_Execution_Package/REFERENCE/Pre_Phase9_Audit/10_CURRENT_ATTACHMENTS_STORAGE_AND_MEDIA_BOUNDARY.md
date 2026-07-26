# Attachments, storage and media boundary

**VERIFIED.** `ReportAttachment` stores metadata plus `storage_object_id`; private bytes are `StorageObject` with UUID-derived key in `direct_uploads.presign`. `attachments.routes` authorizes every view/download/status through report scope, then redirects to short-lived signed object/derivative URLs. It never exposes a public local path.

`UploadSelectionSession`, `UploadBatch`, `UploadBatchItem` track daily-report selection and `client_section_id`; `complete` HEAD-verifies object metadata; finalize activates object/marks item finalized. `MediaProcessingJob` and `StorageDerivative` produce thumbnail/preview; status reports processing/recovery/failed states. `daily-report-create-v2.js`, `report-direct-upload.js`, `report-attachment-status.js`, and `media-preview-modal.js` form the client boundary; allowed V2 metadata includes JPG/PNG/WebP/HEIC/HEIF, with HEIC local preview support.

Phase 9 must only add metadata/relations around these interfaces. It must not restore public/local serving, replace PUT/HEAD/finalize, or attach objects without session authorization. Cleanup and delete are idempotency-sensitive.
