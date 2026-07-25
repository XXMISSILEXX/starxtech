# Status dropdowns

Actual enums (`app/models/enums.py:20-33`): overall = `UPDATED, GOOD, PROCESSING, ATTENTION, CRITICAL`; section = `INFO, GOOD, PROCESSING, ATTENTION, CRITICAL`. Shared values intentionally map identically; `UPDATED` versus `INFO` is the only set difference.

| value | label | icon class | tone | source result |
|---|---|---|---|---|
| UPDATED / INFO | Cập nhật / Thông tin | `bi bi-info-circle-fill` | info | complete |
| GOOD | Tốt | `bi bi-check-circle-fill` | good | complete |
| PROCESSING | Đang xử lý | `bi bi-arrow-repeat` | processing | complete |
| ATTENTION | Cần chú ý | `bi bi-exclamation-triangle-fill` | attention | complete |
| CRITICAL | Khẩn cấp | `bi bi-x-octagon-fill` | critical | complete |

The presentation map is built in `app/ui.py:86-104`, serialized into option `data-icon-class` in `reports/form.html:32,69,108`, rendered by `app.js:227-232`, and styled in `app.css:432-448`. Bootstrap Icons 1.11.3 is loaded from jsDelivr (`base.html:11`). A direct fetch of that exact CSS confirmed all five selectors, including `bi-arrow-repeat` and `bi-x-octagon-fill`, exist.

Consequently missing source metadata and missing icon-font selectors are ruled out for HEAD. Runtime pseudo-element values, font requests, CSP errors, and DOM classes could not be collected without the browser, so no proven cause for the reported missing two icons exists. A stale asset is plausible: CRITICAL changed from `bi-exclamation-octagon-fill` to `bi-x-octagon-fill` in `d2ed32f`; runtime identity is not yet proven.

Create owns only V2 sections; `app.js` suppresses legacy `initReportSections()` if V2 form is present (`app.js:1-3`). It still owns the shared custom-select renderer. Edit uses legacy direct-upload controller and the same custom-select renderer. Source contains an idempotency guard (`data-custom-ready`) and no duplicate wrapper owner, but runtime wrapper counts remain unverified.
