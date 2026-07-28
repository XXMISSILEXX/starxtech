# TOOL-LEAD-MAP.md

Every automated-tool finding, mapped to exactly one audit unit. Read-only —
reachability assessments below are preliminary scoping to hand to the unit
that owns the deep verification, not final verdicts. "Reachable" means a
concrete code path from an HTTP request (or, for CLI/migration code, from an
operator command) to the vulnerable functionality was found by direct
reading; "Not reachable" means the vulnerable function/parameter combination
was searched for and not found in this codebase's call sites.

---

## Semgrep — 11/11 covered

| Source | ID / rule | file:line | Severity | Assigned unit | Verify-by |
|---|---|---|---|---|---|
| semgrep | `python.sqlalchemy.security.audit.avoid-sqlalchemy-text` | `app/cli.py:498` | ERROR | 1 (CLI & Ops) | `sync_postgres_sequence()`'s `table_name`/`column_name` args are only ever passed from `sync_partner_demo_sequences()` iterating the hardcoded `PARTNER_SEED_TABLES` constant (`app/cli.py:510-512`) — confirmed not reachable from any HTTP route or user input; operator-invoked `flask seed-partner-demo` only. Downgrade to Info unless Unit 1 finds another call site. |
| semgrep | `python.sqlalchemy.security.audit.avoid-sqlalchemy-text` | `migrations/versions/20260722_0014_three_layer_authorization.py:52` | ERROR | 1 (CLI & Ops, migrations are in its cross-reference scope via Foundation-A2) | `manager_flags` is built by joining a hardcoded module-level `FLAGS` constant, not user input — one-time `flask db upgrade` backfill, not reachable from any route. Downgrade to Info. |
| semgrep | `python.sqlalchemy.security.audit.avoid-sqlalchemy-text` | `migrations/versions/20260722_0014_three_layer_authorization.py:53` | ERROR | 1 (CLI & Ops) | Same file, `reporter_flags` built from a hardcoded tuple literal at the call site (`app/`-relative line 48-50) — same verdict as above. Downgrade to Info. |
| semgrep | `python.django.security.injection.raw-html-format.raw-html-format` | `app/project_documents/routes.py:303` | WARNING | 14 (Template safety) | `Markup(f'...{archived_url}...')` with no `escape()` call, unlike the two call sites in `app/ui.py:196,199` which do call `escape()`. `archived_url` is built by `_folder_url()` → `url_for(...)` (`app/project_documents/routes.py:66-69`), which percent-encodes query values — likely not exploitable today, but confirm no other value ever gets concatenated into this same f-string unescaped, and confirm `_folder_context()`'s `q`/`source` values can't smuggle anything past `url_for`'s encoding. |
| semgrep | `python.flask.security.injection.raw-html-concat.raw-html-format` | `app/project_documents/routes.py:303` | WARNING | 14 (Template safety) | Same line, second rule firing on the same pattern — one code location, listed once above, not double-counted as two distinct issues. |
| semgrep | `typescript.react.security.audit.react-unsanitized-method` | `app/static/js/app.js:269` | WARNING | 11 (Frontend JS) | `insertAdjacentHTML` in `initStatusBadges()`. Preliminary read: `statusIconMarkup()` (same file, ~line 260) regex-validates `iconKey` against `^[a-z0-9-]+$` before use and calls `escapeHtml()` on `sprite` — looks defensively written. Confirm every template that sets `data-status-icon-key`/the sprite-URL data attribute only ever emits a fixed status-enum value (`DailyReportStatus`/`SectionStatus`/`IssueStatus`/`IssueSeverity`, all in `app/models/enums.py`), never free text. |
| semgrep | `generic.html-templates.security.var-in-href` | `app/templates/dashboard/_type_navigation.html:7` | WARNING | 14 (Template safety) | `href="{{ item.href }}"` — `item.href` traced to server-computed `url_for(...)` output in dashboard navigation config, not raw user input. Likely false positive; confirm the navigation-item builder never accepts a caller-supplied redirect target. |
| semgrep | `generic.html-templates.security.var-in-href` | `app/templates/issues/index.html:10` | WARNING | 14 (Template safety) / 7b (Issues) | `href="{{ create_url }}"` — traced to a server-computed `url_for('issues.new', ...)`-style value in `app/issues/routes.py`. Likely false positive; confirm. |
| semgrep | `generic.html-templates.security.var-in-href` | `app/templates/issues/index.html:62` | WARNING | 14 (Template safety) / 7b (Issues) | Same pattern, second occurrence in the same template (empty-state variant). Same verdict. |
| semgrep | `generic.html-templates.security.var-in-href` | `app/templates/modules/index.html:7` | WARNING | 14 (Template safety) / 10 (Account+Modules) | `href="{{ module.url }}"` — traced to `app/modules/services.py`'s module-list builder, server-computed `url_for(...)` targets for the four fixed modules (reports/partners/project_documents/company_media), not user input. Likely false positive; confirm. |
| semgrep | `generic.html-templates.security.var-in-script-tag` | `app/templates/project_documents/permissions.html:66` | WARNING | 14 (Template safety) | `<script type="application/json">{{ principal_options\|tojson }}</script>` — `\|tojson` is Flask/Jinja's blessed safe pattern for this exact use case (escapes `</script>` and HTML-sensitive sequences). Near-certain false positive; confirm quickly and close, don't spend time here. |

**Note on coverage**: 61 of the 66 templates in this repo produced a
parse error during this semgrep run (see `PRE-FINDINGS.md` PRE-010) — the 5
template-related findings above came from partial parses, not full-file
analysis. Unit 14's manual sweep is the real coverage, not this table.

---

## pip-audit — 5 packages, 21 distinct advisory IDs (28 raw entries incl. duplicate PyPA/OSV cross-listings)

| Source | Package | Installed → fix | Advisory IDs | Severity | Assigned unit | Reachability |
|---|---|---|---|---|---|---|
| pip-audit | `flask` | 3.0.3 → 3.1.3 | PYSEC-2026-2151 | Medium (cache/session info exposure, not RCE) | Foundation-A1 (session handling lives here — per your instruction, Flask/Werkzeug/Jinja2/itsdangerous findings land in A1) | Reachable in principle on any authenticated route if this deployment sits behind a caching proxy that doesn't respect `Vary: Cookie`/doesn't mark responses private. Cloudflare Tunnel is the ingress (`docker-compose.yml`); confirm its cache rules don't cache authenticated HTML responses. A1 must read Flask's session-access code path to confirm which of this app's `session[...]` accesses (if any) use the affected "key-only" access pattern the advisory describes. |
| pip-audit | `python-dotenv` | 1.0.1 → 1.2.2 | PYSEC-2026-2270 | Low (local-attacker symlink write, requires `set_key()`/`unset_key()`) | Foundation-A1 | **Not reachable** — confirmed by repo-wide grep: this app only calls `load_dotenv()` (`app/config.py:6`), read-only. `set_key`/`unset_key`/`find_dotenv` have zero call sites anywhere in `app/`. Info only; upgrade opportunistically, not urgent. |
| pip-audit | `pillow` | 10.4.0 → 12.1.1 / 12.2.0 / 12.3.0 (varies per advisory) | PYSEC-2026-165, -2249, -2250, -2252, -2253, -2254, -2255, -2256, -2257, -2874, -3451, -3453, -3454, -3493, -3494, -3495, -3496 (17 distinct) | Mixed High (several out-of-bounds write / heap corruption; one CPU-exhaustion DoS via malicious PDF, PYSEC-2026-2874; one Windows-only shell-command-construction issue, PYSEC-2026-2257, not applicable — this deploys on Linux containers) | **10 (Account, primary)**, cross-reference **1 (CLI seed/demo)**, **Foundation-B (media_processing)** | **Reachable.** Three concrete `Image.open()` call sites take attacker-controlled bytes with no `formats=` restriction and no `Image.MAX_IMAGE_PIXELS` cap in the synchronous request path: `app/account/routes.py:61-62` (avatar upload — the unit-10 focus), `app/display_images.py:47,49` (partner/company/branding images, shared foundation code). `app/media_processing/pipeline.py:54-57` **does** set `Image.MAX_IMAGE_PIXELS` before opening — but that mitigation only helps the decompression-bomb-shaped advisories, not the memory-corruption ones (malicious PSD/PCF/BDF/GD/TGA/JPEG2000/coordinate-overflow/ImageCms/rank-filter advisories are format-parser bugs, unaffected by a pixel-count cap), and it runs in a separate Celery worker process — it does not protect the synchronous account/display-image path at all. `CVE-2026-2257`'s Windows `cmd.exe` command-construction issue is not applicable on this Linux-only deployment. |
| pip-audit | `pillow-heif` | 0.18.0 → 1.3.0 | PYSEC-2026-2258 | Medium (integer overflow in the **encode** path) | 10 (Account) / Foundation-B | Used in 4 files (`app/display_images.py`, `app/media_processing/pipeline.py`, `app/cli.py`, `app/reports/services.py`), but every usage found only calls `register_heif_opener()` (decode-side registration). No explicit HEIF-encode call site found (no `.save(..., format="HEIF")` located by this pass). The specific vulnerable encode path looks **not reachable** as currently used, but this was a grep-level check, not exhaustive — Unit 10/1 should confirm no `.save(format="heif"/"HEIF")` exists anywhere before closing. |
| pip-audit | `pytest` | 8.3.2 → 9.0.3 | PYSEC-2026-1845 | Low (local `/tmp/pytest-of-{user}` race, UNIX) | 13 (Test suite integrity) | **Not reachable from any deployed/web-facing path** — pytest only runs during local/CI test execution, never in the running application. Worth noting `pytest` is in `requirements.txt` (not a separate dev-requirements file), so it *is* installed in the production venv per this repo's structure, which is unnecessary attack surface/bloat even though not currently exploitable via any request path — a hardening note for Unit 1, not a vulnerability. |

---

## trivy fs — 13/13 HIGH-severity entries covered (0 CRITICAL, 0 secrets)

| Source | ID | Package | Severity | Assigned unit | Reachability |
|---|---|---|---|---|---|
| trivy | CVE-2026-25990, CVE-2026-40192, CVE-2026-42311, CVE-2026-54058, CVE-2026-54059, CVE-2026-54060, CVE-2026-55379, CVE-2026-55380, CVE-2026-59197, CVE-2026-59199, CVE-2026-59200, CVE-2026-59204, CVE-2026-59205 | `pillow` 10.4.0 (via `requirements.txt`) | HIGH ×13 | 10 (Account, primary), Foundation-B, 1 | Same underlying package and same reachable sinks as the pip-audit Pillow row above (`app/account/routes.py:61-62`, `app/display_images.py:47,49`) — trivy and pip-audit are flagging overlapping vulnerabilities in the same dependency under different ID namespaces (CVE vs. PYSEC). Not attempting a 1:1 CVE↔PYSEC cross-reference offline; treat both lists together as "Pillow needs an upgrade to ≥12.3.0 and the account/display-image upload path needs `formats=`/`MAX_IMAGE_PIXELS` hardening regardless of which specific ID is cited." |

## trivy config — 1 misconfiguration type, LOW severity

| Source | ID | Location | Severity | Assigned unit | Note |
|---|---|---|---|---|---|
| trivy config | `DS-0026` "No HEALTHCHECK defined" | `Dockerfile`, `deploy_backup_2026-07-14_142253/Dockerfile`, `docker_backup_2026-07-14_131012/Dockerfile` | LOW | 12 (Docker/IaC) | Confirmed by direct read of `trivy-config.json` (the raw file had a log preamble mixed into it, stripped for reading — a tooling artifact, not a repo issue). Not urgent, but Unit 12 already owns `Dockerfile` — a HEALTHCHECK could also improve the "is the app actually up" signal Compose/orchestration relies on, relevant to the PRE-004 Celery-worker-supervision question. |

---

## Summary: no unassigned findings

All 11 semgrep results, all 21 distinct pip-audit advisory IDs (28 raw
entries), all 13 trivy HIGH entries, and the 1 trivy misconfiguration type
are assigned above. No gaps.
