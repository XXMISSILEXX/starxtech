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
  assignment edit/remove lifecycle, nullable assignment dates, strict
  DD/MM/YYYY parsing, and recent ProjectUpdate lists on dashboards.
- Full authenticated browser verification of the new selector transition,
  edit/remove modal lifecycle, and resource-backed recent-update lists remains
  pending local data that is safe to exercise. It is intentionally not marked
  PASS in this evidence.

## Automated gate result (2026-07-27)

- `PYTHONWARNINGS=error pytest -q -ra`: **316 passed**.
- `python -m compileall -q app tests migrations`, JavaScript syntax checks,
  `npm test`, `pip check`, and `git diff --check`: PASS.
- `flask security-audit`: PASS after PostgreSQL was available.
- Migration current and head: `c4d2e980f617`.
