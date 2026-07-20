# Security risk review

| Threat | Risk | Mitigation |
|---|---|---|
| Leaked signed URL | bearer URL works until expiry | private bucket, 2–5 min GET TTL, no DB storage/logging URL, referrer policy, issue only after ACL; revoke blocks new URLs, not existing TTL |
| Object key guessing | unauthorized object access | UUID keys, private bucket, block public ACL/policy, no direct object listing |
| MIME/extension spoof | active content/malicious download | backend allowlist both normalized extension + declared MIME; completion HEAD; safe disposition attachment for HTML/SVG/script/unknown; browser MIME is not proof |
| Malicious file/no scan | malware distribution | restrictive types/size, attachment disposition, audit; add async AV quarantine before broad rollout if documents are untrusted |
| Storage abuse | cost/DoS | per-type size caps, module/project quotas, short upload TTL, POST length policy, rate limit presign, pending cleanup |
| Pending/orphan object | cost/data inconsistency | pending state invisible, HEAD completion, scheduled idempotent cleanup/delete and audit |
| Race/revoked access | URL issued after permission change | transaction/recheck ACL on complete and every GET; short TTL; audit share/revoke and signed URL issuance |
| Thumbnail spoof | misleading/malicious content | thumbnail key generated server-side; bind to same storage object, WebP allowlist, placeholder fallback; future worker verification |
| Broad CORS/public bucket | cross-site upload/read | exact app origins/methods/headers, no wildcard, block public access, encryption/least-privilege IAM prefix policy |
| Path traversal/filename injection | storage/UI attack | never use user filename as key/path; escape display values; Content-Disposition filename generated safely |
| Delete mismatch | object remains or wrong object deleted | metadata lifecycle first, retention cleanup worker, object key immutable, idempotent delete, reconciliation report |
| Download abuse | bandwidth/cost | short URLs, rate limiting signed-url endpoint, audit downloads, quotas; CDN only later with private signed policy |
| Redis loss/Celery duplicate | lost or repeated work | PostgreSQL job state source of truth, reconcile Beat, idempotent DB-locked task, unique derivative type/object |
| Infinite retry/queue starvation | cost and delayed work | finite max retries, backoff/jitter, time limits, separate image/video queues and low video concurrency |
| Batch presign abuse | excessive signed URLs/storage cost | max files/total size/pending batches, target quota and rate limit; per-item validation before key issuance |
| ffmpeg/decompression/temp attack | RCE/DoS/disk leak | no shell=True, argument list/timeouts/resource limits, Pillow bomb limits, temp dir per job/finally cleanup, worker non-root |
| Revoke during upload/partial orphan | unauthorized activation/orphan object | strict ACL recheck on complete, per-item pending state, HEAD verify and cleanup/reconcile |
| Derivative spoof | malicious/mismatched thumbnail | worker-generated UUID derivative keys, original linked by internal ID, immutable type mapping, never trust client thumbnail |

## Bucket/IAM notes

Use a dedicated private bucket per environment, block public access, SSE encryption, TLS-only policy, versioning/lifecycle decision documented, access logs/provider audit enabled. Application IAM may only `PutObject/GetObject/HeadObject/DeleteObject` under prescribed prefixes; it must not list arbitrary buckets or change policy. Browser receives only presigned capability, never cloud credentials.

## Audit events

Record `storage.presign`, `storage.complete`, `storage.complete_failed`, `storage.cleanup`, document/media folder/album create/update/move/archive/restore/share/revoke, file metadata upload/archive/restore, and signed view/download issuance. Store actor, entity IDs, scope, object key hash/ID and non-secret metadata; never store signed URL, authorization headers, raw file bytes or credentials.
