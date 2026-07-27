# Step 9.10 — Manual UI acceptance

## Completed public-page smoke (2026-07-27)

- Chrome headless loaded `/login` successfully at desktop, 390×844, and
  430×932 viewports.
- The 390×844 and 430×932 screenshots show the login form inside the viewport
  with no horizontal page overflow.

## Authenticated smoke — Step 9.10A

- Authenticated local login succeeded without changing account data.
- System Dashboard rendered four permission-aware Dashboard cards and the
  active module label was **Quản lý dự án**.
- At 390×844, 430×932, and 768×1024, the authenticated System Dashboard had
  `scrollWidth == clientWidth`; no horizontal overflow was detected.
- The local database contained no accessible Customer, Project, or Contractor
  records, so resource selector transitions, Workspace cards with project
  data, ProjectUpdate, and assignment mutation flows could not be exercised
  without creating user data. They remain covered by automated scope and UI
  tests. No credential is recorded in this evidence.

## Remaining Step 9.10A acceptance scope

- Automated coverage now verifies the scoped Project Dashboard selector,
  assignment edit/remove lifecycle, nullable assignment dates, native ISO date
  parsing, Daily Report/Project Update future-date rejection, recent dashboard
  lists, System analytics payloads, and constant query behaviour.
- Full authenticated browser verification of the new selector transition,
  edit/remove modal lifecycle, native picker/future-date feedback, analytics
  rendering, and resource-backed recent lists remains pending local data that
  is safe to exercise. It is intentionally not marked PASS in this evidence.

## Step 9.10B implementation evidence (2026-07-27)

- The Project Update form renders a native ISO date input with `max` from
  `Asia/Ho_Chi_Minh`. Its static guard blocks a value greater than `max`, adds
  the Bootstrap invalid state, and shows `Ngày cập nhật không được lớn hơn ngày
  hôm nay.` before submit. The service-layer future-date regression remains in
  place.
- Desktop sidebar and mobile offcanvas both render Reports navigation as
  Dashboard quản trị → Hôm nay → Quản lý dự án & đối tác → Cấu hình.
- System Dashboard renders tabs as Tổng quan → Phân tích hệ thống → Báo cáo →
  Vấn đề tồn đọng → Đối tác. The contractor chart reads coverage `values`, is
  vertical, has a per-column palette, hides the single-dataset legend, and
  uses the Vietnamese active-project axis and tooltip.
- The analytics grid is two columns at desktop widths. Dedicated card/canvas
  CSS constrains chart height to 280px desktop, 240px tablet, and 210px mobile;
  `maintainAspectRatio: false` is applied to analytics canvases.

No local Flask server or browser process was running during this pass, so the
new authenticated browser smoke at 390×844, 430×932, and 768×1024 was not
replayed. It remains pending rather than inferred from automated checks.

## Step 9.10B automated gate result (2026-07-27)

- `python -m compileall -q app tests migrations`, syntax checks for every
  JavaScript module, `npm test`, `pip check`, and `git diff --check`: PASS.
- `PYTHONWARNINGS=error pytest -q -ra`: **321 passed**, including the Project
  Update native-max/static-guard, desktop/mobile navigation order, System tab
  order, and vertical coverage chart contract tests.
- `flask security-audit`: BLOCKED by `FAIL database-checks: OperationalError`
  because no PostgreSQL service was available in this pass. This is recorded as
  a failed release gate, not a passing security result; no commit was made.

## Automated gate result (2026-07-27)

- `PYTHONWARNINGS=error pytest -q -ra`: **316 passed**.
- `python -m compileall -q app tests migrations`, JavaScript syntax checks,
  `npm test`, `pip check`, and `git diff --check`: PASS.
- `flask security-audit`: PASS after PostgreSQL was available.
- Migration current and head: `c4d2e980f617`.
