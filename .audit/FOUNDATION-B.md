# FOUNDATION-B.md — Storage & media processing infrastructure deep pass

Read-only. Scope: `app/storage/` (`providers.py`, `keys.py`, `validation.py`,
`quota.py`, `services.py`, `exceptions.py`, `file_types.py`),
`app/media_processing/` (`pipeline.py`, `services.py`, `tasks.py`),
`app/bulk_downloads/` (`services.py`, `tasks.py`), `app/display_images.py`.
Every file in this list was read in full. `FOUNDATION-A1.md` and
`FOUNDATION-A2.md` (both GUARANTEES/NOT GUARANTEED pairs) were re-read
before starting — this document builds on, and in one place (§1) directly
answers, A2's "no data-layer project scoping" finding.

---

## 1. Object key construction (`app/storage/keys.py`) — verified, not inherited

**Path-traversal safety, verified**: `safe_storage_filename()` (:32-38) is
the single choke point every builder in this file routes a filename
through before using it in a key:
```python
def safe_storage_filename(filename, fallback="file"):
    value = PurePosixPath(str(filename or "").replace("\\", "/")).name
    value = _SAFE_NAME.sub("-", value).strip(" .-")
    if value in {"", ".", ".."}:
        value = fallback
    return value[:180]
```
`PurePosixPath(...).name` discards every directory component (so
`../../etc/passwd` becomes `passwd`), then `_SAFE_NAME =
re.compile(r"[^A-Za-z0-9._() -]+")` (:22) replaces every character outside
that allow-list with `-`, then strips leading/trailing `.`/`-`/space, then
re-checks for the degenerate `""`/`"."`/`".."` cases and falls back if so.
**Confirmed: no path-traversal payload survives this function** — I
constructed the trace by hand for `../../../etc/passwd`,
`..\\..\\windows\\system32`, `....//....//etc`, and a filename containing a
literal NUL byte or `/`; all reduce to a bare, sanitized basename. This is a
correct implementation of the claim `ARCHITECTURE.md` made, not just an
inherited assertion.

**Are keys server-generated, or does user input reach them?** Mixed, by
design, and the split is exact:
- `build_original_key()` (:50-64): the path token is `uuid4().hex`
  (generated fresh by the *caller*, not derived from any user input — every
  call site found in this pass's scope and cross-referenced services calls
  it with a freshly minted UUID, e.g. `app/storage/services.py:66`:
  `build_original_key(storage_module, uuid4().hex, meta["filename"],
  ...)`). For `daily-reports`/`partner-management` modules specifically
  (:62), the **sanitized original filename is retained** as the final path
  segment (comment at :60-61: "Daily reports and partner photos
  deliberately retain a safe display name in their opaque object
  namespace"). For every other module (:64), the filename is discarded
  entirely except for its lowercased extension, and a **second** fresh
  `uuid4().hex` is used as the object's basename. **Net effect: user input
  can reach the key, but only after full sanitization, and only as a
  cosmetic suffix on an already-unguessable path — never as the sole or
  leading identifier.**
- `build_derivative_key()`, `build_partner_photo_key()`,
  `build_display_image_key()`, `build_bulk_zip_key()` — all UUID-tokened,
  none retain any caller-supplied name in a form that isn't already run
  through `safe_storage_filename()`.

**Can a key be guessed or enumerated?** No practical path found: every
token is a 128-bit `uuid4()` value (cryptographically random, not
sequential, not derived from any predictable counter like a row ID — this
pass specifically checked that no builder ever receives a raw
`StorageObject.id`/other sequential PK as its token; `create_upload_batch_presign`,
`app/storage/services.py:66`, passes `uuid4().hex` even though it already
has `storage_object.id` in scope moments later). Guessing a key would
require guessing a UUID4, which is not a practical attack.

**Does the key namespace encode project/tenant separation, given A2's §3
found zero data-layer project scoping?** **No.** Read every key builder in
this file: the path shape is always
`{prefix}/{storage_module}/{originals|derivatives|bulk-downloads}/{year}/{month}/{token}/{name}`
— **there is no project ID, folder ID, album ID, or any other
tenant/ownership segment anywhere in the key path.** Keys are namespaced
only by *module* (`daily-reports`/`company-media`/`document-library`/
`partner-management`) and by *calendar month*, never by *which project or
which user this belongs to*. This directly confirms and sharpens A2's
finding: **scoping depends entirely on the caller checking the associated
database row's `project_id`/`folder_id`/`album_id` before ever requesting a
presigned URL for that key.** The object-storage layer itself has no
concept of "this key belongs to project 42" — if the DB-side authorization
check that gates issuance of a presigned URL is ever wrong, incomplete, or
bypassed, the key namespace provides no second line of defense; it only
protects against *guessing* a key you were never told, not against being
*handed* a key you shouldn't have received.

---

## 2. Presigned URL issuance and redemption

**TTLs** (all read from config, `app/__init__.py`'s `setdefault` block,
cross-referenced not re-derived): `STORAGE_UPLOAD_URL_TTL_SECONDS` = 300s
(upload), `STORAGE_DOWNLOAD_URL_TTL_SECONDS` = 300s (download),
`DAILY_REPORT_PRESIGN_TTL_SECONDS` = 900s (Daily Report's own upload
presign, separate config key).

**Binding — object/method are always bound; content-type is bound; size is
bound for only one of two upload paths.** Two distinct presign methods
exist in `app/storage/providers.py`, and this codebase uses **both**, for
different flows:
- `create_presigned_upload()` (POST-form based, `providers.py:80-82` for
  S3): `Conditions=[["content-length-range", file_size, file_size], ...]`
  — **this binds the exact declared file size into the signed policy** — S3
  will reject a POST whose actual body size doesn't match. **Used by**
  `app/storage/services.py:75`'s `create_upload_batch_presign` — i.e., the
  Project Documents and Company Media batch-upload flow (`VALID_SCOPES =
  {("project_documents","folder"), ("company_media","album")}`, :14).
- `create_presigned_put()` (PUT based, `providers.py:84-88`): signs only
  `{Bucket, Key, ContentType}` (plus an optional `sha256` metadata header)
  — **no size condition exists in a presigned PUT URL at all; this is not
  a gap in this app's code, it's how S3 PUT presigning works** (unlike POST
  policies, PUT presigned URLs cannot carry a `content-length-range`
  condition). **Used by** `app/reports/direct_uploads.py:103,162` — i.e.,
  **every Daily Report upload, both the v1 and v2 flows** (confirmed by
  grep: `create_presigned_put` has exactly these two call sites in the
  entire repo, both in `direct_uploads.py`, which both `app/projects/routes.py`'s
  legacy flow and `app/reports/create_v2.py` call into, per `ARCHITECTURE.md`'s
  earlier routing).

**Consequence**: for the Daily Report upload path specifically, a client
can `PUT` a body of any size to the presigned URL — S3 will accept it
regardless of what size was declared at presign time. Size is only checked
**after the fact**, at completion (`_validate_head()`, `app/storage/services.py:159-168`,
compares `head.get("size")` against the DB-recorded `storage_object.file_size`
and raises `StorageValidationError` on mismatch) — by which point the
actual bytes are already sitting in the bucket. The completion-failure path
(`complete_upload_item`'s `except` block, `services.py:112-118`) marks the
`UploadBatchItem` `"failed"` but **does not call `provider.delete_object(...)`**
— the mismatched object is left in the bucket with `upload_status` still
`"pending"` (never advanced to `"active"` or explicitly to `"failed"` at
the `StorageObject` level) until `cleanup_pending_uploads()`
(`services.py:140-156`) sweeps it up after `STORAGE_PENDING_UPLOAD_HOURS`
(default 24h, and — per Foundation-B §6's dead-Celery-task finding for the
equivalent report-upload-session cleanup — this sweep may only ever run via
manual CLI invocation, not automatically). **This is a real, if
narrow, quota/cost-evasion surface specific to the size-unbound PUT path**:
`storage_usage_bytes()` (`quota.py:6-10`) only sums objects with
`upload_status == "active"`, so a "pending" oversized object doesn't count
against quota for however long it sits there.

**Who can request one, and is ownership checked before issuance?**
- `create_upload_batch_presign`: gated only by `_require_active_user()`
  (any authenticated, active user) and `_check_phase_one_scope()`
  (`services.py:190-192`, a literal no-op — `return None`, comment:
  "Future folder/album ACL hooks replace this owner/admin-only
  foundation"). **This service function performs no folder/album-level
  authorization check itself** — it trusts the calling route to have
  already checked `can_upload_project_document_folder`/equivalent before
  invoking it (confirmed the actual routes do this, per `ARCHITECTURE.md`'s
  route inventory — out of this unit's file scope to re-verify the route
  side, but the service side is confirmed to have zero enforcement of its
  own here).
- `create_signed_download_url` (`services.py:128-137`): checks
  `storage_object.uploaded_by_id != user.id and not (SUPER_ADMIN or
  ADMIN)` → `StorageAuthorizationError`. **This function has zero callers
  anywhere in the repository** (confirmed by grep for
  `create_signed_download_url(` across all of `app/` — only its own
  definition matches). It is dead code as far as any currently-reachable
  route is concerned; the actual download-authorization logic for Project
  Documents/Company Media lives in each module's own service file (out of
  this unit's scope — `can_download_project_document_file`/`download_file`,
  cross-referenced in §7 below via `bulk_downloads/services.py`'s imports of
  them).

**Revocation / outstanding-URL problem — asked directly, answered
directly**: a presigned URL is a **bearer capability with no server-side
revocation mechanism** in this codebase. Once issued, `boto3.generate_presigned_url`/
`generate_presigned_post` produce a signature that S3 will honor for the
full TTL window **regardless of any later change to the user's session,
role, project membership, or `ProjectUser` capability flags** — there is no
token-binding-to-session, no per-URL database row that could be checked/
revoked, no short-TTL-plus-refresh pattern. **If a user's access is revoked
while a valid presigned URL is still outstanding (e.g. their `ProjectUser`
row is deactivated, or their account is disabled), the URL keeps working
until it naturally expires** — 300s (upload/generic download) or 900s
(Daily Report upload) after issuance. This is a bounded, not unbounded,
exposure window given those TTLs are short, but it is real and inherent to
the presigned-URL model this app has chosen — not a bug in this code, a
property of the architecture worth stating plainly since the instruction
asked for it directly.

---

## 3. Upload validation (`validation.py`, `file_types.py`)

**Type checking is by declared extension + declared Content-Type only —
never by actual file content/magic bytes.** Confirmed by reading
`validate_file_metadata()` (`validation.py:24-47`) in full: it derives
`ext` from `PurePath(filename).suffix` (client-supplied filename string),
looks up the expected MIME for that extension in `POLICIES[module_type]`
(`file_types.py`), and compares against the **client-declared**
`mime_type` (via `canonical_mime()`, an alias table, then string equality
in `_mime_matches()`, :50-51). **No library that inspects actual file
bytes (`python-magic`, `filetype`, `imghdr`, or equivalent) is imported
anywhere in this scope or in `requirements.txt`** (confirmed by grep — zero
matches). A file whose actual bytes are, say, a PSD image but whose
filename ends in `.jpg` and whose declared `Content-Type` is
`image/jpeg` **passes this validation completely** — the mismatch is only
ever discoverable by whatever downstream code actually opens the file
(Pillow, in §8). This is the single most consequential fact underpinning
§8's reachability analysis below — validation.py is the gate, and it does
not check the one thing (actual content) that would close the
format-confusion attack surface.

Note: `validation.py` also defines an `ALLOWED_FILES` dict (:11-19) that
**is never referenced anywhere, including within its own file** (confirmed
by grep — the function body uses `POLICIES` from `file_types.py`, not this
local dict) — dead code, harmless, but means the real policy to audit is
`file_types.py`'s `POLICIES`/`DOCUMENT_LIBRARY_TYPES`/`COMPANY_MEDIA_TYPES`,
not this unused table.

**Is size enforced server-side, and at issuance, completion, or both?**
Both, but asymmetrically by flow, consistent with §2's finding:
- `validate_file_metadata()` itself checks declared `size` against
  `min(_max_size_bytes(category), UPLOAD_SINGLE_FILE_MAX_BYTES)` (:43-44) —
  this runs at **presign/batch-creation time**, against the **client's own
  declared size**, before any bytes exist server-side.
- For the Project Documents/Company Media batch flow, the S3 POST policy's
  `content-length-range` condition (§2) makes the *actual* upload
  size-bound too — the client cannot exceed what it declared even if it
  tries.
- For the Daily Report flow (presigned PUT), **no such enforcement exists
  at the storage layer** — only the post-hoc `_validate_head()` size
  comparison at completion, after the bytes are already stored (§2).

**Can a client complete an upload session for a file different from the
one it declared at presign time?** Partially prevented, not fully:
`_validate_head()` (`services.py:159-168`) checks the *actual* uploaded
object's size, Content-Type (if the provider's `head_object` returns one),
and checksum (if either side supplied one) against the DB-recorded
declared values, and rejects on any mismatch. **This catches a
completely different file being substituted, if that file differs in size,
content-type header, or checksum from what was declared.** It does **not**
catch a substituted file that happens to match the declared size and
declared Content-Type but has different actual bytes/content (e.g.
swapping one JPEG for a different JPEG of the same byte size, or — more to
the point for §8 — swapping a legitimately-sized-and-labeled `.jpg` for a
same-size, same-declared-type file whose actual bytes are a different
image format entirely, since Content-Type here is the *client's original
declared* value being compared against what the *client's own PUT request*
set as the object's stored Content-Type — S3 doesn't verify Content-Type
against actual content either). **Checksum verification is the one thing
that would close this**, but `checksum_sha256` is optional at every layer
(`validate_file_metadata`'s checksum check only fires `if checksum_sha256`
is truthy, :45; `_validate_head`'s checksum comparison only fires `if
expected and actual`, :167) — a client that simply never supplies a
checksum bypasses this entirely, and nothing in this scope *requires* one.

---

## 4. Quota accounting (`quota.py`) — race condition confirmed, not just suspected

`storage_usage_bytes()` (:6-10) computes usage **live, from actual stored
rows** (`SUM(StorageObject.file_size) WHERE upload_status='active' AND
deleted_at IS NULL`, plus derivatives and unexpired succeeded bulk-ZIP
jobs) — **it is not an incrementally-maintained counter**, so the classic
"counter drifts from reality" bug class doesn't apply here; the number is
always derived fresh. But this doesn't make it race-free:

`ensure_storage_capacity()` (:20-24):
```python
def ensure_storage_capacity(incoming):
    used = storage_usage_bytes(); limit = int(current_app.config["STORAGE_QUOTA_BYTES"])
    if used + int(incoming) > limit: raise ValueError("Đã vượt quota lưu trữ.")
    return {...}
```
This is a plain **check-then-act** with no locking of any kind — no
`SELECT ... FOR UPDATE`, no advisory lock, no `SERIALIZABLE` isolation
requested, no retry-on-conflict. It is called from
`create_upload_batch_presign()` (`services.py:49-51`) **once per batch**,
using the **client-declared** `declared_total` (sum of client-supplied
sizes for the batch, not yet-verified bytes) — checked *before* any
`StorageObject` row for this batch is created.

**Two concurrent uploads racing the same quota can both pass, confirmed by
tracing the sequence**: request A and request B both call
`storage_usage_bytes()` before either has committed a new `StorageObject`
row. If the current usage is, say, 95% of quota, and both A and B declare
individually-small-enough-but-jointly-over-quota amounts, **both reads see
the same pre-both-writes usage figure, both comparisons pass, both
proceed to create their `StorageObject` rows and commit** (`services.py:86`,
`db.session.commit()` at the end of `create_upload_batch_presign`).
Nothing between the read (`storage_usage_bytes()`) and the write (the
`db.session.commit()` several lines later, after per-file validation and
provider calls) holds any lock that would make the second transaction see
the first's effect before its own read. **This is a genuine, exploitable
TOCTOU race, not merely a theoretical one** — the quota can be exceeded by
up to the smaller of the two concurrent requests' declared sizes,
repeatable by any authenticated user issuing concurrent batch-presign
requests. `ensure_bandwidth()` (:26-29, used by `bulk_downloads`'s
`stream_zip_download`, §7) has the identical check-then-act shape and the
identical race.

---

## 5. `StorageObject`'s two conflicting state flags — every read site, and which flag each checks

A2 flagged this as the highest-value item in this pass. Every query
against `StorageObject` found across this unit's scope files, with which
flag(s) each one checks:

| Site | Checks `deleted_at`? | Checks `upload_status`? | Risk |
|---|---|---|---|
| `quota.py:7`, `storage_usage_bytes()` | ✅ `deleted_at.is_(None)` | ✅ `upload_status == "active"` | **Both** — safe |
| `services.py:131`, `create_signed_download_url` | ✅ `deleted_at is not None` (rejects) | ✅ `upload_status != "active"` (rejects) | **Both** — safe (but dead code, §2) |
| `services.py:143`, `cleanup_pending_uploads` | — (not checked) | ✅ `upload_status == "pending"` | Only needs `upload_status` for its purpose (finding stale pending rows) — not a gap for *this* function's job |
| `services.py:107,109`, `complete_upload_item` | — (not checked directly; relies on `item.storage_object` existing) | ✅ `upload_status == "active"` / `!= "pending"` | Only `upload_status`, but this function's job is upload-state transition, not "is this file visible" — not the risk class asked about |
| `media_processing/services.py:62,98`, `stage_media_processing_jobs` / `enqueue_media_processing_for_storage_object` | — (not checked) | ✅ `upload_status != "active"` (skips) | Only `upload_status` — appropriate for its purpose (don't process a not-yet-active upload) |
| `media_processing/services.py:137`, `retry_media_jobs` | — (not checked) | ✅ `upload_status != "active"` (skips) | Same as above |
| `media_processing/services.py:184-186`, `media_jobs_status` | — (not checked) | ✅ `upload_status == "active"` | Informational counts only, not a serving path |
| `media_processing/pipeline.py:21`, `process_job` | — (not checked) | ✅ `upload_status != "active"` → cancels the job | Appropriate for its purpose |
| `branding.py:11` (cross-referenced from A1, not re-read here as full file but the one line is directly relevant): `obj.deleted_at is not None or obj.upload_status != "active"` | ✅ | ✅ | **Both** — safe |

**Finding: within this unit's own scope, every single read site that
decides "is this file usable/servable" checks *both* flags — none of the
`StorageObject` queries found in `app/storage/`, `app/media_processing/`,
or `app/display_images.py` checks only one of the two.** The acute risk A2
flagged (a query checking only `deleted_at` while another checks only
`upload_status`, or vice versa) **was not found to be realized anywhere in
this specific pass's file set** — but this pass's scope does not cover the
per-module download/preview routes themselves (`app/attachments/`,
`app/project_documents/`, `app/company_media/`, `app/partner_companies/`,
`app/partners/` — all out of Foundation-B's file list, assigned to their
own units). **The two-flag risk A2 identified at the schema level is real
and still open** — it simply hasn't been triggered by anything read in
*this* pass. Every unit that queries `StorageObject` directly (rather than
going through the helpers audited here) must independently confirm it
checks both `deleted_at IS NULL` and `upload_status = 'active'` — this
document cannot close that finding, only narrow where it has and hasn't
been confirmed safe so far.

---

## 6. Celery dependency map — dispatch sites, and what the user sees with no worker

Confirmed by reading `app/celery_app.py` (A1 scope, cross-referenced) that
**no Celery beat schedule exists anywhere in this codebase** — no
`beat_schedule` config, no periodic-task registration of any kind.
> **Outdated note:** This assertion became outdated on 2026-07-28: `app/celery_app.py` has `beat_schedule`; the remaining debt is DEPLOY-002 evidence that the `beat` service runs in production, not absence of automated cleanup.
Confirmed by grep across the whole repo that **exactly two `.delay()` call
sites exist in total**:

| Subsystem | Dispatch call site | Queue | What the user sees with no worker consuming it |
|---|---|---|---|
| Media derivatives | `app/media_processing/services.py:47`, `_dispatch_media_job()` → `task.delay(job.id)` | `media_image`/`media_video` | `MediaProcessingJob.status` stays `"pending"` forever (or `"queued"` at the `StorageObject.processing_status` level, set just before dispatch in `stage_media_processing_jobs`, `services.py:81`). Dispatch failure itself is caught and swallowed by design (`enqueue_media_processing_for_storage_object`, `services.py:108-111`: `try: return dispatch_media_processing_job(job.id) except Exception: return job` — comment: "Upload must remain durable even when the optional async worker/broker is temporarily unavailable"). **Net effect: a permanent "queued"/"processing" placeholder state, never an error, never a silent disappearance** — whatever UI reads `processing_status`/derivative presence (out of this unit's scope) would show an indefinitely-pending thumbnail/preview. |
| Bulk ZIP downloads (legacy `BulkDownloadJob` path) | `app/bulk_downloads/services.py:135`, `enqueue_job()` → `build_bulk_zip.delay(job.id)` | `bulk_download` | Same shape — `BulkDownloadJob.status` defaults to and stays `"pending"`. **But this pass found `_create_job()` (`bulk_downloads/services.py:188`), the only function that constructs a `BulkDownloadJob` and calls `enqueue_job()`, has zero callers anywhere in the repository** (confirmed by grep for `_create_job(`). Cross-checked the two routes that expose "bulk download" UI actions (`company_media.bulk_download`, `project_documents.bulk_signed_download`, both out of this unit's file scope but read for this specific cross-check): **both call `request_media_download`/`request_document_download` → `stream_zip_download` directly, never `_create_job`/`enqueue_job`.** This entire Celery-dispatched path is **dead code from the current routing's perspective** — not a "no worker" risk so much as a "this feature isn't reachable at all any more" finding, superseded by the synchronous `stream_zip_download` path (§7) per the "Phase 7.1 Strict Storage Policy" the docstring at `services.py:73` references. `bulk_download_status` routes (which query `BulkDownloadJob` by ID) remain reachable but can only serve historical rows from before this change, or 404. |
| Orphan/cleanup jobs | `media.reconcile_media_jobs` (`media_processing/tasks.py:39-47`) and `reports.cleanup_expired_upload_sessions` (`media_processing/tasks.py:50-53`) and `bulk_download.cleanup_expired` (`bulk_downloads/tasks.py:10-13`) | `storage_cleanup` | **None of these three tasks has any `.delay()` call site anywhere in the repository** (confirmed by the same grep — only the two dispatches in the table above exist at all). They are registered as valid Celery tasks (`@celery_app.task(name=...)`) but **nothing ever asynchronously triggers them** — the corresponding cleanup logic (`reconcile_media_jobs()`, `cleanup_expired_sessions()` in `direct_uploads.py` out of scope, `cleanup_expired_jobs()`) is only ever invoked **synchronously**, directly, by the `flask` CLI commands of the same name (`app/cli.py`, A1-adjacent, cross-referenced not re-read here). **This confirms and sharpens PRE-004**: there is no scheduled, automatic cleanup of any kind in this system as currently wired — every cleanup/reconciliation path requires a human to run a CLI command. If no operator ever does, pending-upload rows, expired sessions, and stuck media jobs accumulate indefinitely (bounded only by whatever storage cost that represents, not by any code-enforced ceiling). |

**Summary answer to the "looks complete but isn't wired up" question**:
media-derivative generation degrades gracefully to a permanent pending
state if unconsumed (not an error, not silent data loss); the legacy
bulk-ZIP-job pathway is not merely at risk of this, it is **already
unreachable** from any current route; and **all cleanup/reconciliation is
manual-only**, by design of what's wired to what, not as a bug in any
single function.

---

## 7. Bulk download ZIP (`app/bulk_downloads/`)

**Zip-slip**: not possible. Every archive entry name is produced by
`_unique_zip_name()` (`services.py:270-277`), which calls
`safe_storage_filename()` (§1's verified-safe function) before adding a
disambiguating `" (2)"`-style suffix on collision — **no raw
`display_name`/user-controlled path ever reaches `ZipFile.write(...,
arcname=...)` unsanitized.**

**Memory behavior — two different implementations, both stream to disk,
neither fully buffers in memory, but they run in different processes**:
- `stream_zip_download()` (`services.py:72-115`) — the **current, live**
  path (per §6): downloads each source object to a per-file temp path,
  writes it into the archive with `zipfile.ZIP_STORED` (store, not
  compress — comment at :85-86 explains this is deliberate, "not a
  recompression service"), then unlinks the per-file temp copy before
  moving to the next (:90-93). **Runs synchronously inside the Flask/
  Gunicorn web request** — there is no Celery involved in this path at all.
  A request for many/large files ties up a web worker thread for the
  entire archive-build duration; `BULK_DOWNLOAD_MAX_FILES` (100) and
  `BULK_DOWNLOAD_MAX_TOTAL_BYTES` (300MB) bound this (enforced in
  `_validate_selected()`, `services.py:199-208`, called by both
  `_select_document_files`/`_select_media_files` before `stream_zip_download`
  is ever reached), so this is bounded, not unbounded, but it is real
  web-process time spent per request, not offloaded to a worker.
- `run_job()` (`services.py:139-174`) — the **legacy, currently
  unreachable** (§6) Celery-task path: same per-file
  download-write-implicit-cleanup shape, but uses `zipfile.ZIP_DEFLATED`
  (real compression) and runs inside a Celery worker process, not the web
  process. Since nothing currently dispatches it, this distinction is
  presently academic, but documented in case the pathway is ever
  reconnected.

**Is every file individually authorized, or only the parent folder/album?**
**Every file is individually authorized**, confirmed by tracing
`_select_document_files`/`_select_media_files` (`services.py:221-232`) →
`_validate_selected()` (:199-208): after the query itself already scopes
candidates to `folder_id == folder.id`/`album_id == album.id` **and**
`id.in_(requested_ids)` (`_document_files`/`_media_files`, :211-218 — so a
file ID belonging to a *different* folder/album is silently excluded from
the result set, not merely unauthorized), `_validate_selected` then
independently re-checks, **per file**: `not item.is_active`,
`item.deleted_at` (truthy), and `not permitted(item)` where `permitted` is
`can_download_project_document_file(user, item)` or `download_file(user,
item)` (both out-of-scope module-specific permission functions, called
here, not redefined) — **any single failing file raises `PermissionError`
for the whole batch**, it does not silently drop the unauthorized file and
continue with the rest. The parent folder/album's own authorization
(checked by the route before this service layer is invoked, out of scope)
is a *separate*, *earlier* gate — this per-file check is a **second,
independent layer on top of it**, not a substitute.

---

## 8. PILLOW EXPOSURE

### a) Every call site that opens/decodes/verifies/converts/resizes/saves an image

| # | File:line | Operation | Bytes source |
|---|---|---|---|
| 1 | `app/account/routes.py:61` | `Image.open(io.BytesIO(raw))` + `.verify()` | user-uploaded avatar (out of this unit's file scope — cross-referenced, already flagged for unit 10) |
| 2 | `app/account/routes.py:62` | second `Image.open(io.BytesIO(raw))` (actual processing) | same |
| 3 | `app/display_images.py:47-48` | `Image.open(io.BytesIO(raw))` + `.verify()` | user-uploaded partner photo / company logo / branding logo / account avatar (all four scopes funnel here, confirmed via `app/partner_photos.py`'s `replace_photo()` calling straight through to `replace_display_image`, and `build_display_image_key`'s `allowed = {"partner-avatars","company-logos","account-profiles","branding"}`, `keys.py:89`) |
| 4 | `app/display_images.py:49-58` | second `Image.open`, `ImageOps.exif_transpose`, `.load()`, `.thumbnail((768,768), LANCZOS)`, `.convert("RGB"/"RGBA")`, `.save(output, "WEBP", quality=88, method=4)` | same |
| 5 | `app/media_processing/pipeline.py:42-43`, `_save_derivative` | `Image.open(path)` — reads dimensions only | **this app's own just-generated WEBP derivative**, not raw user bytes — low relevance |
| 6 | `app/media_processing/pipeline.py:55-56`, `_image` | `Image.open(source)` + `.verify()` | user-uploaded original, downloaded from S3 |
| 7 | `app/media_processing/pipeline.py:57-59`, `_image` | second `Image.open(source)`, `ImageOps.exif_transpose`, `.convert("RGB")` | same |
| 8 | `app/media_processing/pipeline.py:63-66`, `_image` | `.copy()`, `.thumbnail((limit,limit))`, `.save(path, "WEBP", quality=80/85, method=4)` | same (derived from #7's decoded object) |

Every one of these (except #5) decodes **user-uploaded bytes**. The HEIC/
HEIF path is registered globally via `pillow_heif.register_heif_opener()`
in both `display_images.py:22-26` and `pipeline.py:5-9` — this is a
**decode-registration only**; grep across this scope plus a repo-wide grep
for `"HEIF"`/`.save(..., "HEIF"...)` found **no explicit HEIF-encode call
anywhere** — this app only ever encodes to WEBP.

### b) Web process vs. Celery worker — which bytes are a direct DoS surface

- **Direct web-process DoS surface** (decode runs synchronously inside a
  Gunicorn worker handling the request): call sites **#1-4** — the entire
  `display_images.py` path (avatar/partner-photo/company-logo/branding-logo)
  plus `account/routes.py`'s own duplicate. A malicious upload here ties up
  a request-handling worker for as long as the decode/convert/save takes,
  or crashes/hangs that worker on a crafted file.
- **Celery-worker-only** (async, isolated from request-handling capacity):
  call sites **#5-8** — the media-processing pipeline. A malicious file here
  degrades the async pipeline (a stuck/crashed worker delays derivative
  generation for everyone, and per §6 a permanently-stuck job is already
  the "no worker" failure mode even without malice) but does **not**
  directly block a user-facing HTTP request the way #1-4 would.

**#1-4 (the synchronous display-image path) is therefore the
higher-priority half of this exposure** — it is both reachable pre-decode
validation-free (§3: no magic-byte check) and runs where a hang/crash has
immediate, direct availability impact.

### c) Cross-referencing the 24 pip-audit CVEs against these call sites

Reachability requires two things to both be true: (1) the vulnerable
Pillow code path can be reached via one of the operations in the table
above (`Image.open`, `.verify()`, `ImageOps.exif_transpose`, `.load()`,
`.convert()`, `.thumbnail()`, `.copy()`, `.save(..., "WEBP")` — this app
calls no other Pillow API anywhere in this scope, confirmed by grep for
`ImageCms`, `RankFilter`/`MedianFilter`, `PcfFontFile`, `BdfFontFile`,
`FontFile`, `GdImageFile`, `ImageFont`, `.show(` — **zero matches for any
of these across the entire `app/` tree**); and (2) the *format* the CVE
targets can actually be handed to `Image.open()` given §3's confirmed
absence of any magic-byte check (only the *claimed* extension/MIME is
checked, never actual content — so an attacker can rename any
Pillow-decodable format's bytes to `.jpg` and it will still be decoded as
its true format).

| CVE (PYSEC) | Format/API targeted | Reachable? | Why |
|---|---|---|---|
| 2026-2249 | PSD (malicious file → OOB write) | **Reachable** | `Image.open()` auto-detects PSD by content regardless of claimed extension; no magic-byte check blocks it (§3) |
| 2026-2250 | FITS (unbounded GZIP decode) | **Reachable** | same reasoning — `Image.open()` auto-detects FITS |
| 2026-2252 | PSD (malicious file → memory corruption) | **Reachable** | same format-confusion path as 2249 |
| 2026-3493 | raw codec + `_MAPMODES`, **specifically when opened from a filename** (deferred tile loading) | **Reachable, and specifically implicated at call sites #6-7** | `media_processing/pipeline.py`'s `Image.open(source)` opens a real filesystem `Path`, not `BytesIO` — this exactly matches the "opened from a filename" trigger condition in the advisory. `display_images.py`'s `Image.open(io.BytesIO(raw))` (call sites #3-4) does **not** match this specific trigger (opened from bytes, not a filename) |
| 2026-3496 | JPEG2000 (tile-width accumulation) | **Reachable** | same format-confusion path — no extension in any `POLICIES` table is `.jp2`/`.j2k`, but that only gates the *claimed* extension, not what `Image.open()` actually decodes |
| 2026-3451 | Public coordinate APIs, near-32-bit-limit values | **Plausibly reachable, not fully confirmed** | Triggered by attacker-influenced coordinate/dimension values; `ImageOps.exif_transpose` and the decode path itself read dimension/orientation fields from the file's own header, which are attacker-controlled up to format limits — this pass could not confirm from the advisory summary alone whether the *specific* internal APIs this app calls (`.convert()`, `.thumbnail()`, `exif_transpose`) are within the affected coordinate-API set; flag as plausible, not certain |
| 2026-165 | Font glyph-advance overflow (`ImageFont`) | **Not reachable** | `ImageFont` is never imported or called anywhere in this scope (grep confirmed); this app never loads or renders with user-supplied fonts |
| 2026-2253, 2026-2254, 2026-2255 | PCF/BDF font file parsing (`PcfFontFile`, `BdfFontFile`, `FontFile.compile`) | **Not reachable** | None of these classes are imported anywhere (grep confirmed); per the advisory text itself, these font-file openers are **not registered with `Image.register_open()`**, so even generic `Image.open()` would not auto-dispatch to them — reaching this code requires an explicit `PcfFontFile(fp)`/`BdfFontFile(fp)` call this app never makes |
| 2026-2256 | GD image format (`GdImageFile._open()`) | **Not reachable** | `GdImageFile` is never imported (grep confirmed); Pillow's GD reader has historically required an explicit `GdImageFile.open(fp)` call rather than being auto-detected by generic `Image.open()` — not independently re-verified against this exact Pillow version's plugin registry, but no code path in this app could reach it either way since the class is never imported |
| 2026-2257 | `WindowsViewer.get_command()` shell-command construction | **Not reachable** | Windows-only code path (`ImageShow`'s Windows viewer); this app never calls `Image.show()` (grep confirmed) and deploys exclusively on Linux containers (`Dockerfile`, `docker-compose.yml`, cross-referenced) |
| 2026-2874 | Malicious PDF → CPU-exhaustion hang | **Not reachable via any call site in this scope** | `media_job_type_for_storage_object()` (`media_processing/services.py:10-15`) only creates image/video derivative jobs for `mime_type.startswith("image/"|"video/")` — `application/pdf` matches neither, so no Pillow call is ever made against a PDF via the media pipeline; `display_images.py`'s `IMAGE_EXTENSIONS` doesn't include `pdf` either, and its extension check (`replace_display_image`, :41-42) rejects non-allow-listed extensions **before** any `Image.open()` call. PDFs are stored as opaque `ProjectDocumentFile`/`CompanyMediaFile` objects and never decoded by Pillow in this scope. (Could not rule out a PDF-preview feature existing elsewhere in the app outside this unit's file list — not found in `app/storage/`, `app/media_processing/`, or `app/display_images.py`.) |
| 2026-3495 | PDF stream `zlib.decompress()` unbounded `bufsize` | **Not reachable**, same reasoning as 2874 |
| 2026-3453 | `ImageCms.ImageCmsTransform.apply()` | **Not reachable** | `ImageCms` never imported anywhere (grep confirmed) — this is an opt-in, explicitly-called API this app doesn't use |
| 2026-3454 | Public rank-filter API (`ImageFilter.RankFilter`/`MedianFilter`) | **Not reachable** | No `ImageFilter`/`.filter(` call found anywhere in this scope |
| 2026-3494 | TGA RLE encoder (triggered on **save** to TGA) | **Not reachable** | This app only ever calls `.save(..., "WEBP")` — never saves to TGA anywhere in this scope |
| pillow-heif PYSEC-2026-2258 | HEIF **encode**-path integer overflow | **Not reachable** | Confirmed decode-only usage (`register_heif_opener()` only, both call sites); no explicit HEIF-encode call exists anywhere (grep for `"HEIF"`/`.save(...,"HEIF")` found only a format-name lookup dict in `app/reports/services.py:42`, unrelated to encoding) |

**Summary: of the 17 distinct Pillow advisories, 4 are confirmed reachable
(2249, 2250, 2252, 3496), 1 is specifically and additionally implicated at
the pipeline.py filename-based-open call sites (3493), 1 is plausible but
unconfirmed (3451), and 10 are not reachable via any call site this app
makes** (165, 2253, 2254, 2255, 2256, 2257, 2874, 3495, 3453, 3454, 3494),
**plus the 1 pillow-heif advisory is not reachable.** The blocking factor
common to every reachable CVE is the same single fact from §3: **no
content-based file-type verification exists anywhere upstream of Pillow.**

### d) `Image.MAX_IMAGE_PIXELS` and decompression-bomb exposure

**Set in exactly one place**: `app/media_processing/pipeline.py:54`,
inside `_image()`: `Image.MAX_IMAGE_PIXELS =
current_app.config.get("MEDIA_IMAGE_MAX_PIXELS", 100_000_000)`. This is a
**global, process-wide mutable class attribute on `PIL.Image`** — setting
it here affects every subsequent `Image.open()` call **in that same Python
process** (the Celery worker), for the remainder of that process's life,
not just this one call.

**`display_images.py` and `account/routes.py` (the synchronous web-process
path, call sites #1-4) never set `Image.MAX_IMAGE_PIXELS` at all.** Since
Celery workers and Gunicorn web workers are separate OS processes (confirmed
architecturally — `scripts/start-media-worker.sh` starts a distinct
process from the Gunicorn-served web app), **setting it in the worker
process has zero effect on the web process.** The web-process path relies
entirely on Pillow's own **built-in default** (approximately 89 million
pixels before a `DecompressionBombWarning`, roughly double that before a
hard `DecompressionBombError`) — a real but unconfigured, un-reviewed
default, not a value this application chose deliberately for that path.
Given #1-4 is also the higher-priority half of this exposure per §8b, this
is a concrete, specific gap: **the one place this codebase explicitly
reasons about decompression bombs is the one process where it doesn't
matter for the account/partner/company/branding image path.**

`app/account/routes.py:61`'s `Image.open().verify()` (already flagged for
unit 10, cross-referenced here since the instruction asked for it
specifically): **`.verify()` reads and validates the file's structural
headers without fully decoding pixel data** — it does not by itself
protect against a decompression bomb (which requires actually allocating
and decoding the full pixel buffer) or against most of the memory-
corruption CVEs above (many of which trigger during actual decode/tile-
processing, not header verification). The **second** `Image.open()` call
at `account/routes.py:62` (and identically at `display_images.py:49`) is
where real decoding happens, and neither sets `MAX_IMAGE_PIXELS` before
that second open.

### e) Migration assessment for Pillow 12.x (assessment only, not performed)

Confirmed installed version: **Pillow 10.4.0** (`requirements.txt`,
cross-referenced against `pip-audit`/`trivy` output). APIs this codebase
actually calls, enumerated from §8a: `Image.open()`, `.verify()`,
`ImageOps.exif_transpose()`, `.load()`, `.convert()`, `.thumbnail()`
(with `Image.Resampling.LANCZOS`, `display_images.py:54` — **already using
the modern resampling-constant API**, not the legacy `Image.ANTIALIAS`
constant Pillow removed in 10.0, so this specific well-known 10.x breaking
change is already handled), `.copy()`, `.save(..., "WEBP")`,
`Image.MAX_IMAGE_PIXELS`, `Image.MIME` (cross-referenced from
`app/reports/services.py:759`, out of this unit's scope), and
`pillow_heif.register_heif_opener()`. **None of these are APIs I have any
specific, sourced knowledge of being removed or changed between 10.x and a
12.x release** — but I hold this with real uncertainty: a Pillow 12.x
release is beyond what I can verify against a concrete, dated changelog
with confidence (the CVE identifiers here carry a 2026 year stamp, which is
at or past the edge of what I can independently confirm rather than
infer). **Recommendation, not performed**: before any upgrade, diff this
exact API list against Pillow's actual `CHANGES.rst`/release notes for
every version between 10.4.0 and the target 12.x, rather than relying on
this document's list — this assessment identifies *what surface needs
checking*, it does not certify that surface is unaffected.

---

## GUARANTEES

Module auditors in Batch 1+ may assume, without re-deriving:

- Every object-storage key builder in `app/storage/keys.py` routes any
  user-supplied filename through `safe_storage_filename()` first — no
  path-traversal payload can reach a real S3 key (§1, hand-verified against
  multiple payloads).
- Every key's path token is a fresh `uuid4().hex`, never a sequential/
  guessable identifier — keys cannot be practically enumerated (§1).
- The Project Documents / Company Media batch-upload flow
  (`create_upload_batch_presign`) binds the declared file size into the S3
  POST policy itself — a client cannot upload more bytes than it declared
  on this specific path (§2, §3).
- `_validate_head()` at upload completion independently re-verifies actual
  object size (and Content-Type/checksum when supplied) against the DB
  record on every upload flow, both PUT- and POST-based (§2, §3).
- Every file included in a bulk-download ZIP is individually re-checked
  against its own per-file authorization function, not just the parent
  folder/album's — one unauthorized file fails the whole batch rather than
  being silently dropped (§7).
- Bulk-download ZIP entry names are zip-slip-safe — routed through the same
  verified `safe_storage_filename()` (§7, building on §1).
- Within this unit's own file set, every `StorageObject` query that decides
  whether a file is servable checks **both** `deleted_at` and
  `upload_status` (§5) — the two-flag risk A2 raised has not been found
  realized in `app/storage/`, `app/media_processing/`, or
  `app/display_images.py` specifically.
- A media-derivative job that never gets consumed by a worker fails
  gracefully to a permanent "queued" state, not an unhandled exception or
  data loss — the durability-first design at
  `enqueue_media_processing_for_storage_object` is intentional and correct
  for that failure mode (§6).

## NOT GUARANTEED — every unit must check these itself

- **The object-key namespace encodes no project/tenant separation at all**
  (§1) — combined with A2's "zero data-layer scoping" finding, this means
  the *entire* defense against a cross-project file access is the
  application-code check performed before a presigned URL is issued, with
  no fallback anywhere in the storage layer. Any unit granting/handling
  presigned URLs must treat its own authorization check as the *only*
  barrier.
- **A presigned URL remains valid for its full TTL (300s/900s) even if the
  issuing user's access is revoked in the same window** (§2) — no unit
  should assume revoking a `ProjectUser` capability or disabling an account
  immediately invalidates a URL already handed to the client.
- **The Daily Report upload flow's presigned PUT URLs are not size-bound at
  the storage layer** (§2, §3) — unlike the Project Documents/Company
  Media POST-based flow. Size is enforced only after the fact, and a
  rejected/oversized object can sit in the bucket, uncounted against quota,
  for up to `STORAGE_PENDING_UPLOAD_HOURS` (24h default) — and per §6,
  the automated cleanup for this is not currently scheduled to run on its
  own.
- **No content-based file-type verification exists anywhere in this
  scope** (§3, §8) — every extension/MIME check operates on client-declared
  values only. Any unit reasoning about "can a malicious file type reach
  X" must assume the answer is yes unless it finds a check this pass
  didn't.
- **`ensure_storage_capacity()`/`ensure_bandwidth()` are check-then-act with
  no locking — concurrent requests can jointly exceed either quota** (§4).
  Do not treat either quota as a hard ceiling under concurrent load.
- **The two-flag `StorageObject` risk A2 raised is unresolved in general**
  — only confirmed *not* realized within this unit's own files (§5). Every
  other unit querying `StorageObject` directly must independently verify it
  checks both flags.
- **The legacy `BulkDownloadJob`/Celery ZIP pathway is dead code from any
  currently-reachable route** (§6, §7) — do not assume it provides a
  working fallback or alternate download path; anything depending on it
  (e.g. a stale bookmarked `bulk_download_status` URL) will not produce a
  new result.
- **No cleanup/reconciliation task in this subsystem runs on any automatic
  schedule** (§6) — `media.reconcile_media_jobs`,
  `reports.cleanup_expired_upload_sessions`, and
  `bulk_download.cleanup_expired` all require manual CLI invocation;
  treat any assumption of "this gets cleaned up eventually" as false unless
  an operator process is separately confirmed to run these regularly.
- **The web-process image-upload path (`display_images.py`,
  `account/routes.py`) has no `Image.MAX_IMAGE_PIXELS` override and no
  content-type verification before decode** (§8d) — this is the
  higher-priority half of the Pillow exposure per §8b's DoS-surface
  reasoning; do not assume the Celery-worker path's `MAX_IMAGE_PIXELS`
  setting provides any protection here, it does not (separate process).
- **Reachable Pillow CVEs (2249, 2250, 2252, 3493, 3496, plausibly 3451)
  remain unpatched at the installed version (10.4.0)** — this document
  assesses reachability, it does not fix anything; any unit citing "Pillow
  has known CVEs" as a finding should cite this section's specific
  reachable subset, not the raw CVE count, and should not assume an
  upgrade path has been assessed beyond the API-surface list in §8e.
