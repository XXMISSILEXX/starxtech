# Quyết định cuối cùng Phase 9

| Chủ đề | Quyết định đã khóa |
|---|---|
| Daily Report section status | Giữ `INFO/GOOD/PROCESSING/ATTENTION/CRITICAL` |
| Daily Report overall status | Giữ `UPDATED/GOOD/PROCESSING/ATTENTION/CRITICAL` |
| Health model | Không tạo |
| PersistentIssue | Phần riêng, không liên quan Daily Report |
| OpenIssue mới | Không tạo |
| Observation table | Không tạo |
| ReportCategory | Tái sử dụng model hiện tại, không tạo ProjectReportItem |
| Category lịch sử | Thêm snapshot tên/icon additive nếu source audit xác nhận an toàn |
| `is_required` | Enforce sau khi form và finalize cùng được cập nhật, không phá report cũ |
| ProjectUpdate | Một timeline riêng của project |
| Update contractor | `ProjectUpdate.contractor_assignment_id` nullable |
| Contractor domain | Model mới độc lập Partner/CRM |
| Contractor roles | `CONSTRUCTION`, `SOLUTION` |
| Hai role cùng project | Được phép |
| Assignment removal | Chuyển `ENDED`, giữ lịch sử |
| Customer/project/contractor delete | Archive |
| Custom roles | Dùng permission catalogue hiện tại |
| Multi-role | Không làm Phase 9 |
| Direct per-user permission | Không làm Phase 9 |
| Project scope | Tái sử dụng `ProjectUser` và helper hiện tại |
| Project chưa nộp | Không tính chart; hiển thị riêng và giảm submission rate |
| Contractor dashboard | Không quy kết section status/PersistentIssue cho contractor |
| Daily Report upload | Giữ nguyên toàn bộ V2/S3/HEIC/Celery |
| Project status create report | Mặc định chỉ `ACTIVE`; trạng thái khác read-only trong Phase 9 |
| Customer backfill | Nhóm `Khách hàng chưa phân loại`, vẫn hiển thị theo user project scope |
| ProjectUpdate attachments | Không làm trong Phase 9 MVP |
| Update approval workflow | Không làm |
