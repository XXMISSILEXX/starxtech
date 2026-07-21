# 02. Khuyến nghị RBAC + ACL thực tế

## Quyết định đề xuất

StarX nên tiếp tục dùng **RBAC + scoped ACL hybrid**:

1. RBAC theo role là quyền nền và quyền vào phân hệ/action.
2. ACL chỉ mở phạm vi trên folder, album hoặc project cụ thể.
3. Không triển khai direct per-user global permissions mặc định.
4. Nếu có ngoại lệ thật sự, ưu tiên ACL; nếu người dùng kiêm nhiều nhiệm vụ lâu dài, ưu tiên multi-role trong phase sau trước khi tạo global override.

## RBAC và ACL trong StarX

**RBAC** trả lời “với chức vụ này, người đó thường làm được gì?” Ví dụ PARTNER_MANAGER được quản lý đối tác; MEDIA_CONTRIBUTOR có các code Company Media cơ bản.

**ACL** trả lời “trong số resource đó, người/role này được làm gì tại đây?” Ví dụ share album Flamingo cho Trần Đức An; role media contributor có upload ở album truyền thông Q3; nhóm pháp lý xem folder pháp lý một dự án.

ACL không thay RBAC: `can_upload` album không cấp `company_media_files.upload`; share folder không cấp `project_document_files.download` nếu RBAC thiếu. Đây là thiết kế an toàn và dễ audit.

## Khi dùng role, khi dùng ACL

| Dùng role khi | Dùng ACL khi |
| --- | --- |
| Nhiệm vụ ổn định, lặp lại cho nhiều người/resource. | Ngoại lệ theo dự án/folder/album hoặc thời hạn ngắn. |
| Cần module access hay quyền quản trị chung. | Cần chia sẻ một resource restricted cụ thể. |
| Có owner vận hành chịu trách nhiệm cấp/thu hồi. | Cần đóng quyền ngay khi dự án/chiến dịch kết thúc. |

Không tạo role mới chỉ để mở một album hay folder. Không dùng ACL để cấp users/roles/system settings, quản trị toàn cục, hoặc chức năng thường xuyên của một chức vụ.

## Khi nên/không nên thêm role

Tạo role nếu có tối thiểu một nhóm người dùng ổn định, permission profile lặp lại, owner nghiệp vụ và ví dụ onboarding/offboarding rõ. Không tạo role khi khác biệt chỉ là một project, album, folder hoặc một lần chia sẻ; dùng ACL khi đó.

Role mới trước mắt là **đề xuất**, không được seed trong phase 6.1A: MEDIA_CONTRIBUTOR, DOCUMENT_MANAGER, PARTNER_MANAGER; EXECUTIVE_VIEWER và BASIC_USER chỉ thêm khi tổ chức thực sự có nhóm phù hợp.

## Nguyên tắc vận hành

- Role biểu diễn chức vụ/nhiệm vụ dài hạn; ACL biểu diễn chia sẻ resource cụ thể.
- Chỉ role quản trị được giữ dangerous permissions: archive/delete, restore, share, users.manage, roles.manage, system settings.
- Cấp quyền tối thiểu: module access + action cần thiết, sau đó ACL đúng resource.
- ACL có thể mở quyền vào resource đã share, nhưng không bypass action RBAC.
- Thu hồi ACL khi kết thúc dự án/cộng tác; review role định kỳ khi thay đổi vị trí.
- Không dùng SUPER_ADMIN cho công việc thường ngày.

