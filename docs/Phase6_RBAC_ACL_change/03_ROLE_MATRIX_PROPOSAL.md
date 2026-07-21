# 03. Role matrix đề xuất

Các role dưới đây là proposal vận hành, chưa phải thay đổi DB/default grant.

| Role | Mục đích / ai dùng | Daily Reports | Project Documents | Company Media | Partner Management | Projects | Users/Roles Admin | Can Share | Can Archive/Delete | Ghi chú |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SUPER_ADMIN | 1–2 người kỹ thuật tin cậy | Full | Full | Full | Full | Full | Full | Có | Có | Bypass; không dùng daily operation. |
| ADMIN | Quản trị vận hành | Full theo grant | Full theo grant | Full theo grant | Full theo grant | Manage | Users manage; roles/system chỉ khi cấp riêng | Có | Có | Tách roles/system khỏi default nếu không cần. |
| VIEWER_ADMIN | Lãnh đạo/auditor cần xem rộng | Read | Read toàn cục, kể cả restricted | Read/download, kể cả restricted | Read | Read | Chỉ xem user; không roles manage | Không | Không | Không dùng thay EXECUTIVE_VIEWER nếu không muốn thấy admin data. |
| PROJECT_MANAGER | PM phụ trách project | View/create/edit theo assignment | Theo project + folder ACL | Không mặc định; ACL nếu cần | Không mặc định | View assigned | Không | Có khi được document ACL/RBAC | Hạn chế | Ví dụ PM dự án A. |
| REPORTER | Người lập báo cáo | View/create, edit own theo assignment | View/upload theo assignment + ACL | Không mặc định | Không | View assigned | Không | Không | Không | Ví dụ kỹ sư hiện trường. |
| MEDIA_CONTRIBUTOR | Nhân sự truyền thông | Không | Không | module/view/download/upload tối thiểu + album ACL | Không | Không | Không | Không | Không mặc định | Cấp `can_view/can_upload/can_download` theo album phụ trách; không share/delete. |
| DOCUMENT_MANAGER | Văn thư/QL hồ sơ | Read khi cần | folder create/upload/edit/share theo project/folder scope | Không | Không | View scoped | Không | Có ở folder được giao | Hạn chế | Không quản trị user/role; ACL theo folder/project. |
| PARTNER_MANAGER | Nhân sự quản lý đối tác | Không | Không | Không | CRUD partners/companies/fields/relations phù hợp | Không | Không | Không | Archive theo policy | Không tự có users/roles. |
| EXECUTIVE_VIEWER | Ban lãnh đạo chỉ xem nghiệp vụ | Read | Read | Read/download theo policy | Read | Read | Không | Không | Không | Dùng khi VIEWER_ADMIN xem quá rộng về admin. |
| BASIC_USER | User mặc định tối thiểu | Không mặc định | Không mặc định | Không mặc định | Không | Không | Không | Không | Không | Chỉ hữu ích khi có quy trình cấp quyền rõ; tránh role “rỗng” mơ hồ. |

## Chi tiết role nghiệp vụ đề xuất

### MEDIA_CONTRIBUTOR / Cộng tác viên media

Người phụ trách ảnh/video công ty hoặc agency nội bộ. Nên có `modules.company_media.access`, `company_media_albums.view`, `company_media_files.view`, `company_media_files.upload`, và download nếu chính sách cho phép. Không nên có create/rename/archive album, delete/archive media, share, users/roles. Cần album ACL `can_view`, `can_upload`, và tùy policy `can_download` cho từng album restricted. Ví dụ: nhân sự truyền thông tải ảnh sự kiện vào album “Flamingo Q3”.

### DOCUMENT_MANAGER / Quản lý hồ sơ tài liệu

Văn thư hoặc điều phối hồ sơ; quyền nền documents cần được scope theo project assignment hoặc một cơ chế scope được chốt trước. Chỉ cấp share cho folder chịu trách nhiệm, không cấp quản trị users/roles. Ví dụ: điều phối viên cập nhật folder hồ sơ nghiệm thu của dự án A.

### PARTNER_MANAGER / Quản lý đối tác

Nhóm procurement/BD quản lý đối tác, công ty, quan hệ và các field cần thiết. Không cần quyền report/project admin hay users/roles. Archive/delete chỉ cấp cho owner nghiệp vụ sau khi có quy trình review.

