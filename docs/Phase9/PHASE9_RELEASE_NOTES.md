# Phase 9 release notes

Step 9.10 stabilizes Vietnamese Reports/Project Operations workflows, uses
modal confirmation for update deletion and contractor removal, and makes the
four canonical dashboards reachable from UI. Assignment removal sets `ENDED`
and preserves history. Daily Report V2 is unchanged.

Step 9.10A replaces the Dashboard hub selectors with canonical dashboard-type
cards, adds Project Workspace cards, limits dashboard activity lists to five,
and renames the `reports` module display to Quản lý dự án.

The same step adds the scoped Project Dashboard selector, editable assignment
lifecycle (including nullable start/end dates), a DD/MM/YYYY form-date
component, and recent ProjectUpdate lists limited to five on every canonical
dashboard. Assignment removal sets `ENDED`, keeps update history, and no
longer invents an end date when the user leaves it blank.
