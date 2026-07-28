# Findings — Unit 10: Account, module switcher, and media display preview

## Summary

- The account blueprint is registered at `/account`; its three routes are login-protected. `/media-display-preview` is separately registered directly on the application, but its view function carries `@login_required`.
- Account mutation is self-scoped: the only record passed to the shared replacement/removal helper is `current_user`; no target-user identifier is accepted. Avatar rendering follows only `current_user.avatar_storage_object` and rejects non-active or soft-deleted objects.
- Display images are synchronously read, verified, fully decoded, transformed and re-encoded to WebP in the Gunicorn request process. This is a security boundary distinct from the Celery media worker.
- The module switcher uses fixed server-side URLs and validates each selectable module; it accepts no `next`/return URL. Direct destination routes retain their own authorization, so changing `session["active_module"]` is presentation state only.
- Two findings: reachable vulnerable/format-confused Pillow decoding (High), and display-image replacement objects retained indefinitely while excluded from quota accounting (Medium).

Files read: 27 (8/8 primary files; 19 direct registration, auth, storage, model, configuration, navigation, JS/template, and dependency files) | Primary files unread: none | Other unread: no deploy-time S3 lifecycle policy is present in the repository; runtime policy is therefore listed under Needs verification.

## Route and authorization matrix

| Method | Route | Authentication / authorization | CSRF / rate limit | Effect |
|---|---|---|---|---|
| GET | `/account/` | `@login_required` at `app/account/routes.py:14-16`; global app login hook also runs first | N/A | Renders only the current account profile. |
| POST | `/account/` | Same; passes only `current_user` to the avatar replacement helper | Global Flask-WTF CSRF; no route rate limit | Replaces caller's avatar. |
| POST | `/account/avatar/delete` | `@login_required` at `app/account/routes.py:28-31`; target is only `current_user` | Global Flask-WTF CSRF; no route rate limit | Soft-deletes caller's avatar association. |
| GET | `/account/avatar` | `@login_required` at `app/account/routes.py:36-39`; reads only caller's relation | N/A | Issues a 300-second inline presigned redirect only for an active, non-deleted avatar. |
| POST | `/media-display-preview` | Direct application registration, with the function's `@login_required` at `app/account/routes.py:48-50` | Global Flask-WTF CSRF; `30 per minute` | Decodes supplied bytes and returns an ephemeral WebP response; no DB/S3 write. |
| GET | `/modules/` | Global login hook; visible cards filtered by `get_accessible_modules(current_user)` | N/A | Renders allowed module cards. |
| GET | `/modules/select/reports` | Global login + `can_access_reports_module(current_user)` | N/A | Sets a fixed `active_module` session value then redirects to a server-selected reports route. |
| GET | `/modules/select/partners` | Global login + `can_access_partners_module(current_user)` | N/A | Sets fixed `active_module="partners"`; fixed redirect. |
| GET | `/modules/select/admin` | Global login + any of five admin view permissions | N/A | Sets fixed `active_module="admin"`; fixed redirect. |

Hook order is confirmed from `create_app()`: blueprints/direct route registration occurs at `app/__init__.py:69,88-135`; `register_auth_guard(app)` is invoked at `:72`; then the app-wide `require_login` hook is defined at `:152-167`. Flask executes this app hook before a blueprint view. `account` and `modules` are intentionally not reports-module-gated; they are account and selector surfaces. `media_display_preview` has endpoint name `media_display_preview`, so the global login hook does not exempt it (`public_endpoints` is only `auth.login`, `health`, `healthz`, and `static`, `:152-167`).

## Findings

### ACCOUNT-001 — Synchronous display-image endpoints decode format-confused bytes with a vulnerable Pillow release and no application pixel limit

- **Severity:** High
- **Confidence:** High
- **CWE:** CWE-400 (uncontrolled resource consumption), CWE-20 (improper input validation)
- **Location:** `requirements.txt:9`; `app/display_images.py:28-29,36-61`; `app/account/routes.py:48-68`; `app/media_processing/pipeline.py:53-57`
- **Reachability:** Any authenticated, active user can POST an avatar to `/account/`; any authenticated user can POST preview bytes to `/media-display-preview`. The account upload route itself has no rate-limit decorator. Both run in the synchronous web process before any storage write.
- **Vulnerable code:**
  ```python
  # requirements.txt:9
  Pillow==10.4.0

  # app/display_images.py:40-58
  if extension not in IMAGE_EXTENSIONS:
      raise DisplayImageError("Chỉ cho phép ảnh JPG, JPEG, PNG, WebP, HEIC hoặc HEIF.")
  raw = upload.read()
  ...
  with Image.open(io.BytesIO(raw)) as source:
      source.verify()
  with Image.open(io.BytesIO(raw)) as source:
      image = ImageOps.exif_transpose(source)
      image.load()
      ...
      image.save(output, "WEBP", quality=88, method=4)
  ```
  ```python
  # app/account/routes.py:61-65
  with Image.open(io.BytesIO(raw)) as probe: probe.verify()
  with Image.open(io.BytesIO(raw)) as source:
      image = ImageOps.exif_transpose(source); image.load(); image.thumbnail((768, 768), Image.Resampling.LANCZOS)
      if image.mode not in {"RGB", "RGBA"}: image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
      output = io.BytesIO(); image.save(output, "WEBP", quality=86, method=4); output.seek(0)
  ```
- **Evidence and exploit path:** The only pre-decode type check is a filename-extension allow-list (`app/display_images.py:40-42`; the preview duplicates it at `app/account/routes.py:53-56`). Neither call uses Pillow's `formats=` argument or checks a declared MIME type, magic bytes, or `source.format` against the extension. Thus an authenticated caller can name a non-allow-listed but Pillow-decodable payload `image.jpg`; `Image.open()` chooses its decoder from bytes, not the name. `pillow_heif.register_heif_opener()` also expands the registered decoder set at `app/display_images.py:22-26`.

  `.verify()` is not a full-pixel decode, but the second open explicitly calls `image.load()` before thumbnailing. The code does not set `Image.MAX_IMAGE_PIXELS`, make `DecompressionBombWarning` fatal, or impose width/height limits anywhere in the web path. The sole application assignment is inside the separate Celery path:
  ```python
  # app/media_processing/pipeline.py:53-57
  def _image(obj,job,source,tmp,provider):
   Image.MAX_IMAGE_PIXELS=__import__('flask').current_app.config.get("MEDIA_IMAGE_MAX_PIXELS",100_000_000)
   with Image.open(source) as original:
    original.verify()
  ```
  It cannot protect Gunicorn because it runs only when a Celery worker executes `_image`; the synchronous routes above do not enqueue that function. The repository also contains no configuration for `MEDIA_IMAGE_MAX_PIXELS` (`app/config.py:33-116`). Pillow's built-in default warning threshold is not an application-selected cap, and a warning is not caught/escalated by either web handler (their `except` clauses list only `UnidentifiedImageError`, `OSError`, and `ValueError`).

  This creates two concrete effects for a low-privilege authenticated account: a small compressed image can force a large full decode/convert in a request worker (roughly four bytes per pixel for an RGBA buffer, plus decode/conversion/encoder overhead), and content-format confusion reaches parser code in installed Pillow 10.4.0. The assigned dependency lead was independently checked against the actual flow: `TOOL-LEAD-MAP.md` identifies reachable Pillow format-parser advisories and the source confirms that no `formats=` restriction blocks those decoders. The process does re-encode successful output to `image/webp`, so this is not an attacker-controlled active-content response/XSS path; it is a parser and availability boundary.
- **Impact:** An authenticated user can consume substantial web-worker CPU/memory or trigger a reachable vulnerable image decoder. Repetition is not throttled on `/account/`; preview is limited to 30/minute but processes the same unsafe decode path. A crashed or saturated worker degrades the application for other users.
- **Recommended remediation (not implemented):** Upgrade Pillow to a release that remediates the assigned reachable advisories; set a web-process pixel limit before either `Image.open`, turn decompression-bomb warnings into controlled rejections, require a decoded `source.format` from the allowed set (using `formats=` where supported), and apply an appropriate upload rate limit. Retain the WebP re-encode.

### ACCOUNT-002 — Replaced and deleted display-image objects remain in S3 but are removed from quota accounting

- **Severity:** Medium
- **Confidence:** High for code-path behavior; Medium for persistent cost impact because an external S3 lifecycle rule is not represented in this repository
- **CWE:** CWE-400 (uncontrolled resource consumption)
- **Location:** `app/display_images.py:65-83,86-90`; `app/storage/quota.py:6-24`; `app/storage/services.py:140-156`
- **Reachability:** Any authenticated user can repeatedly replace or delete their own avatar through the unrate-limited `/account/` POST routes. The same shared helper is also used for partner, company, and branding display images.
- **Vulnerable code:**
  ```python
  # app/display_images.py:73-83
  db.session.add(obj); db.session.flush()
  with tempfile.NamedTemporaryFile(suffix=".webp") as temp:
      temp.write(encoded); temp.flush()
      get_storage_provider().upload_object(obj.bucket, obj.object_key, temp.name, "image/webp", {"sha256": obj.checksum_sha256})
  ...
  old = getattr(record, attribute)
  setattr(record, f"{attribute}_id", obj.id)
  if old:
      old.deleted_at = db.func.now(); old.upload_status = "deleted"
  ```
  ```python
  # app/display_images.py:86-90
  def remove_display_image(record, *, attribute):
      old = getattr(record, attribute)
      if old:
          old.deleted_at = db.func.now(); old.upload_status = "deleted"
      setattr(record, f"{attribute}_id", None)
  ```
  ```python
  # app/storage/quota.py:6-10
  originals = db.session.query(func.coalesce(func.sum(StorageObject.file_size), 0)).filter(
      StorageObject.upload_status == "active", StorageObject.deleted_at.is_(None)).scalar()
  ```
- **Exploit:** Submit distinct valid avatar images repeatedly. Each replacement first uploads a new UUID-keyed WebP. It then only marks the prior database object `deleted`; it never calls `get_storage_provider().delete_object`. The only in-repository object deletion sweep is explicitly restricted to stale **pending** uploads:
  ```python
  # app/storage/services.py:140-150
  objects = StorageObject.query.filter(StorageObject.upload_status == "pending", StorageObject.created_at < threshold).all()
  ...
  provider.delete_object(storage_object.bucket, storage_object.object_key)
  storage_object.upload_status = "failed"
  ```
  Therefore replaced/deleted display objects are neither selected nor physically removed by this cleanup. They also stop counting toward `ensure_storage_capacity()` because quota sums only active, non-deleted rows. The pre-upload quota check at `app/display_images.py:65-67` consequently remains near the size of the current avatar rather than cumulative historical S3 bytes.
- **Impact:** A normal account can generate unbounded retained S3 objects/cost by cycling a 10 MB-or-smaller accepted upload. This is a data-retention and quota-integrity issue; object keys are UUIDs, so it does not by itself grant another user read access.
- **Recommended remediation (not implemented):** Define a retention policy explicitly: either delete the old provider object after the replacement transaction commits, or retain soft-deleted objects only with a scheduled lifecycle/cleanup job that includes them in accounting until removal. Coordinate the DB/storage transaction so a failed DB commit does not strand an active unreferenced object.

## Needs verification

- No S3 lifecycle configuration is present in the repository. An external bucket rule could eventually delete `display-images/*` objects and reduce ACCOUNT-002's persistence/cost impact; proving that requires the deployed bucket policy, which was not accessed.
- The runtime Pillow plugin registry and exact upstream advisory applicability were not executed against crafted files (no PoCs were created or run). The source-level finding does not depend on a PoC: format selection is unrestricted in code and the installed package is `Pillow==10.4.0`.
- The limiter key is `get_remote_address` (`app/extensions.py:1-12`). Whether the 30/min preview limit is globally shared across web workers depends on the deployed limiter backend; this does not mitigate the unrate-limited account upload route.

## Explicitly checked and found clean

- **Authentication, ownership, and association:** `profile()` passes `current_user` as both target record and uploader (`app/account/routes.py:17-20`); `delete_avatar()` does the same (`:30-32`). No target user ID, storage-object ID, mass-assigned profile field, or client-selected scope is accepted. `StorageObject.uploaded_by_id=user.id` is assigned server-side (`app/display_images.py:68-72`).
- **Avatar serving:** `avatar()` reads only `current_user.avatar_storage_object` and rejects both `deleted_at` and non-`active` status before creating the inline URL (`app/account/routes.py:38-45`). Profile/base rendering calls `url_for('account.avatar')`, not a storage key or user-controlled URL (`app/templates/account/profile.html:3`; `app/templates/base.html:76,138`).
- **Replacement sequencing:** new bytes upload before the account foreign-key association, and the old row is marked deleted only after upload succeeds (`app/display_images.py:73-82`). A storage upload error is not intentionally converted into a false success. However, no distributed transaction exists; the orphan/cleanup limitation is captured in ACCOUNT-002.
- **Image output:** both web paths fully decode then save a fresh WebP (`app/display_images.py:49-60`, `app/account/routes.py:61-65`). EXIF is not passed to `save`, so the output does not intentionally retain original EXIF metadata. SVG is not in the extension allow-list and Pillow does not receive an SVG-specific active-content path; successful responses have fixed `image/webp` type (`app/account/routes.py:68`) and application-wide `X-Content-Type-Options: nosniff` (`app/__init__.py:221-235`).
- **Preview controls:** `/media-display-preview` is registered POST-only with endpoint `media_display_preview` (`app/__init__.py:112-115`), has `@login_required` and `@limiter.limit("30 per minute")` (`app/account/routes.py:48-50`), inherits global CSRF protection, enforces a 10 MB raw-byte limit (`:57-59`) and the global Flask request cap defaults to 10 MB (`app/config.py:43-46`; `app/__init__.py:241-249`). `send_file(..., max_age=0)` avoids a positive freshness lifetime. It creates no database or S3 object (`app/account/routes.py:50-68`).
- **Module switcher and redirects:** cards are generated from a constant module list and `url_for` for fixed endpoints (`app/modules/services.py:8-39`); the Semgrep `href="{{ module.url }}"` lead is a false positive for user-controlled URL injection. Each select route checks the corresponding access predicate before `session["active_module"]` is changed (`app/modules/routes.py:14-39`), and accepts no `next`/return parameter. No module-switcher open redirect was found. `active_module` is only a navigation fallback; the request blueprint takes precedence (`app/navigation.py:29-41`), while destination routes retain their own global/blueprint/RBAC checks.
- **Account PII, passwords, and audit:** profile renders the caller's own full name, username, and email only (`app/templates/account/profile.html:2`); it renders no password field/hash. Avatar upload/delete do not call `log_audit`; this is recorded as an audit-coverage gap, not an authorization vulnerability, because no project/admin authority or PII boundary is crossed.
- **pillow-heif lead:** the application only registers the HEIF decoder (`app/display_images.py:22-26`) and always calls `image.save(..., "WEBP")` (`:58`); no HEIF encode call was found in the reviewed call chain. The assigned encode-path pillow-heif advisory is therefore not a distinct reachable finding.

## Counts

| Severity | Critical | High | Medium | Low | Info | Needs verification |
|---|---:|---:|---:|---:|---:|---:|
| Unit 10 | 0 | 1 | 1 | 0 | 0 | 3 |

Primary files read in full: `app/account/__init__.py`, `app/account/routes.py`, `app/modules/__init__.py`, `app/modules/routes.py`, `app/modules/services.py`, `app/display_images.py`, `app/templates/account/profile.html`, and `app/templates/modules/index.html` (8/8). Files unread in the assigned primary scope: none.
