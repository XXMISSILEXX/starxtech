# Findings — Phase 11 Delta: Reports, project integration, account and browser clients

## Summary

- Read all changed U3–U6/U9 code and templates, their newly reached unchanged permission/attachment/document paths, and the related changed tests.  Authorization changes were traced from route decorator/global module gate, through project/customer capability predicate, to the object query and rendered/JSON response.
- One confirmed product-contract regression was found: Daily Report sections now accept ten active images, while the retained system contract says at most three.  The code and a standalone read-only proof agree this is intentional code behaviour, but no approved contract change was supplied.
- No new REPORTS prefix-gate miss, cross-report attachment deletion, cross-project section selection, customer/project assignment bypass, account preference injection, or thumbnail/original-media fallback was confirmed.
- Files not changed and not on these new paths remain deliberately outside this delta audit; baseline coverage is recorded in `PHASE11-DELTA-SCOPE.md` with references to findings 2, 3a, 4, 7, 8, 10, 11 and 14.

## REPORTS-007 — Daily Report section attachment limit changed from three to ten without an approved product-contract update

> **Distinction:** This is the Phase 11 3-versus-10 attachment-limit finding; the separate Phase 10 upload-session audit-trail finding with the same ID is in `findings-3a-reports.md`.

- **Severity:** Medium.
- **Confidence:** High.
- **Category:** Product/integrity regression (not a confidentiality or authorization flaw).
- **Reachability:** Any authorized reporter/admin creating or editing a Daily Report section using V2 direct upload, legacy multipart upload, or direct-session attachment.  Four through ten images are accepted; the eleventh is rejected.
- **Location:** `AGENTS.md:39,64` (retained contract); `app/reports/constants.py:1-7`; `app/reports/services.py:131-166,745-806`; `app/reports/direct_uploads.py:147-148,276-277`; `app/reports/routes.py:209`; `app/projects/routes.py:274`; `.env.example:11,49-54`; `app/config.py:63-70`.
- **Evidence:** The sole report-contract constant is `MAX_ATTACHMENTS_PER_REPORT_SECTION = 10`.  V2 preflight rejects only a per-section count greater than that constant and returns “tối đa 10 ảnh” (`services.py:159-161`).  The legacy and direct-upload finalize paths apply the same constant (`:760-762`, `:804-806`).  The client limits endpoints expose 10.  Conversely, the governing repository instructions state both “Attachments, tối đa 3 ảnh/section” and “Mỗi section tối đa 3 ảnh.”
- **Reproduction:**

  ```text
  PYTHONWARNINGS=error .venv/bin/python -m pytest -q \
    .audit/poc/REPORTS-007-section-image-limit.py
  # FAILED: assert 10 == 3
  ```

  The PoC is intentionally a failing contract test and performs no DB, S3 or filesystem mutation outside `.audit/`.  The changed application regression test `tests/test_reports_attachments.py::test_upload_more_than_ten_images_for_one_section_fails` independently encodes the new 10/11 behaviour and passed.
- **Impact:** A report can store 4–10 active images for one section, contrary to the declared MVP scope.  This changes expected report volume/UI workload and makes the deployed section cap impossible to tune back to 3 through `DAILY_REPORT_MAX_FILES_PER_SECTION`: config now hard-codes 10.  `.env.example` still advertises 3, so operator expectation and production behaviour diverge.
- **Why this is not merely stale documentation:** The authoritative master context and the build-pack requirements independently retain the 3-image limit.  The service, public limit response, error strings and test all changed together to 10.  This is an executable contract change with no reviewed specification update in the examined delta.
- **Remediation decision required before production:** Either (1) restore a single authoritative 3-image constant and align all three paths/tests/config documentation, or (2) obtain explicit product approval changing the master contract to 10 and update every authoritative specification and deployment template together.  Do not retain a misleading environment variable that cannot affect the effective limit.

## Explicitly checked and found clean

- **Global reports gate:** `app/__init__.py:186-206` still applies its endpoint-prefix gate to all changed report, project, customer, attachment and project-operation endpoints.  `ENDPOINTS-g5.md` records route-by-route whether the prefix matches.  New account, branding, Company Media and Project Documents endpoints correctly use their own module/ACL model rather than accidentally relying on the reports gate.
- **Report edit identity/scoping:** Changed service logic validates requested section IDs belong to the edited report and scopes requested attachment deletion to that report before soft-deleting (`app/reports/services.py:730-742` and edit helpers).  Tests passed for adding a server section ID, rejecting a section from another report, validation rollback preserving attachments, and deletion audit/storage cleanup.  No cross-report attachment deletion was found.
- **Report upload type/size checks:** V2 metadata uses the established storage validator then restricts to image extensions and 25 MB per image (`services.py:142-151`); aggregate limit remains 30 images/300 MB (`:131-132,162-163`).  The attachment-count finding does not alter these checks.
- **Admin project/customer linkage:** The changed admin save flow checks edit/manage scope over the old and new customer before changing an assignment, and customer attach checks an active non-deleted unassigned project plus scope on both objects.  No caller-supplied project/customer ID reaches a write without both object predicates.
- **Project documents:** New thumbnail handling checks document-file viewing authority first and chooses only a ready derivative/poster.  The signed-download error contract returns a stable application payload.  Existing unchanged preview branches were read only because changed JavaScript invokes them; they remain Phase 10 scope (`findings-4-project-documents.md`) and are not silently reclassified here.
- **Account preferences/theme:** The new preference endpoint is self-only, uses server-side allow-lists/normalization and writes an audit event.  The preload script reads a user-namespaced localStorage preference only to reduce paint flash; server-side normalized preferences remain canonical.  Changed DOM code uses controlled values/text rather than request-derived HTML.
- **CSRF and request methods:** Every changed state-changing browser endpoint is POST and continues through global CSRF; the changed display/thumbnail routes are GET-only reads.  New JSON upload endpoints are exercised by the existing CSRF-aware client helpers.

## Documentation/configuration consistency

### CONFIG-OP-001 — Environment template advertises settings that no longer control Daily Report’s effective per-section cap

- **Classification:** Confirmed documentation/operations defect; included with REPORTS-007 rather than counted as a second security finding.
- **Location:** `.env.example:11,52` says `MAX_IMAGES_PER_SECTION=3` and `DAILY_REPORT_MAX_FILES_PER_SECTION=3`; `app/config.py:63-70` calls the former legacy and fixes the latter at 10.
- **Impact:** An operator can set 3 believing it is enforced while the app accepts 10.  This is particularly hazardous during incident rollback or capacity planning, even though no secret/data boundary is affected.
- **Disposition:** Resolve as part of the REPORTS-007 product decision; remove dead settings or make the documented setting authoritative.

## Test evidence and limits

Passed during this audit:

```text
npm test
# 7 pass, 0 fail

PYTHONWARNINGS=error .venv/bin/python -m pytest -q -ra \
  tests/test_account_preferences.py tests/test_project_customer_assignment.py \
  tests/test_project_documents_upload_ux.py tests/test_daily_report_create_v2.py
# Each named suite passed when run in the recorded audit groups; see
# VERIFIED-PHASE11-DELTA.md for the exact group totals and commands.

PYTHONWARNINGS=error .venv/bin/python -m pytest -q \
  tests/test_reports_attachments.py::test_upload_more_than_ten_images_for_one_section_fails \
  tests/test_reports_attachments.py::test_edit_can_add_section_using_server_section_id \
  tests/test_reports_attachments.py::test_edit_rejects_section_id_from_another_report \
  tests/test_reports_attachments.py::test_report_edit_validation_fail_keeps_existing_attachment \
  tests/test_reports_attachments.py::test_attachment_delete_hard_deletes_storage_and_audits
# 5 passed
```

Two broader pytest invocations were terminated by the execution environment before pytest produced a summary.  They are not reported as passes.  Full regression execution on Python 3.12/PostgreSQL remains a release prerequisite.
