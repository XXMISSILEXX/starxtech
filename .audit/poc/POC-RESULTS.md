# Phase 10 Step 7 — PoC results

Commands executed:

```text
PYTHONWARNINGS=error pytest -q -ra \
  .audit/poc/customer_001_project_move_authz_test.py \
  .audit/poc/contractor_001_cross_scope_assignment_test.py \
  .audit/poc/reports_001_cross_project_cleanup_test.py \
  .audit/poc/ai_002_document_download_permission_test.py \
  .audit/poc/issue_002_delete_permission_test.py

PYTHONWARNINGS=error pytest -q -ra .audit/poc/*_test.py
```

The explicit run collected five new tests.  All five reached their real Flask
endpoints and failed only at the final secure assertion.  The complete run
collected ten tests: five existing and five new.  It had ten expected security
failures, zero collection errors, and zero infrastructure/setup errors.

| Finding | PoC file | Collected? | Result today | Assertion failure | Infrastructure error? | Failure proves |
|---|---|---|---|---|---|---|
| Critical 01 | `critical_01_admin_self_grant_super_admin_test.py` | Yes | EXPECTED SECURITY FAILURE | Expected rejection and retained `ADMIN`; got 302 and `SUPER_ADMIN`. | No | An ADMIN can self-promote. |
| Critical 02 | `critical_02_super_admin_password_reset_test.py` | Yes | EXPECTED SECURITY FAILURE | Expected denial, unchanged hash, and no secret; hash changed and secret rendered. | No | An ADMIN can reset a SUPER_ADMIN password. |
| Critical 03 | `critical_03_roles_manage_self_grant_test.py` | Yes | EXPECTED SECURITY FAILURE | Expected rejection and no dangerous grant; got 302 with `system.settings`. | No | A role manager can expand its own role. |
| Critical 04 | `critical_04_project_membership_self_insert_test.py` | Yes | EXPECTED SECURITY FAILURE | Expected denial and no membership; got 302 with all capabilities. | No | Assignment manager can self-insert into an unrelated project. |
| Critical 05 | `critical_05_company_media_acl_escalation_test.py` | Yes | EXPECTED SECURITY FAILURE | Expected denial and no elevated ACL flags; got 302 with elevated flags. | No | Share-only album ACL can self-escalate. |
| CUSTOMER-001 | `customer_001_project_move_authz_test.py` | Yes | EXPECTED SECURITY FAILURE | Expected denial and source customer retained; got 302 and `customer_id=9102`. | No | A source-project reader moves the project without source-customer management. |
| CONTRACTOR-001 | `contractor_001_cross_scope_assignment_test.py` | Yes | EXPECTED SECURITY FAILURE | Expected denial and no project-1 assignment; got 302 and assignment inserted. | No | An assignment manager attaches a contractor otherwise visible only through project 2. |
| REPORTS-001 | `reports_001_cross_project_cleanup_test.py` | Yes | EXPECTED SECURITY FAILURE | Own cancellation returned 200 but removed unrelated project-2 DB object and fake-storage bytes. | No | Cancelling an owned session invokes global destructive cleanup. |
| AI-002 | `ai_002_document_download_permission_test.py` | Yes | EXPECTED SECURITY FAILURE | Expected denial/no URL/no event; got 200, URL, and event count `0/1`. | No | Document view capability mints a signed download URL without the download permission. |
| ISSUE-002 | `issue_002_delete_permission_test.py` | Yes | EXPECTED SECURITY FAILURE | Expected denial and active issue retained; got 302 and soft-deleted issue. | No | Issue edit capability performs delete without `issues.delete`. |

Classification: all ten failures are expected security failures. Each test
created only isolated fixture data; signed URL/object assertions use the normal
fake storage provider. No production service, persistent database, or remote
storage was contacted.
