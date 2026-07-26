# Master Context cho Codex — Phase 9

## Sứ mệnh

Mở rộng chính phân hệ Reports hiện tại thành **Quản lý dự án & nhà thầu**, không dựng một hệ thống song song và không rewrite Daily Report V2.

## Hệ thống hiện tại phải tái sử dụng

- Flask/Jinja/Bootstrap/JavaScript.
- PostgreSQL, SQLAlchemy, Alembic.
- RBAC: `Role`, `Permission`, `RolePermission`, `User.can()`.
- Project scope: `ProjectUser` và helper hiện tại.
- `Project`, `ReportCategory`, `DailyReport`, `DailyReportSection`.
- `PersistentIssue` là Vấn đề tồn đọng riêng của project.
- `ReportAttachment`, `StorageObject`, upload sessions.
- Direct-to-S3/MinIO, presign, complete/HEAD verify.
- Celery derivatives.
- Client-only HEIC/JPG/PNG preview.
- AuditLog và CSRF/security headers.

## Domain mới tối thiểu

```text
Customer
  1 ─── N Project

ProjectContractor
  N ─── N Project qua ProjectContractorAssignment

Project
  1 ─── N ProjectUpdate

ProjectUpdate
  optional ─── ProjectContractorAssignment
```

## Ý nghĩa

- `Customer`: Geleximco, Handico, Taseco.
- `Project`: An Bình Homeland, XY Land.
- `ProjectContractor`: VTS, HT Hyundai, ZTSS.
- `ProjectContractorAssignment`: VTS là thi công/giải pháp tại một project cụ thể.
- `ProjectUpdate`: cập nhật xuyên suốt chung của project hoặc cập nhật riêng của assignment.

Ví dụ:

```text
ProjectUpdate.project_id = An Bình Homeland
ProjectUpdate.contractor_assignment_id = VTS / SOLUTION / An Bình Homeland
ProjectUpdate.update_type = HANDOVER
ProjectUpdate.title = Hoàn tất bàn giao 2 hạng mục
```

## Bất biến Daily Report

Giữ nguyên:

```text
DailyReportStatus:
UPDATED, GOOD, PROCESSING, ATTENTION, CRITICAL

SectionStatus:
INFO, GOOD, PROCESSING, ATTENTION, CRITICAL
```

Biểu đồ section phải dùng trực tiếp năm status này.

Không được thêm:

```text
health_status
ISSUE status mới
status mapping
observation table
auto PersistentIssue
Daily Report V3 transport
```

## PersistentIssue

- Là trang riêng của mỗi project.
- Người có quyền tự tạo/sửa/close/reopen theo lifecycle hiện tại.
- Không FK sang DailyReport, DailyReportSection, ReportCategory, contractor assignment.
- Không tự tạo từ section.
- Dashboard chỉ tổng hợp riêng theo status/severity/date; không gọi một domain mới là OpenIssue.

## Báo cáo xuyên suốt

- Là trang/timeline riêng của project.
- Dùng một bảng `ProjectUpdate`.
- Cập nhật chung: `contractor_assignment_id = NULL`.
- Cập nhật contractor: FK tới assignment cùng project.
- Không dùng attachment trong MVP Phase 9, trừ khi chủ hệ thống phê duyệt riêng.
- Không workflow duyệt.

## Partner module boundary

Không dùng hoặc FK tới:

- `Company`
- `CompanyDepartment`
- `Partner`
- `PartnerFieldDefinition`
- `PartnerFieldValue`
- `PartnerRelationship`

Không đặt route mới dưới `/partners` hoặc `/partner-companies`.

## Authorization

Mọi route mới phải qua:

```text
authenticated + active
AND modules.reports.access
AND action permission
AND project scope đối với tài nguyên thuộc project
```

Custom roles được tạo từ permission catalogue hiện có. Không kiểm tra role bằng chuỗi cho chức năng mới, ngoại trừ SUPER_ADMIN bypass theo chính sách hiện tại.

Một custom role có thể chỉ được:

- nộp Daily Report;
- quản lý contractor;
- thêm ProjectUpdate;
- xem dashboard;
- cấu hình category;
- hoặc kết hợp các quyền trên.

## Navigation Reports module

```text
Hôm nay
Quản lý dự án & nhà thầu
Dashboard quản trị
Cấu hình
```

Visibility dựa trên permission, direct URL vẫn phải backend-enforce.

## Dashboard

### Project/Customer/System

- Tỷ lệ nộp báo cáo.
- Project chưa nộp riêng.
- Pie section status hôm nay: 5 status.
- Stacked column 7/14/30 ngày: 5 status.
- Overall report status có thể là component riêng.
- PersistentIssue tổng hợp riêng.
- ProjectUpdate/contractor update timeline.

### Contractor

- Project/customer tham gia.
- Vai trò/status assignment.
- ProjectUpdate gắn assignment.
- Daily Report overall status chỉ là bối cảnh.
- Không dùng section status để đánh giá contractor.
- PersistentIssue của project chỉ là bối cảnh, không quy trách nhiệm.

## Phương pháp triển khai

- Additive migration.
- Nullable trước, backfill, validate rồi mới constraint.
- Archive/end, không hard-delete lịch sử.
- Không sửa tests cũ chỉ để xanh.
- Không broad mock, skip, xfail.
- Mỗi step targeted tests → full suite → runtime checks → commit.
