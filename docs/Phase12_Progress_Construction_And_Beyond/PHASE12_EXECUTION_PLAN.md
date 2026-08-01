# Phase 12 — Kế hoạch thi hành

Kế hoạch từng bước để triển khai mô đun "Quản lý tiến độ thi công".

- Đặc tả nghiệp vụ: `PHASE12_CONSTRUCTION_PROGRESS.md` (cùng thư mục). Khi kế
  hoạch này và đặc tả xung đột, **đặc tả thắng** — trừ khi kế hoạch nói rõ nó
  đang sửa đặc tả.
- Quy tắc repo: `CLAUDE.md`. Ghi đè mọi mặc định của agent.
- Bối cảnh: `AGENTS.md`, `README.md`.

Nguyên tắc xuyên suốt: **8 commit nhỏ, mỗi commit `pytest` xanh, mỗi commit tự
đứng vững được.** Không gộp. Không viết trước code của bước sau.

---

## Bước 0 — Mốc xanh trước khi viết dòng code đầu tiên

Bắt buộc, không được bỏ. Delta audit Phase 11 ghi nhận **hai lượt pytest rộng
bị môi trường dừng trước khi có summary**, nên hiện tại chưa ai biết chắc suite
đang xanh hoàn toàn. Nếu bắt đầu code mà không có mốc, mọi test đỏ sau này đều
không phân biệt được là do Phase 12 hay đã đỏ từ trước.

Việc phải làm:

1. Xác nhận đang ở branch `Phase12/Progress-and-beyond`, `git status` sạch.
2. **Commit ngay các file untracked đang có** trước khi làm bất cứ việc gì:
   `.audit/PHASE11-DELTA-*.md`, `.audit/ENDPOINTS-g5.md`,
   `.audit/findings-15..17-*.md`, `.audit/VERIFIED-PHASE11-DELTA.md`,
   `.audit/poc/REPORTS-007-section-image-limit.py`, và toàn bộ
   `docs/Phase12_Progress_Construction_And_Beyond/`.
   Lý do: bản đặc tả Phase 12 đã từng bị mất một lần vì để untracked. Hồ sơ
   audit cũng đang untracked và sẽ mất theo cùng một cách.
3. Chạy và **lưu nguyên văn output** vào
   `docs/Phase12_Progress_Construction_And_Beyond/BASELINE.md`:

```bash
pytest -p no:cacheprovider -q 2>&1 | tail -40
npm test 2>&1 | tail -20
```

4. Nếu có test đỏ hoặc suite không chạy hết: **ghi lại chính xác test nào, lỗi
   gì, và DỪNG. Báo trước khi tự sửa.** Không sửa test cũ, không sửa code cũ để
   lấy màu xanh — đó là phạm vi khác.
5. Nếu xanh hết: ghi số test pass và thời gian chạy vào `BASELINE.md`, commit
   file đó, rồi mới sang Bước 1.

**Cổng dừng #1:** báo kết quả Bước 0 trước khi sang Bước 1.

---

## Danh sách file được phép sửa trong cả phase

Tạo mới:

```
app/models/progress.py
app/construction_progress/__init__.py
app/construction_progress/routes.py
app/construction_progress/services.py
app/templates/construction_progress/*.html
app/static/js/construction-progress.js          (nếu cần)
tests/test_construction_progress_models.py
tests/test_construction_progress_services.py
tests/test_construction_progress_authz.py
tests/test_construction_progress_entries.py
tests/test_construction_progress_views.py
tests_js/construction-progress.test.js          (nếu có file JS mới)
migrations/versions/<hash>_phase12_construction_progress.py
docs/Phase12_Progress_Construction_And_Beyond/BASELINE.md
docs/Phase12_Progress_Construction_And_Beyond/PHASE12_RESULT.md
```

Được sửa, **chỉ ở phần liên quan tới mô đun mới**:

```
app/__init__.py                       # gate tuple + register_blueprints
app/models/__init__.py                # re-export
app/models/project.py                 # 4 cột capability trên ProjectUser
app/permissions/registry.py           # resource + permissions
app/project_memberships.py            # CAPABILITY_FIELDS/LABELS, READ_CAPABILITIES, PRESETS
app/auth/permissions.py               # THÊM helper/decorator mới, không sửa cái cũ
app/navigation.py                     # mapping blueprint
app/project_operations/routes.py      # thẻ mô đun trong project_workspace()
app/templates/<template quản lý thành viên>   # chỉ nếu nó liệt kê capability bằng tay
```

**Cấm chạm:** `app/config.py`, `docker-compose.yml`, `Dockerfile*`,
`pytest.ini`, `requirements.txt`, `package.json`, mọi file trong `.audit/`,
mọi test đã có, và các hàm `project_read_required` / `project_write_required` /
`project_manage_required` / `can_write_project` trong `app/auth/permissions.py`.

Nếu một bước có vẻ đòi hỏi sửa file ngoài danh sách trên: **DỪNG và báo**,
đừng tự mở rộng phạm vi.

---

## Bước 1 — Models và migration

Commit: `Phase12: add construction progress models and migration`

Việc:

- `app/models/progress.py`: `ProgressType`, `ProgressGroup`, `ProgressItem`,
  `ProgressEntry` theo đúng bảng cột ở mục 3 của đặc tả. Bám style
  `app/models/project_update.py`.
- Re-export cả 4 model trong `app/models/__init__.py`.
- 4 cột boolean mới trên `ProjectUser`: `can_view_progress`,
  `can_create_progress_entries`, `can_edit_all_progress_entries`,
  `can_manage_progress_structure` — `nullable=False`, `server_default` false.
- Sinh migration bằng `flask db migrate -m "phase12 construction progress"`,
  rồi **đọc lại file autogenerate bằng tay** và sửa nếu cần: tên constraint
  (`uq_`/`ck_`/`ix_`), kiểu `Numeric(18,3)`, `server_default`, và `downgrade()`
  drop đúng thứ tự FK.

Nghiệm thu:

- `pytest` xanh (chưa có route nào, chỉ models).
- Import được từ `app.models`, không phải từ submodule.
- Migration có cả `upgrade()` và `downgrade()` hoàn chỉnh; đọc lại thấy khớp
  đặc tả; **không chạy `flask db upgrade` lên bất kỳ DB nào ngoài DB local dùng
  một lần của bạn**.

Test (`tests/test_construction_progress_models.py`):

- Unique `(progress_item_id, report_date)` chặn phiếu thứ hai cùng ngày.
- Unique tên trong phạm vi cha (3 cấp).
- CheckConstraint `quantity > 0` và `planned_quantity >= 0`.
- `value_mode` chỉ nhận `quantity` / `money`.
- Ghi rõ trong docstring: SQLite in-memory **không** chứng minh hành vi
  PostgreSQL đồng thời.

---

## Bước 2 — Phân quyền ba lớp

Commit: `Phase12: wire construction progress permissions`

Việc — làm đủ cả bốn điểm, thiếu một điểm là mô đun hỏng theo cách khó thấy:

1. `app/__init__.py`: thêm `"construction_progress."` vào tuple
   `report_endpoints` trong `require_reports_module_access()`.
2. `app/permissions/registry.py`: thêm resource `construction_progress` và 6
   permission theo mẫu `project_updates` (mục 6.2 đặc tả).
3. `app/project_memberships.py`: 4 flag vào `CAPABILITY_FIELDS`, nhãn tiếng
   Việt vào `CAPABILITY_LABELS`, `can_view_progress` vào `READ_CAPABILITIES`,
   cập nhật `PROJECT_ROLE_PRESETS`.
4. `app/auth/permissions.py`: **thêm** 3 helper + 3 decorator mới theo mục 6.4
   đặc tả, dựng trên `_project_permission_required`. Cộng
   `can_edit_progress_entry(entry, user=None)` cho kiểm tra theo chủ sở hữu.
   Không sửa helper/decorator nào đang có.
5. `app/navigation.py`: `"construction_progress": "reports"` vào mapping
   `get_active_module()`.
6. Kiểm template quản lý thành viên dự án: nếu liệt kê capability bằng tay thì
   cập nhật; nếu nó lặp qua `CAPABILITY_FIELDS` thì không cần sửa — ghi rõ
   trong commit message bạn đã kiểm và kết luận thế nào.

Nghiệm thu:

- Test khẳng định 6 permission code có trong `PERMISSIONS`.
- Test khẳng định `ADMIN` có đủ 6 code; `VIEWER_ADMIN` **chỉ** có
  `construction_progress.view` và không có code mutation nào.
- Test khẳng định `can_view_progress ∈ READ_CAPABILITIES`.
- Test khẳng định preset của từng project role đúng như đặc tả.
- Test khẳng định `"construction_progress."` nằm trong tuple gate.
- **Không** chạy `flask sync-permissions`.

---

## Bước 3 — Service và tính toán

Commit: `Phase12: add construction progress services`

Việc — `app/construction_progress/services.py`:

- Hàm thuần, không cần request context: `item_percent(item)`,
  `group_percent(group, value_mode)`, `type_percent(progress_type)`.
- `progress_tree(project, progress_type)` trả cấu trúc lồng đã tính sẵn phần
  trăm cho template và cho JSON.
- `recalculate_item_completed(item)`: `opening_quantity + SUM(quantity)` trong
  cùng transaction. **Không** `+=`. Trên PostgreSQL lấy `FOR UPDATE` trên hàng
  item trước khi tính.
- `create_entry(...)`, `update_entry(...)`, `delete_entry(...)`: validate ngày
  qua `local_today()` / `parse_iso_date()`, bắt `IntegrityError` cho trùng
  ngày, gọi `recalculate_item_completed`, ghi `log_audit(...)`.
- CRUD cấu trúc: `create_type/group/item`, `update_*`, `archive_*`; sửa
  `planned_quantity` / `opening_quantity` phải tính lại và ghi audit.
- Exception riêng, thông báo tiếng Việt: `DuplicateEntryError`,
  `FutureDateError`, `InvalidQuantityError`.

Nghiệm thu — `tests/test_construction_progress_services.py` phủ đủ:

| Trường hợp | Kỳ vọng |
|---|---|
| `planned_quantity = 0` | loại khỏi trung bình, không phải 0% |
| khu vực rỗng | loại khỏi trung bình cấp loại |
| `completed > planned` | lưu được, phần trăm thật > 100, hiển thị cap 100 |
| `value_mode = money` | cộng dồn tiền, không lấy trung bình |
| `Decimal` lẻ | không sai số, chỉ làm tròn khi hiển thị |
| trùng ngày | `DuplicateEntryError`, chỉ 1 hàng trong DB |
| ngày tương lai | `FutureDateError` |
| ngày quá khứ | cho phép |
| `quantity <= 0` | `InvalidQuantityError` |
| sửa phiếu | lũy kế tính lại đúng |
| xóa phiếu | lũy kế giảm đúng, audit có `old_values` |
| gọi `create_entry` hai lần cùng tham số | chỉ 1 hàng |

---

## Bước 4 — Blueprint, route, phân quyền route

Commit: `Phase12: add construction progress routes`

Việc:

- `app/construction_progress/__init__.py`: blueprint `construction_progress`,
  import routes ở cuối file (theo mẫu `app/project_operations/__init__.py`).
- `app/construction_progress/routes.py`: đủ 13 route ở mục 7.3 đặc tả. Chưa
  cần template đẹp — trả về tối thiểu để test phân quyền chạy được.
- Đăng ký blueprint trong `register_blueprints()` ở `app/__init__.py`.
- Mọi route: lấy đối tượng bằng truy vấn **có điều kiện `project_id`**, id
  thuộc dự án khác trả 404. Không `get_or_404` trần.
- Áp decorator: GET → `progress_read_required`; POST phiếu →
  `progress_entry_required`; POST cấu trúc → `progress_structure_required`;
  sửa/xóa phiếu → `progress_entry_required` + `can_edit_progress_entry(entry)`
  sau khi load.

Nghiệm thu:

- `flask --app run.py routes | grep construction_progress` liệt kê đủ 13 route.
- `tests/test_construction_progress_authz.py` phủ **7 vai** × các nhóm route
  (đọc / tạo phiếu / sửa cấu trúc / JSON): chưa đăng nhập, bị chặn module gate,
  có module nhưng không phải thành viên, thành viên thiếu capability, thành
  viên có capability, `VIEWER_ADMIN`, `ADMIN`.
- Test thay ID chéo dự án cho `type_id`, `group_id`, `item_id`, `entry_id` → 404
  và **không lộ tên** trong body.
- Test: thành viên chỉ có `can_create_progress_entries` không sửa được phiếu
  của người khác.
- Mọi nhánh bị chặn: khẳng định **không có hàng DB nào** được tạo.

**Cổng dừng #2:** báo kết quả ma trận phân quyền trước khi sang template. Sai
ở đây thì template làm xong cũng phải làm lại.

---

## Bước 5 — Template cấu trúc và thẻ mô đun

Commit: `Phase12: add construction progress screens`

Việc:

- `app/templates/construction_progress/`: `index.html` (danh sách loại),
  `type_detail.html` (cây khu vực/hạng mục), `item_detail.html` (chi tiết +
  form phiếu + lịch sử), cùng các modal form. Theo mục 7.4 đặc tả.
- Thẻ mô đun trong `project_workspace()` (`app/project_operations/routes.py`)
  cùng `summaries["progress"]`.
- CSRF token trên mọi form, theo pattern `app/templates/project_operations/`.
- Chuỗi tiếng Việt, thuật ngữ thống nhất với đặc tả.

Nghiệm thu — `tests/test_construction_progress_views.py`:

- Thẻ mô đun hiện với người có `construction_progress.view`, **không** hiện với
  người không có.
- Trang cây render đủ 3 cấp và số phần trăm khớp service.
- Nút tạo/sửa cấu trúc **không** render cho người thiếu
  `can_manage_progress_structure` (và route tương ứng vẫn 403 — UI ẩn không
  phải là kiểm soát).
- Không có `|safe` trên dữ liệu do người dùng nhập (tên hạng mục, ghi chú).
  Test XSS: tên hạng mục chứa `<script>` phải bị escape trong HTML trả về.

---

## Bước 6 — Phiếu: tạo, sửa, xóa, lịch sử

Commit: `Phase12: add daily progress entries`

Việc: nối form phiếu vào service, thông báo lỗi tiếng Việt, dòng "Mang sang"
trong lịch sử, cảnh báo khi ngày đã có phiếu, `max` ngày = hôm nay trên input
(kèm kiểm ở server — input chỉ là tiện lợi).

Nghiệm thu — `tests/test_construction_progress_entries.py` qua HTTP layer:

- POST trùng ngày → hiển thị thông báo tiếng Việt, DB vẫn 1 hàng.
- POST ngày tương lai → chặn.
- POST `quantity = 0` và số âm → chặn.
- POST hai lần liên tiếp cùng payload → 1 hàng.
- Sửa rồi xóa → `completed_quantity` và phần trăm 3 cấp đúng ở mỗi bước.
- Audit log có bản ghi cho create/update/delete với `old_values`/`new_values`.

---

## Bước 7 — Biểu đồ cột

Commit: `Phase12: add construction progress chart`

Việc:

- Route `…/chart-data` trả JSON: nhãn khu vực, phần trăm từng khu vực, phần
  trăm chung của loại; với `money` thêm số đã thực hiện và còn lại.
- Biểu đồ **cột dọc** bằng Chart.js theo cách các dashboard hiện có đang dùng.
  Với `money` dùng cột xếp lớp. Số tổng luôn hiển thị bằng chữ cạnh biểu đồ.
- Nếu tách file `app/static/js/construction-progress.js` thì **bắt buộc** có
  `tests_js/construction-progress.test.js` theo mẫu
  `tests_js/report-direct-upload.test.js` (CLAUDE.md yêu cầu).
- Mọi số hiển thị phải làm tròn tường minh.

Nghiệm thu:

- Endpoint JSON qua đủ ba lớp phân quyền; test cả 7 vai như Bước 4.
- Test: JSON không chứa dữ liệu của dự án khác, không chứa id không cần thiết.
- `npm test` xanh.

---

## Bước 8 — Chốt phase

Commit: `Phase12: close construction progress phase`

Việc — viết `docs/Phase12_Progress_Construction_And_Beyond/PHASE12_RESULT.md`:

1. Danh sách file thêm/sửa, kèm lý do từng file.
2. Đối chiếu từng dòng "Định nghĩa hoàn thành" (mục 12 đặc tả): đạt / chưa đạt
   / không áp dụng, kèm chứng cứ.
3. Bảng test: mỗi yêu cầu ở mục 9 đặc tả → tên test cụ thể. Yêu cầu nào chưa có
   test thì nói rõ và giải thích.
4. Output `pytest` và `npm test` dán **nguyên văn**, không tóm tắt.
5. Việc phải làm khi deploy: chạy `flask sync-permissions --apply-defaults`, và
   `flask db upgrade` với revision nào.
6. Giới hạn đã biết: SQLite không chứng minh được gì, phần nào chưa test được.
7. Chỗ nào phải tự quyết vì đặc tả chưa nói rõ, và đã quyết thế nào.
8. Điều gì đã bỏ qua hoặc làm tạm.

---

## Bốn cái bẫy đã biết

Đã trả giá để tìm ra, đừng đâm lại:

1. **Module gate theo tiền tố endpoint.** Không thêm
   `"construction_progress."` vào `report_endpoints` là route mở toang dù
   decorator đầy đủ. `app/__init__.py` ~dòng 196.
2. **Thẻ mô đun lọc bằng RBAC toàn cục**, không phải capability dự án
   (`current_user.can(card[4])`, `app/project_operations/routes.py:113`). Thiếu
   permission code trong registry là thẻ không bao giờ hiện.
3. **`READ_CAPABILITIES`** (`app/project_memberships.py:60`). Quên thêm
   `can_view_progress` là `VIEWER_ADMIN` bị 403 một cách khó hiểu.
4. **`project_write_required` hardcode `can_edit_all_reports`**
   (`app/auth/permissions.py:235`). Dùng nó cho mô đun này là `PROJECT_REPORTER`
   không tạo được phiếu. Dùng wrapper mới trên `_project_permission_required`
   (mục 6.4 đặc tả). Không sửa primitive dùng chung.

---

## Điều kiện DỪNG và báo

- Bước 0 phát hiện test đỏ có sẵn.
- Một bước đòi sửa file ngoài danh sách được phép.
- Một trong 4 quyết định ở mục 11 đặc tả gây mâu thuẫn dữ liệu.
- Cần đổi kiến trúc, thêm dependency, hay đổi cấu hình.
- Phát hiện lỗ hổng bảo mật ở code cũ trong lúc làm: ghi lại, **không sửa** —
  đó là phạm vi audit, không phải phase này.

## Ngoài phạm vi tuyệt đối

Xem mục 10 đặc tả. Bổ sung: finding `REPORTS-007` (giới hạn 10 ảnh/section trái
hợp đồng 3 ảnh, mở sau delta audit Phase 11) **không** thuộc phase này. Không
sửa nó ở đây.
