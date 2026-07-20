# RBAC permission recommendation

## Options

| Option | Archive | Restore | Nhận xét |
| --- | --- | --- | --- |
| A | `*.delete` | `*.edit` | Ít code nhưng restore là hành động đặc quyền bị lẫn với edit. |
| B | `*.delete` | `*.restore` mới | Rõ ràng, giữ compatibility với delete hiện hữu và audit tốt. |
| C | `*.archive` mới | `*.restore` mới | Ngữ nghĩa tốt nhất nhưng tăng migration registry/UI, không cần thiết ngay. |

Khuyến nghị **Option B**: giữ `partners.delete`, `partner_companies.delete`,
`partner_relations.delete` cho archive để không phá policy hiện có; thêm quyền
restore rõ ràng. Với Department, dùng `partner_companies.restore` nếu route
vẫn ở Company resource, hoặc thêm `partner_departments.restore` nếu tách
resource/permission ở phase mô hình hóa. Chọn một hướng duy nhất trước khi
sync registry; ưu tiên `partner_departments.restore` cho least privilege dài
hạn vì department mutation hiện đang dùng Company permission.

## Permission đề xuất

```
partners.restore
partner_companies.restore
partner_departments.restore       # nếu Department có lifecycle restore public
partner_relations.restore         # chuẩn bị cho audit/admin restore
```

`*.delete` UI label sẽ là “Lưu trữ”, không phải hard delete. `*.restore` là
dangerous permission và không thay cho `*.edit`.

## Default grants khuyến nghị

| Role | View archived | Archive | Restore |
| --- | --- | --- | --- |
| SUPER_ADMIN | Có, bypass | Có | Có |
| ADMIN | Có qua `*.view` | Có qua existing `*.delete` | Có qua `*.restore` |
| VIEWER_ADMIN | Có qua view | Không | Không |
| PROJECT_MANAGER | Không có module Partner mặc định | Không | Không |
| REPORTER | Không có module Partner mặc định | Không | Không |

Nếu một custom Partner operator được thêm sau này, cấp `view/create/edit/delete`
nhưng cấp restore riêng chỉ khi được phê duyệt. Module guard
`modules.partners.access` vẫn bắt buộc trước mọi permission resource.
