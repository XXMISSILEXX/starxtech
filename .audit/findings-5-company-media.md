# Findings — Company Media (Unit 5)

## Summary

- Company Media is a global, album-scoped library. It has no project dimension: access is derived from global RBAC and/or `CompanyMediaAlbumPermission` ACL rows. Its own blueprint gate runs after the global login hook.
- All 24 Company Media URL rules were traced from route through the blueprint gate, permission helper, storage/bulk-download service, ORM relationship, and storage side effect. File IDs are resolved from the database and, for bulk paths, constrained to the requested album.
- The principal high-impact issue found is distinct from the already verified ACL `can_share` self-escalation: a view-only subject can request a presigned URL for an original video despite the separate download permission and ACL flag.
- Several lower-impact issues concern audit completeness, directory metadata disclosure, raw exception disclosure, and duplicate-album integrity under concurrency. The generic storage quota race and the bounded bearer-URL lifetime are inherited Foundation-B concerns and are not duplicated here as Company Media findings.
- Files read in full: 25 (4 Company Media Python files, 3 Company Media templates, 12 direct authorization/storage/model/bulk/media-processing helpers, 4 shared audit artefacts, plus `app/__init__.py`/`app/audit.py`). Files skipped: none in the assigned primary scope. The excluded `claude-partial-audit-backup/` tree was not read.

## Findings

### CM-001 — View permission can mint a presigned URL for an original video, bypassing download permission

- **Severity:** High
- **Confidence:** High
- **CWE:** CWE-863 (Incorrect Authorization)
- **Classification:** Reachable authorization vulnerability.
- **Location:** `app/company_media/routes.py:98-102`, `app/company_media/permissions.py:78-81`, `app/company_media/services.py:45-52`
- **Reachability:** Any authenticated active user who can enter Company Media and has `company_media_files.view`/album ACL `can_view` on an album. The user need not have `company_media_files.download` or ACL `can_download`.
- **Evidence:** The preview route performs only the view check before calling the signer:

  ```python
  # app/company_media/routes.py:98-102
  @bp.post("/files/<int:file_id>/signed-preview")
  def preview(file_id):
      f=_one(CompanyMediaFile, file_id)
      if not p.view_file(current_user,f):abort(403)
      return jsonify(s.signed_preview(f,(request.get_json() or {}).get("variant"),current_user))
  ```

  `view_file` checks the album action but neither file lifecycle flag:

  ```python
  # app/company_media/permissions.py:78-81
  def view_file(user, file, archived=False): return bool(file and _can(user, file.album, "company_media_files.view", "view", archived))
  def download_file(user, file): return bool(file and file.is_active and not file.deleted_at and _can(user, file.album, "company_media_files.download", "download"))
  ```

  For MP4/WebM, `signed_preview` signs the original object's key after no additional authorization or object-state check:

  ```python
  # app/company_media/services.py:45-52
  def signed_preview(f,variant=None,user=None):
      obj=f.storage_object; types=("thumbnail","preview") if obj.mime_type.startswith("image/") else ("poster",)
      if obj.mime_type in {"video/mp4", "video/webm"} and variant in {"preview", "stream"}:
          ...
          return {"ok":True,"status":"ready","kind":"video","mime_type":obj.mime_type,"url":get_storage_provider().create_presigned_download(obj.bucket,obj.object_key,300,"inline",f.display_name)["url"]}
  ```

- **Exploit:** A view-only subject sends `POST /company-media/files/<video-id>/signed-preview` with JSON `{"variant":"preview"}`. The server returns a 300-second S3 URL for `StorageObject.object_key`, which contains the original video bytes. The subject can retrieve/save that URL's response although `POST /company-media/files/<video-id>/signed-download` would reject them via `download_file()`.
- **Impact:** The separately modelled `company_media_files.download` RBAC permission and ACL `can_download` flag do not protect original MP4/WebM content. The same missing lifecycle check also allows preview of an archived/soft-deleted `CompanyMediaFile` while its album remains accessible. A presigned URL is a bearer capability for its TTL; subsequent session/ACL revocation does not revoke it.
- **Recommended remediation (not implemented):** Require `download_file(user, file)` for any branch that returns an original-object URL, or make the preview endpoint return only a derivative that is explicitly authorized by view permission. In every signing branch, re-check the file lifecycle and `StorageObject.upload_status == "active" and deleted_at is None` in the service, not just the route.
- **Effort:** S

### CM-002 — Share-capable album users receive the full active-user directory and all roles

- **Severity:** Low
- **Confidence:** High
- **CWE:** CWE-200 (Exposure of Sensitive Information)
- **Classification:** Reachable metadata-disclosure / least-privilege gap.
- **Location:** `app/company_media/routes.py:172-196`
- **Reachability:** Any active user that satisfies `share_album(current_user, album, True)`. Per `app/company_media/permissions.py:64-67`, a matching album ACL with only `can_share` can satisfy this check; this finding does not rely on exercising the separately verified self-escalation issue.
- **Evidence:** After only the album share check, the GET route serializes every active user, including email and role name, and every role into the response data:

  ```python
  # app/company_media/routes.py:172-196
  if not p.share_album(current_user,a,True):abort(403)
  ...
  users = User.query.filter_by(is_active=True).order_by(User.full_name, User.username).all()
  roles = Role.query.order_by(Role.name, Role.code).all()
  principal_options = [
      {"type": "user", "id": user.id, "name": user.full_name, "username": user.username,
       "email": user.email, "role": user.role.name if user.role else ""}
      for user in users
  ] + [
      {"type": "role", "id": role.id, "name": role.name, "description": role.description,
       "code": role.code}
      for role in roles
  ]
  ```

- **Exploit:** A user legitimately granted `can_share` on one album requests its permissions page and obtains the organization-wide active-user names, usernames, emails, role labels, and complete role catalogue, regardless of any other album visibility.
- **Impact:** Album-specific sharing authority implicitly grants a broader directory-read capability. This expands personal-data and role-structure exposure beyond the target album. The data may be intentionally necessary for this UI, so the severity is low; the source proves the disclosure but not the business need.
- **Recommended remediation (not implemented):** Decide whether every album sharer is entitled to directory access. If not, restrict the principal search result to an authorized directory scope, minimize returned fields, and use a separately authorized lookup endpoint.
- **Effort:** M

### CM-003 — Bulk archive/restore accept uncapped, untyped IDs and can amplify database work

- **Severity:** Low
- **Confidence:** High
- **CWE:** CWE-400 (Uncontrolled Resource Consumption)
- **Classification:** Reachable availability/performance debt.
- **Location:** `app/company_media/routes.py:127-143`
- **Reachability:** Any user who can view an album can invoke both bulk endpoints. Per-file delete/restore permission is checked later, but parsing and the unbounded query happen first.
- **Evidence:** The route trusts `parse_file_ids()` directly, passes the resulting list into an `IN` predicate without normalization, deduplication, or a count bound, and has no route limiter:

  ```python
  # app/company_media/routes.py:127-143
  def _bulk(album_id, action):
      a=_one(CompanyMediaAlbum, album_id)
      if not p.view_album(current_user,a):abort(403)
      try: ids=parse_file_ids(request)
      except BulkDownloadError as exc: return jsonify(error=str(exc)),400
      items=CompanyMediaFile.query.filter(CompanyMediaFile.album_id==a.id,CompanyMediaFile.id.in_(ids)).all(); result={action:[] if action=="downloads" else 0,"skipped":0,"forbidden":0}
      ...
  @bp.post("/albums/<int:album_id>/files/bulk-archive")
  def bulk_archive(album_id): return _bulk(album_id,"archived")
  @bp.post("/albums/<int:album_id>/files/bulk-restore")
  def bulk_restore(album_id): return _bulk(album_id,"restored")
  ```

  The normal bulk-download implementation demonstrates the missing boundary by converting and deduplicating IDs and then imposing a 100-file maximum:

  ```python
  # app/bulk_downloads/services.py:199-208,264-267
  ids = _normal_ids(requested_ids)
  if not ids or len(files) != len(ids):
      raise BulkDownloadError("Tệp đã chọn không thuộc vị trí hiện tại.")
  if len(files) > int(current_app.config["BULK_DOWNLOAD_MAX_FILES"]):
      raise BulkDownloadError("Bạn chỉ có thể tải xuống tối đa 100 tệp mỗi lần.")
  ...
  def _normal_ids(values):
      try: ids = [int(value) for value in (values or [])]
      except (TypeError, ValueError): raise BulkDownloadError("Danh sách tệp không hợp lệ.")
      return list(dict.fromkeys(ids))
  ```

- **Exploit:** An album viewer posts a large JSON or form `file_ids` list to bulk archive/restore. Before authorization rejects individual items, the application creates a correspondingly large SQL `IN` query and iterates all matched rows. Non-numeric values can also reach the database type coercion path rather than returning a controlled 400.
- **Impact:** Repeated requests can consume application/database resources and may exceed database parameter/type limits, producing 500 responses. `MAX_CONTENT_LENGTH` bounds the request body but still permits a multi-megabyte list; no endpoint-specific rate limit or item-count limit narrows it.
- **Recommended remediation (not implemented):** Reuse a server-side `_normal_ids`-style parser before the query, reject non-integers, deduplicate, cap the list (the Project Documents equivalent uses 50), and return 400/403 for invalid/all-forbidden selections.
- **Effort:** S

### CM-004 — Sensitive Company Media mutations lack audit records

- **Severity:** Low
- **Confidence:** High
- **CWE:** CWE-778 (Insufficient Logging)
- **Classification:** Reachable forensic/audit-coverage gap.
- **Location:** `app/company_media/routes.py:66-70,109-126,127-143,172-183`; contrast `app/company_media/services.py:31-34,74-77`
- **Reachability:** Any actor authorized for the respective edit/delete/restore/share action.
- **Evidence:** Several writes commit directly with no `audit(...)` call:

  ```python
  # app/company_media/routes.py:66-70
  def clear_cover(album_id):
      a=_one(CompanyMediaAlbum, album_id)
      if not p.edit_album(current_user,a): abort(403)
      a.cover_media_id=None; s.db.session.commit();return redirect(...)

  # app/company_media/routes.py:109-126
  else: f.display_name=name;f.updated_by_id=current_user.id;s.db.session.commit()
  ...
  f.is_active=False;f.deleted_at=__import__('datetime').datetime.utcnow();f.updated_by_id=current_user.id;s.db.session.commit()
  ...
  f.is_active=True;f.deleted_at=None;f.updated_by_id=current_user.id;s.db.session.commit()

  # app/company_media/routes.py:177-183
  if request.form.get("remove_id"):
      ...
      else:s.db.session.delete(entry);s.db.session.commit()
  else:
      try:s.set_permission(current_user,a,...)
  ```

  `set_permission` itself commits without recording a share event:

  ```python
  # app/company_media/services.py:91-95
  flags=("can_view","can_upload","can_edit","can_delete","can_download","can_share")
  ...
  for flag in flags: setattr(entry,flag,bool(form.get(flag)))
  db.session.add(entry);db.session.commit();return entry
  ```

  This is inconsistent with the adjacent audited operations, for example:

  ```python
  # app/company_media/services.py:74-77
  def set_cover(user,a,media_id):
      ...
      a.cover_media_id=f.id;a.updated_by_id=user.id;audit("company_media.album.cover","CompanyMediaAlbum",a.id);db.session.commit()
  ```

- **Exploit:** An authorized user can rename, archive, restore, bulk-archive/bulk-restore media, clear a cover, or grant/revoke an album ACL without a corresponding `AuditLog` row. This is especially consequential for ACL changes because it leaves no record of the grant/revocation event itself.
- **Impact:** Incident response cannot reliably attribute those business and authorization changes. This does not bypass the route authorization checks, so it is a low-severity detection/forensics issue rather than a direct privilege escalation.
- **Recommended remediation (not implemented):** Centralize these mutations in audited service functions and write an audit event, with actor, target, before/after values, in the same database transaction as each state change.
- **Effort:** M

### CM-005 — Upload presign endpoint returns raw exception messages

- **Severity:** Low
- **Confidence:** Medium
- **CWE:** CWE-209 (Generation of Error Message Containing Sensitive Information)
- **Classification:** Reachable information-disclosure gap; exact production message content needs verification.
- **Location:** `app/company_media/routes.py:71-78`
- **Reachability:** Any user with `upload_album` access to an album. The route is not rate limited.
- **Evidence:** The endpoint catches every exception and reflects `str(e)` in JSON:

  ```python
  # app/company_media/routes.py:71-78
  @bp.post("/albums/<int:album_id>/files/presign-batch")
  def presign(album_id):
      ...
      try:
          data=request.get_json() or {}; return jsonify(s.presign(current_user,a,data.get("files",[]),data.get("selection_session_id")))
      except StorageAuthorizationError: abort(403)
      except Exception as e:return jsonify(error=str(e)),400
  ```

- **Exploit:** An authorized uploader can submit malformed upload metadata that reaches an unexpected exception, or induce a storage/provider failure, and receive the exception's message in the response.
- **Impact:** At minimum, this exposes Python validation/type details. Depending on the exception source, it can disclose storage/SQLAlchemy implementation and deployment information. No claim is made that credentials are exposed: that requires a controlled non-production test and inspection of the configured provider errors.
- **Recommended remediation (not implemented):** Catch only expected validation/storage exceptions, return a fixed user-safe message for unexpected failures, and log exception detail server-side.
- **Effort:** S

### CM-006 — Album-name uniqueness has no transaction or database backstop

- **Severity:** Low
- **Confidence:** High
- **CWE:** CWE-362 (Race Condition)
- **Classification:** Reachable data-integrity race, not an authorization bypass.
- **Location:** `app/company_media/services.py:28-31`; `app/models/company_media.py:8-22`
- **Reachability:** Any user allowed to create albums can issue concurrent create requests for the same name.
- **Evidence:** Name uniqueness is enforced only by a read before insert:

  ```python
  # app/company_media/services.py:28-31
  def create_album(user,name,description="",restricted=False):
      name=_name(name)
      if CompanyMediaAlbum.query.filter(func.lower(CompanyMediaAlbum.name)==name.lower(),CompanyMediaAlbum.is_active.is_(True),CompanyMediaAlbum.deleted_at.is_(None)).first(): raise CompanyMediaError("Đã có album cùng tên.")
      a=CompanyMediaAlbum(name=name,description=(description or "").strip() or None,is_restricted=restricted,created_by_id=user.id);db.session.add(a);db.session.flush();audit("company_media.album.create","CompanyMediaAlbum",a.id);db.session.commit();return a
  ```

  The model has no unique constraint/index on `name` (only fields and relationships are declared):

  ```python
  # app/models/company_media.py:8-22
  class CompanyMediaAlbum(TimestampMixin, db.Model):
      __tablename__ = "company_media_albums"
      id = db.Column(DOCUMENT_ID, primary_key=True)
      name = db.Column(db.String(255), nullable=False)
      ...
      files = db.relationship("CompanyMediaFile", back_populates="album")
      permissions = db.relationship("CompanyMediaAlbumPermission", back_populates="album", cascade="all, delete-orphan")
  ```

- **Exploit:** Two concurrent create requests for the same normalized album name can both observe no active match and commit separate albums.
- **Impact:** Duplicate albums can have different ACLs and make administrative selection/audit interpretation ambiguous. This is a correctness/data-integrity issue; the duplicate IDs remain distinct and no cross-album access follows solely from duplication.
- **Recommended remediation (not implemented):** Add a database constraint/index matching the intended active-name semantics and translate `IntegrityError` into `CompanyMediaError`; retain the application-level pre-check for a friendly common-case response.
- **Effort:** M

## Known verified critical finding not duplicated

The `can_share` ACL self-escalation is already verified in [.audit/VERIFIED-CRITICAL.md](VERIFIED-CRITICAL.md) and has an existing failing PoC under `.audit/poc/`. It is not assigned a new finding ID or counted above.

The reviewed root cause is `app/company_media/permissions.py:64-68`, where a matching ACL directly returns success, combined with `app/company_media/services.py:91-95`, which lets a share-capable actor choose any permission flags without comparing them to the actor's existing authority. This report references that behavior only where needed to establish different exposure paths (for example, the permissions-page directory disclosure); it does not duplicate the escalation finding.

## Project Documents comparison — independently completed

The permission-grant implementations are materially similar in input validation and upsert behavior but have different enforcement consequences. This table is a separate Company Media review; it does not modify Unit 4's deliverable.

| Control | Project Documents evidence | Company Media evidence | Equivalent? | Security consequence |
|---|---|---|---|---|
| Module/RBAC backstop | `app/project_documents/permissions.py:46-48` requires `_base(...) and _acl_allows(...)`; `_base` is project capability or module + action-RBAC at `:4-14`. | `app/company_media/permissions.py:64-68` returns `True` for a matching ACL before `has_module_access(user) and user.can(code)`. `access()` also admits `has_album_acl` at `:36-41`. | No | Company Media ACL can be the entire module/action grant; Project Documents ACL only narrows independently held baseline authority. This difference underlies the separately verified critical escalation. |
| Who may share | Route calls `can_share_project_document_folder` before `set_folder_permission`: `app/project_documents/routes.py:317-319`; capability/action is `can_share_documents`/`share` at `permissions.py:56`. | Route calls `p.share_album(..., True)` before `set_permission`: `app/company_media/routes.py:172-182`; capability is album-share / ACL `can_share` at `permissions.py:77`. | No | Both have an authorization check, but Company Media makes a bare matching share ACL sufficient; Project Documents also requires the sharer’s base capability. |
| Actor must possess granted capabilities | `set_folder_permission` accepts all five supplied flags without comparing them to actor flags: `project_documents/services.py:442-457`. | `set_permission` accepts all six supplied flags without an actor-capability comparison: `app/company_media/services.py:91-95`. | Input validation is equivalent; exploitability differs. | In Project Documents the `_base` AND gate neutralizes an over-grant. In Company Media this is the known verified critical issue; not duplicated here. |
| User principal validation | Existing, active `User` required: `project_documents/services.py:435-438`. | Existing, active `User` required: `app/company_media/services.py:83-88`. | Yes | Prevents grants to nonexistent/inactive user principals. |
| Role principal validation | Existing `Role` required: `project_documents/services.py:439-440`. | Existing `Role` required: `app/company_media/services.py:89-90`. | Yes | A role ACL intentionally applies to every user whose canonical `role_id` matches (`permissions.py:43` vs `app/company_media/permissions.py:44-46`); no hierarchy/implicit cross-role expansion was found. Neither implementation restricts grantable role codes. |
| Principal/flags input and duplicates | Type allow-list, digits, positive ID, at least one of five flags, explicit scoped query then create: `project_documents/services.py:429-457`. DB uniqueness is `(folder_id,user_id)`/`(folder_id,role_id)` in `app/models/project_document.py`. | Same type/positive/existence checks, six flags, and `query.first() or Model(...)`: `app/company_media/services.py:78-95`. DB uniqueness is `(album_id,user_id)`/`(album_id,role_id)` at `app/models/company_media.py:42-59`. | Yes in effect | Duplicate ACL rows are prevented by schema; concurrent upserts can still surface an `IntegrityError` rather than a graceful response because neither code handles it. |
| Target visibility/restricted semantics | ACL is evaluated only at the nearest restricted ancestor; unrestricted folders return `True` before reading rows: `app/project_documents/permissions.py:26-43`. | `_matching_acl_allows` runs before `_acl`’s unrestricted shortcut: `app/company_media/permissions.py:49-68`. | No | A Project Documents ACL on an unrestricted folder is inert; a Company Media ACL is effective even on an unrestricted album. The Company Media template’s statement that unrestricted-album ACLs are ineffective (`templates/company_media/permissions.html:11`) is inconsistent with server enforcement. |
| Project scope | Folder baseline becomes `ProjectUser` capability when `folder.project_id` exists: `app/project_documents/permissions.py:4-14`. | Albums have no project ID (`app/models/company_media.py:8-22`) and permissions are global-RBAC/album ACL only. | No | Project membership cannot constrain Company Media, by design; album ACL is its object scope. |
| Update/removal scope | Updates scoped by `folder_id` and principal; revoke filters both `id` and `folder_id`: `project_documents/services.py:446-465`. | Updates scoped by `album_id` and principal; revoke filters both `id` and `album_id`: `app/company_media/services.py:93`, `routes.py:177-180`. | Yes | Cross-folder/cross-album ACL-ID substitution is closed on removal/update. |
| Audit logging | Grant flushes then calls `audit("document.folder.share", ...)`; revoke audits `document.folder.revoke`: `project_documents/services.py:458-465`. | Neither grant (`app/company_media/services.py:91-95`) nor revoke (`app/company_media/routes.py:177-180`) calls `audit`. | No | Company Media ACL changes are unattributable; recorded independently as CM-004. |
| Transaction boundary | Grant flushes/audits/commits in one service function; revoke also service-owned: `project_documents/services.py:458-465`. | Grant commits in service, but revocation mutates/commits inline in route: `app/company_media/services.py:95`, `routes.py:177-180`. | No | The split increases behavioral drift and is why the route-level revocation lacks a shared audit/validation point. |

## Explicitly checked and found clean

- **Authentication and module gate:** `app/__init__.py:155-167` applies login before blueprint hooks. `app/company_media/routes.py:18-20` then enforces `p.access(current_user)` on every Company Media endpoint. No Company Media endpoint is publicly reachable.
- **Album/file IDOR:** Single-file routes load the `CompanyMediaFile` then derive its album from `file.album`; they never accept a second caller-controlled album ID. Cover assignment additionally checks `f.album_id != a.id` in `app/company_media/services.py:74-77`, and the SQLAlchemy flush listener independently enforces the same album association at `app/models/company_media.py:62-68`.
- **Bulk signed download:** `request_media_download` selects by both `album_id` and requested ID, normalizes IDs, caps selection at 100 files/300 MB, and re-checks `download_file` for every file (`app/bulk_downloads/services.py:64-69,199-232`). Cross-album IDs cannot be smuggled into a ZIP.
- **Upload selection session IDOR:** `_selection_session` binds session owner, module type, target type, and target ID before finalization/presign (`app/storage/services.py:89-97`); Company Media routes pass the requested album as the target (`app/company_media/routes.py:79-92`).
- **Storage-object ownership/association:** `CompanyMediaFile.storage_object_id` is unique (`app/models/company_media.py:25-39`), preventing one storage object from backing multiple media rows. Upload completion checks batch module and target album before attachment (`app/company_media/services.py:36-42`); the missing `target_type` comparison is currently inert because `VALID_SCOPES` permits only `("company_media", "album")` (`app/storage/services.py:14`).
- **Restricted/unrestricted album visibility:** `has_album_acl` filters active, non-deleted albums (`app/company_media/permissions.py:18-33`), and normal album list/detail permissions reject inactive/deleted albums unless their route explicitly requests archived visibility. ACL rows remain after soft archive but cannot confer module access until the album is restored.
- **Unsafe storage keys and upload-size policy:** Company Media uses the Foundation-B POST-presign flow, which binds exact declared size into the S3 policy (`app/storage/providers.py:80-82`). Storage keys are UUID-based/sanitized per Foundation-B; no path traversal or key enumeration path was found in this module.
- **GET side effects:** Company Media GET handlers (`index`, `album`, `bulk_download_status`, permissions GET) do not mutate database state. State changes use POST and remain under global CSRF protection.
- **Role ACL semantics:** ACL matching compares the target role row to the user’s canonical non-null `role_id` (`app/company_media/permissions.py:44-46`; `app/models/user.py:21,77-82`). A role ACL applies to all holders of that explicit role, as intended; no implicit role hierarchy or cross-project expansion exists.
- **Celery failure handling:** `enqueue_media_processing_for_storage_object` commits the durable media job first and catches dispatch failure (`app/media_processing/services.py:96-111`); upload completion remains durable rather than partially rolling back because a worker/broker is unavailable.

## Needs verification

1. **Production presigned-URL containment:** Source confirms 300-second bearer URLs (`app/storage/providers.py:90-92`) and no source-side revocation. Production S3/MinIO CORS, bucket policy, proxy/referrer handling, browser history, and cache behavior are deployment-state facts not readable under this audit’s remote-system prohibition.
2. **CM-005 exact error exposure:** A controlled non-production test should exercise provider and unexpected ORM failures to establish which messages reach an uploader. No PoC was created, and no storage system was contacted.
3. **Concurrent grant/create UX:** The schema enforces ACL uniqueness but neither ACL upsert catches `IntegrityError`; album names have no matching database constraint. A PostgreSQL concurrency test is needed to quantify resulting response behavior. This report proves the missing transaction backstops, not a production race outcome.
4. **Storage content validation:** Foundation-B establishes that Company Media validates declared extension/MIME and POST size, not magic bytes. The downstream media worker decodes client-controlled bytes asynchronously; whether that operational risk is accepted is owned by Foundation-B/worker deployment review, not re-reported here.

## Tool leads closed as false positive/info

- No Semgrep, pip-audit, or Trivy lead in `.audit/TOOL-LEAD-MAP.md` is assigned specifically to Unit 5. The relevant shared storage/Pillow tooling leads are assigned to Foundation-B/Unit 10 and were not duplicated.
- The existing Company Media `can_share` escalation is a confirmed issue, not a scanner lead. It is intentionally cross-referenced above and excluded from this report’s counts.
- The missing `target_type` comparison in `app/company_media/services.py:38` is **Info / defense in depth**, not a currently reachable substitution: `app/storage/services.py:14` currently admits only the `("company_media", "album")` pair.
- The generic quota check-then-act race and the lack of automatic cleanup scheduling are Foundation-B findings affecting the shared storage service; Company Media invokes that service but does not create a distinct root cause.
