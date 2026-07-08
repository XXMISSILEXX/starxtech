# PROMPT 04 — Admin Users, Projects, Categories

---

Hãy xây các màn hình quản trị cho SUPER_ADMIN.

## A. User Management

Routes:

```text
GET  /admin/users
GET  /admin/users/create
POST /admin/users/create
GET  /admin/users/<id>/edit
POST /admin/users/<id>/edit
POST /admin/users/<id>/deactivate
POST /admin/users/<id>/activate
POST /admin/users/<id>/reset-password
```

Fields:

- full_name
- username
- email
- role
- is_active
- password khi tạo

Validation:

- username required unique
- email unique nếu nhập
- password tối thiểu 8 ký tự khi tạo
- role nằm trong SUPER_ADMIN, VIEWER_ADMIN, REPORTER

## B. Project Management

Routes:

```text
GET  /admin/projects
GET  /admin/projects/create
POST /admin/projects/create
GET  /admin/projects/<id>/edit
POST /admin/projects/<id>/edit
POST /admin/projects/<id>/archive
GET  /admin/projects/<id>/users
POST /admin/projects/<id>/users
```

Fields:

- code
- name
- description
- status
- start_date
- expected_end_date

Project assignment:

- Admin chọn nhiều REPORTER để gán vào project.
- Không gán VIEWER_ADMIN bắt buộc vì viewer xem toàn bộ.
- Cho phép remove reporter khỏi project.

## C. Report Categories

Routes:

```text
GET  /admin/projects/<project_id>/categories
POST /admin/projects/<project_id>/categories/create
POST /admin/categories/<id>/edit
POST /admin/categories/<id>/deactivate
POST /admin/categories/<id>/activate
```

Fields:

- name
- description
- icon
- sort_order
- is_active
- is_required

Validation:

- Không trùng name trong cùng project.
- Nếu category đã được dùng trong report, không xóa cứng, chỉ deactivate.

## UI

- Bootstrap table.
- Badge role/status.
- Nút create/edit/deactivate.
- Flash message rõ ràng.

## Audit

Ghi audit log cho:

- create/update/deactivate/activate user
- create/update/archive project
- assign/remove project user
- create/update/deactivate category

## Tests

- VIEWER_ADMIN không truy cập được admin write routes.
- REPORTER không truy cập được admin routes.
- SUPER_ADMIN tạo project/category/user thành công.

Sau khi xong, liệt kê file đã tạo/sửa và command chạy test.
