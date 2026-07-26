# Phase 9 Complete Execution Package

## Mục tiêu

Bộ tài liệu và prompt này dùng để biến phân hệ **Báo cáo hàng ngày** của StarX thành **Quản lý dự án & nhà thầu**, theo hướng additive, dễ hiểu, ít rủi ro và giữ nguyên các nền tảng đã ổn định ở Phase 8.

Repository mục tiêu:

```text
~/Documents/Construction_Management
```

Baseline audit tham chiếu:

- Nhánh audit: `rewrite/daily-report-create-v2`
- Commit audit: `b45281086d72e950ef62a41dc21024e904198296`
- Migration audit: `20260725_0026`
- Audit nằm trong `REFERENCE/Pre_Phase9_Audit/`

Trước mỗi bước, Codex phải xác minh branch, HEAD, migration và working tree thực tế; không được giả định baseline vẫn còn nguyên.

## Quyết định nghiệp vụ đã khóa

1. Giữ nguyên status Daily Report hiện tại.
2. Không tạo `health_status`, `derived_health`, status mapping hoặc Daily Report V3.
3. `PersistentIssue` là phần **Vấn đề tồn đọng** riêng của dự án, không liên kết và không tự sinh từ Daily Report.
4. Không tạo khái niệm OpenIssue mới và không tạo observation table.
5. Báo cáo xuyên suốt dự án là timeline `ProjectUpdate`, tách biệt Daily Report và PersistentIssue.
6. `ProjectUpdate` có thể gắn optional vào một `ProjectContractorAssignment`, cho phép cập nhật riêng cho từng đối tác thi công/giải pháp ở từng dự án.
7. Module Partner/CRM hiện tại hoàn toàn độc lập, không dùng `Company`, `Partner` hoặc `PartnerRelationship` cho Phase 9.
8. Giữ và mở rộng `Project`, `ProjectUser`, `ReportCategory`, `DailyReport`, `DailyReportSection`, `PersistentIssue`, RBAC, S3 và Celery hiện tại.
9. Không tạo `ProjectReportItem`; `ReportCategory` đã là cấu hình đầu mục theo project.
10. Custom role là cách cấp quyền theo từng phần; không hard-code chức năng mới theo tên role.
11. Một user tiếp tục có một role. Không làm multi-role hoặc direct per-user permissions trong Phase 9.
12. Customer, ProjectContractor và assignment đã có lịch sử dùng archive/end, không hard-delete.
13. Một contractor được phép có cả vai trò `CONSTRUCTION` và `SOLUTION` trong cùng project.
14. Biểu đồ Daily Report dùng trực tiếp năm section status hiện có: `INFO`, `GOOD`, `PROCESSING`, `ATTENTION`, `CRITICAL`.
15. Project chưa nộp báo cáo không được tính vào biểu đồ trạng thái; phải hiển thị riêng và làm giảm tỷ lệ nộp.

## Cách dùng gói

Khuyến nghị giải nén vào repo:

```bash
cd ~/Documents/Construction_Management
mkdir -p docs
unzip /path/to/Phase_9_Complete_Execution_Package.zip -d docs/
```

Sau đó đọc:

1. `MASTER_CONTEXT.md`
2. `FINAL_DECISIONS.md`
3. `TARGET_ARCHITECTURE.md`
4. `TARGET_RBAC_AND_CUSTOM_ROLES.md`
5. `PHASE9_EXECUTION_MAP.md`
6. Chạy lần lượt prompt trong `PROMPTS/`.

Không đưa toàn bộ prompt cho Codex cùng lúc. Thực hiện từng bước, chỉ sang prompt tiếp theo khi gate của bước hiện tại đạt và commit đã được tạo.

## Trình tự thực hiện

| Bước | Prompt | Kết quả chính |
|---|---|---|
| 9.0 | `00_PHASE9_0_LOCK_BASELINE.md` | Khóa scope, baseline, decisions |
| 9.1 | `01_PHASE9_1_RBAC_CUSTOM_ROLES.md` | Permission catalogue và custom role |
| 9.2 | `02_PHASE9_2_CUSTOMERS_PROJECTS.md` | Customer và Project grouping |
| 9.3 | `03_PHASE9_3_CONTRACTORS_ASSIGNMENTS.md` | Contractor và assignment |
| 9.4 | `04_PHASE9_4_PROJECT_UPDATES.md` | Báo cáo xuyên suốt, cập nhật từng contractor |
| 9.5 | `05_PHASE9_5_PROJECT_OPERATIONS_UI.md` | UI quản lý dự án & nhà thầu |
| 9.6 | `06_PHASE9_6_TODAY_NAV_CONFIG_REPORTS.md` | Hôm nay, navigation, cấu hình, category safety |
| 9.7 | `07_PHASE9_7_DASHBOARD_CORE_PROJECT.md` | Dashboard core và Project Dashboard |
| 9.8 | `08_PHASE9_8_CUSTOMER_SYSTEM_DASHBOARDS.md` | Customer/System Dashboard |
| 9.9 | `09_PHASE9_9_CONTRACTOR_DASHBOARD.md` | Contractor Dashboard |
| 9.10 | `10_PHASE9_10_STABILIZATION_RELEASE.md` | Stabilization, rehearsal, release |

## Branch/commit mặc định

Dùng một branch tích hợp để lịch sử dễ đọc:

```bash
git switch <phase-8-stable-branch>
git pull --ff-only   # chỉ khi branch có remote và user chủ động muốn pull
git switch -c feature/phase-9-project-contractor-management
```

Mỗi bước tạo đúng một commit chính sau khi gate đạt. Không commit tự động nếu test còn đỏ.

## Nội dung gói

- Tài liệu kiến trúc và quyết định.
- Prompt copy-paste cho Codex theo từng bước.
- Runbook môi trường, migration, test và commit.
- Script gate tham khảo.
- Checklist manual acceptance và release.
- Bản audit Phase 8/Pre-Phase 9 để đối chiếu source.
