# Findings — Unit 4: Project Documents

## Summary

- The registered `project_documents` blueprint is mounted at `/project-documents` (`app/project_documents/__init__.py:3`) and is registered by `app/__init__.py:123`. App-wide login runs before the blueprint hook (`app/__init__.py:155-167`); the hook then denies callers that fail `can_access_project_documents()` (`app/project_documents/routes.py:25-27`).
- Project-scoped authorization is capability-based (`can_view_documents`, `can_upload_documents`, etc.) and restricted folders add an ACL requirement inherited from the nearest restricted ancestor (`app/project_documents/permissions.py:26-48`). There is no ORM-level tenant filter, so these checks are the project boundary.
- Project Document files are tied to their folder's project at ORM flush time (`app/models/project_document.py:91-99`). File routes derive the folder/project from the loaded file rather than accepting a project ID, and upload completion binds the batch item to the target folder.
- A restricted-folder sharee with only `can_share` can overwrite their own ACL to add unrelated permissions. This is a distinct Project Documents root cause; the already verified Company Media ACL escalation remains documented only in `.audit/VERIFIED-CRITICAL.md`.
- Archive state is checked only on the target folder/file, not every ancestor. Archiving a parent does not prevent direct access to its still-active descendants.
- Files read: 24 primary/supporting code and template files in full (including all four `app/project_documents/` Python files and all three matching templates) | Files skipped: no primary-scope files; bytecode under `__pycache__/` was not read because it is generated, non-authoritative output.

## Findings

### PD-001 — Restricted-folder `can_share` holder can grant themselves unrelated ACL capabilities

- **Severity:** High
- **Confidence:** High
- **CWE:** CWE-269 (Improper Privilege Management)
- **Location:** `app/project_documents/permissions.py:35-56`; `app/project_documents/routes.py:316-323`; `app/project_documents/services.py:429-459`
- **Reachability:** An authenticated, active non-admin member who has the project-level `can_share_documents` flag and a matching `can_share` ACL at a restricted folder (or nearest restricted ancestor) can reach `POST /project-documents/folders/<folder_id>/permissions`. Global login and the module hook apply, but neither restricts the ACL flags the sharing actor may set.
- **Vulnerable code:**

  ```python
  def can_share_project_document_folder(user, folder, include_archived=False): return _can(user, folder, "can_share_documents", "share", include_archived)
  ```
  `app/project_documents/permissions.py:56`

  ```python
  flag = "can_" + action
  return any(getattr(entry, flag, False) for entry in anchor.permissions
             if (entry.user_id == user.id or entry.role_id == user.role_id))
  ```
  `app/project_documents/permissions.py:41-43`

  ```python
  if not can_share_project_document_folder(current_user, target, include_archived=not (target.is_active and target.deleted_at is None)): abort(403)
  if request.method == "POST":
      ...
      else: set_folder_permission(current_user, target, request.form.get("principal_type"), request.form.get("principal_id"), request.form)
  ```
  `app/project_documents/routes.py:319-323`

  ```python
  entry = query.first()
  if not entry:
      entry = ProjectDocumentFolderPermission(...)
      db.session.add(entry)
  for flag in permission_flags:
      setattr(entry, flag, bool(flags.get(flag)))
  db.session.flush(); audit("document.folder.share", "ProjectDocumentFolder", folder.id,
      new_values={"principal_type": principal_type, "principal_id": principal_id}); db.session.commit(); return entry
  ```
  `app/project_documents/services.py:451-459`

- **Exploit:**
  1. Give a project member `can_share_documents` and one or more target project capabilities (for example `can_edit_documents` or `can_archive_documents`), but give the member a direct (or role) ACL at a restricted folder containing only `can_share=True`. The project capability is otherwise denied by the folder restriction.
  2. The member sends a valid CSRF-protected POST to that folder's permissions endpoint with `principal_type=user`, `principal_id=<their own ID>`, and `can_edit=1`, `can_delete=1`, and/or `can_upload=1`.
  3. `can_share_project_document_folder` succeeds from the existing share ACL. `set_folder_permission` finds the same `(folder_id, user_id)` row and overwrites every flag without comparing the requested set to the actor's ACL or project capabilities.
  4. Subsequent checks consult the newly added matching ACL entry, allowing the actor to use the target project capability in the previously restricted subtree; the actor can also remove or rewrite other principals' ACLs through the same `can_share` route.
- **Impact:** A scoped sharing delegate can turn a narrow share permission into edit, upload, archive, and continued sharing permission on a restricted folder and its descendants. The attack is limited by the independent project capability layer for project folders, so it is not a duplicate of Company Media's broader ACL-only action bypass; it is still a real least-privilege failure at the restricted-folder boundary.
- **Fix:** Make ACL grants monotonic with the actor's authority: resolve the actor's effective ACL at the restriction anchor and reject every requested flag the actor lacks; separately define whether a sharer may edit/remove only ACL entries they created. Enforce this in `set_folder_permission`, not only the route, and retain the route gate.
- **Effort:** M

### PD-002 — Archived ancestor does not block direct descendant and file access

- **Severity:** Medium
- **Confidence:** High
- **CWE:** CWE-284 (Improper Access Control)
- **Location:** `app/project_documents/services.py:415-418`; `app/project_documents/permissions.py:26-48,59-63`; `app/project_documents/routes.py:73-79,152-165`
- **Reachability:** Any user who could view a descendant of a folder before its parent is archived can continue to request the descendant's ID directly, then obtain a download/preview URL for a still-active file. The caller must remain authenticated, in the Documents module, and hold the existing project/ACL capability.
- **Vulnerable code:**

  ```python
  def archive_folder(user, folder):
      if folder.is_root: raise DocumentValidationError("Không thể lưu trữ thư mục gốc.")
      folder.is_active = False; folder.deleted_at = datetime.utcnow(); folder.updated_by_id = user.id
      audit("document.folder.archive", "ProjectDocumentFolder", folder.id); db.session.commit(); return folder
  ```
  `app/project_documents/services.py:415-418`

  ```python
  def _can(user, folder, capability, action, include_archived=False):
      return bool(folder and (include_archived or (folder.is_active and folder.deleted_at is None))
                  and _base(user, capability, folder.project_id) and _acl_allows(user, folder, action))
  ```
  `app/project_documents/permissions.py:46-48`

  ```python
  def can_download_project_document_file(user, file):
      return bool(file and file.is_active and file.deleted_at is None and _can(user, file.folder, "can_view_documents", "view"))
  ```
  `app/project_documents/permissions.py:62-63`

  ```python
  target = db.get_or_404(ProjectDocumentFolder, folder_id)
  if not can_view_project_document_folder(current_user, target, include_archived=True): abort(403)
  ```
  `app/project_documents/routes.py:75-76`

- **Exploit:**
  1. Create a folder P with an active child C and an active file F in C; give a user the usual view capability/ACL.
  2. An authorized actor archives P. Only P is changed; C and F remain active.
  3. The user requests `GET /project-documents/folders/<C>` or posts to `POST /project-documents/files/<F>/signed-download`.
  4. `_can` checks C's state but never walks parents to require P active. The request therefore succeeds and the storage URL is issued.
- **Impact:** Folder archival does not withdraw access to its descendant documents. This is material where archive is used to remove completed, superseded, or sensitive directory trees from normal access; guessing or retaining a child/file ID is sufficient after an archive operation.
- **Fix:** Define archive semantics explicitly. If archive is subtree-wide, cascade archive/restore atomically. If it is ancestor-gating, add an ancestor-active check to `_can` (and all list/bulk paths) before authorizing a child or file.
- **Effort:** M

### PD-003 — A GET route creates a project root folder outside CSRF protection

- **Severity:** Low
- **Confidence:** High
- **CWE:** CWE-352 (Cross-Site Request Forgery)
- **Location:** `app/project_documents/routes.py:46-52`; `app/project_documents/services.py:19-28`
- **Reachability:** An authenticated Documents viewer for a project may be induced to navigate to `GET /project-documents/projects/<project_id>` for an accessible project that has no root. Flask-WTF CSRF protects non-safe methods globally, not this GET.
- **Vulnerable code:**

  ```python
  @bp.get("/projects/<int:project_id>")
  def project_root(project_id):
      project = Project.query.filter_by(id=project_id, deleted_at=None).first_or_404()
      if project not in list_accessible_projects(current_user): abort(403)
      root = get_or_create_project_root_folder(project, current_user)
  ```
  `app/project_documents/routes.py:46-50`

  ```python
  root = ProjectDocumentFolder(project_id=project.id, name="__ROOT__", is_root=True, root_type="project", created_by_id=user.id)
  db.session.add(root)
  db.session.flush()
  audit("document.folder.create", "ProjectDocumentFolder", root.id, new_values={"root": True, "project_id": project.id})
  db.session.commit()
  ```
  `app/project_documents/services.py:23-27`

- **Exploit:** An attacker causes a logged-in permitted user to load the URL for a project with no document root (for example, an image/link/navigation request). The GET inserts a persistent folder and audit record naming the victim as creator.
- **Impact:** Low-integrity state change and misleading audit attribution. There is no attacker-selected folder name, no cross-project bypass, and the unique root invariant bounds it to one root per project.
- **Fix:** Provision roots at project creation or move creation behind a CSRF-protected POST. A GET should load and redirect only.
- **Effort:** S

### PD-004 — Folder and file display-name uniqueness is race-prone

- **Severity:** Low
- **Confidence:** High
- **CWE:** CWE-362 (Race Condition)
- **Location:** `app/project_documents/services.py:102-112,367-385`; `app/models/project_document.py:12-58`
- **Reachability:** Any two authorized creators/uploaders operating concurrently in the same folder can pass the pre-insert name lookup before either commits.
- **Vulnerable code:**

  ```python
  if query.first():
      raise DocumentValidationError("Đã có tệp cùng tên trong thư mục này.")
  ```
  `app/project_documents/services.py:102-112`

  ```python
  if query.first():
      raise DocumentValidationError("Đã có thư mục cùng tên trong vị trí này.")
  ```
  `app/project_documents/services.py:367-373`

  ```python
  __table_args__ = (
      db.Index("idx_project_document_files_folder", "project_id", "folder_id", "deleted_at"),
      db.UniqueConstraint("storage_object_id", name="uq_project_document_files_storage_object"),
  )
  ```
  `app/models/project_document.py:44-47`

- **Exploit:** Two authorized requests submit the same folder name or file display name concurrently. Both see no matching active row and insert/commit. No database unique constraint rejects the second transaction.
- **Impact:** Duplicate display names can confuse selection, sharing, audit review, and file restoration. This is an integrity/performance debt rather than a cross-project authorization bypass.
- **Fix:** Add partial, case-normalized unique constraints for active siblings/files (or serialize creation) and translate `IntegrityError` to the existing validation message.
- **Effort:** M

### PD-005 — A restricted custom-root creator can be locked out of the resource they create

- **Severity:** Info (authorization-consistency / availability debt)
- **Confidence:** High
- **CWE:** CWE-863 (Incorrect Authorization)
- **Location:** `app/project_documents/permissions.py:4-18,35-48`; `app/project_documents/routes.py:36-43`; `app/project_documents/services.py:31-40`
- **Reachability:** An active non-admin granted `project_documents.custom_roots.create` can POST `is_restricted=1`. The normal template does not expose that control, but the server accepts it.
- **Evidence:**

  ```python
  def can_create_custom_root(user):
      return bool(user and user.is_authenticated and user.is_active and (is_project_admin(user) or user.can("project_documents.custom_roots.create")))
  ```
  `app/project_documents/permissions.py:17-18`

  ```python
  root = ProjectDocumentFolder(project_id=None, name=name, description=(description or "").strip() or None,
      is_root=True, root_type="custom", is_restricted=is_restricted, created_by_id=user.id)
  ```
  `app/project_documents/services.py:37-38`

  ```python
  anchor = _restriction_anchor(folder)
  ...
  return any(getattr(entry, flag, False) for entry in anchor.permissions
             if (entry.user_id == user.id or entry.role_id == user.role_id))
  ```
  `app/project_documents/permissions.py:38-43`

- **Impact:** Creation does not add an ACL for the creator. A creator who has only the special create permission (and not the project-less root view RBAC/module permissions plus an ACL) is redirected to a resource they cannot view; if restricted, no non-admin can bootstrap its ACL. This is a functional authorization dead-end, not a confidentiality escalation.
- **Fix:** Either disallow `is_restricted` on this endpoint for non-admins, or create a creator `can_view`/`can_share` ACL atomically and require the base project-less permissions as part of create authorization.
- **Effort:** S

## Project Documents ↔ Company Media permission-grant comparison

The Company Media `can_share` self-escalation is already verified in `.audit/VERIFIED-CRITICAL.md` (finding 05) and is not duplicated as a Company Media finding here. The table compares the implementations because Project Documents independently contains a related, but not identical, grant-subset failure (PD-001).

| Control | Project Documents file:line | Company Media file:line | Equivalent? | Security consequence |
|---|---|---|---|---|
| RBAC/module backstop | Blueprint calls `can_access_project_documents()` at `routes.py:25-27`; project folders use `user_has_project_capability` in `permissions.py:14,46-48`; project-less roots require module + action RBAC in `permissions.py:4-13`. | Blueprint calls `p.access()` at `routes.py:18-20`; `access()` admits any active ACL at `permissions.py:18-41`; `_can()` short-circuits on matching ACL at `permissions.py:64-68`. | No. | PD has an independent project-capability/RBAC layer; CM's matching album ACL itself becomes module and action authority. |
| Who may share | `can_share_project_document_folder` requires base `can_share_documents` plus restricted-anchor `can_share` (if restricted), `permissions.py:35-56`; route enforces it at `routes.py:316-323`. | `share_album` calls `_can(..., "company_media_albums.share", "share")`, `permissions.py:55-77`; a matching `can_share` ACL short-circuits before RBAC, `:64-68`; route is `routes.py:172-182`. | No. | Both allow a sharer to manage ACLs, but CM allows a bare ACL sharee while PD requires the project-level share capability too. |
| Actor's existing capabilities examined during grant | `set_folder_permission` takes `user` but never tests its capabilities/ACL; it validates only target and nonempty flags, `services.py:429-459`. | `set_permission` likewise never tests `user`; it validates only target and nonempty flags, `company_media/services.py:78-95`. | Yes. | Neither service applies defense in depth; its route gate is the only actor check. |
| Actor may grant capabilities they do not possess | Every requested PD flag is assigned without subset enforcement, `project_documents/services.py:442-457`. | Every requested CM flag is assigned without subset enforcement, `company_media/services.py:91-95`. | Yes, with different reach. | PD-001 permits restricted-subtree ACL escalation; the known CM issue lets `can_share` alone grant edit/delete/upload/download on the album. |
| User vs role principal validation | User must exist and be active; role must exist, `project_documents/services.py:435-440`. | Same user existence/active and role existence checks, `company_media/services.py:83-90`. | Yes. | Prevents dangling/new invalid principals but does not limit role ACL reach to an intended project audience. |
| Duplicate ACL behavior | Looks up `(folder_id, principal_type, principal id)` then updates in place, `project_documents/services.py:446-457`; DB has per-folder user/role unique constraints, `models/project_document.py:68-83`. | Same find-or-create pattern at `company_media/services.py:93-95`; DB has equivalent per-album unique constraints, `models/company_media.py:42-55`. | Yes. | Re-submitting an ACL is an overwrite, which makes self-escalation immediate rather than requiring a new duplicate row. |
| Target folder/album visibility | Target must be shareable by actor, including `_acl_allows` at nearest restricted ancestor, `project_documents/routes.py:318-319`, `permissions.py:26-43`. | Target must pass `share_album`, `company_media/routes.py:173-175`; bare matching share ACL satisfies it, `company_media/permissions.py:64-77`. | No. | PD protects the target through both scope and anchor ACL; CM has the verified narrow-ACL escalation condition. |
| Project scope | Folder carries `project_id`; file/folder actions use it in `_base`, and an ORM `before_flush` prevents file/folder project mismatch (`permissions.py:14,46-48`; `models/project_document.py:91-99`). Custom roots explicitly have `project_id=None` and use RBAC, `permissions.py:4-13`. | Albums have no project field (`models/company_media.py:8-22`). | No. | PD ACLs are scoped to a project subtree or a global custom root; CM is global album scope, so a role ACL applies to every active holder of that role for that album. |
| Removal/update semantics | Remove is folder-scoped (`id` plus `folder_id`) and audited, `project_documents/services.py:462-465`; update replaces all five flags, `:442-459`. | Route deletes only by `(id, album_id)` and commits, `company_media/routes.py:177-180`; update replaces all six flags, `services.py:91-95`. | Partially. | Both safely bind removal to parent ID; PD creates an audit record, CM deletion/update lacks one. |
| Audit logging | `document.folder.share` and `document.folder.revoke` audit before commit, `project_documents/services.py:458-465`. | `set_permission` commits with no `audit(...)`, `company_media/services.py:78-95`; ACL deletion commits without audit, `company_media/routes.py:177-180`. | No. | PD changes are reconstructable (although flags themselves are not recorded); CM ACL changes are not reliably attributable. |
| Transaction boundaries | ACL write does `flush`, audit add, then one `commit`, `project_documents/services.py:451-459`; revoke delete/audit/commit, `:462-465`. | ACL write/add/commit is a single basic transaction but no audit, `company_media/services.py:93-95`; delete/commit is route-local, `routes.py:177-180`. | Partially. | Neither handles a concurrent duplicate-ACL `IntegrityError`; PD's audit participates in its commit, CM has no audit to atomically preserve. |

## Explicitly checked and found clean

- **Module and authentication chain:** app-wide login is registered before blueprint hooks (`app/__init__.py:152-189`), blueprint registration is explicit (`:104,123`), and the Documents hook is present on every blueprint route (`app/project_documents/routes.py:25-27`). No route bypasses it.
- **Project/file ID substitution:** File endpoints load only `ProjectDocumentFile` and authorise via `file.folder` (`routes.py:108-110,152-165`; `permissions.py:59-69`); upload completion requires matching module, target type, and target folder (`services.py:131-139`). The ORM rejects a file whose stored project differs from its folder (`models/project_document.py:91-99`).
- **Folder move / traversal:** Route checks both source-edit and destination-create authority (`routes.py:286-290`); service rejects cross-project moves, archived destinations, self/descendant targets, and duplicate sibling names (`services.py:405-412`).
- **Restricted-root inheritance:** `_restriction_anchor` walks ancestors until the nearest restricted folder and `_acl_allows` uses that anchor (`permissions.py:26-43`). Child ACLs do not bypass an ancestor restricted anchor.
- **Bulk archive/restore:** Requested records are constrained to the URL folder (`services.py:285-289`) and each is re-authorized (`:292-328`); cross-folder IDs are not operated on. Bulk ZIP selection uses a stricter all-selected-files validation (`app/bulk_downloads/services.py:199-225`).
- **Single and bulk download authorization:** The route and service both check document-file authority, and active storage requires both `upload_status == "active"` and `deleted_at is None` before a presigned URL is generated (`routes.py:152-157`; `services.py:156-176`). Bulk ZIP validates every file and the selection folder relation (`bulk_downloads/services.py:199-225`). URLs are bearer capabilities for 300 seconds by code (`services.py:171,198,210,239`), a bounded and documented consequence rather than a route authorization bypass.
- **Archive/restore and deletion:** There is no hard-delete folder/file route in this module. File archive is soft state only and does not call object-storage deletion (`services.py:254-266`); restore checks the direct parent folder is active (`:261-266`). Folder operations audit create/rename/move/archive/restore (`services.py:376-426`).
- **Upload selection and batch ownership:** Selection sessions are bound to creator, module, target type, and folder ID (`app/storage/services.py:89-97`); complete upload verifies the item belongs to the specified Documents folder (`project_documents/services.py:135-139`). Presigned uploads bind an exact client-declared file size in the storage layer per Foundation-B; quota checks remain the known global check-then-act concern, not a Documents-specific authorization finding.
- **Filename/path handling:** Folder names forbid separators and dot segments (`services.py:360-364`); file rename forbids separators and locks a pre-existing extension (`services.py:83-99`). Storage keys are generated by the shared UUID key builder rather than a submitted name (`app/storage/services.py:65-75`).
- **No GET writes other than PD-003:** Every other document mutation route is declared `POST` (`routes.py:36,113,123,131,140,152,160,169,178,186,213,222,231,243,268,277,286,295,307,316`).

## Needs verification

- **Production object-store policy:** Code issues 300-second presigned download/preview URLs (`app/project_documents/services.py:171,198,210,239`). This audit did not contact the remote bucket, so it cannot verify that bucket policy prevents direct public reads or that the provider honours the requested TTL. Verify with deployment configuration and provider-side policy review, not a live download attempt.
- **Concurrent project-root creation behavior:** `get_or_create_project_root_folder` has a read-then-insert race (`services.py:19-28`), while the model has a partial unique root index (`models/project_document.py:14-19`). The likely result is an unhandled `IntegrityError` for the loser, but exact production PostgreSQL exception handling was not executed because this Batch is read-only/no-PoC. This is availability/integrity debt, not counted as a separate confirmed security finding.
- **Upload-complete error conversion:** `complete_upload_item` can raise `StorageAuthorizationError` on non-owner completion (`app/storage/services.py:100-125,195-202`), but `project_documents.complete_upload` does not catch that exception (`routes.py:141-149`). Confirm with a controlled test whether Flask renders a generic 500; it does not alter another user's item because the owner check itself is present.

## Tool leads closed as false positive/info

- `app/project_documents/routes.py:303` uses `Markup` around `archived_url`, but `_folder_url` builds it exclusively through `url_for("project_documents.folder", folder_id=..., **context)` (`routes.py:66-70,302-303`). `folder_id` is an integer and context values are URL-encoded by Flask; no controllable HTML delimiter reaches the attribute. The template-safety unit owns the final cross-template inventory; this route lead is **false positive for exploitable XSS**.
- The apparently tautological `folder.project_id != getattr(folder, "project_id", None)` at `services.py:118` is dead validation, but the real flush listener at `models/project_document.py:91-99` enforces file/folder project equality. **Info / defense-in-depth dead code, not an IDOR.**
- `project_document_files.download` appears in the project-less-root RBAC map (`permissions.py:7-13`) but project-file download intentionally uses the project capability `can_view_documents` (`permissions.py:62-63`). This is an authorization-model naming inconsistency, not evidence that a caller can download a file outside its visible folder/project.
