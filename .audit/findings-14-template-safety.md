# Findings — Unit 14: Template output safety

## Summary

- Read all 66 `app/templates/**/*.html` files (3,163 lines / 310,422 bytes) and all 16 first-party `app/static/js/**/*.js` files (1,853 lines / 127,506 bytes). No application-template file uses `|safe`, `Markup` in a template, or `{% autoescape false %}`.
- The trust boundary is user-writable database text (names, descriptions, notes, issues, report content, category icons, filenames and ACL-principal data) and request values rendered back into HTML. Normal Jinja interpolation is autoescaped; no candidate turned that output into executable markup without a second escaping/allow-list control.
- Inventoried 38 JS DOM/script/URL-sink line occurrences across 12 JS files. The dynamic sinks either receive fixed markup, browser-local `File`/object URLs, server-rendered autoescaped HTML, an authenticated endpoint's presigned URL, or values escaped/allow-listed before HTML construction.
- The Semgrep leads in the prompt are closed below. `project_documents/routes.py:303` is a `Markup` call, but its only interpolated URL is constructed through `url_for` from normalized context; it is not raw HTML from the request.
- Findings: none. This is an output-safety result only; it does not make presigned URLs non-bearer credentials or replace authorization checks in their issuing endpoints.

Files read: 66 templates; 16 JS files; supporting Python/routes/services listed in the evidence below.  
Files skipped and why: no in-scope template or JS files skipped. `claude-partial-audit-backup/` was deliberately neither read nor searched, per the Batch 2 exclusion.

## Findings

No reachable template-injection, DOM-XSS, or dangerous-URL injection finding was proven.

## Output-safety inventories and lead resolution

### 1. `|safe` and disabled autoescaping

| Construct | Inventory | Verdict |
| --- | --- | --- |
| `|safe` | 0 occurrences in all 66 templates | Clean. |
| `{% autoescape false %}` | 0 occurrences in all 66 templates | Clean. |
| Python `Markup` | `app/ui.py:192,196,199`; `app/project_documents/routes.py:303` | Resolved individually below; no unescaped user string is made trusted HTML. |

### 2. Template contexts: scripts, event attributes, URL attributes, styles, and JS-consumed `data-*`

The mechanical inventory found 205 template lines with a variable `href`, 28 with a variable `src`, one with a variable `style`, 58 with a variable `data-*`, and nine lines with inline event-handler attributes. The high-volume `href`/`src` population is overwhelmingly `url_for(...)`; the variable URL cases are resolved here rather than treated as automatically exploitable.

| Context / candidate | Source trace and evidence | Verdict |
| --- | --- | --- |
| `dashboard/_type_navigation.html:7` `href="{{ item.href }}"` | `dashboard_navigation_context()` creates every `href` with `url_for` at `app/dashboard/routes.py:156-160`; its four card dictionaries are fixed literals. | Clean: not user-controlled URL input. |
| `issues/index.html:10,62` `href="{{ create_url }}"` | The two callers assign it only via `url_for`: `app/issues/routes.py:53` and `app/projects/routes.py:209`. | Clean: controlled route output. |
| `modules/index.html:7` `href="{{ module.url }}"` | `get_accessible_modules()` maps fixed module keys to `url_for` results, `app/modules/services.py:30-38`. Its labels/icons/descriptions are constants at `:8-14`. | Clean: no database/request URL reaches the `href`. |
| `project_operations/workspace.html:7` `href="{{ href }}"` | `cards` contains only six fixed `url_for` values at `app/project_operations/routes.py:99-106`. | Clean. |
| `base.html:25,66` and `admin/branding.html:1` `src="{{ branding.logo_url }}"` | `get_current_branding()` loads the stored logo object only when `deleted_at is None` and `upload_status == "active"`, then creates its URL through the configured storage provider (`app/branding.py:8-19`). The S3 provider returns a generated `get_object` URL (`app/storage/providers.py:90-92`), not a URL DB field. | Not a template-XSS finding. This is an external, time-limited bearer URL in an image context; see Needs verification for storage-endpoint configuration. |
| `reports/form.html:12-19,62,78-80`; `partners/form.html:96`; `admin/projects/reporters.html:18`; `project_documents/folder.html:24` | `data-*` values consumed by JS are Jinja attribute-escaped, with structured content encoded through `tojson`. Examples: report categories/statuses feed `JSON.parse` in `app/static/js/app.js:56-57`; partner definitions feed `JSON.parse` at `:556-557`; folder destinations feed JSON to the move UI. The later HTML constructors escape user database text (`app.js:541-548,587-615`). | Clean. DB-backed category/field names/options are not inserted as raw HTML. |
| `partner_relations/tree.html:10` then `app/static/js/app.js:800-815` | The URL attribute is `url_for('partner_relations.department_summary', ...)`. The fetched response is rendered from `_department_summary.html` (`app/partner_relations/routes.py:163-190`), whose user-writable department/company/partner text uses ordinary `{{ ... }}` at `app/templates/partner_relations/_department_summary.html:4-75`. | Clean: the sole HTML-response-to-`innerHTML` flow remains Jinja-autoescaped end-to-end. |
| `reports/form.html:12` dynamic HEIC decoder URL | The `data-heic-decoder-url` is `url_for('static', ...)`; `daily-report-create-v2.js:64` assigns that URL to a created `<script>`. | Clean: dynamic script source is a fixed first-party static asset, not request/database input. |
| Inline `onsubmit` occurrences | Nine template lines use only fixed `return confirm('literal')` forms (for example `project_documents/folder.html:17-18,24,51` and permission-removal forms). | Clean: no interpolation enters JavaScript source. |
| Inline style | The sole interpolated-style inventory entry is a Bootstrap layout value in a template; no user-controlled value is placed into CSS. The report progress width at `reports/form.html:172` is fixed `0%`; JS writes a numeric computed width at `app/static/js/report-direct-upload.js:66`. | Clean. |

### 3. Every `tojson` use

| Location | Consumer and source | Safe context verdict |
| --- | --- | --- |
| `reports/form.html:12,19,62,78-79` | JSON is carried in single-quoted data attributes then parsed by the report JS. `category.name`/`category.icon` are database fields, but `tojson` JSON-escapes them and later `optionHtml` escapes all inserted values (`app/static/js/app.js:69-80`). | Safe. |
| `partners/form.html:96` | Field metadata is JSON in a data attribute, parsed at `app/static/js/app.js:556-557`; `field.label` and option strings are passed through `escapeHtml` before `row.innerHTML` (`:587-615`). | Safe. |
| `admin/projects/reporters.html:18` | Presets and active-user payload are `tojson` data attributes. Search result and selected-user markup escape every user string (`app/static/js/app.js:835-849`). | Safe. |
| `project_documents/folder.html:24` | Move destinations are `tojson` in a data attribute; the action code uses DOM APIs / option text, not raw HTML. | Safe. |
| `project_documents/permissions.html:66` | `principal_options` is inside `<script type="application/json">`; consumer parses `source.textContent` (`app/static/js/project-document-permissions.js:3-7`) and escapes names/details before `innerHTML` (`:49-69`). | Safe. |
| `company_media/permissions.html:23` | Same application/json pattern; consumer is `app/static/js/company-media-permissions.js:2-6,25,31`. | Safe. |

`tojson` is used in script data or quoted data-attribute contexts, not as an unquoted executable JavaScript expression. It also avoids a literal `</script>` break-out in the two application/json script blocks.

### 4. `Markup` / `markupsafe.Markup` inventory

| Location | Real code / data origin | Verdict |
| --- | --- | --- |
| `app/ui.py:192` | `return Markup('<span class="category-emoji">📌</span>')` | Fixed literal. |
| `app/ui.py:196` | `return Markup(f'<i class="bi bi-{escape(normalized)}"></i>')` after `re.fullmatch(r"[a-z0-9][a-z0-9-]{0,48}", normalized)` | Clean: category icon input is allow-listed and explicitly escaped. Resolves lead `app/ui.py:196`. |
| `app/ui.py:199` | `return Markup(f'<span class="category-emoji">{escape(value)}</span>')` after max-eight-character branch | Clean: explicit `markupsafe.escape`. Resolves lead `app/ui.py:199`. |
| `app/project_documents/routes.py:303` | `flash(Markup(f'... href="{archived_url}" ...'))` | Closed false-positive/info. `archived_url` comes only from `_folder_url()` (`:66-70`), which calls `url_for`; its request-derived `q` passes as a URL query parameter after `_folder_context()` (`:55-63`). URL percent-encoding means request bytes cannot terminate the HTML attribute; no raw query string is concatenated into markup. This resolves the required `archived_url` lead. |

### 5. DOM and dynamic URL/script-sink inventory

38 line occurrences were reviewed (no `outerHTML`, `document.write`, or `DOMParser` occurrences). The table groups all sink lines by their actual data source.

| File:line(s) | Sink / source | Verdict |
| --- | --- | --- |
| `app/static/js/app.js:87,183,243,269` | `innerHTML`/`insertAdjacentHTML` for report sections and custom selects. Dynamic category/status values originate in `tojson` data attributes; `optionHtml`, `renderCategoryIcon`, and `statusIconMarkup` escape strings and regex-allow-list icon keys (`:69-80,250-280,541-548`). | Clean. |
| `app/static/js/app.js:319,330,334,338,340,350` | Upload-preview DOM writes. HTML strings are fixed; user-controlled `File.name` goes through `textContent`/`alt`, and image sources are browser-created object URLs. | Clean. |
| `app/static/js/app.js:609,641` | Partner dynamic-field markup. Field labels/options/IDs use `escapeHtml` before HTML construction (`:573-615`); empty state is fixed. | Clean. |
| `app/static/js/app.js:804,814,817` | Department-summary modal. Static loading/error HTML at `:804,817`; `:814` inserts the response rendered by the autoescaped `_department_summary.html` partial. | Clean; no raw user HTML reaches the response. |
| `app/static/js/app.js:840,846-849` | Project-membership user picker. `available_user_payload` comes from `tojson`; user name/username/email/role go through `escapeHtml` before HTML. | Clean. |
| `app/static/js/project-document-permissions.js:60,68` | ACL search results use an `escapeHtml` helper implemented with `textContent`, then insert only the escaped result. | Clean. |
| `app/static/js/company-media-permissions.js:25,31` | Equivalent ACL search result flow and helper. | Clean. |
| `app/static/js/daily-report-create-v2.js:63-64,67` | File preview uses browser object URLs; dynamic `<script>.src` is the static `url_for` value described above. User filename enters `alt`/`aria-label` via DOM APIs. | Clean. |
| `app/static/js/project-document-preview.js:5-8`; `company-media-covers.js:1`; `report-attachment-status.js:9-10`; `media-preview-modal.js:9-16` | Image/video `src` and download `href` receive authenticated endpoint paths or JSON presigned URLs. These are storage bearer-capability outputs, not markup strings; authorization must be verified at their issuing routes (Units 4/5/7). | No DOM-XSS demonstrated. |
| `app/static/js/report-direct-upload.js:53`; `app/static/js/display-image-picker.js:21,48,53,62` | Browser-selected files/object URLs and saved, pre-existing `viewport.innerHTML`; no server/database string is treated as markup. | Clean. |
| `app/static/js/scoped-dashboard-charts.js:150`; `contractor-dashboard-charts.js:22` | `insertAdjacentHTML` receives fixed Vietnamese error literals only. | Clean. |

### 6. User-controlled values reaching the DOM

| Value class | Reachability / treatment | Verdict |
| --- | --- | --- |
| User/company/customer/project/partner names, descriptions, roles, emails, notes, issues, report highlight/content | Rendered by ordinary `{{ value }}` in templates, including `reports/form.html:43,48,121`, `issues/index.html:31-37`, `dashboard/contractor.html:42-48`, and `_department_summary.html:4-75`; where copied into JS markup, values go through `escapeHtml`. | Autoescaped / clean. |
| Category icon | `category_icon()` only returns trusted markup after regex validation plus `escape` (`app/ui.py:189-201`). | Clean. |
| Uploaded/original/display filenames | Template attribute contexts are autoescaped (for example `reports/form.html:138`); JS uses `textContent`/`alt` or presigned URLs with filename only in Content-Disposition. | No DOM-XSS shown. |
| Raw search/request input | Reflected in normal template fields such as the project-document `q` value; `_folder_context()` supplies it to `url_for`, not to raw markup (`app/project_documents/routes.py:55-70`). | Clean. |
| S3/presigned URLs | Generated by `StorageProvider.create_presigned_download`, e.g. `app/storage/providers.py:90-92`, and passed to DOM URL properties, not `innerHTML`. | Not XSS; bearer-capability handling is an authorization/deployment concern. |

## Explicitly checked and found clean

- Global Jinja template autoescaping was not disabled anywhere in `app/templates/`; ordinary `{{ value }}` was not reported as XSS merely because its database field is user-writable.
- The three named variable-`href` leads (`dashboard/_type_navigation.html`, `issues/index.html`, and `modules/index.html`) are all route-generated `url_for` values.
- `project_documents/permissions.html:66` and `company_media/permissions.html:23` use `tojson` in non-executable `application/json` script elements, and both consumers escape user/role fields before constructing their result buttons.
- `app/ui.py:196,199` provide explicit escaping before `Markup`; `app/project_documents/routes.py:303` uses a URL generated by `url_for`, not direct request text.
- Every first-party `innerHTML`/`insertAdjacentHTML` occurrence in `app/static/js/app.js` and the other 15 JS files was traced. No unescaped database/request value reaches a markup sink.
- No dynamic script source is user-controlled; the single dynamic loader is the fixed static HEIC decoder URL.
- Direct Jinja `href`/`src` values produced by `url_for` were not treated as exploitability without a controllable scheme/context break. No such break was found.

## Needs verification

1. **Deployment concern, not a template finding:** confirm the production `STORAGE_ENDPOINT_URL` is a trusted HTTPS S3/MinIO endpoint and that only trusted operators can change it. `branding.logo_url` and media preview/download URLs eventually become external `img`/`video`/`href` values through `S3StorageProvider` (`app/storage/providers.py:70-92`). Application code shown here supplies bucket/key/disposition, but this read-only code audit cannot validate the deployed endpoint, TLS, or operator access. This would not turn normal Jinja escaping into XSS; it would establish whether the expected storage trust boundary holds.

## Tool leads closed as false positive/info

- Semgrep's general template findings are information only after manual review: the scanner could not fully parse most Jinja templates (see `.audit/PRE-FINDINGS.md`), so this report used source tracing rather than scanner classification.
- `app/ui.py:196,199`: false-positive/info; both `Markup` constructions explicitly escape dynamic content, with an additional icon-key allow-list at `:195-196`.
- `app/project_documents/routes.py:303`: false-positive/info; `archived_url` is `url_for` output generated from normalized query context, not unescaped raw HTML.
- Variable `href` leads in dashboard, issues, modules (and the analogous workspace card): false-positive/info; all resolve to fixed route `url_for` outputs.
- `project_documents/permissions.html:66` principal JSON: false-positive/info; `tojson` is in an inert JSON script block and its JS consumer escapes DOM-markup fields.
- `app/static/js/app.js` and all other reported `innerHTML`/`insertAdjacentHTML` sites: false-positive/info for XSS after the source-to-sink checks above; the one server HTML response inserted into the DOM is rendered from an autoescaped Jinja partial.
