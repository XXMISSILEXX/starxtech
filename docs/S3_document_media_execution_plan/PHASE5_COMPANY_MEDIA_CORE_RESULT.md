# Phase 5 — Company Media Core

Company Media provides independent company image/video albums with RBAC and optional restricted album ACL. It reuses shared storage objects, upload batches, signed runtime URLs, and Celery derivatives. Archive is metadata-only; signed URLs are never stored.

Routes include `/company-media`, album lifecycle/permissions, batch presign/complete, and signed preview/download. No transcoding, Office preview, ZIP download, file-level ACL, or hard delete is included.
