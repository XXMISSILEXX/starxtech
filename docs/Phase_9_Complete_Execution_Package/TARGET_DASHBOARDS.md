# Dashboard Phase 9

## Dữ liệu Daily Report

### Pie hôm nay

Đếm `DailyReportSection.status` của report đúng selected date:

```text
INFO
GOOD
PROCESSING
ATTENTION
CRITICAL
```

Không dùng health mapping.

### Stacked column

Mỗi ngày gồm năm series trên. Có 7/14/30 ngày và có thể toggle count/percentage.

### Submission coverage

Project population là project `ACTIVE` trong effective scope. Project chưa nộp:

- không nằm trong status chart;
- nằm trong missing list;
- giảm submission rate;
- coverage hiển thị dạng `4/6 dự án`.

## DashboardScope

```text
SYSTEM
CUSTOMER
PROJECT
CONTRACTOR
```

Effective project IDs luôn là giao của selected scope và authorization scope.

## Project Dashboard

Cards:

- project status;
- report hôm nay;
- thi công/giải pháp active;
- tổng vấn đề tồn đọng theo policy hiện tại;
- ProjectUpdate gần nhất.

Charts:

- section status pie hôm nay;
- stacked status trend;
- overall report status history nếu hữu ích;
- PersistentIssue by status/severity.

Lists:

- recent Daily Reports;
- recent ProjectUpdates;
- PersistentIssues;
- contractor assignments.

## Customer Dashboard

Cards:

- active project count;
- submission rate;
- missing reports;
- distinct contractor count;
- PersistentIssue count.

Charts:

- section status pie của project đã nộp;
- stacked trend;
- submission by project;
- overall status by project;
- PersistentIssue by project/status/severity;
- contractor by role.

Lists:

- project child rows;
- missing reports;
- recent ProjectUpdates.

## System Dashboard

Tương tự Customer nhưng aggregate toàn effective scope. Dùng tabs để tránh quá nhiều biểu đồ:

```text
Tổng quan
Báo cáo
Vấn đề tồn đọng
Nhà thầu
```

## Contractor Dashboard

Không vẽ Daily Report section distribution như hiệu suất contractor.

Cards:

- project count;
- customer count;
- construction assignments;
- solution assignments;
- active assignments;
- latest assigned ProjectUpdate.

Charts/list:

- project by customer;
- assignments by role/status;
- timeline ProjectUpdate gắn assignment;
- project overall report status chỉ là context.

PersistentIssue của project nếu hiển thị phải có nhãn “Bối cảnh dự án”, không ghi là trách nhiệm contractor.

## Performance

- Index date/project/status.
- Aggregate SQL, không Python N+1.
- Query count test cho dashboard.
- Dataset test đủ nhiều Customer/Project/Report/Section/Contractor.
