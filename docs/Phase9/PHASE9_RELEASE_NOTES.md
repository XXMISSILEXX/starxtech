# Phase 9 release notes

Step 9.10 stabilizes Vietnamese Reports/Project Operations workflows, uses
modal confirmation for update deletion and contractor removal, and makes the
four canonical dashboards reachable from UI. Assignment removal sets `ENDED`
and preserves history. Daily Report V2 is unchanged.

Step 9.10A replaces the Dashboard hub selectors with canonical dashboard-type
cards, adds Project Workspace cards, limits dashboard activity lists to five,
and renames the `reports` module display to Quản lý dự án.

The same step adds the scoped Project Dashboard selector, editable assignment
lifecycle (including nullable start/end dates), native ISO form-date controls,
and recent ProjectUpdate lists limited to five on every canonical
dashboard. Assignment removal sets `ENDED`, keeps update history, and no
longer invents an end date when the user leaves it blank.

Step 9.10A supersedes the text-date component with native `type="date"`
controls across Reports, Project Operations, Issues, Admin/Storage, and
Partner forms. Form values are ISO (`YYYY-MM-DD`); `DD/MM/YYYY` is retained
only for read-only output. Daily Reports (legacy edit and V2 preflight/finalize)
and Project Updates reject future dates using `Asia/Ho_Chi_Minh`.

System Dashboard now exposes additive JSON analytics for customer project
share, active contractor coverage, project status distribution, and project
activity. Analytics are rendered only on System Dashboard and use aggregate
queries; Customer Dashboard's established payload remains compact and
compatible.

## Step 9.10B — Dashboard/UI polish

Project Update keeps the native ISO date input and now blocks a future date in
the browser before submit, with the same Vietnamese message as the server.
The server-side `Asia/Ho_Chi_Minh` validation remains the authoritative guard.

Reports navigation is ordered consistently on desktop and mobile as **Dashboard
quản trị**, **Hôm nay**, **Quản lý dự án & đối tác**, then **Cấu hình**. System
Dashboard tabs place **Phân tích hệ thống** directly after **Tổng quan**;
Customer Dashboard has no analytics tab and keeps its existing order.

The active-contractor chart now uses the API's active-project counts rather
than percentages. It is a vertical, per-contractor colour chart with Vietnamese
axis, tooltip, and text-summary labels. The analytics cards use constrained,
responsive chart containers to prevent overflow on desktop, tablet, and mobile.

## Step 9.10C — Project activity doughnuts and configuration context

System Dashboard project activity now renders two accessible doughnuts:
**Vấn đề tồn đọng theo dự án** and Daily Reports for the default 30-day period.
The API still exposes 7/30/90 periods; each activity adds `total_count` and
`percentages`. Empty datasets show a Vietnamese text state without creating a
Chart.js instance. Shared project IDs use the same deterministic colour in both
charts, and tooltips/summaries use Vietnamese count and percentage text.

Project, Customer, contractor, category, and membership configuration keep
their existing endpoints but permanently render inside **Quản lý dự án** with
**Cấu hình** active. `/reports/config` only lists project-domain entries;
roles/permissions stays in System Admin at `/admin/roles`.
