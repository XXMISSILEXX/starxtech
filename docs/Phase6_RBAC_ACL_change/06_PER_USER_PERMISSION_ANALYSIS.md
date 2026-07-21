# 06. Phân tích per-user permission

## Có nên xây full permission cho từng user ngay không?

**Không.** Direct per-user global permission không nên là mặc định hiện tại.

| Mô hình | Ưu điểm | Hạn chế | Khuyến nghị StarX |
| --- | --- | --- | --- |
| Single role/user | Dễ hiểu, onboard/offboard nhanh, audit đơn giản | Không diễn tả người kiêm nhiều nhiệm vụ | Giữ hiện tại khi tổ chức còn nhỏ. |
| Multiple roles/user | Ghép profile nghiệp vụ, ít exception hơn | Cần conflict/union policy, UI/audit mới | Bước tiếp theo hợp lý nếu role đơn không đủ. |
| Direct per-user permissions | Linh hoạt, xử lý ngoại lệ nhanh | Dễ loạn quyền, khó biết lý do, khó offboard và test | Chưa làm. |
| RBAC + scoped ACL | Role giữ baseline, ACL xử lý exception theo resource | Cần discovery/module policy rõ | Mô hình nên dùng hiện tại. |

Per-user permission có lợi ích linh hoạt và xử lý tình huống gấp, nhưng tạo “permission drift”: user đổi vị trí vẫn giữ các grant cũ, reviewer khó trả lời “vì sao người này có quyền”, test matrix tăng nhanh. ACL đã giải quyết phần lớn ngoại lệ đúng scope mà không biến thành global grant.

## Roadmap hợp lý

1. Giữ single-role và bổ sung role nghiệp vụ có tên rõ khi cần.
2. Dùng ProjectUser/folder ACL/album ACL cho phạm vi cụ thể.
3. Nếu nhiều người kiêm vai trò lâu dài, thiết kế multi-role per user với union allow, audit và UX giải thích nguồn quyền.
4. Chỉ sau đó mới cân nhắc `UserPermissionOverride`: allow/deny explicit, reason bắt buộc, creator, `expires_at`, audit, review và màn “effective permissions”.

