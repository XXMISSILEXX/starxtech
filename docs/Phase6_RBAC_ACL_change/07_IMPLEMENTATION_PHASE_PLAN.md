# 07. Roadmap implement sau audit

Phase 6.2 completes the three-layer boundary: canonical Global RBAC, capability-flag memberships, and inherited folder/album ACL. Phase 6.1A was audit-only.

## Phase 6.1B — Module switch và accessible modules

- Luôn hiện Đổi phân hệ cho authenticated user.
- Tạo helper read-only xác định accessible modules/resources, không chỉ `modules.*.access`.
- Chốt Company Media visibility theo role/ACL và policy Project Documents scoped access.
- Empty state rõ; route backend giữ enforcement; thêm sidebar/module-switch tests.

## Phase 6.1C — Role matrix/defaults

- Chốt matrix với owner vận hành.
- Nếu quyết định, thêm MEDIA_CONTRIBUTOR, DOCUMENT_MANAGER, PARTNER_MANAGER bằng migration/seed có kế hoạch tương thích; không phá role cũ.
- Chuẩn hóa default grants và review `sync-permissions --apply-defaults`; chỉ dùng reset defaults với approval.

## Phase 6.1D — Role Permissions UI polish

- Group rõ hơn, search/filter permissions, dangerous warning.
- Preset role templates nếu owner vận hành xác nhận.
- Preview effective permissions, nguồn grant và confirmation trước save.

## Phase 6.1E — RBAC/ACL hardening tests

- Matrix tests từng role/action/route.
- Module switch/sidebar visibility tests.
- Scoped ProjectUser, folder ancestor ACL, album ACL, inactive principal, add/update/remove ACL tests.
- Regression Project Documents, Company Media, reports, partners và authorization direct URLs.

## Tương lai

- Multi-role per user khi single role tạo nhiều exception lặp lại.
- User permission override có audit/reason/expiry khi thật sự cần.
- Audit log chuyên biệt cho mọi permission change; permission diff trước save; export/import được kiểm soát.
- Không thêm file-level ACL, ZIP bulk download hoặc storage namespace work chỉ vì roadmap RBAC này.

## Bugs/gaps ghi nhận, chưa sửa trong phase này

- Module switch/sidebar chưa đảm bảo discoverability cho user chỉ có scoped ACL.
- “Đổi phân hệ” hiện bị điều kiện bởi reports + partners access.
- Naming delete/archive và dangerous restore chưa hoàn toàn thống nhất.
- Single-role model cần review trước khi dùng global per-user exception.
