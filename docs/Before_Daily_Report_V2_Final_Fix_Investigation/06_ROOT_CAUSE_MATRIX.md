# Root cause matrix

| Issue | Runtime symptom | First failing step | Exact evidence | Source location | Confidence | Minimal fix area | Risk | Required test |
|---|---|---|---|---|---|---|---|---|
| duplicate-date infinite overlay | 409 leaves validating overlay and locked form | error cleanup | `failed=false`; `failed?.file.name` throws before failed render/unlock | `daily-report-create-v2.js:43-48` | Proven | `failSave` only | low | failing 409 terminal-state test |
| HEIC placeholder | original uploads, local preview unavailable | likely Blob Worker creation | bundle creates Blob Worker; CSP lacks `worker-src blob:`; exact browser error/file absent | bundle; `app/__init__.py:216-225`; controller `57-61` | Probable contributor | CSP capability only if DevTools confirms | medium/security | exact-file isolated harness + browser CSP capture |
| missing status icons | Processing/Critical visual glyph absent | unobserved runtime rendering | HEAD metadata and Bootstrap CSS selectors are complete; runtime identity/pseudo-elements unavailable | `ui.py:43-104`, `app.js:227-232` | Unknown | only after runtime capture | low-medium | computed `::before`, font and wrapper assertions |
