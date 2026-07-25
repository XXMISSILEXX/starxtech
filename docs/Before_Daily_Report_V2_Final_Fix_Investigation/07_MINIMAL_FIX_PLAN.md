# Minimal fix plan (do not implement)

1. Duplicate overlay: change only the unsafe filename access in `failSave` (`app/static/js/daily-report-create-v2.js`) so the no-file duplicate path reaches the existing failed rendering and cleanup. Do not change endpoint/API/service/template/CSS. Keep and pass the 409 characterization test; manually submit a real duplicate and verify failed overlay, unlocked form, date focus, no S3 call.

2. HEIC: first run the exact-file harness and browser capture. If the console proves Blob Worker CSP blocking, make the smallest reviewed CSP capability adjustment in `app/__init__.py`; do not replace `heic-to`, alter upload, or weaken unrelated directives. Test a HEIC and a JPEG, verify original File identity and no new CSP violation. Roll back the single CSP directive if it causes security review failure.

3. Statuses: do not change icons/CSS until runtime identity and computed styles show the failed layer. If stale assets are proven, deploy/restart/cache-bust operationally rather than changing presentation code. If a mapping is proven absent in live HTML, change only that metadata serialization path and add Create/Edit DOM tests. Do not modify enum values.
