# Phase 7.1 — Strict storage policy

Uploads use an optional server-side selection session (two-hour TTL) and enforce 500 files/2 GB per selection, 50 files/512 MB per batch, and 300 MB per object. The direct-upload MIME policy is module-aware; Company Media is image/video only, while Document Library permits the documented files including HEIC/HEIF and ZIP.

New multi-file downloads are server-streamed: Flask downloads the original objects into a request-local temporary directory, creates the ZIP, returns it directly, then removes the temporary files. No new ZIP is uploaded to S3/Object Storage and no new `BulkDownloadJob` is created. The `bulk-downloads` prefix and job cleanup exist only for ZIPs created by legacy Phase 7 flows.

Single downloads are capped at 300 MB. ZIP downloads are capped at 100 files and 300 MB total source size. Set temporary disk capacity above 300 MB per concurrent ZIP request and configure Gunicorn/proxy timeouts for a 300 MB response. Storage is capped at 500 GB and downloads are estimated against a 1 TB UTC-month quota; events never store URLs or request fingerprints.
