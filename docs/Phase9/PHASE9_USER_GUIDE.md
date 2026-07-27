# Phase 9 user guide

## Quản lý dự án

Use **Dashboard quản trị** to open the four canonical dashboards.  The System
Dashboard is the hub; each available dashboard-type card navigates to its first
resource in the user's permitted scope.  Customer, Project, and Contractor
selectors always navigate to a canonical resource URL.

Project Workspace presents cards for Tổng quan, Báo cáo ngày, Báo cáo xuyên
suốt, Vấn đề tồn đọng, Đối tác thi công, and Đối tác giải pháp.  Only functions
the current permission set allows are shown.

## Đối tác và cập nhật

Assignments can be added, edited, or removed from the corresponding Project
Workspace card. Removing an assignment sets it to `ENDED` and preserves its
history and related ProjectUpdate records. Start and end dates are optional;
an active or paused assignment cannot keep an end date.

All visible form dates use `DD/MM/YYYY`, for example `27/07/2026`. Internal
database values and API date keys remain ISO-formatted. Dashboard activity
lists show at most five newest records; the **Xem tất cả** link opens the
appropriate complete scoped list.
