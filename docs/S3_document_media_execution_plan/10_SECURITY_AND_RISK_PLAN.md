# Security and Risk Plan

## Core rules

- Bucket private.
- No public object.
- No signed URL in DB/log/audit.
- Signed URLs short-lived.
- Backend checks permission before issuing URL.
- Object keys UUID.
- Original filename display-only.
- No GET mutation.
- POST CSRF for state changes.
- HEAD verify complete upload.
- Strict complete after ACL revoke.

## Threats and mitigations

| Threat | Mitigation |
|---|---|
| Signed URL leaked | TTL 2–5 min, private bucket, no logging, issue only after ACL |
| Object key guessing | UUID keys, private bucket, no list access |
| MIME spoofing | extension + MIME allowlist, HEAD verify, safe disposition |
| Malware | restrict types/size, audit, attachment disposition, AV phase later |
| Storage abuse | batch limits, per-file caps, quota, rate limit presign |
| Pending/orphan objects | pending invisible, cleanup/reconcile |
| ACL revoked mid-upload | complete rechecks ACL, strict block |
| Redis loss | PostgreSQL job state source of truth, Beat requeue |
| Duplicate Celery task | idempotent job and derivative unique constraints |
| Infinite retry | max attempts, backoff, jitter, terminal failed |
| Video queue starvation | separate queue, low video concurrency |
| ffmpeg injection | no shell=True, argument list |
| Decompression bomb | Pillow limits |
| Temp file leak | per-job temp dir + finally cleanup + Beat cleanup |
| Derivative spoof | worker-generated keys only |
| Broad CORS | exact origins/methods/headers, no wildcard |
| Delete mismatch | metadata archive first, retention cleanup, object immutable |

## IAM/bucket

Minimum app/worker IAM:

```text
PutObject
GetObject
HeadObject
DeleteObject
```

Only under approved prefixes.

Must not allow:

```text
List all buckets
Change bucket policy
Public ACL
Wildcard admin actions
```

## Audit events

Log:

```text
storage.presign_batch
storage.presign_item_rejected
storage.complete
storage.complete_failed
storage.signed_url_issued
storage.cleanup
media.job_created
media.job_started
media.job_succeeded
media.job_failed
document.folder.share/revoke
media.album.share/revoke
file.archive/restore
```

Never log:

```text
signed URL
S3 credentials
Authorization header
raw file bytes
```

## Rate limits

Recommended:

```text
presign-batch: per user/IP/target
signed-url endpoint: per user/file
complete-upload: per user/object
share changes: per admin/operator
```
