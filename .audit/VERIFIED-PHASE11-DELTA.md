# Phase 11 Delta — Verification register

## Audit identity

| Item | Value |
|---|---|
| Baseline | `fc1a117` — `docs(audit): close Phase 10 and record RC readiness` |
| Audited HEAD | `e764509c5e2cc174499248c79e7d4ec7fdedfe2a` |
| Branch at start | `Phase12/Progress-and-beyond` |
| Delta self-check | 20 commits; 111 files; +7,685/−303 lines |
| Source write policy | No source/config/test/deployment file modified; audit output only in `.audit/` |

## Findings status

| ID | Classification | Severity | Status | Evidence / disposition |
|---|---|---:|---|---|
| REPORTS-007 | Confirmed product-contract regression | Medium | **Open** | `AGENTS.md` retains max 3 images/section; changed common constant and all create/edit paths enforce 10. Reproduced by `.audit/poc/REPORTS-007-section-image-limit.py`. Resolve by approved 3 or approved 10 contract decision before production. |
| CONFIG-OP-001 | Confirmed documentation/operations defect | Low | Open with REPORTS-007 | `.env.example` says 3 while config ignores that setting and fixes 10. Resolve together with the product decision. |
| CM-OP-001 | Accepted documented operational limitation | n/a | Requires owner evidence | DB-only cancellation intentionally leaves potential S3 pending bytes for external lifecycle/reconciliation. No S3 deletion/listing belongs in the HTTP path. |
| STORAGE-OP-002 | Unverified operational capacity risk | n/a | Staging required | CloudFly multipart overhead allowance and pending-object lifecycle need observation with the real provider. |
| DEPLOY-OP-001 | Unverified deployment condition | n/a | Staging required | Host cache mount permissions/UID 1000/Nginx internal routing cannot be proven from repository source. |
| DEPLOY-OP-002 | Confirmed documentation ambiguity | Low | Open | Compose defaults to `send_file` although template wording implies X-Accel. State a selected production mode. |

## Regression review of closed Phase 10 evidence

No confirmed regression of a Phase 10 finding was established in this delta.  The following old components were read because changed paths reach them, rather than re-audited wholesale:

| Existing record | Why read in this delta | Result |
|---|---|---|
| `findings-3a-reports.md`, `findings-3b-uploads.md` | New report attachment-limit/edit/direct-upload code and reports module gate | No new old-ID regression; new REPORTS-007 is separate contract drift |
| `findings-4-project-documents.md` | Changed signed-download and thumbnail/UI callers | No new endpoint authorization/original-preview fallback introduced |
| `findings-5-company-media.md` | New idempotency, cleanup, thumbnail and download-error contracts | No confirmed access regression; CM-OP-001 remains an intentional boundary |
| `findings-7-attachments.md` | New cache callers | Authorization still occurs before cache materialisation |
| `findings-10-account.md`, `findings-11-frontend-js.md`, `findings-14-template-safety.md` | Preferences/theme/static UI changes | No confirmed injection or self-scope regression |
| `findings-12-deploy-iac.md`, `findings-13-test-integrity.md` | Docker/Compose/config and new tests | Deployment evidence conditions above remain |

## Commands and observed results

| Command | Result |
|---|---|
| `git status --short --branch` | Clean at audit start; expected branch |
| `git log --oneline fc1a117..HEAD` / `git diff --stat fc1a117..HEAD` | Exact expected delta identity/counts |
| `git diff --check fc1a117..HEAD` | Passed |
| `.venv/bin/python -m compileall -q app tests` | Passed |
| `npm test` | 7 passed, 0 failed |
| Media cache/signed-download/account suites | 30 passed |
| Company Media permission/idempotency/cleanup/limits suites | 46 passed |
| Project/customer/document/deployment suites | 32 passed |
| Daily Report V2 suite | 13 passed |
| Selected report attachment/edit/deletion tests | 5 passed |
| `.audit/poc/REPORTS-007-section-image-limit.py` | Intentionally failed: `assert 10 == 3` |

Two broad pytest runs were externally terminated before a pytest summary.  They are intentionally absent from the passed rows.  The local `.venv` used Python 3.10; production must repeat the relevant suite with Python 3.12 and PostgreSQL.
