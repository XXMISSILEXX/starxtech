# Findings — Unit 11: Frontend JavaScript

## Summary

- Read all 15 first-party files under `app/static/js/` (1,833 LOC) and all 3 JS tests (152 LOC). No first-party JS, test, template, or backend file was modified.
- Mapped 23 programmatic network primitives (22 `fetch`/one `XMLHttpRequest`) and three native dynamic-form submits. The JSON/form APIs re-authorize their target project/folder/album/item and validate the meaningful client-controlled fields; client checks are UX only.
- Read the direct server-side twins for daily-report V2 and legacy upload sessions, Project Documents, Company Media, dashboard APIs, attachments, and partner-department summary. No client-bypass-only finding is reported.
- The Semgrep `insertAdjacentHTML` lead at `app.js:269` is not exploitable from the reviewed call chain: icon keys are enum-derived/regex-constrained, the sprite is a fixed `url_for('static', ...)` output, and the sink receives generated SVG only.
- JS test coverage is narrow: the three tests exercise two report workflows and scoped dashboard rendering, but do not exercise real HTTP authorization, upload ownership, DOM-sink provenance, or failure/retry paths for most first-party scripts.

Files read: 18 primary files (15 JS + 3 JS tests); 17 direct templates/backend files listed in the trace below.

## Network request inventory

`CSRF` means an explicit token/header in this script; global Flask-WTF protection remains the server-side backstop.

| JS file:line | Method / URL | CSRF | Input source | Backend / server-side twin |
|---|---|---|---|---|
| `app.js:362-368` | POST `/media-display-preview` | form field | selected HEIC/HEIF | `account.routes.media_display_preview`; Unit 10 owns image validation |
| `app.js:806-815` | GET `data-department-summary-url` | n/a GET | server-rendered `url_for` in `partner_relations/tree.html:10` | `partner_relations.routes.department_summary:163-189`, RBAC decorator |
| `company-media-covers.js:1` | POST `data-preview-url` | header | server-rendered `url_for` | `company_media.routes.preview:98-102`, `view_file` |
| `contractor-dashboard-charts.js:15` | GET dashboard API | n/a GET | server-rendered `url_for` | `dashboard.routes:94-102`, module/RBAC/scope checks |
| `daily-report-create-v2.js:77,79-80` | POST preflight, session create, presign, complete, finalize | `X-CSRFToken` | report date/status/sections/file metadata/session/item IDs | `reports/create_v2.py:50-134`; `_project()` calls `can_create_report`; `reports/services.py:80-149,152-215` validates each field, locks session/items |
| `daily-report-create-v2.js:78` | PUT presigned object URL | S3 signed headers | original `File` bytes | URL minted only by `direct_uploads.v2_presign`; completion calls `_validate_head` (`direct_uploads.py:170-186`) |
| `display-image-picker.js:15-20` | POST `/media-display-preview` | form field | selected HEIF/HEIC | Unit 10 path |
| `project-dashboard-charts.js:23` | GET `data-section-status-api` | n/a GET | server-rendered `url_for` | `dashboard.routes:66-78`; reports module, permission, project scope, date parsing |
| `project-document-file-actions.js:54-63` | POST bulk archive/restore URL | header | checked file IDs | Project Documents/Company Media routes parse IDs and re-check each file permission |
| `project-document-file-actions.js:93-103` | POST direct/bulk-download validation URL | header | checked file IDs | module routes re-check parent and every selected file; Foundation-B §7 confirms per-file authorization |
| `project-document-file-actions.js:109-122` | native POST bulk download | hidden CSRF | selected file IDs | same server-side bulk-download checks |
| `project-document-preview.js:4-8` | POST signed preview/download URL | header | server-rendered `url_for`, variant | respective `signed_preview`/`signed_download` routes check file ACL |
| `project-document-upload.js:37-47` | POST selection-session, presign, complete, finalize; POST presigned S3 | header except S3 | file count/size/name/MIME, selection/item IDs, bytes | `project_documents.routes:113-149` and parallel Company Media routes; folder/album capability, session target/owner, metadata and HEAD verification |
| `report-attachment-status.js:16-20` | POST `/attachments/status-batch` | header | visible attachment IDs | `attachments.routes:54-66`: max 100 and `can_view_report` per row |
| `report-direct-upload.js:41-45,90-109,129-155` | POST legacy session/presign/complete/cancel/state/report submit; PUT presigned S3 | CSRF for same-origin JSON; form includes token | report fields, file metadata, session/item IDs, persisted session ID | `projects.routes:136-192`, `reports/direct_uploads.py:41-186`, and report route/service validate capability, ownership, file metadata, status and manifest |
| `scoped-dashboard-charts.js:101` | GET `data-dashboard-api` | n/a GET | server-rendered `url_for` | `dashboard.routes:81-102`, scope/RBAC checks |

There are **23 programmatic request primitives** (22 `fetch` plus one `XMLHttpRequest`) and **three native `form.submit()` paths** (two confirmation fallbacks and one ZIP request): **26 network submission sites** total. No `navigator.sendBeacon`, `DOMParser`, `outerHTML`, `localStorage`, or presigned token persistence was found.

## Client validation and server-side twins

| Client area | Client check | Server-side twin / verdict |
|---|---|---|
| V2 report date/status/sections | `daily-report-create-v2.js:73-76` | `reports/services.py:80-113` parses ISO date, blocks future dates, allow-lists status, validates unique section/category and project-bound category. Present. |
| V2 files | `daily-report-create-v2.js:71,75` | `reports/services.py:114-148`; `direct_uploads.py:110-186`: file count, per-section count, declared MIME/extension/size, session/item binding, storage HEAD verification. Present (content-sniffing limitation is Foundation-B / Unit 10-related, not a missing server twin). |
| Legacy report direct upload | `report-direct-upload.js:71-88` | `projects/routes.py:136-192`, `direct_uploads.py:52-107,170-186`, and manifest validation. Present. |
| Project Documents / Company Media upload | `project-document-upload.js:23,37-47` | project-document routes/services at `routes.py:113-149`, `services.py:76-80,131-147`, plus parallel Company Media routes. Present. |
| Project-update future date | `app.js:677-702` | Not re-reported: server counterpart belongs to Unit 8; this is only client-side UX validation. |
| Dynamic ACL principals/flags | `project-document-permissions.js:42-90`; `company-media-permissions.js:27-36` | Server ownership/permission enforcement belongs to Units 4/5; those units independently audited it. No JS-only authorization claim was trusted. |

## Findings

### JS-001 — First-party JS security-critical paths have little direct behavioral test coverage

- **Severity:** Low (evidence/test-confidence weakness, not a demonstrated production vulnerability)
- **Confidence:** High
- **CWE:** CWE-693
- **Location:** `tests_js/daily-report-create-v2.test.js:11-54`; `tests_js/report-direct-upload.test.js:14-25`; `tests_js/scoped-dashboard-charts.test.js:48-71`
- **Reachability:** Every browser user relies on untested scripts for client upload orchestration, DOM rendering, preview, download, and dashboard behavior. The gap does not bypass server authorization by itself.
- **Evidence:**
  ```js
  // tests_js/report-direct-upload.test.js:20-25
  assert.match(source, /event\.preventDefault\(\); save\(\)/);
  assert.match(source, /data\.delete\(input\.name\)/);
  assert.match(source, /Math\.min\(3, Number\(limits\.concurrency\)/);
  ```
  ```js
  // tests_js/daily-report-create-v2.test.js:21-23
  const responseBody = { ok: false, error: { code: "duplicate_report_date", ... } };
  dom.window.fetch = async () => new Response(JSON.stringify(responseBody), { status: 409, ... });
  ```
  The suite has only these three test files. `app.js` (850 lines), Project Document/Company Media upload and permission scripts, media preview scripts, attachment polling, and dashboard scripts have no corresponding JS test. The V2 test replaces `fetch` with a synthetic `Response`; it does not reach Flask or prove CSRF, project scope, session ownership, presigned upload, server validation, or retry/idempotency behavior.
- **Impact:** Regressions in failure-state handling, client/server contract assumptions, or sink provenance can ship without a JS-level regression signal. This is a reliability/security-assurance gap, not proof of exploitable client-side authorization.
- **Recommended future test:** Add browser/JSdom tests for V2 cancel/retry/double-submit, legacy recovery, object-URL cleanup, status-icon source provenance, and every upload error terminal state; retain real-route authorization tests in the Python suite.
- **Effort:** M

## Needs verification

- The direct-upload implementation stores only session/item IDs, filenames, and sizes in `sessionStorage` (`report-direct-upload.js:69,155`), not presigned URLs or file bytes. Runtime testing in a real browser would confirm it is cleared on all terminal navigation/error paths; no secret exposure is evidenced by source.
- `app.js:806-815` assigns a same-origin HTML fragment to `innerHTML`. The endpoint is permission-guarded and the complete fragment uses normal Jinja escaping (`partner_relations/_department_summary.html:4-83`), so no XSS is demonstrated. Any future `|safe`/raw HTML in that fragment would change this assessment; cross-reference Unit 14 rather than duplicate its template review.
- V2 preview decoding dynamically loads `form.dataset.heicDecoderUrl` (`daily-report-create-v2.js:64`). In the only template source, it is a fixed static `url_for` (`reports/form.html:12`). A deployed CSP/runtime integrity check would be required to establish supply-chain handling beyond source review.

## Explicitly checked and found clean

- **Status badge Semgrep lead:** `app.js:258-269` admits only `/^[a-z0-9-]+$/` icon keys, escapes the static sprite URL, and inserts only `statusIconMarkup()` output. The sole callers are server-rendered `status_presentation()` enum metadata: `base.html:2`, `reports/form.html:31-33,69`, `reports/index.html:66`, `reports/detail.html:10,40`, `dashboard/project.html:111`. No free-text/user-controlled icon source reaches the sink. Verdict: false positive / no finding.
- All dynamic markup sinks were reviewed. User-/server-data interpolation at `app.js:78,183,243,609-616,840,846` and permission scripts uses `escapeHtml`; other `innerHTML`/`insertAdjacentHTML` uses are fixed literals or the same safe status helper. `project-document-permissions.js:60,67-69` and `company-media-permissions.js:25,31` encode via DOM `textContent` before inserting markup.
- No raw server error response is inserted as HTML. Errors become `textContent`, `alert`, or fixed literal markup (`daily-report-create-v2.js:25-56`; `project-document-file-actions.js:61-123`; chart scripts).
- URLs that cause navigation are server-rendered `url_for` dataset values or server-returned, authorized signed URLs. The API endpoints independently authorize objects (`dashboard/routes.py:66-130`; `project_documents/routes.py:113-155`; `company_media/routes.py:98-108`; `attachments/routes.py:54-66`). No client-side permission/visibility decision was accepted as a security boundary.
- V2 has a submission guard/watchdog (`daily-report-create-v2.js:12,39-56,80-81`); the server finalizer is idempotent per `client_request_id` and locks the session/items (`reports/services.py:159-215`). Legacy upload retries reuse V2-like owned sessions/items (`direct_uploads.py:110-186`).
- Object URLs are generally revoked on image load/removal/pagehide (`app.js:329-338`, `daily-report-create-v2.js:62,81`, `report-direct-upload.js:70`, `display-image-picker.js:38,62`); no material retained blob-URL exposure was proven.
- No `target=_blank` assignments, open-redirect construction, `sendBeacon`, `localStorage`, password/CSRF logging, or attacker-controlled active SVG/HTML response insertion was found in first-party JS.

## Test integrity details

- `daily-report-create-v2.test.js`: real source evaluated in JSDOM, but all network is mocked; covers blank section, remove behavior, 409 and 422 UI terminals.
- `report-direct-upload.test.js`: one mocked hanging submit and regex/source-characterization checks; does not execute an upload state-machine completion.
- `scoped-dashboard-charts.test.js`: mocked dashboard JSON and mocked Chart; covers project-activity render/empty state only.
- No test validates a real DOM sink (`initStatusBadges`, permission result rendering, or department-summary insertion), image preview, Company Media/Project Document upload, attachment polling, or the complete legacy upload state machine.

