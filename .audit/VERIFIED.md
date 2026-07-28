# Phase 10 Independent Finding Verification

## Verification summary

| Original findings | Canonical findings | Confirmed | False positive | Uncertain | Duplicate | Not security |
|---:|---:|---:|---:|---:|---:|---:|
| 76 | 75 | 34 | 3 | 5 | 1 | 33 |

Original severities: Critical 6, High 10, Medium 31, Low 25, Info 4.  Adjusted, confirmed-security severities: Critical 4, High 7, Medium 12, Low 11.  The remaining items are classified below rather than carrying a nominal severity.

## PoC verification summary

| Finding | PoC result | Verifier verdict | Notes |
|---|---|---|---|
| CRIT-01 | fails securely as expected | CONFIRMED | Real POST; default ADMIN is the minimum actor; persisted self-promotion proves takeover. |
| CRIT-02 | fails securely as expected | CONFIRMED | Real POST; lower admin changes SUPER_ADMIN hash and receives the secret. |
| CRIT-03 | fails securely as expected | CONFIRMED | Custom role has only `roles.view/manage`; route rewrites its own grants. |
| CRIT-04 | fails securely as expected | CONFIRMED | Actor has only assignment management; arbitrary target/capabilities persist. |
| CRIT-05 | fails securely as expected | CONFIRMED | Share-only ACL both reaches and rewrites the same album ACL. |
| CUSTOMER-001 | fails securely as expected | CONFIRMED | Actor only reads the source project; move commits without source management. |
| CONTRACTOR-001 | fails securely as expected | CONFIRMED | Direct POST bypasses the GET picker’s contractor-scope query. |
| REPORTS-001 | fails securely as expected | CONFIRMED | Own cancellation invokes global cancelled-session cleanup and deletes foreign bytes/row. |
| AI-002 | fails securely as expected | FALSE POSITIVE | Endpoint is real and test is sound, but its asserted separate download policy contradicts the project-capability implementation. |
| ISSUE-002 | fails securely as expected | CONFIRMED | Valid destructive permission policy: dangerous `issues.delete` is registered but route uses edit capability. |

All PoCs use the real factory/routes, no authorization monkeypatches, and the repository’s documented CSRF-disabled test configuration. `PYTHONWARNINGS=error pytest -q -ra .audit/poc/*_test.py` produced **10 collected, 10 secure-assertion failures, 0 collection/fixture errors, 0 skipped, 0 xfailed**. The one rejected policy is AI-002, not a test-infrastructure defect.

## Inventory and deduplication

| Canonical ID | Source IDs | Root cause | Treatment |
|---|---|---|---|
| DELETE-PERM-001 | REPORTS-004, ISSUE-002 | Dangerous delete permission catalogue is bypassed by edit predicates | One confirmed canonical finding; ISSUE-002 is duplicate. |
| CRIT-01..05 | VERIFIED-CRITICAL 01..05 | Role hierarchy, password-reset, role grant, membership, and album ACL controls | Separate root causes. |
| All other IDs below | Same source ID | As stated in its row | Independently retained, dropped, or reclassified. |

## Verdict table

| ID | Original severity | Verdict | Adjusted severity | Minimum actor | PoC | One-line reason |
|---|---|---|---|---|---|---|
| CRIT-01 | Critical | CONFIRMED | Critical | `users.view` + `users.manage` | yes | Can assign self SUPER_ADMIN. |
| CRIT-02 | Critical | CONFIRMED | Critical | `users.manage` | yes | Can reset SUPER_ADMIN and see password. |
| CRIT-03 | Critical | CONFIRMED | Critical | `roles.view` + `roles.manage` | yes | Can expand own role into takeover chain. |
| CRIT-04 | Critical | CONFIRMED | Critical | `project_assignments.manage` | yes | Can make self owner of any project. |
| CRIT-05 | Critical | CONFIRMED | High | matching `can_share` ACL | yes | Can make own album ACL more powerful. |
| AI-001 | Medium | NOT A SECURITY FINDING | — | operator | no | Python-version specification/deployment mismatch. |
| AI-002 | Medium | FALSE POSITIVE | — | document viewer | yes | View is the implemented project-document download capability. |
| AI-003 | Low | NOT A SECURITY FINDING | — | operator | no | Dead feature flag is operational configuration debt. |
| AI-004 | Info | NOT A SECURITY FINDING | — | role manager | no | Unused codes guard no reachable feature. |
| CLI-001 | High | CONFIRMED | High | deployment misconfiguration | no | Unknown APP_ENV enables known signing key in public service. |
| CLI-002..005 | Medium/Low | NOT A SECURITY FINDING | — | operator | no | Readiness, recovery, and deployment-operability gaps. |
| ADMIN-001 | Medium | CONFIRMED | Medium | `users.manage` | no | Can deactivate a non-last SUPER_ADMIN. |
| ADMIN-002 | Low | CONFIRMED | Low | uploader then export reader | no | Filename is emitted unsanitised in CSV. |
| ADMIN-003 | Low | NOT A SECURITY FINDING | — | admin | no | Audit detail completeness only. |
| REPORTS-001 | High | CONFIRMED | High | report creator on one project | yes | Cancelling one session globally deletes other sessions. |
| REPORTS-002 | Medium | CONFIRMED | Medium | `reports.today.view` without report-view | no | Today query uses project-read scope. |
| REPORTS-003 | Medium | CONFIRMED | Medium | report viewer retaining prior scope | no | List query omits project soft-delete predicate. |
| DELETE-PERM-001 | Medium | CONFIRMED | Medium | report/issue editor without delete grant | ISSUE PoC | Attachment/issue deletes use edit instead of dangerous delete policy. |
| REPORTS-005 | Medium | NOT A SECURITY FINDING | — | concurrent reporter | no | Retry/IntegrityError UX, not an authorization/security effect. |
| REPORTS-006 | Medium | CONFIRMED | Medium | existing report editor | no | Archived project remains writable through reports routes. |
| REPORTS-007 | Low | NOT A SECURITY FINDING | — | reporter | no | Audit coverage gap. |
| UPLOAD-001 | High | UNCERTAIN | Medium if exploitable | authorized uploader | no | Byte validation gap is real; Pillow/Celery impact needs runtime/CVE proof. |
| UPLOAD-002 | Medium | CONFIRMED | Low | authorized uploader | no | Cancelled V2 bytes evade quota/cleanup state. |
| UPLOAD-003 | Medium | UNCERTAIN | Low if reproduced | concurrent uploader | no | Check-then-act race requires PostgreSQL concurrency reproduction. |
| PD-001 | High | CONFIRMED | High | project sharer on restricted folder | no | May grant own principal capabilities beyond share. |
| PD-002 | Medium | UNCERTAIN | Medium if archive is revocation | prior descendant viewer | no | Source permits it; archive product semantics are undecided. |
| PD-003 | Low | CONFIRMED | Low | authenticated document viewer | no | GET creates/audits a root without CSRF. |
| PD-004..005 | Low/Info | NOT A SECURITY FINDING | — | authorized operator | no | Duplicate naming and creator lockout are integrity/UX. |
| CM-001 | High | CONFIRMED | High | media viewer | no | Video preview can issue original URL with view, bypassing download. |
| CM-002 | Low | CONFIRMED | Low | album sharer | no | ACL page discloses active user/role directory. |
| CM-003 | Low | FALSE POSITIVE | — | media user | no | Shared `parse_file_ids` caps and integer-validates requests. |
| CM-004,006 | Low | NOT A SECURITY FINDING | — | media editor | no | Audit coverage and uniqueness reliability. |
| CM-005 | Low | CONFIRMED | Low | uploader | no | Broad exception reflects raw server/provider message. |
| PARTNER-001..003 | Medium/Low | CONFIRMED | Medium/Low | respective editor/viewer | no | Lifecycle permissions are bypassed; redirect leaks bearer URL to otherwise authorised requester. |
| PARTNER-004..005 | Low | NOT A SECURITY FINDING | — | partner editor | no | Form integrity and post-commit error handling. |
| PARTNER-FIELD-001..003 | Low/Info | NOT A SECURITY FINDING | — | field manager | no | Input/lifecycle integrity, no security boundary crossed. |
| PARTNER-REL-001 | Low | CONFIRMED | Low | relationship manager | no | Multi-row write can create cycle outside intended invariant. |
| PARTNER-REL-002 | Low | CONFIRMED | Low | relation viewer | no | Archived company records remain directly readable. |
| PARTNER-REL-003 | Low | NOT A SECURITY FINDING | — | corrupt-data operator | no | Corrupt hierarchy recursion is maintenance/recovery debt. |
| ATTACH-001 | Medium | UNCERTAIN | Low if effective | URL recipient | no | Must measure CDN/S3 quota/rate behaviour; code alone proves no app counter. |
| ATTACH-002 | Low | CONFIRMED | Low | same browser profile user | no | Redirect cache policy can retain a bearer redirect across sessions. |
| ISSUE-001 | Medium | CONFIRMED | Medium | issue viewer on A/read viewer on B | no | Global list scopes rows by project-read, not issue-view. |
| ISSUE-002 | Medium | DUPLICATE | — | issue editor | yes | Owned by DELETE-PERM-001. |
| ISSUE-003 | Low | FALSE POSITIVE | — | issue viewer | no | SQLAlchemy/date comparison does not establish claimed database failure. |
| ISSUE-004 | Low | NOT A SECURITY FINDING | — | issue editor | no | Validation/DB-error UX only. |
| CUSTOMER-001 | High | CONFIRMED | High | source-project reader + target manager | yes | Source customer gets access, not manage, check. |
| CONTRACTOR-001 | High | CONFIRMED | High | assignment manager | yes | POST never checks submitted contractor visibility. |
| PROJECT-OPS-001 | Medium | CONFIRMED | Low | update creator | no | Validation error includes foreign contractor identity. |
| DASHBOARD-001..004 | Medium | CONFIRMED | Medium | scoped dashboard viewer | no | Dashboard queries omit distinct report/update/issue scope predicates. |
| ACCOUNT-001 | High | UNCERTAIN | Medium if vulnerable runtime | authenticated image uploader | no | Need installed Pillow/version-specific decompression/CVE test. |
| ACCOUNT-002 | Medium | CONFIRMED | Low | display-image editor | no | Superseded object is not deleted but leaves quota accounting. |
| JS-001, TEST-001..004 | Low/Info/Medium | NOT A SECURITY FINDING | — | developer | no | Coverage/evidence weaknesses, not application defects. |
| DEPLOY-001..007 | Critical/High/Medium/Low | NOT A SECURITY FINDING | — | deployer | no | Production readiness and architecture controls, not remotely reachable application flaws. |

## Canonical findings

The following compact records satisfy the full code/guard/effect trace. “Global” means `create_app` login hook, then the reports-module hook where the endpoint prefix requires it; Flask-WTF CSRF applies to POST routes in production.

### CRIT-01 — self-promotion
- **Source IDs:** VERIFIED-CRITICAL 01. **Verdict:** CONFIRMED. **Original/adjusted:** Critical/Critical. **Confidence:** high. **Minimum authority:** `users.view/manage`.
- **Reachability/code actually read:** registered `/admin/users/<id>/edit`; `app/__init__.py`, `app/admin/routes.py:58-70,443-504`, RBAC/model files.
- **Upward/downward:** Global login → `users.view` → POST `users.manage`; `_save_user` accepts any role, commits it. **PoC:** valid real endpoint/state proof. **Impact:** total admin takeover. **Phase 11 blocker:** YES.

### CRIT-02 — privileged password reset
- **Source IDs:** VERIFIED-CRITICAL 02. **Verdict:** CONFIRMED. **Original/adjusted:** Critical/Critical. **Confidence:** high. **Minimum authority:** `users.manage`.
- **Reachability/code:** registered `/admin/users/<id>/reset-password`; `app/admin/routes.py:199-208`, services/RBAC. **Trace:** login → permission → arbitrary target hash replacement → commit and plaintext flash. **PoC:** valid. **Impact:** privileged-account takeover. **Blocker:** YES.

### CRIT-03 — self-role expansion
- **Source IDs:** VERIFIED-CRITICAL 03. **Verdict:** CONFIRMED. **Original/adjusted:** Critical/Critical. **Confidence:** high. **Minimum authority:** `roles.view/manage`.
- **Reachability/code:** registered role permissions POST; `app/admin/routes.py:142-157`, RBAC models/services. **Trace:** guards exclude only SUPER_ADMIN target; form IDs replace own grants and commit. **PoC:** valid. **Impact:** chain to CRIT-01. **Blocker:** YES.

### CRIT-04 — arbitrary project membership
- **Source IDs:** VERIFIED-CRITICAL 04. **Verdict:** CONFIRMED. **Original/adjusted:** Critical/Critical. **Confidence:** high. **Minimum authority:** `project_assignments.manage`.
- **Reachability/code:** `/admin/projects/<id>/memberships`; `app/admin/routes.py:284-336`, `app/project_memberships.py`. **Trace:** no project/target/grant-ceiling guard; all posted flags persist. **PoC:** valid. **Impact:** cross-project owner authority. **Blocker:** YES.

### CRIT-05 — album ACL self-escalation
- **Source IDs:** VERIFIED-CRITICAL 05. **Verdict:** CONFIRMED. **Original/adjusted:** Critical/High. **Confidence:** high. **Minimum authority:** active matching `can_share` ACL.
- **Reachability/code:** Company Media hook plus `/albums/<id>/permissions`; `permissions.py`, `routes.py:172-197`, `services.py:78-95`. **Trace:** ACL itself passes module/share checks; form rewrites it. **PoC:** valid. **Impact:** bounded album privilege escalation. **Blocker:** YES.

### CLI-001 — APP_ENV fail-open
- **Source IDs:** CLI-001. **Verdict:** CONFIRMED. **Original/adjusted:** High/High. **Confidence:** high. **Minimum authority:** deployment error only.
- **Reachability/code:** `app/config.py:35-41`, `app/security.py:61-82`, `app/cli.py`; public service is reachable if misstarted. **Trace:** nonexact `production` bypasses validation and retains `dev-secret-key`; forged session is then possible. **PoC:** none. **Impact:** account impersonation. **Blocker:** YES.

### ADMIN-001 — deactivate SUPER_ADMIN
- **Source IDs:** ADMIN-001. **Verdict:** CONFIRMED. **Original/adjusted:** Medium/Medium. **Confidence:** high. **Minimum authority:** `users.manage`.
- **Reachability/code:** registered deactivate POST; `app/admin/routes.py:73-83,663-674`. **Trace:** only last-active-admin rule; no hierarchy rule; commits disable. **Impact:** privileged-admin DoS. **Blocker:** NO.

### ADMIN-002 — CSV formula injection
- **Source IDs:** ADMIN-002. **Verdict:** CONFIRMED. **Original/adjusted:** Low/Low. **Confidence:** medium. **Minimum authority:** upload-capable user plus privileged export operator. **Code:** `app/admin_storage/routes.py`, storage filename validation/services.
- **Trace/impact:** CSV writer preserves formula-leading filename; spreadsheet execution is client-dependent. **Blocker:** NO.

### REPORTS-001 — global upload cleanup
- **Source IDs:** REPORTS-001. **Verdict:** CONFIRMED. **Original/adjusted:** High/High. **Confidence:** high. **Minimum authority:** creator on one project. **Code:** registered cancel route `app/projects/routes.py:180-190`; `direct_uploads.py:290-311`.
- **Trace:** owner/session scope is checked, then cleanup selects every cancelled/expired daily-report session and deletes rows/objects. **PoC:** valid, proves foreign DB and storage deletion. **Impact/blocker:** cross-project destructive loss; YES.

### REPORTS-002 / REPORTS-003 — report read lifecycle scope
- **Source IDs:** REPORTS-002, REPORTS-003. **Verdict:** CONFIRMED. **Original/adjusted:** Medium/Medium each. **Confidence:** high. **Minimum authority:** scoped report page user.
- **Code/trace:** `app/reports/routes.py:70-92`, `services.py:227-232`; list uses accessible-project project-read query and does not filter soft-deleted project. Dedicated report access uses `can_view_report`. **Impact:** limited report metadata/content disclosure. **Blocker:** NO.

### DELETE-PERM-001 — destructive permission mismatch
- **Source IDs:** REPORTS-004, ISSUE-002. **Verdict:** CONFIRMED. **Original/adjusted:** Medium/Medium. **Confidence:** high. **Minimum authority:** report/issue editor lacking delete RBAC.
- **Code/trace:** `app/attachments/routes.py:84-91`, `app/issues/routes.py:146-154`, `app/auth/permissions.py:189-190`, registry. Both registered POSTs check edit capability then soft/delete. **PoC:** ISSUE PoC valid. **Policy:** dangerous `issues.delete` and `report_attachments.delete` are explicitly registry/UI controls, so edit is not the intended delete authority. **Blocker:** NO.

### REPORTS-006 — archived project report mutation
- **Source IDs:** REPORTS-006. **Verdict:** CONFIRMED. **Original/adjusted:** Medium/Medium. **Confidence:** high. **Code:** report/project routes and `auth/permissions.py`.
- **Trace:** active membership capability permits route/service mutations without project status check. **Impact:** lifecycle integrity. **Blocker:** NO.

### UPLOAD-002 — cancelled V2 orphan bytes
- **Source IDs:** UPLOAD-002. **Verdict:** CONFIRMED. **Original/adjusted:** Medium/Low. **Confidence:** high. **Code:** `create_v2.py`, `direct_uploads.py`, quota service.
- **Trace:** cancellation leaves uploaded objects outside active quota and no per-session cleanup schedule. **Impact:** bounded storage cost/cleanup reliability. **Blocker:** NO.

### PD-001 — folder ACL grant ceiling
- **Source IDs:** PD-001. **Verdict:** CONFIRMED. **Original/adjusted:** High/High. **Confidence:** high. **Minimum authority:** restricted-folder sharer with project share capability.
- **Code/trace:** documents hook → `can_share...` → `set_folder_permission` in routes/permissions/services. Actor may submit all flags for own principal; no subset guard. **Impact:** restricted-subtree privilege escalation. **Blocker:** YES.

### PD-003 — GET root creation
- **Source IDs:** PD-003. **Verdict:** CONFIRMED. **Original/adjusted:** Low/Low. **Confidence:** high. **Code:** `project_documents/routes.py:46-52`, services root creation.
- **Trace:** login/view scope, GET commits root/audit; safe-method CSRF protection does not apply. **Impact:** one bounded state/audit attribution change. **Blocker:** NO.

### CM-001 — preview issues original URL
- **Source IDs:** CM-001. **Verdict:** CONFIRMED. **Original/adjusted:** High/High. **Confidence:** high. **Minimum authority:** album viewer lacking download.
- **Code/trace:** Company Media hook → `view_file` preview route → service can return original video URL; download route separately checks `download_file`. **Impact:** confidential original disclosure. **Blocker:** YES.

### CM-002 / CM-005 — media metadata and exception disclosure
- **Source IDs:** CM-002, CM-005. **Verdict:** CONFIRMED. **Original/adjusted:** Low/Low. **Confidence:** high/medium. **Code:** `company_media/routes.py:71-78,172-197`, permissions.
- **Trace:** a sharer receives full active-user/role options; presign catches broad exception and returns `str(e)`. **Impact:** bounded metadata/internal-message exposure. **Blocker:** NO.

### PARTNER-001 / PARTNER-002 — lifecycle permission bypasses
- **Source IDs:** PARTNER-001, PARTNER-002. **Verdict:** CONFIRMED. **Original/adjusted:** Medium/Medium. **Confidence:** high. **Code:** partner-company edit/department routes.
- **Trace:** edit handler accepts `is_active` on archived/deactivated records although restore/deletion has separate permission. **Impact:** scoped lifecycle/destructive semantic bypass. **Blocker:** NO.

### PARTNER-003 — redirect bearer URL disclosure
- **Source IDs:** PARTNER-003. **Verdict:** CONFIRMED. **Original/adjusted:** Low/Low. **Confidence:** high. **Code:** partner/company preview routes and `partner_photos.py`.
- **Trace:** authorised GET returns `Location` with presigned bearer URL. **Impact:** browser/history/referrer exposure, not cross-user IDOR. **Blocker:** NO.

### PARTNER-REL-001 / PARTNER-REL-002
- **Source IDs:** PARTNER-REL-001, PARTNER-REL-002. **Verdict:** CONFIRMED. **Original/adjusted:** Low/Low. **Confidence:** high. **Code:** partner relationship routes/model traversal.
- **Trace:** multi-row relation write evades single-parent cycle check; archived company endpoint loads it directly. **Impact:** hierarchy integrity and limited archived-data disclosure. **Blocker:** NO.

### ATTACH-002 — cached redirect replay
- **Source IDs:** ATTACH-002. **Verdict:** CONFIRMED. **Original/adjusted:** Low/Low. **Confidence:** medium. **Code:** attachment preview/thumbnail redirects and global headers.
- **Trace:** authorisation occurs before redirect but redirect response is not explicitly `no-store`; private browser cache can retain bearer location. **Impact:** same-profile session boundary only. **Blocker:** NO.

### ISSUE-001 — global issue list scope drift
- **Source IDs:** ISSUE-001. **Verdict:** CONFIRMED. **Original/adjusted:** Medium/Medium. **Confidence:** high. **Code:** `issues/routes.py:29-44`, report scope service.
- **Trace:** entry requires any issue view; rows use `can_view_project` accessible projects, then render issue metadata. **Impact:** cross-project metadata disclosure. **Blocker:** NO.

### CUSTOMER-001 / CONTRACTOR-001
- **Source IDs:** CUSTOMER-001, CONTRACTOR-001. **Verdict:** CONFIRMED. **Original/adjusted:** High/High. **Confidence:** high. **Code:** customer and project-operation routes/services.
- **Trace:** customer move requires source access plus target manage, not source manage; contractor POST accepts ID without `can_access_contractor`. **PoCs:** valid real route/mutation proofs. **Policy:** moves require manage on both source and target customers; attachment requires contractor visibility plus target-project manage. **Impact/blocker:** cross-customer/project mutation; YES.

### PROJECT-OPS-001 — contractor identity error leak
- **Source IDs:** PROJECT-OPS-001. **Verdict:** CONFIRMED. **Original/adjusted:** Medium/Low. **Confidence:** high. **Code:** update route/service/template.
- **Trace:** invalid foreign assignment is rejected but validation message interpolates contractor identity. **Impact:** bounded metadata oracle. **Blocker:** NO.

### DASHBOARD-001..004 — dashboard capability drift
- **Source IDs:** DASHBOARD-001, DASHBOARD-002, DASHBOARD-003, DASHBOARD-004. **Verdict:** CONFIRMED. **Original/adjusted:** Medium/Medium. **Confidence:** high.
- **Code/trace:** registered HTML/API routes in project/dashboard modules apply dashboard + project-read gates but builders query reports, updates, issue totals, or contractor-linked issue titles without their distinct per-resource checks. **Impact:** scoped report/update/issue disclosure; contractor route uses any-project issue permission. **Blocker:** NO.

### ACCOUNT-002 — display-image orphan accounting
- **Source IDs:** ACCOUNT-002. **Verdict:** CONFIRMED. **Original/adjusted:** Medium/Low. **Confidence:** high for code, medium for cost. **Code:** `display_images.py`, quota/storage services.
- **Trace:** replacement/deletion removes reference/quota contribution without object deletion. **Impact:** bounded unnoticed storage consumption. **Blocker:** NO.

### UNCERTAIN-001 — upload byte validation
- **Source IDs:** UPLOAD-001. **Verdict:** UNCERTAIN. **Original/adjusted:** High/Medium if demonstrated. **Code:** storage metadata/provider, media pipeline.
- **Reasoning:** declared type is trusted before Pillow; endpoint/actor are real, but actual Pillow version, decompression limits, worker limits, and exploit impact are unproven. **Exact test:** isolated S3/Celery worker with malformed image corpus and installed dependency audit. **Secure behavior:** verify bytes before processing. **Blocker:** NO pending proof.

### UNCERTAIN-002 — concurrent V2 presign
- **Source IDs:** UPLOAD-003. **Verdict:** UNCERTAIN. **Original/adjusted:** Medium/Low if reproduced. **Code:** `direct_uploads.py:116-167`.
- **Reasoning:** source has unlocked read-then-create counters, but SQLite test results cannot establish PostgreSQL isolation outcome. **Exact test:** two real PostgreSQL transactions/barrier, assert declared limits and unique items. **Secure behavior:** one transaction serializes or rejects excess. **Blocker:** NO.

### UNCERTAIN-003 — archive ancestor semantics
- **Source IDs:** PD-002. **Verdict:** UNCERTAIN. **Original/adjusted:** Medium/Medium if archive revokes. **Code:** document permissions/routes/services.
- **Reasoning:** child authorisation ignores archived ancestor, but repository never states that archive withdraws descendant access. **Human decision:** choose subtree/lifecycle-revocation versus organisational archive. **Secure behavior if revocation:** deny descendant list/preview/download. **Blocker:** NO.

### UNCERTAIN-004 — attachment preview bandwidth
- **Source IDs:** ATTACH-001. **Verdict:** UNCERTAIN. **Original/adjusted:** Medium/Low if effective. **Code:** attachment routes, quota, limiter.
- **Reasoning:** app does not call bandwidth limiter for preview redirects, but actual S3/CDN traffic, caching, and quota scope are unverified. **Exact test:** production-like provider load/accounting test. **Secure behavior:** enforce equivalent egress/rate policy. **Blocker:** NO.

### UNCERTAIN-005 — display-image/Pillow DoS
- **Source IDs:** ACCOUNT-001. **Verdict:** UNCERTAIN. **Original/adjusted:** High/Medium if demonstrated. **Code:** requirements, `display_images.py`, account route/pipeline.
- **Reasoning:** synchronous decoder lacks application pixel cap, but claimed vulnerable release/CVE and practical request impact require installed-runtime test. **Exact test:** controlled decompression-bomb corpus with production dependency/version. **Secure behavior:** reject by verified pixels before transform. **Blocker:** NO.

### Reclassified operational, test, and maintenance findings
- **Source IDs:** AI-001, AI-003, AI-004; CLI-002..005; ADMIN-003; REPORTS-005, REPORTS-007; PD-004, PD-005; CM-004, CM-006; PARTNER-004, PARTNER-005; PARTNER-FIELD-001..003; PARTNER-REL-003; ISSUE-004; JS-001; TEST-001..004; DEPLOY-001..007.
- **Verdict:** NOT A SECURITY FINDING. **Reasoning:** code observations are mostly accurate, but their consequences are deployment readiness, missing test evidence, reliability, audit completeness, or authenticated data-quality debt without a concrete authorization/confidentiality/integrity security boundary. DEPLOY-001/002/003/006 still require operational resolution before a safe release.

## False positives

- **AI-002:** The PoC accurately mints a URL, but it invents a policy conflict. Project Documents uses `can_view_documents` for preview and download everywhere, while the alleged RBAC code is for project-less/root catalogue surfaces; no repository decision says project viewers must not download. It must not drive a fix without a product policy change.
- **CM-003:** `parse_file_ids` supplies bounded integer parsing to the bulk route; the claim that it accepts uncapped/untyped IDs is stale.
- **ISSUE-003:** no parsing exists, but binding a string to SQLAlchemy’s date comparison does not itself prove a database error; a source-only reliability claim was overstated.

## Uncertain findings

UPLOAD-001, UPLOAD-003, PD-002, ATTACH-001, and ACCOUNT-001 require exactly the runtime/policy tests specified in their records. None blocks Phase 11 by itself; each needs a regression decision before being promoted into deployment-blocking work.

## Verification integrity

- **Source files unread:** none of the cited application/route/service/configuration/test sources; immutable `claude-partial-audit-backup/` was not read, searched, compared, or changed.
- **PoCs re-run:** yes; 10/10 collected and valid mechanical failures; one policy assertion (AI-002) rejected.
- **Errors:** none in collection/fixtures; expected assertion failures only.
- **Remote/runtime verification needed:** PostgreSQL concurrency, installed Pillow/CVE behavior, S3/CDN cache/egress policy, Celery processing, and production deployment supervision.
- **Dropped, merged, or reclassified:** 36 of 76 source findings (47.4%) are false, duplicate, uncertain, or non-security. This is materially above the 10% scrutiny threshold; the original audit was not treated as presumptively correct.

## Per-ID completion records

These records make explicit the individual canonical treatment where the main analysis correctly grouped a shared implementation. All cited handlers are registered by `app/__init__.py`; global login/module and production CSRF guards were traced before the local checks.

### AI-001 — Python runtime mismatch
- **Source IDs:** AI-001. **Verdict:** NOT A SECURITY FINDING. **Original/adjusted:** Medium/—. **Confidence:** high. **Minimum authority:** deployer. **Reachability/code actually read:** `Dockerfile`, Compose. **Guard/effect:** image builds Python 3.10; no request sink. **PoC:** none. **Reasoning/impact:** specification and delivery readiness mismatch only. **Phase 11 blocker:** NO (operations owns it).

### AI-002 — document download catalogue
- **Source IDs:** AI-002. **Verdict:** FALSE POSITIVE. **Original/adjusted:** Medium/—. **Confidence:** high. **Minimum authority:** document viewer. **Reachability/code:** Documents hook, signed-download route, permissions/services. **Guard/effect:** `can_view_documents` is deliberately the project-file view/download predicate and emits an authorised URL. **PoC:** mechanically valid but policy-invalid. **Impact:** none beyond changing product policy. **Blocker:** NO.

### AI-003 — media-processing flag
- **Source IDs:** AI-003. **Verdict:** NOT A SECURITY FINDING. **Original/adjusted:** Low/—. **Confidence:** high. **Minimum authority:** operator. **Code:** `config.py`, media services. **Trace:** flag is unused and jobs still dispatch. **Impact:** operational expectation only. **Blocker:** NO.

### AI-004 — unused dangerous codes
- **Source IDs:** AI-004. **Verdict:** NOT A SECURITY FINDING. **Original/adjusted:** Info/—. **Confidence:** high. **Minimum authority:** role manager. **Code:** registry/routes search. **Trace/effect:** no route consumes the three codes. **Impact:** catalogue maintenance only. **Blocker:** NO.

### CLI-002 — static security audit
- **Source IDs:** CLI-002. **Verdict:** NOT A SECURITY FINDING. **Original/adjusted:** Medium/—. **Confidence:** high. **Minimum authority:** operator. **Code:** CLI, Compose, worker script. **Trace/effect:** configuration lint cannot prove external worker/CORS. **Impact:** false readiness confidence only. **Blocker:** NO.

### CLI-003 — restore safety
- **Source IDs:** CLI-003. **Verdict:** NOT A SECURITY FINDING. **Original/adjusted:** Medium/—. **Confidence:** high. **Minimum authority:** restore operator. **Code:** `scripts/restore_db.sh`. **Trace/effect:** operator-selected dump may partially restore. **Impact:** recovery procedure risk, not remote application vulnerability. **Blocker:** NO.

### CLI-004 — backup atomicity
- **Source IDs:** CLI-004. **Verdict:** NOT A SECURITY FINDING. **Original/adjusted:** Medium/—. **Confidence:** high. **Minimum authority:** backup operator. **Code:** backup scripts. **Trace/effect:** partial archive/retention values affect recovery. **Impact:** operational data recovery risk. **Blocker:** NO.

### CLI-005 — entrypoint seeding race
- **Source IDs:** CLI-005. **Verdict:** NOT A SECURITY FINDING. **Original/adjusted:** Low/—. **Confidence:** high. **Minimum authority:** deployer enabling flags. **Code:** entrypoint/CLI. **Trace/effect:** replicas can reseed/contend. **Impact:** deployment reliability. **Blocker:** NO.

### ADMIN-003 — membership audit detail
- **Source IDs:** ADMIN-003. **Verdict:** NOT A SECURITY FINDING. **Original/adjusted:** Low/—. **Confidence:** high. **Minimum authority:** administrator. **Code:** admin routes/audit helper. **Trace/effect:** flags are not reconstructable from log snapshot. **Impact:** forensic completeness only. **Blocker:** NO.

### REPORTS-002 — Today scope
- **Source IDs:** REPORTS-002. **Verdict:** CONFIRMED. **Original/adjusted:** Medium/Medium. **Confidence:** high. **Minimum authority:** today viewer without report-view. **Code/trace:** report route/service read project scope, not report capability, and render report data. **PoC:** none. **Impact:** scoped report disclosure. **Blocker:** NO.

### REPORTS-003 — soft-deleted project reports
- **Source IDs:** REPORTS-003. **Verdict:** CONFIRMED. **Original/adjusted:** Medium/Medium. **Confidence:** high. **Minimum authority:** former project reader. **Code/trace:** list service joins/retrieves reports without project deleted predicate. **Impact:** lifecycle disclosure. **Blocker:** NO.

### REPORTS-004 — attachment delete capability
- **Source IDs:** REPORTS-004. **Verdict:** DUPLICATE. **Original/adjusted:** Medium/—. **Confidence:** high. **Minimum authority:** report editor. **Code/trace:** registered delete route uses edit capability. **PoC:** covered by DELETE-PERM-001 family. **Impact/blocker:** owned by DELETE-PERM-001; NO.

### REPORTS-005 — create retry race
- **Source IDs:** REPORTS-005. **Verdict:** NOT A SECURITY FINDING. **Original/adjusted:** Medium/—. **Confidence:** high. **Minimum authority:** concurrent reporter. **Code:** report service/model unique constraint. **Trace/effect:** retry can surface transaction error; it cannot confer access. **Blocker:** NO.

### REPORTS-007 — upload audit gap
- **Source IDs:** REPORTS-007. **Verdict:** NOT A SECURITY FINDING. **Original/adjusted:** Low/—. **Confidence:** high. **Minimum authority:** report creator. **Code:** cancellation/cleanup. **Trace/effect:** missing audit event only. **Blocker:** NO.

### UPLOAD-001 — byte validation
- **Source IDs:** UPLOAD-001. **Verdict:** UNCERTAIN. **Original/adjusted:** High/Medium if demonstrated. **Confidence:** medium. **Minimum authority:** uploader. **Reachability/code:** real upload/media pipeline. **Trace/effect:** metadata precedes decoder; CVE/resource impact unknown. **Required test:** production Pillow/Celery corpus. **Blocker:** NO.

### UPLOAD-003 — V2 counters
- **Source IDs:** UPLOAD-003. **Verdict:** UNCERTAIN. **Original/adjusted:** Medium/Low if reproduced. **Confidence:** medium. **Minimum authority:** concurrent uploader. **Code:** V2 presign/quota. **Trace/effect:** race plausible, database outcome untested. **Required test:** PostgreSQL two-transaction barrier. **Blocker:** NO.

### PD-002 — archived ancestors
- **Source IDs:** PD-002. **Verdict:** UNCERTAIN. **Original/adjusted:** Medium/Medium if revocation. **Confidence:** high for behavior. **Minimum authority:** descendant viewer. **Code:** document routes/permissions/services. **Trace/effect:** parent state ignored. **Required decision:** whether archive revokes descendants. **Blocker:** NO.

### PD-004 — document display uniqueness
- **Source IDs:** PD-004. **Verdict:** NOT A SECURITY FINDING. **Original/adjusted:** Low/—. **Confidence:** high. **Minimum authority:** concurrent editor. **Code:** document service/model. **Effect:** duplicate names are integrity UX. **Blocker:** NO.

### PD-005 — restricted root lockout
- **Source IDs:** PD-005. **Verdict:** NOT A SECURITY FINDING. **Original/adjusted:** Info/—. **Confidence:** high. **Minimum authority:** custom-root creator. **Code:** document permissions/routes/services. **Effect:** self lockout, no boundary expansion. **Blocker:** NO.

### CM-003 — bulk ID parsing
- **Source IDs:** CM-003. **Verdict:** FALSE POSITIVE. **Original/adjusted:** Low/—. **Confidence:** high. **Minimum authority:** media user. **Code:** bulk route and shared parser. **Trace/effect:** parser caps and integer-validates IDs. **Blocker:** NO.

### CM-004 — media audit records
- **Source IDs:** CM-004. **Verdict:** NOT A SECURITY FINDING. **Original/adjusted:** Low/—. **Confidence:** high. **Code:** media routes/services. **Effect:** logging completeness only. **Blocker:** NO.

### CM-006 — album uniqueness
- **Source IDs:** CM-006. **Verdict:** NOT A SECURITY FINDING. **Original/adjusted:** Low/—. **Confidence:** high. **Code:** media service/model. **Effect:** concurrency/data-quality only. **Blocker:** NO.

### PARTNER-004 — crafted partner form
- **Source IDs:** PARTNER-004. **Verdict:** NOT A SECURITY FINDING. **Original/adjusted:** Low/—. **Confidence:** high. **Minimum authority:** partner editor. **Code:** partner routes/services. **Effect:** permitted editor can create inconsistent field values; no cross-scope effect. **Blocker:** NO.

### PARTNER-005 — post-commit photo failure
- **Source IDs:** PARTNER-005. **Verdict:** NOT A SECURITY FINDING. **Original/adjusted:** Low/—. **Confidence:** high. **Code:** partner routes/display image service. **Effect:** partial-operation UX/reliability. **Blocker:** NO.

### PARTNER-FIELD-001 — submitted definitions
- **Source IDs:** PARTNER-FIELD-001. **Verdict:** NOT A SECURITY FINDING. **Original/adjusted:** Low/—. **Confidence:** high. **Minimum authority:** field manager. **Code:** collection route/model. **Effect:** inactive/invalid definition integrity and FK error. **Blocker:** NO.

### PARTNER-FIELD-002 — label uniqueness
- **Source IDs:** PARTNER-FIELD-002. **Verdict:** NOT A SECURITY FINDING. **Original/adjusted:** Info/—. **Confidence:** high. **Code:** field service/model. **Effect:** data naming ambiguity. **Blocker:** NO.

### PARTNER-FIELD-003 — collection activation
- **Source IDs:** PARTNER-FIELD-003. **Verdict:** NOT A SECURITY FINDING. **Original/adjusted:** Low/—. **Confidence:** high. **Code:** collection route. **Effect:** lifecycle UX. **Blocker:** NO.

### PARTNER-REL-003 — hierarchy recursion
- **Source IDs:** PARTNER-REL-003. **Verdict:** NOT A SECURITY FINDING. **Original/adjusted:** Low/—. **Confidence:** high. **Minimum authority:** corrupt-data operator. **Code:** relation traversal. **Effect:** corrupt-data maintenance/availability, not remotely created by low authority. **Blocker:** NO.

### ATTACH-001 — preview bandwidth
- **Source IDs:** ATTACH-001. **Verdict:** UNCERTAIN. **Original/adjusted:** Medium/Low if effective. **Confidence:** medium. **Minimum authority:** URL recipient. **Code:** attachment routes/quota/limiter. **Trace/effect:** no app egress call for previews; provider behavior unverified. **Required test:** production-like S3/CDN accounting. **Blocker:** NO.

### ISSUE-002 — issue delete capability
- **Source IDs:** ISSUE-002. **Verdict:** DUPLICATE. **Original/adjusted:** Medium/—. **Confidence:** high. **Minimum authority:** issue editor. **Code:** issue route/helper. **PoC:** valid; owned by DELETE-PERM-001. **Blocker:** NO.

### ISSUE-003 — date filter error
- **Source IDs:** ISSUE-003. **Verdict:** FALSE POSITIVE. **Original/adjusted:** Low/—. **Confidence:** medium. **Code:** issue/project filters. **Trace/effect:** absent parsing alone does not prove claimed DB exception. **Blocker:** NO.

### ISSUE-004 — issue title length
- **Source IDs:** ISSUE-004. **Verdict:** NOT A SECURITY FINDING. **Original/adjusted:** Low/—. **Confidence:** high. **Code:** issue service/model. **Effect:** validation UX. **Blocker:** NO.

### DASHBOARD-001 — report dashboard data
- **Source IDs:** DASHBOARD-001. **Verdict:** CONFIRMED. **Original/adjusted:** Medium/Medium. **Confidence:** high. **Minimum authority:** dashboard/project reader lacking report view. **Code:** projects/dashboard routes/services/template. **Trace/effect:** builder returns report records after only project-read. **Blocker:** NO.

### DASHBOARD-002 — update dashboard data
- **Source IDs:** DASHBOARD-002. **Verdict:** CONFIRMED. **Original/adjusted:** Medium/Medium. **Confidence:** high. **Minimum authority:** dashboard reader lacking updates view. **Code:** dashboard service/template versus update route. **Trace/effect:** query omits `project_updates.view`. **Blocker:** NO.

### DASHBOARD-003 — issue aggregates
- **Source IDs:** DASHBOARD-003. **Verdict:** CONFIRMED. **Original/adjusted:** Medium/Medium. **Confidence:** high. **Minimum authority:** dashboard reader lacking project issue view. **Code:** dashboard routes/services. **Trace/effect:** aggregate query omits capability. **Blocker:** NO.

### DASHBOARD-004 — contractor issues
- **Source IDs:** DASHBOARD-004. **Verdict:** CONFIRMED. **Original/adjusted:** Medium/Medium. **Confidence:** high. **Minimum authority:** issue viewer on another contractor project. **Code:** contractor dashboard service/template. **Trace/effect:** `has_any_project_capability` gates all selected projects. **Blocker:** NO.

### ACCOUNT-001 — display image decode
- **Source IDs:** ACCOUNT-001. **Verdict:** UNCERTAIN. **Original/adjusted:** High/Medium if demonstrated. **Confidence:** medium. **Minimum authority:** image uploader. **Code:** requirements/display image/account route. **Trace/effect:** no app pixel ceiling; actual dependency exploitability untested. **Required test:** controlled corpus on deployed Pillow. **Blocker:** NO.

### JS-001 — JS coverage
- **Source IDs:** JS-001. **Verdict:** NOT A SECURITY FINDING. **Original/adjusted:** Low/—. **Confidence:** high. **Code:** JS tests. **Effect:** test-confidence only. **Blocker:** NO.

### TEST-001 — synthetic decorators
- **Source IDs:** TEST-001. **Verdict:** NOT A SECURITY FINDING. **Original/adjusted:** Info/—. **Confidence:** high. **Code:** conftest/test routes. **Effect:** dead-decorator coverage only. **Blocker:** NO.

### TEST-002 — excluded PoCs
- **Source IDs:** TEST-002. **Verdict:** NOT A SECURITY FINDING. **Original/adjusted:** Medium/—. **Confidence:** high. **Code:** pytest configuration/PoCs. **Effect:** regression evidence gap. **Blocker:** NO.

### TEST-003 — SQLite fixture limits
- **Source IDs:** TEST-003. **Verdict:** NOT A SECURITY FINDING. **Original/adjusted:** Medium/—. **Confidence:** high. **Code:** conftest and transaction callers. **Effect:** production-evidence gap. **Blocker:** NO.

### TEST-004 — image coverage
- **Source IDs:** TEST-004. **Verdict:** NOT A SECURITY FINDING. **Original/adjusted:** Medium/—. **Confidence:** high. **Code:** test suite/account route. **Effect:** missing regression only. **Blocker:** NO.

### DEPLOY-001 — storage startup
- **Source IDs:** DEPLOY-001. **Verdict:** NOT A SECURITY FINDING. **Original/adjusted:** Critical/—. **Confidence:** high. **Code:** Compose/config validation. **Effect:** tracked deployment cannot meet startup storage validation. **Blocker:** NO (operations release gate).

### DEPLOY-002 — worker supervision
- **Source IDs:** DEPLOY-002. **Verdict:** NOT A SECURITY FINDING. **Original/adjusted:** High/—. **Confidence:** high. **Code:** Compose/worker scripts. **Effect:** jobs may accumulate; operational. **Blocker:** NO (operations release gate).

### DEPLOY-003 — artifact recovery
- **Source IDs:** DEPLOY-003. **Verdict:** NOT A SECURITY FINDING. **Original/adjusted:** High/—. **Confidence:** high. **Code:** deployment docs/artifacts. **Effect:** recovery readiness. **Blocker:** NO.

### DEPLOY-004 — backup Compose drift
- **Source IDs:** DEPLOY-004. **Verdict:** NOT A SECURITY FINDING. **Original/adjusted:** Medium/—. **Confidence:** high. **Code:** backup Compose. **Effect:** operational configuration drift. **Blocker:** NO.

### DEPLOY-005 — mutable Cloudflared
- **Source IDs:** DEPLOY-005. **Verdict:** NOT A SECURITY FINDING. **Original/adjusted:** Medium/—. **Confidence:** high. **Code:** Compose. **Effect:** supply-chain hardening policy. **Blocker:** NO.

### DEPLOY-006 — deployment docs
- **Source IDs:** DEPLOY-006. **Verdict:** NOT A SECURITY FINDING. **Original/adjusted:** Medium/—. **Confidence:** high. **Code:** documentation/Compose. **Effect:** operational ambiguity. **Blocker:** NO.

### DEPLOY-007 — hardening/health
- **Source IDs:** DEPLOY-007. **Verdict:** NOT A SECURITY FINDING. **Original/adjusted:** Low/—. **Confidence:** high. **Code:** Docker/Compose. **Effect:** defence-in-depth/reliability. **Blocker:** NO.
