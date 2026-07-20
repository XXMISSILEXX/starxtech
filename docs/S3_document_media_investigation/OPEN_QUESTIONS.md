# Open questions requiring approval

## Business

1. Is project assignment a baseline allow to root documents, or must every folder be explicitly shared?
2. Are restricted/private folders required in MVP? If yes, approve the chosen inheritance/override rule before schema/UI.
3. Which role owns documents: should PROJECT_MANAGER receive delete/share by default, and can REPORTER create folders?
4. Which roles may view/upload Company Media? Is it company-wide read or album-share only?
5. Exact file allowlist, per-file caps (document/image/video/audio), project/album/user quotas, and whether ZIP/executable/HTML/SVG are prohibited.
6. Retention: archive duration, legal hold, actual S3 deletion timing, restore window, and whether “delete” UI always means archive.
7. Is external/public sharing ever planned? This design assumes no.
8. Are captions/tags/event date required and is Vietnamese full-text search needed later?

## Technical and security

1. Which provider (AWS S3, MinIO, Cloudflare R2, other), region/endpoint, SDK compatibility and support for Presigned POST/content-length policy?
2. Bucket per environment/account, encryption/KMS, versioning, lifecycle, logs, CORS production/staging/local origins, and IAM role provisioning owner.
3. Browser support constraints for canvas/video frame thumbnail generation; required max dimensions and acceptable fallback.
4. Is SHA-256 practical client-side for target file sizes, or should checksum verification be optional/ETag/provider-specific?
5. Is antivirus/quarantine required before documents are broadly downloadable? If not, who accepts residual risk?
6. What scheduler infrastructure is available for pending cleanup/reconciliation (cron, worker, platform scheduler), and what alert channel exists?
7. Do signed viewer URLs need Content-Disposition, watermarking, download logging, IP restrictions, or CDN later?
8. Do admins bypass ACL for recovery/audit, and should such access require an extra reason/audit field?
9. Is a root folder record per project created lazily or by project creation workflow? How are existing archived projects handled?
10. Are DB partial unique indexes/PostgreSQL-only constraints acceptable for active sibling naming, or must SQLite tests mirror semantics in service validation?
11. Should Celery result backend remain Redis, or should results be disabled/short-lived because PostgreSQL is the only durable job state?
12. What are approved maximum files/batch, total batch bytes, image/document/video/audio bytes, and per-project/album quota?
13. Is multipart upload required for large video in the first release; if so, what video maximum duration and resumability expectation applies?
14. Is poster-only video preview sufficient, or is transcoding explicitly required later?
15. Must antivirus/quarantine run before a worker reads objects, before user download, or both?
16. After ACL revoke during presigned upload, approve strict completion block (recommended) or allow completion if upload started?
17. Approve `UploadBatchItem` as a separate table for rejected/partial/retry states?
18. Is polling batch/job progress sufficient for MVP, or is SSE/WebSocket required?
