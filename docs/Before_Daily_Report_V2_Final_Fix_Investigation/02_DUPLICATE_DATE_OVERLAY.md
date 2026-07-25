# Duplicate-date overlay

## Proven failing path

The API correctly returns JSON 409 at `app/reports/create_v2.py:76-81`; it creates no upload session or S3 request before that branch. In the browser controller:

```text
submit event (daily-report-create-v2.js:73)
  -> save() (72), sets submitting=true and renderOverlay(validating)
  -> validate() (65), counters
  -> api(/preflight) (69)
  -> response.json(), then throw Error with code=duplicate_report_date
  -> catch -> failSave(error) (72)
  -> failSave() (40-50)
```

For a duplicate, `recoverable` is false at line 42, so `failed` is the boolean `false` at line 43. Line 46 evaluates `failed?.file.name`. Optional chaining only covers `failed`; it evaluates `.name` on `undefined` and throws `TypeError: Cannot read properties of undefined (reading 'name')`.

Therefore `renderOverlay("failed")`, `finishSave()`, focus mapping, `submitting=false`, and unlock never run. The immediately preceding state is `validating`; its overlay is visible, `aria-busy=true`, spinner visible, and `setLocked(true)` set `window.onbeforeunload` and disables controls (lines 19-37). This exactly explains the observed permanent overlay after 409.

The error JSON is parsed once, response `ok` is false, field errors are attached to the Error, and no upload Promise is started. No evidence of double JSON parsing, `Promise.all`, AbortController, duplicate save listener, or a later overlay render is present in the Create source.

State transitions: `idle -> validating -> failed` is intended; actual 409 path is `idle -> validating -> failSave throws -> stuck validating`. Upload states are `creating_session -> presigning -> uploading -> verifying -> finalizing -> succeeded`; cancellation renders `cancelled`; generic errors intend `failed`.

Regression range: the expression is introduced in checkpoint `d2ed32f` (line 46). Preflight itself was introduced by `5edab10`; it is the first path that sends duplicate-date errors through this new handler.
