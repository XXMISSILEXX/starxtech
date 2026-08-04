# Phase 12 — Mô đun "Quản lý tiến độ thi công"

Tài liệu này mô tả một mô đun mới ở **phạm vi một dự án**, nằm cạnh các mô đun
hiện có trong không gian dự án (Tổng quan, Báo cáo ngày, Báo cáo xuyên suốt,
Vấn đề tồn đọng, Đối tác thi công, Đối tác giải pháp).

Đọc `CLAUDE.md`, `AGENTS.md`, `README.md` trước khi bắt đầu. Tài liệu này là
đặc tả nghiệp vụ và điểm tích hợp, không thay thế các quy tắc chung của repo.

Kế hoạch thi hành từng bước: `PHASE12_EXECUTION_PLAN.md` cùng thư mục.

Trạng thái: **chưa triển khai**. Đây là brief cho phase tiếp theo.

---

## 1. Mục tiêu

Hiện tại tiến độ thi công được theo dõi bằng file Excel ngoài hệ thống: mỗi
khu vực (Tầng hầm, Tòa C1…) có nhiều hạng mục thi công (Cắt đục tường & đặt
ống âm, Đi ống nổi, Chôn đế âm…), mỗi hạng mục có đơn vị riêng (mét, căn hộ,
cái), khối lượng kế hoạch và khối lượng đã thực hiện. Người dùng cập nhật tay
và tự tính phần trăm.

Mô đun này đưa toàn bộ việc đó vào hệ thống, với ba mục tiêu:

1. Khai báo được cấu trúc tiến độ nhiều cấp cho từng dự án.
2. Ghi nhận khối lượng thực hiện theo từng ngày, có tác giả và có thể truy vết.
3. Tự động tính phần trăm hoàn thành ở cả ba cấp và vẽ biểu đồ, để số trên
   dashboard luôn khớp với số người dùng đã nhập.

Không nhằm thay thế Báo cáo ngày. Báo cáo ngày là bản mô tả công việc bằng
văn bản kèm ảnh; mô đun này là số liệu định lượng có cấu trúc. Hai mô đun độc
lập nhau ở phase này (xem mục 10).

---

## 2. Khái niệm

Bốn cấp, đặt tên trong code theo tiếng Anh, hiển thị tiếng Việt:

| Cấp | Code | Nhãn hiển thị | Ví dụ |
|---|---|---|---|
| 1 | `ProgressType` | Loại tiến độ | Tiến độ theo khối lượng / Tiến độ theo dự toán |
| 2 | `ProgressGroup` | Khu vực (đầu mục lớn) | Tầng hầm, Tòa C1, Bãi đỗ xe |
| 3 | `ProgressItem` | Hạng mục (đầu mục nhỏ) | Đi ống nổi, Chôn đế âm (hộp âm tường) |
| 4 | `ProgressEntry` | Phiếu cập nhật | 12 cái, ngày 30/07/2026 |

Quy tắc bất biến của mô đun: **chỉ `ProgressItem` mang số kế hoạch, và chỉ
`ProgressEntry` mang số thực hiện phát sinh.** Mọi con số ở cấp khu vực và cấp
loại đều là giá trị dẫn xuất, không có ô nhập, không lưu như dữ liệu gốc.

`ProgressType.value_mode` quyết định cách cộng lên:

- `quantity` — các hạng mục có đơn vị khác nhau (mét, cái, căn hộ). **Không
  được cộng khối lượng thô.** Cấp trên lấy trung bình phần trăm.
- `money` — đơn vị luôn là VNĐ. Cấp trên cộng dồn tiền rồi mới chia ra phần
  trăm. "Tiến độ theo dự toán" chỉ là một `ProgressType` có `value_mode =
  money`; không viết mô đun riêng cho nó.

---

## 3. Mô hình dữ liệu

Đặt models trong `app/models/progress.py`, re-export qua
`app/models/__init__.py` (import từ `app.models`, không import từ submodule).
Bám sát style của `app/models/project_update.py`: khóa chính
`db.BigInteger().with_variant(db.Integer(), "sqlite")`, FK `ondelete="RESTRICT"`,
`TimestampMixin`, index đặt tên `ix_<table>_<cols>`, constraint `uq_`/`ck_`.

Cả bốn bảng đều mang `project_id`. Đây là chủ ý: mọi truy vấn scope được theo
dự án ngay từ câu query đầu tiên, không phải join ngược lên cha. `project_id`
luôn lấy từ bản ghi cha, **không bao giờ lấy từ dữ liệu client gửi lên**.

### `progress_types`

| Cột | Kiểu | Ghi chú |
|---|---|---|
| `id` | BigInteger PK | |
| `project_id` | FK `projects.id` RESTRICT, not null, index | |
| `name` | String(200) not null | unique cùng `project_id` |
| `value_mode` | String(20) not null default `quantity` | CheckConstraint `IN ('quantity','money')` |
| `description` | Text null | |
| `display_order` | Integer not null default 0 | |
| `is_active` | Boolean not null default true | ẩn thay vì xóa |
| `created_by_id` | FK `users.id` not null | |
| `updated_by_id` | FK `users.id` null | |
| `created_at` / `updated_at` | TimestampMixin | |

Constraint: `uq_progress_types_project_name (project_id, name)`.

### `progress_groups`

`id`, `project_id` (FK, index), `progress_type_id` (FK RESTRICT, index),
`name` String(200), `note` Text null, `display_order`, `is_active`,
`created_by_id`, `updated_by_id`, timestamps.

Constraint: `uq_progress_groups_type_name (progress_type_id, name)`.

### `progress_items`

| Cột | Kiểu | Ghi chú |
|---|---|---|
| `id` | BigInteger PK | |
| `project_id` | FK, index | |
| `progress_group_id` | FK RESTRICT, index | |
| `name` | String(300) not null | unique trong group |
| `unit` | String(30) not null | "mét", "cái", "căn hộ", "m²", "VNĐ" |
| `planned_quantity` | Numeric(18,3) not null default 0 | khối lượng kế hoạch tổng |
| `opening_quantity` | Numeric(18,3) not null default 0 | khối lượng đã làm trước khi lên hệ thống |
| `completed_quantity` | Numeric(18,3) not null default 0 | **cache** = `opening_quantity` + Σ phiếu |
| `assignee_user_id` | FK `users.id` null | người phụ trách mặc định |
| `note` | Text null | ví dụ "02 đế / 1 căn hộ" |
| `display_order`, `is_active` | | |
| `created_by_id`, `updated_by_id`, timestamps | | |

Constraint: `uq_progress_items_group_name (progress_group_id, name)`.
CheckConstraint: `planned_quantity >= 0`, `opening_quantity >= 0`.

### `progress_entries`

| Cột | Kiểu | Ghi chú |
|---|---|---|
| `id` | BigInteger PK | |
| `project_id` | FK, index | |
| `progress_item_id` | FK RESTRICT, index | |
| `report_date` | Date not null | ngày thực hiện |
| `quantity` | Numeric(18,3) not null | khối lượng phát sinh trong ngày |
| `note` | Text null | vướng mắc / ghi chú của ngày đó |
| `created_by_id` | FK not null | |
| `updated_by_id` | FK null | |
| `created_at` / `updated_at` | | phân biệt "làm ngày 12 nhập ngày 30" |

Constraints:

- `uq_progress_entries_item_date (progress_item_id, report_date)` — **đây là
  chỗ thực thi quy tắc một phiếu một ngày. Bắt buộc ở tầng database**, không
  chỉ kiểm ở form.
- `ck_progress_entries_quantity_positive`: `quantity > 0`.
- Index `ix_progress_entries_project_date (project_id, report_date)` cho
  dashboard.

Dùng `Numeric`, **không dùng `Float`**: cộng dồn float sẽ ra `77.99999` sau
vài trăm phiếu.

### Thay đổi bảng có sẵn

`project_users` cần 4 cột boolean mới (xem mục 6). Không thay đổi bảng nào khác.

---

## 4. Quy tắc tính phần trăm

Đặt trong `app/construction_progress/services.py` dưới dạng **hàm thuần**, tách
khỏi route, để test độc lập được.

```
% hạng mục  = completed_quantity / planned_quantity × 100      (planned > 0)

value_mode = quantity:
  % khu vực = trung bình % của các hạng mục hợp lệ
  % loại    = trung bình % của các khu vực hợp lệ

value_mode = money:
  % khu vực = Σ completed / Σ planned × 100
  % loại    = Σ completed / Σ planned × 100
```

Quy tắc trung bình ở `quantity` là chủ ý và khớp với cách người dùng đang làm
trên Excel ("% khu vực = trung bình % các hạng mục, không cộng dồn mét với cái
vì khác đơn vị").

Ba trường hợp biên, phải xử lý đúng vì Excel hiện đang im lặng bỏ qua:

1. **`planned_quantity = 0` hoặc chưa khai báo** → hạng mục bị **loại khỏi phép
   trung bình**, hiển thị `—` kèm nhãn "chưa có kế hoạch". Không tính là 0%:
   một hạng mục khai thiếu sẽ kéo tụt tiến độ toàn dự án một cách sai lệch.
2. **Khu vực không có hạng mục hợp lệ nào** → cũng loại khỏi trung bình cấp
   loại, hiển thị "chưa cấu hình".
3. **Vượt kế hoạch** (`completed > planned`) → **cho phép lưu**, giữ số thật
   trong DB, thanh tiến độ hiển thị cap ở 100%, kèm badge "vượt kế hoạch
   +N%". Chặn cứng sẽ khiến người dùng nhập số sai cho qua.

Làm tròn: giữ nguyên `Decimal` khi tính, chỉ làm tròn khi hiển thị (số nguyên
phần trăm ở bảng, một chữ số thập phân ở chỗ cần chi tiết). Không làm tròn ở
tầng trung gian rồi cộng tiếp.

Chỉ cache `progress_items.completed_quantity`. Phần trăm của khu vực và loại
**tính khi đọc**, không cache: mỗi dự án chỉ vài chục hạng mục, và cache phần
trăm nhiều cấp là nguồn sai số kinh điển.

### Cập nhật lại `completed_quantity`

Khi tạo, sửa, hoặc xóa phiếu, tính lại **trong cùng transaction** với thay đổi
phiếu, bằng cách cộng lại từ đầu:

```
completed_quantity = opening_quantity + SELECT COALESCE(SUM(quantity), 0)
                                        FROM progress_entries
                                        WHERE progress_item_id = :id
```

**Không dùng `completed_quantity += quantity`.** Cộng dồn kiểu đó sẽ sai khi
request bị retry, khi người dùng bấm Lưu hai lần, hoặc khi hai người sửa cùng
lúc. Cùng lớp vấn đề đã xử lý ở commit `DB_RACE_VERIFY_IDEMPOTENT`; theo đúng
hướng đó. Lấy `SELECT ... FOR UPDATE` trên hàng `progress_items` trước khi tính
lại nếu chạy trên PostgreSQL.

Sửa `opening_quantity` hoặc `planned_quantity` cũng phải tính lại và **ghi
audit**, vì nó làm phần trăm của cả dự án nhảy mà không có phiếu nào thay đổi.

---

## 5. Quy tắc phiếu cập nhật

| Quy tắc | Cách thực thi |
|---|---|
| Một phiếu cho mỗi (hạng mục, ngày) | Unique constraint ở DB; service bắt `IntegrityError` và trả thông báo tiếng Việt: "Ngày 29/07/2026 đã có phiếu cho hạng mục này. Hãy mở phiếu đó để sửa." |
| Không cho ngày tương lai | So với `local_today()` trong `app/date_utils.py` (múi giờ Asia/Ho_Chi_Minh). **Kiểm ở server**; `max` trên `<input type="date">` chỉ là tiện lợi cho người dùng |
| Cho phép ngày quá khứ | Không giới hạn cửa sổ. `created_at` cho biết phiếu được nhập muộn |
| `quantity > 0` | Không cho 0 và không cho số âm. Sai thì sửa hoặc xóa phiếu, không nhập phiếu âm để bù trừ |
| Parse ngày | `parse_iso_date()` trong `app/date_utils.py`, không tự parse |
| Sửa / xóa | Người tạo phiếu (nếu có `can_create_progress_entries`) hoặc người có `can_edit_all_progress_entries`; mọi lần đều `log_audit(...)` theo cách `app/project_operations/services.py` đang dùng, kèm `old_values`/`new_values` |

**Không có bước duyệt phiếu ở phase này.** Nó nhân đôi số trạng thái (lũy kế
đã duyệt vs. gồm chờ duyệt) và nhân đôi số câu hỏi "sao số trên dashboard khác
số tôi nhập". Audit log cộng với quyền sửa hẹp là đủ cho quy mô hiện tại. Nếu
sau này cần duyệt, thêm ở phase riêng với migration rõ ràng.

---

## 6. Phân quyền — ba lớp, phải làm cả ba

Hệ thống có ba lớp phân quyền độc lập (xem `CLAUDE.md`). Thiếu một lớp là route
mở toang dù nhìn có vẻ đã bảo vệ.

### 6.1 Module gate — bắt buộc, dễ quên nhất

`require_reports_module_access()` trong `app/__init__.py` (khoảng dòng 187–206)
gate theo **tiền tố tên endpoint**. Thêm `"construction_progress."` vào tuple
`report_endpoints`. Nếu không, mô đun mới sẽ bỏ qua gate
`can_access_reports_module` hoàn toàn.

Mô đun này thuộc phân hệ Quản lý dự án, dùng lại gate sẵn có — **không tạo gate
thứ năm**, không thêm `can_access_*_module` mới.

### 6.2 RBAC toàn cục — `app/permissions/registry.py`

Thêm resource `"construction_progress": "Tiến độ thi công"` vào `_RESOURCES`,
rồi thêm vào `PERMISSIONS` theo đúng mẫu của `project_updates`:

```python
*[_permission(f"construction_progress.{action}", f"{label} Tiến độ thi công",
              dangerous=action in {"delete", "structure"})
  for action, label in (("view", "Xem"), ("create", "Tạo phiếu"),
                        ("edit", "Sửa phiếu của mình"), ("edit_all", "Sửa mọi phiếu"),
                        ("delete", "Xóa phiếu"), ("structure", "Quản lý cấu trúc"))],
```

Trong `DEFAULTS`: `ADMIN` tự động nhận hết (đang lấy toàn bộ `PERMISSIONS`);
`VIEWER_ADMIN` tự nhận `construction_progress.view` qua nhánh
`p["action"] == "view"` — kiểm tra lại để chắc, và **không** thêm quyền mutation
nào cho `VIEWER_ADMIN`.

Sau khi deploy phải chạy tay, không sync ở startup:

```bash
flask sync-permissions --apply-defaults
```

### 6.3 Capability theo dự án — `app/project_memberships.py`

Thêm 4 flag vào `CAPABILITY_FIELDS` và nhãn tiếng Việt vào `CAPABILITY_LABELS`:

| Flag | Nhãn |
|---|---|
| `can_view_progress` | Xem tiến độ thi công |
| `can_create_progress_entries` | Tạo phiếu tiến độ |
| `can_edit_all_progress_entries` | Sửa mọi phiếu tiến độ |
| `can_manage_progress_structure` | Quản lý cấu trúc tiến độ |

Việc phải làm kèm theo:

- Thêm `can_view_progress` vào `READ_CAPABILITIES`, nếu không `VIEWER_ADMIN`
  sẽ không xem được (xem `user_has_project_capability`).
- Cập nhật `PROJECT_ROLE_PRESETS`: `PROJECT_VIEWER` +`can_view_progress`;
  `PROJECT_REPORTER` +`can_view_progress`, `can_create_progress_entries`;
  `PROJECT_EDITOR` thêm cả `can_edit_all_progress_entries`;
  `PROJECT_DOCUMENT_CONTROLLER` và `PROJECT_ISSUE_COORDINATOR` chỉ
  +`can_view_progress`. `PROJECT_OWNER` là `set(CAPABILITY_FIELDS)` nên tự có đủ.
- Thêm 4 cột boolean vào `ProjectUser`, `nullable=False`, `server_default`
  false, kèm migration.
- **Kiểm tra template quản lý thành viên dự án**: nếu form checkbox liệt kê
  từng flag bằng tay thay vì lặp qua `CAPABILITY_FIELDS`/`CAPABILITY_LABELS`,
  phải cập nhật, nếu không admin sẽ không gán được quyền mới.

### 6.4 Helper và decorator

**Quan trọng — đây là chỗ đặc tả bản đầu đã sai và đã được sửa.**
KHÔNG dùng `project_write_required` cho mô đun này. `can_write_project()` ở
`app/auth/permissions.py:235` hardcode `can_edit_all_reports`, nên
`PROJECT_REPORTER` sẽ bị 403 khi tạo phiếu tiến độ dù đã có capability tiến độ.
Gán thêm `can_edit_all_reports` để lách là leo thang quyền sang mô đun Báo cáo
ngày — không được làm.

Cũng KHÔNG sửa `project_read_required`, `project_write_required`,
`project_manage_required`, hay `can_write_project`. Chúng là primitive dùng
chung cho Báo cáo ngày, Vấn đề tồn đọng, và Hồ sơ dự án; đổi chữ ký của chúng
buộc phải soát lại toàn bộ caller cũ.

Cách đúng: dùng chính factory sẵn có
`_project_permission_required(checker, project_id_arg)` ở
`app/auth/permissions.py:269`. Ba decorator hiện có chỉ là ba wrapper mỏng
quanh nó; thêm wrapper mới cho tiến độ:

```python
def can_view_project_progress(project_id, user=None):
    return user_has_project_capability(_user_or_current(user), project_id, "can_view_progress")

def can_create_progress_entry(project_id, user=None):
    return user_has_project_capability(_user_or_current(user), project_id, "can_create_progress_entries")

def can_manage_progress_structure(project_id, user=None):
    return user_has_project_capability(_user_or_current(user), project_id, "can_manage_progress_structure")

def progress_read_required(project_id_arg="project_id"):
    return _project_permission_required(can_view_project_progress, project_id_arg)

def progress_entry_required(project_id_arg="project_id"):
    return _project_permission_required(can_create_progress_entry, project_id_arg)

def progress_structure_required(project_id_arg="project_id"):
    return _project_permission_required(can_manage_progress_structure, project_id_arg)
```

Factory gọi `checker(project_id)` với một tham số vị trí, nên các helper trên
cắm vào trực tiếp, không cần lambda.

Áp dụng: GET dùng `progress_read_required`; POST phiếu dùng
`progress_entry_required`; POST cấu trúc (loại, khu vực, hạng mục) dùng
`progress_structure_required`.

Sửa và xóa phiếu **không gate được bằng decorator** vì phụ thuộc chủ sở hữu:
gate ngoài bằng `progress_entry_required`, rồi sau khi load entry mới kiểm
`can_edit_progress_entry(entry, user=None)` — chủ phiếu hoặc
`can_edit_all_progress_entries` — theo đúng cách `can_edit_report(user, report)`
đang làm.

### 6.5 Chống confused deputy

Mọi route nhận ID lồng nhau (`type_id`, `group_id`, `item_id`, `entry_id`) phải
xác minh chuỗi cha khớp `project_id` trên URL, không chỉ `get_or_404` theo ID.
Lấy đối tượng bằng truy vấn có điều kiện `project_id == project.id` ngay trong
query, đúng nguyên tắc "explicit project-scoped queries" của repo. Một
`item_id` thuộc dự án khác phải trả 404, không phải 403.

---

## 7. Điểm tích hợp giao diện

### 7.1 Thẻ mô đun trong không gian dự án

`project_workspace()` trong `app/project_operations/routes.py` (khoảng dòng
96–114) dựng list `cards` với tuple `(key, label, description, icon,
permission, href)` và lọc bằng `current_user.can(card[4])`, `summaries` cấp
dòng số phụ. Lưu ý: bộ lọc này dùng **RBAC toàn cục**, không phải capability
dự án — thiếu permission code trong registry là thẻ không bao giờ hiện.

```python
("progress", "Quản lý tiến độ thi công",
 "Theo dõi khối lượng và dự toán theo từng khu vực, hạng mục.",
 "bi-bar-chart-steps", "construction_progress.view",
 url_for("construction_progress.project_progress", project_id=project.id)),
```

và `summaries["progress"]` dạng `"11% · 6 khu vực"` hoặc `"Chưa cấu hình"`.

### 7.2 Blueprint mới

`app/construction_progress/{__init__.py, routes.py, services.py}`, blueprint
tên `construction_progress`, đăng ký **bằng tay** trong `register_blueprints()`
ở `app/__init__.py` (không có auto-discovery).

Thêm `"construction_progress": "reports"` vào mapping trong `get_active_module()`
ở `app/navigation.py`, nếu không sidebar sẽ render sai phân hệ.

### 7.3 Danh sách route

| Method | Path | Mục đích |
|---|---|---|
| GET | `/projects/<int:project_id>/progress` | Danh sách loại tiến độ |
| POST | `/projects/<int:project_id>/progress/types` | Tạo loại tiến độ |
| POST | `…/progress/types/<int:type_id>/edit` | Sửa loại |
| POST | `…/progress/types/<int:type_id>/archive` | Ẩn loại |
| GET | `…/progress/types/<int:type_id>` | Cây khu vực / hạng mục |
| POST | `…/progress/types/<int:type_id>/groups` | Tạo khu vực |
| POST | `…/progress/groups/<int:group_id>/edit` \| `/archive` | Sửa / ẩn khu vực |
| POST | `…/progress/groups/<int:group_id>/items` | Tạo hạng mục |
| POST | `…/progress/items/<int:item_id>/edit` \| `/archive` | Sửa / ẩn hạng mục |
| GET | `…/progress/items/<int:item_id>` | Chi tiết + form phiếu + lịch sử |
| POST | `…/progress/items/<int:item_id>/entries` | Tạo phiếu ngày |
| POST | `…/progress/entries/<int:entry_id>/edit` \| `/delete` | Sửa / xóa phiếu |
| GET | `…/progress/types/<int:type_id>/chart-data` | JSON cho Chart.js |

Tất cả POST đều cần CSRF token theo pattern form hiện có trong
`app/templates/project_operations/*.html`. Endpoint JSON cũng phải qua đủ ba
lớp phân quyền như trang HTML.

### 7.4 Màn hình

1. **Danh sách loại tiến độ** — mỗi loại một thẻ: tên, phần trăm tổng, thanh
   tiến độ, số khu vực / hạng mục, ngày cập nhật gần nhất. Nút "Tạo loại tiến độ"
   chỉ hiện với `can_manage_progress_structure`.

2. **Cây khu vực / hạng mục** (màn hình chính) — bảng phân cấp mô phỏng file
   Excel đang dùng: Khu vực/Hạng mục, Đơn vị, Khối lượng kế hoạch, Đã làm,
   % hoàn thành (thanh + số), Người phụ trách, Ghi chú, Ngày cập nhật. Hàng khu
   vực gập/mở được, hiện phần trăm tổng. Mỗi hàng hạng mục có nút tạo phiếu
   nhanh. Dòng "Thêm hạng mục" nằm **trong** từng khu vực để không tạo lẫn cấp.
   Tab chuyển nhanh giữa các loại tiến độ.

3. **Form khu vực / hạng mục** — modal. Hạng mục gồm: tên, đơn vị, khối lượng
   kế hoạch, khối lượng đã làm trước khi dùng hệ thống (kèm chú thích rõ đây là
   số mang sang, không thuộc phiếu nào), người phụ trách, thứ tự, ghi chú.
   Hiển thị trước kết quả "sau khi lưu: 78 / 554 cái · 14%".

4. **Chi tiết hạng mục + tạo phiếu** — 4 thẻ số (kế hoạch, đã làm lũy kế, còn
   lại, % hoàn thành); form phiếu gồm ngày (chặn tương lai), khối lượng trong
   ngày kèm hậu tố đơn vị, ghi chú/vướng mắc; cảnh báo khi ngày đã có phiếu;
   dòng xem trước "sau khi lưu: 90 / 554 cái · 16%". Bảng lịch sử phiếu có dòng
   cuối "Mang sang — khối lượng trước khi dùng hệ thống" để không ai thắc mắc
   lũy kế ở đâu ra.

5. **Biểu đồ** — biểu đồ **cột dọc** phần trăm hoàn thành theo khu vực, kèm
   đường ngang là phần trăm chung của loại. Với `value_mode = money` dùng cột
   xếp lớp: phần đã thực hiện và phần còn lại, đơn vị tiền. Chart.js theo cách
   các dashboard hiện có đang dùng; số tổng luôn hiển thị bằng chữ cạnh biểu đồ.

Toàn bộ chuỗi text hướng người dùng bằng tiếng Việt, thống nhất thuật ngữ đang
dùng ("khối lượng", "dự toán", "khu vực", "hạng mục", "phiếu cập nhật").

---

## 8. Migration và deploy

1. Một migration Alembic: 4 bảng mới + 4 cột boolean trên `project_users`
   (`server_default` false để dữ liệu cũ không null).
2. Không có backfill: dữ liệu Excel do người dùng tự khai lại qua UI, dùng
   `opening_quantity` để mang khối lượng đã làm sang. Import Excel làm ở phase
   riêng nếu cần.
3. Sau deploy: `flask sync-permissions --apply-defaults`.
4. Không cần thay đổi cấu hình storage, Celery, hay quota — xem mục 10.
5. Kiểm tra `downgrade()` xóa được cả bảng và cột, thứ tự drop tôn trọng FK.

---

## 9. Kiểm thử bắt buộc

Theo `CLAUDE.md`, không chỉ assert status code — phải kiểm cả việc **không có**
hàng DB nào được tạo ở các nhánh bị chặn.

**Phân quyền** — cho cả trang HTML và endpoint JSON:

- chưa đăng nhập; đã đăng nhập nhưng bị chặn module gate; có module nhưng không
  phải thành viên dự án; là thành viên nhưng thiếu capability; là thành viên có
  capability; `VIEWER_ADMIN` chỉ đọc; `ADMIN`/`SUPER_ADMIN` bypass.
- Thay ID chéo dự án: `item_id` / `entry_id` / `group_id` của dự án khác phải ra
  404, và không lộ tên hạng mục qua thông báo lỗi.
- Route sửa/xóa phiếu của người khác khi chỉ có `can_create_progress_entries`.

**Nghiệp vụ:**

- Tạo phiếu trùng ngày → chặn, thông báo tiếng Việt, không tạo hàng thứ hai
  (test cả trường hợp gọi service trực tiếp, không chỉ qua form).
- Ngày tương lai → chặn theo `local_today()`.
- Ngày quá khứ → cho phép.
- `quantity <= 0` → chặn.
- Sửa phiếu → `completed_quantity` tính lại đúng, không cộng dồn lệch.
- Xóa phiếu → lũy kế giảm đúng, audit có `old_values`.
- Gửi trùng request tạo phiếu → chỉ một hàng.
- `planned_quantity = 0` → loại khỏi trung bình, không phải 0%.
- Khu vực rỗng → loại khỏi trung bình cấp loại.
- `completed > planned` → lưu được, hiển thị cap 100%, giá trị thật vẫn đúng.
- `value_mode = money` → cộng dồn tiền, không lấy trung bình.
- Hàm tính phần trăm test riêng như hàm thuần, có `Decimal` lẻ và làm tròn.

Lưu ý: test chạy trên SQLite in-memory (`tests/conftest.py`), nên **unique
constraint và `SELECT FOR UPDATE` không chứng minh được hành vi PostgreSQL đồng
thời**. Ghi rõ giới hạn này trong mô tả test.

`pytest.ini` đặt `filterwarnings = error` — không được làm phát sinh warning mới.

---

## 10. Ngoài phạm vi phase này

- **Không** dùng Celery, object storage, hay upload file. Mô đun này là CRUD
  cộng tính toán số. Ảnh minh chứng cho phiếu, nếu cần, làm ở phase sau.
- **Không** liên kết phiếu tiến độ với Báo cáo ngày hay Báo cáo xuyên suốt.
- **Không** làm biểu đồ đường lũy kế theo thời gian. Với `value_mode = quantity`,
  lũy kế theo thời gian **không cộng được** giữa các đơn vị khác nhau: muốn vẽ
  phải tính lại phần trăm trung bình tại từng mốc ngày. Để phase sau.
- **Không** import Excel, không export, không bulk download.
- **Không** thêm bước duyệt phiếu.
- **Không** đưa số tiến độ vào Dashboard toàn hệ thống ở phase này.
- **Không** đổi kiến trúc: không SPA, không auto-discovery blueprint, không hệ
  phân quyền thứ hai, không sync permission ở startup.

---

## 11. Quyết định đã chốt

1. **Hạng mục chưa có kế hoạch và khu vực rỗng**: loại khỏi phép trung bình,
   hiển thị `—` / "chưa cấu hình". Không tính là 0%.
2. **Tiến độ theo dự toán**: là một `ProgressType` có `value_mode = money`, dùng
   chung toàn bộ bảng và code.
3. **Người phụ trách và vướng mắc**: có ở **cả hai cấp** — hạng mục giữ người
   phụ trách mặc định và ghi chú cấu hình, phiếu giữ ghi chú/vướng mắc riêng
   theo từng ngày.
4. **Decorator phân quyền**: wrapper mới trên `_project_permission_required`,
   không sửa `project_write_required` (mục 6.4).

Nếu trong lúc làm phát hiện một trong các quyết định trên gây mâu thuẫn dữ liệu,
dừng lại và báo, đừng tự đổi quy tắc tính.

---

## 12. Định nghĩa hoàn thành

1. Bốn bảng + migration + 4 capability flag, `downgrade()` chạy được.
2. Đủ ba lớp phân quyền: prefix trong module gate, permission trong registry,
   capability trong `ProjectUser` và presets.
3. Thẻ mô đun hiện trong không gian dự án, đúng quyền, có dòng số phụ.
4. Khai báo được loại / khu vực / hạng mục và tạo được phiếu qua UI tiếng Việt.
5. Phần trăm ba cấp đúng, kể cả các trường hợp biên ở mục 4.
6. Biểu đồ cột hiển thị đúng và số tổng khớp với bảng.
7. Test theo mục 9 pass, không suppress warning, không sửa test cho xanh.
8. Audit log đủ cho mọi mutation phiếu và mọi thay đổi cấu trúc.
9. Không có secret hay dữ liệu thật trong commit.
10. Ghi lại: cần chạy `flask sync-permissions --apply-defaults` sau khi deploy.
