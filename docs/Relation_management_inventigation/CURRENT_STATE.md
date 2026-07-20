# Current state

## Model và vòng đời hiện có

| Entity | `is_active` | `deleted_at` | Hiện trạng |
| --- | --- | --- | --- |
| `Partner` | Có | Có (`SoftDeleteMixin`) | POST deactivate đặt cả hai trường. |
| `Company` | Có | Có (`SoftDeleteMixin`) | POST deactivate cũng tồn tại trong source. |
| `CompanyDepartment` | Có | Không | Deactivate chỉ đặt `is_active=False`. |
| `PartnerRelationship` | Có | Có (`SoftDeleteMixin`) | Delete route đặt inactive + deleted_at. |
| `PartnerFieldDefinition` | Có | Không | Deactivate bằng `is_active=False`. |
| `PartnerFieldCollection` | Có | Không | Deactivate bằng `is_active=False`. |
| `PartnerFieldValue` / `PartnerFieldCollectionItem` | Không | Không | Dữ liệu phụ, cascade khi owner bị hard-deleted ở ORM/DB. |

Không có `archived_at`, `is_deleted` hay route restore cho các entity trên.
`CompanyDepartment` và các metadata `is_active` không có timestamp archive,
do đó audit là nguồn lịch sử duy nhất hiện tại.

Quan hệ chính: Company có Departments và Partners; Partner tham chiếu Company
và Department; Relationship tham chiếu Company, Department, Partner và parent
Partner. FK Department/Relationship có một số `SET NULL`, còn quan hệ ORM của
Company/Partner chứa cascade delete-orphan nếu có hard delete bằng ORM.

## Routes hiện có

Tất cả Partner blueprints có `before_request` đòi `modules.partners.access`.
Các mutation khảo sát đều là POST hoặc POST branch của route GET/POST; template
mutation forms có CSRF token.

| Area | Current route | Permission | Hành vi |
| --- | --- | --- | --- |
| Partner | `GET /partners/`, detail/new/edit | `partners.view/create/edit` | `partners_query()` chỉ active + non-deleted. |
| Partner | `POST /partners/<id>/deactivate` | `partners.delete` | `is_active=False`, `deleted_at=now`, audit. |
| Company | `GET /partner-companies/`, detail/new/edit | `partner_companies.view/create/edit` | List/detail lookup `deleted_at IS NULL`. |
| Company | `POST /partner-companies/<id>/deactivate` | `partner_companies.delete` | Tồn tại, đặt inactive + deleted_at, audit. |
| Department | new/edit | `partner_companies.create/edit` | Parent cùng company, active; route mới đã chống cycle. |
| Department | `POST .../departments/<id>/delete` | `partner_companies.delete` | Chỉ inactive, audit. |
| Relationship | manage/edit | `partner_relations.manage` | Chỉ active Partner/Department/Relationship trong tree/list. |
| Relationship | `POST .../relationships/<id>/delete` | `partner_relations.delete` | Soft-delete + inactive, audit; message/UI nói “Xóa”. |
| Field/collection | deactivate routes | `*.manage` | `is_active=False`; có filter `active=1|0`. |

Không có route archive/restore chính thức. `partner_relations.edit_company` chỉ
redirect sang manage relations, không phải sửa Company. Không phát hiện mutation
GET trong các nhóm trên; các GET chỉ read hoặc redirect module/filter.

## UI và query hiện có

- Partner list không có status filter; `partners_query` mặc định ẩn inactive
  và soft-deleted. Detail 404 nếu Partner archived vì `_partner_or_404` lọc
  `deleted_at IS NULL`.
- Company list không lọc `is_active` nhưng lọc `deleted_at IS NULL`; vì
  deactivate đặt `deleted_at`, Company archived biến mất khỏi list/detail.
  Company detail hiện không render nút deactivate dù route tồn tại.
- Department list có filter active/inactive và nút “Vô hiệu hóa”; không restore.
- Relationship list/tree chỉ active/non-deleted; manage UI có nút “Xóa” POST
  + CSRF, dễ hiểu nhầm hard delete.
- Partner detail có nút “Vô hiệu hóa” POST + CSRF khi `partners.delete`; list
  không hiển thị button này. View-only guards sử dụng route-provided booleans
  hoặc `current_user.can`; không thấy hardcoded role để authorize Partner UI.
- Partner create form chỉ select Company non-deleted + active và Department
  active. Edit form cũng dùng cùng query, vì vậy một Partner cũ gắn Company
  inactive/soft-deleted có nguy cơ không thấy option hiện tại và validation chỉ
  kiểm tra Company tồn tại, không kiểm tra Company active.

## Permission, audit và test hiện có

Registry có `partners.view/create/edit/delete`, `partner_companies.view/create/
edit/delete`, `partner_relations.view/manage/delete`, module access và field
permissions. ADMIN được các quyền Partner mặc định; VIEWER_ADMIN được view +
module access; PROJECT_MANAGER/REPORTER không có Partner module mặc định;
SUPER_ADMIN bypass. `Permission`/`RolePermission` là canonical, routes dùng
`permission_required` và UI dùng `current_user.can`.

`AuditLog` lưu actor, action, entity type/id, old/new JSON, IP, user agent.
Partner/Company/Department/Relationship mutations audited, nhưng snapshot
Company/Department hiện không chứa tên riêng trong `new_values` ngoài field
snapshot; entity id/type cho phép truy vết nhưng cần enrich cho archive/restore.

Tests hiện có: module gate cho PM/REPORTER, manual view grant, create/edit
Company/Department/Partner/Relationship, Department tree validation,
relationship delete POST, field/collection deactivate, filters cơ bản. Chưa
thấy lifecycle test cho Partner/Company archive, restore, archived/all filter,
Company cascade behavior hoặc archived Company selection/edit behavior.
