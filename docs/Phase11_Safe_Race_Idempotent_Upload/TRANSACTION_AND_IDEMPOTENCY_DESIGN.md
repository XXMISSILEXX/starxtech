# Transaction and idempotency design

## Canonical key and metadata

Use `(selection_session_id, client_file_id)` for Company Media. A session already binds actor, `company_media`, album target type/ID (`app/storage/services.py:211-218`), so tenant/module/album need not be duplicated in the unique key. Authorization and scope checks still occur before replay.

Compare canonical item metadata: trimmed original filename; canonical MIME; normalized extension; exact declared size; optional checksum only if it is part of the accepted canonical request. Current validator trims name, lowercases extension, canonicalizes aliases and saves expected MIME (`app/storage/validation.py:26-68`; `app/storage/file_types.py:22-30`). Filename is only key-sanitized, not DB-normalized (`app/storage/keys.py:32-64`).

Do not compare object key, signed URL, dates, browser `lastModified`, progress, or policy. Browser sends only ID/name/MIME/size (`app/static/js/company-media-upload.js:268`), and no full-file hash should be added. Empty MIME is only accepted for HEIF/HEIC fallback; standard types require expected MIME.

Same key with changed canonical metadata: HTTP 409 with safe response:

```json
{"ok":false,"error":{"code":"idempotency_conflict","message":"Yêu cầu tải tệp không khớp với lần gửi trước.","details":{},"retryable":false}}
```

No prior metadata, object key, bucket, ID, policy or URL may be exposed.

## Recommended create-or-replay algorithm

Use database unique constraint plus `IntegrityError` savepoint recovery. It fits existing repo idiom (`db.session.begin_nested()` and `IntegrityError` in `app/reports/services.py:193-230`) and is race-safe.

1. Authenticate/authorize album upload; load scoped selection session and validate presign eligibility.
2. Canonicalize/validate files. Query existing `(session, client ID)` items. Matching metadata is replay; mismatch is 409; only unknown valid entries are new.
3. Lock the session with `SELECT ... FOR UPDATE` only while recomputing/checking/incrementing its counters; re-query existing keys after lock. Lock serializes counters but does not replace constraint.
4. Per unknown entry, in `begin_nested()`, make fresh opaque key, StorageObject and item with local session FK, then flush. On unique loss, roll back only savepoint, re-query winning item, metadata-check and replay. Loser StorageObject rolls back with savepoint.
5. Create/increment batch and session counters only for winner inserts. Commit canonical DB outcome before external signer call.
6. Sign canonical/replayed object after commit. A fresh policy for the same key is allowed; signer failure is retryable without new DB records.

## Complete and finalize contracts

Keep generic complete fast replay but present a backward-compatible additional field:

```json
{"ok":true,"status":"completed","idempotent_replay":true}
```

For concurrent complete, lock item/object before state decision or catch `CompanyMediaFile` unique conflict in a savepoint then re-query. Never enqueue on an existing media file. Existing `uq_company_media_files_storage_object` ensures one media record, but handler/lock ensures loser returns success rather than 500.

Finalize must check authorization/scope first. If terminal `completed`, return persisted counts/status and `idempotent_replay:true`; only pending session can apply failure IDs. Different terminal retry payload behavior (replay vs 409) is open, but must never rewrite history.

## Failure matrix

| Case | Required result |
| --- | --- |
| Sequential same presign/key/metadata | same item/object/key; counters unchanged; fresh policy allowed. |
| Same key/different canonical metadata | 409 safe conflict; no signer/new DB rows. |
| Concurrent presign | one canonical row/key and one counter increment; loser replays. |
| Unique race loss | savepoint removes loser object/item; outer request stays usable. |
| Signer fails after commit | safe retryable response; later replay signs canonical item. |
| Complete sequential/concurrent | one active object/file/job; replay success. |
| Finalize replay | same terminal result, no repeat mutation. |
| Presign expired | 410, no replacement session/object/item. |

Query-first without constraint is insufficient. `INSERT ... ON CONFLICT` is viable PostgreSQL-specific alternative, but ORM query-first + constraint/savepoint is the smallest repository-consistent solution. Session locking alone is not an invariant if any path misses it.
