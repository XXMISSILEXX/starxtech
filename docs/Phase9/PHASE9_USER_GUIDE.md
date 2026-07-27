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

All editable dates use the browser's native date control and submit ISO values
(`YYYY-MM-DD`). Read-only dates remain formatted as `DD/MM/YYYY`, for example
`27/07/2026`. A Daily Report or Project Update cannot be dated after today in
`Asia/Ho_Chi_Minh`; the Project Update form stops a future date before submit
and the server validates it again. Existing historical records are never
changed by this rule. Dashboard activity lists show at most five newest records, with the
consistent actions **Xem tất cả báo cáo xuyên suốt**, **Xem tất cả báo cáo
ngày**, and **Xem tất cả vấn đề tồn đọng**.

## System Dashboard analytics

Reports navigation begins with **Dashboard quản trị**. The System Dashboard
tabs are **Tổng quan**, **Phân tích hệ thống**, **Báo cáo**, **Vấn đề tồn
đọng**, and **Đối tác**.

The System Dashboard has an additional analytics tab for project share by
customer (including **Chưa phân loại**), native project status distribution,
active contractor project counts, **Vấn đề tồn đọng theo dự án**, and Daily
Reports by project for 7, 30, and 90 days. The displayed Daily Report activity
uses 30 days by default. The two project activity doughnuts show a text summary
under the chart and a Vietnamese empty state when their activity total is zero.
The contractor chart's vertical axis is **Số dự án
đang hoạt động**; each contractor gets a distinct column colour. It counts
active projects in the effective scope, so a project may be included for more
than one active contractor.

## Cấu hình dự án

**Cấu hình** contains only Dự án, Khách hàng, and Nhà thầu/Đối tác dự án that
your permissions allow. Hạng mục báo cáo and Phân công project are actions
inside a project. These pages always remain in the Quản lý dự án sidebar, even
when opened from a saved `/admin/projects...`, Customer, or contractor URL.
Vai trò & phân quyền is global System Admin functionality and is available at
`/admin/roles`.

## Giới hạn release acceptance

Các tính năng trên vẫn cần được xác nhận bằng Chrome desktop và iPhone Safari
trên môi trường được phê duyệt, đặc biệt là upload JPG/HEIC trực tiếp, Celery
derivatives, lịch sử assignment đã kết thúc và dashboard có dữ liệu thực. Xem
`PHASE9_ACCEPTANCE.md` để biết những mục chưa có tester ký xác nhận.
