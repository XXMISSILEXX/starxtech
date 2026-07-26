Bạn đang làm việc trong repository:

```text
~/Documents/Construction_Management
```

Đây là STEP 9.9 của Phase 9: hoàn thiện Contractor Dashboard và loại bỏ hoàn toàn các dashboard/route legacy đã được thay thế bởi kiến trúc Dashboard Phase 9.

> Điều kiện đầu vào bắt buộc: STEP 9.8 đã được manual smoke, runtime/security gate PASS, commit xong và working tree sạch. Không bắt đầu STEP 9.9 trên working tree còn thay đổi của STEP 9.8.

Trước khi sửa code:

1. Đọc `AGENTS.md` hoặc hướng dẫn repo nếu có.
2. Đọc đầy đủ:
   - `docs/Phase_9_Complete_Execution_Package/MASTER_CONTEXT.md`
   - `docs/Phase_9_Complete_Execution_Package/FINAL_DECISIONS.md`
   - tài liệu TARGET liên quan;
   - `docs/Phase_9_Complete_Execution_Package/REFERENCE/Pre_Phase9_Audit/`;
   - toàn bộ docs/evidence STEP 9.7 và STEP 9.8.
3. Ghi lại:
   - branch;
   - HEAD;
   - `git status --short`;
   - `flask db current`;
   - `flask db heads`;
   - `flask routes` liên quan dashboard.
4. Đọc đầy đủ source liên quan, không chỉ grep snippet.
5. Không reset/stash/overwrite thay đổi có sẵn.
6. Không commit khi bất kỳ automated gate hoặc manual smoke nào chưa đạt.

## Ràng buộc bất biến

- Không dùng `Company`, `Partner`, `PartnerRelationship` cho Customer/contractor Phase 9.
- Không thêm health status hoặc đổi Daily Report status.
- Giữ nguyên các status Daily Report/section hiện tại.
- Không tự tạo hoặc liên kết `PersistentIssue` từ Daily Report.
- Không tạo OpenIssue, observation table hoặc contractor issue responsibility.
- Không tạo `ProjectReportItem`.
- Không rewrite Daily Report V2, direct S3, HEIC, finalize, attachment hoặc Celery.
- Không hard-code chức năng mới theo tên custom role; dùng permission codes.
- Không skip/xfail/broad mock để che lỗi.
- Không tạo migration nếu schema hiện tại đã đủ.
- Không xóa route ngoài phạm vi dashboard legacy đã được xác minh là thực sự được thay thế.

# STEP 9.9 — Contractor Dashboard + Legacy Dashboard Removal

## Mục tiêu A — Contractor Dashboard

Xây dashboard nhẹ cho `ProjectContractor`, tập trung vào participation, assignment và `ProjectUpdate` gắn assignment.

### Cards

- số Project ACTIVE đang tham gia;
- số Customer liên quan;
- số assignment vai trò `CONSTRUCTION`;
- số assignment vai trò `SOLUTION`;
- phân bổ assignment theo status;
- cập nhật gần nhất.

### Charts/lists

- Project theo Customer;
- assignment theo role/status;
- timeline `ProjectUpdate` theo Project/type;
- danh sách Project đang/đã tham gia;
- overall Daily Report status hiện tại chỉ là bối cảnh Project, không phải điểm đánh giá contractor.

### PersistentIssue

Nếu hiển thị:

- đặt dưới nhãn **“Bối cảnh dự án”** hoặc **“Vấn đề tồn đọng của dự án”**;
- không gọi là trách nhiệm contractor;
- không filter/assign issue cho contractor vì schema không có quan hệ;
- không tạo chỉ số “vấn đề contractor đang mở”.

### Daily Report

- không dùng section-status pie/stacked để đánh giá contractor;
- không tạo contractor score;
- không suy diễn hiệu suất contractor từ status chung của Project;
- overall Daily Report status nếu hiển thị phải ghi rõ là bối cảnh Project.

### Scope và authorization

- Contractor Dashboard chỉ tổng hợp assignment có Project nằm trong effective project scope của user, trừ khi user có `projects.scope_all`.
- Catalog existence không được làm lộ tên Project ngoài scope.
- Assignment `ENDED` được giữ lịch sử và chỉ hiện khi filter/permission cho phép.
- Page và API cần đồng thời:
  - `modules.reports.access`;
  - `dashboards.contractor.view`;
  - effective Project scope hoặc `projects.scope_all` theo policy hiện hành.
- `projects.scope_all` chỉ mở scope, không tự cấp `dashboards.contractor.view` hay quyền ghi.
- Custom role read-only xem được dashboard nhưng không tự có quyền sửa contractor, assignment hoặc ProjectUpdate.

### Route/API đề xuất

Codex phải kiểm tra route convention hiện tại rồi chọn endpoint phù hợp, ưu tiên:

```text
GET /reports/dashboard/contractors/<int:contractor_id>
GET /api/reports/dashboard/contractors/<int:contractor_id>/overview
```

Không được đoán endpoint nếu codebase đã có convention khác. Báo chính xác route sau khi triển khai bằng `flask routes`.

---

# Mục tiêu B — Loại bỏ hoàn toàn Dashboard Legacy

## Định nghĩa phạm vi legacy cần loại bỏ

Trước khi xóa, bắt buộc tạo inventory thực tế từ source và route map.

Các surface legacy đã biết cần kiểm tra gồm:

```text
GET /reports/dashboard
GET /api/reports/dashboard/report-count-chart
GET /api/reports/dashboard/status-chart
```

Endpoint name hiện tại có thể tương ứng:

```text
dashboard.index
dashboard_api.report_count_chart
dashboard_api.status_chart
```

Đây chỉ là danh sách khởi đầu. Codex phải dùng `flask routes`, `rg/grep`, `url_for(...)`, template, JavaScript, tests và docs để xác định toàn bộ dashboard legacy thực tế.

## Nguyên tắc xóa

1. Chỉ xóa dashboard/report-centric legacy đã được thay thế đầy đủ bởi:
   - System Dashboard;
   - Customer Dashboard;
   - Project Dashboard;
   - Contractor Dashboard.
2. Không xóa các route nghiệp vụ không phải dashboard.
3. Không xóa package `app/dashboard` nếu package đó đang chứa dashboard Phase 9 mới.
4. Không xóa helper/service dùng chung bởi dashboard mới.
5. Không giữ compatibility route, redirect hoặc alias cho dashboard legacy.
6. Route legacy sau khi xóa phải không còn trong `flask routes` và trả 404 tự nhiên.
7. Không tạo route 410, không tạo redirect 301/302 và không giữ endpoint ẩn.
8. Mọi navigation, button, bookmark nội bộ và `url_for()` trong source phải chuyển sang route Phase 9 mới trước khi xóa route cũ.
9. Không giữ JavaScript/template/CSS/test chỉ phục vụ dashboard legacy.
10. Xóa wording legacy như:
    - “Vấn đề đang mở”;
    - “Vấn đề nghiêm trọng” theo nghĩa OpenIssue;
    nếu chúng chỉ thuộc dashboard legacy.
11. Dashboard Phase 9 mới chỉ dùng khái niệm **Vấn đề tồn đọng** dựa trên `PersistentIssue` hiện tại.

## Dashboard quản trị canonical sau khi xóa legacy

- Sidebar **“Dashboard quản trị”** phải trỏ tới System Dashboard mới.
- Canonical route dự kiến:

```text
/reports/dashboard/system
```

- `/reports/config`, Project Workspace, Customer detail và các màn liên quan không được còn link tới `/reports/dashboard` legacy.
- Không có link 404 sau khi xóa.

## Legacy inventory bắt buộc

Trước khi sửa, tạo:

```text
docs/Phase9/evidence/09_9_legacy_dashboard_inventory.md
```

Tài liệu phải ghi:

- route URL;
- endpoint name;
- route function;
- template;
- JavaScript;
- service/query helper;
- navigation reference;
- tests phụ thuộc;
- docs reference;
- replacement Phase 9 tương ứng;
- quyết định DELETE hoặc KEEP và lý do.

Không được xóa bất kỳ route nào không có replacement rõ ràng hoặc không thuộc dashboard legacy.

## Công việc xóa legacy

Sau khi Contractor Dashboard mới hoạt động và inventory hoàn chỉnh:

1. Xóa route/page legacy.
2. Xóa API chart legacy.
3. Xóa template dashboard legacy không còn dùng.
4. Xóa JavaScript/CSS chỉ dùng cho dashboard legacy.
5. Xóa service/query helper dead code sau khi xác minh không được dashboard mới sử dụng.
6. Cập nhật navigation desktop/mobile dùng System Dashboard mới.
7. Cập nhật `url_for()` và raw URL references.
8. Cập nhật tests:
   - xóa compatibility expectation cũ;
   - thêm assertion legacy route không còn trong route map;
   - legacy URLs trả 404;
   - canonical System/Customer/Project/Contractor dashboards trả đúng status theo permission.
9. Cập nhật docs/evidence để không còn hướng dẫn dùng dashboard legacy.
10. Không để orphan translation/label/config key nếu chỉ dùng cho legacy.

---

# Tests bắt buộc

## Contractor Dashboard

- contractor tham gia nhiều Customer/Project;
- cùng contractor có hai role;
- partial Project scope;
- timeline chỉ lấy `ProjectUpdate` gắn đúng assignment;
- general ProjectUpdate không bị gắn nhãn contractor update;
- assignment `ENDED` xuất hiện trong lịch sử khi filter cho phép;
- contractor archived không tạo assignment/update mới nhưng lịch sử vẫn đọc được;
- không có section-status contractor analytics;
- không có contractor score;
- PersistentIssue chỉ là Project context;
- custom contractor-viewer role;
- `projects.scope_all` không tự cấp dashboard permission;
- page/API authorization tương đương;
- unknown/inaccessible contractor không làm lộ Project names;
- query count không tăng tuyến tính theo số assignment/update.

## Legacy removal

- `flask routes` không còn endpoint legacy;
- `/reports/dashboard` trả 404;
- `/api/reports/dashboard/report-count-chart` trả 404;
- `/api/reports/dashboard/status-chart` trả 404;
- không còn `url_for()` tới endpoint legacy;
- không còn raw internal link tới URL legacy;
- sidebar Dashboard quản trị mở `/reports/dashboard/system`;
- System Dashboard hoạt động;
- Customer Dashboard hoạt động;
- Project Dashboard hoạt động;
- Contractor Dashboard hoạt động;
- API mới của cả bốn scope hoạt động;
- custom-role permission matrix không regress;
- không còn template/JS/service dead code legacy;
- không còn nhãn OpenIssue trong dashboard Phase 9 mới;
- Daily Report V2 và Project Workspace không regress.

## Route-reference scan

Chạy và lưu kết quả vào evidence:

```bash
flask routes | grep -Ei 'dashboard|status-chart|report-count-chart|overview'

rg -n \
  "dashboard\.index|report_count_chart|status_chart|/reports/dashboard(?:[\"'?#]|$)|/api/reports/dashboard/(?:report-count-chart|status-chart)" \
  app tests docs \
  || true
```

Nếu `rg` không có, dùng `grep -RInE` tương đương.

Kết quả sau removal chỉ được còn:

- docs/evidence mô tả việc đã xóa;
- test assertion legacy URL trả 404;
- không được còn live navigation, template, JS hoặc backend references.

---

# Query/performance

- Aggregate contractor data trong SQL.
- Không load toàn bộ Project/assignment/update rồi lọc ngoài Python.
- `ProjectUpdate` timeline chỉ lấy update có `contractor_assignment_id` thuộc contractor đang xem.
- General update `contractor_assignment_id IS NULL` không được đưa vào timeline contractor.
- Distinct Customer/Project counts đúng.
- Active counts chỉ dùng assignment/project theo policy hiện tại.
- Recent update bỏ soft-deleted records.
- Eager-load quan hệ cần render.
- Bổ sung query-count regression với dataset nhỏ/lớn.

---

# UI/UX và accessibility

- Dashboard contractor dùng tabs/cards/charts nhất quán với System/Customer Dashboard.
- Có header contractor, trạng thái catalog và tên viết tắt nếu có.
- Có filter assignment status và Project khi cần.
- Không chỉ dùng màu để truyền đạt role/status.
- Chart có text summary hoặc accessible label.
- External JavaScript, không inline executable script bị CSP chặn.
- Empty state tiếng Việt.
- Mobile 390×844 và 430×932 không overflow.
- Không duplicate element IDs.
- Tôn trọng `prefers-reduced-motion`.

---

# Commands và gates

## Baseline trước sửa

```bash
cd ~/Documents/Construction_Management

git branch --show-current
git rev-parse HEAD
git status --short
flask db current
flask db heads
flask routes | grep -Ei 'dashboard|status-chart|report-count-chart|overview'
```

## Targeted tests

Dùng đúng tên test file thực tế sau khi đọc source. Tối thiểu bao gồm:

```bash
pytest -q \
  tests/test_three_layer_authorization.py \
  tests/test_rbac_navigation.py \
  tests/test_dashboard_issues.py \
  <contractor-dashboard-tests> \
  <legacy-removal-tests> \
  -vv
```

## Static/build checks

```bash
python -m compileall -q app tests migrations
node --check app/static/js/scoped-dashboard-charts.js
node --check <contractor-dashboard-js-file>
npm test
pip check
git diff --check
```

## Full gate

```bash
PYTHONWARNINGS=error pytest -q -ra
flask security-audit
flask db current
flask db heads
```

Yêu cầu:

```text
Full pytest: 0 failed
npm test: PASS
compileall: PASS
node --check: PASS
pip check: PASS
security-audit: PASS
migration current = head = c4d2e980f617
git diff --check: PASS
```

Không tạo migration mới trong STEP 9.9.

---

# Manual smoke

## Contractor Dashboard

Xác minh update VTS **“Đã bàn giao xong 2 hạng mục”** xuất hiện tại:

1. VTS assignment timeline trong An Bình Homeland.
2. Báo cáo xuyên suốt Project.
3. Project Dashboard recent updates.
4. Customer Dashboard recent updates.
5. VTS Contractor Dashboard.

Không được xuất hiện như VTS update ở Project khác.

Kiểm tra thêm:

- contractor nhiều Customer/Project;
- cùng contractor hai role;
- assignment ACTIVE/ENDED;
- partial scope user;
- custom contractor-viewer read-only;
- general ProjectUpdate không xuất hiện trong contractor timeline;
- PersistentIssue chỉ nằm trong “Bối cảnh dự án”.

## Legacy removal

Sau khi restart app:

```text
/reports/dashboard                                  → 404
/api/reports/dashboard/report-count-chart           → 404
/api/reports/dashboard/status-chart                 → 404
```

Các route sau phải hoạt động theo permission:

```text
/reports/dashboard/system
/reports/dashboard/customers/<id>
/reports/projects/<id>/dashboard
/reports/dashboard/contractors/<id>
```

Kiểm tra:

- Sidebar Dashboard quản trị mở System Dashboard.
- Không có link 404 trong navigation/config/workspace.
- Không có browser console error/CSP error.
- Mobile 390×844 và 430×932 PASS.
- Custom role chỉ thấy dashboard được cấp.

---

# Evidence bắt buộc

Tạo/cập nhật:

```text
docs/Phase9/evidence/09_9_legacy_dashboard_inventory.md
docs/Phase9/evidence/09_9_contractor_dashboard_smoke.md
docs/Phase9/evidence/09_9_legacy_dashboard_removal_smoke.md
```

Evidence phải ghi kết quả thật, không điền PASS trước khi kiểm tra.

---

# Commit strategy

STEP 9.9 có hai thay đổi lớn và phải tách thành hai commit để dễ rollback.

## Commit A — Contractor Dashboard

Chỉ commit khi Contractor Dashboard targeted/full gate và manual smoke PASS:

```bash
git add app/dashboard app/project_operations app/templates app/static tests docs/Phase9
git diff --cached --check
git commit -m "feat(dashboard): add contractor analytics"
```

## Commit B — Legacy removal

Sau Commit A, xóa legacy, chạy lại targeted + full gate + manual smoke. Chỉ commit khi tất cả PASS:

```bash
git add app/dashboard app/navigation.py app/templates app/static tests docs/Phase9
git diff --cached --check
git commit -m "refactor(dashboard): remove legacy dashboard routes"
```

Không dùng `git add -A` nếu chưa review toàn bộ file.

Sau mỗi commit:

```bash
git status --short
git show --stat --oneline HEAD
git show --check HEAD
```

Working tree phải sạch trước khi chuyển sang STEP 9.10.

---

# Kết quả cuối phải báo

1. Branch và HEAD trước/sau.
2. Contractor Dashboard route/API thực tế.
3. Authorization matrix.
4. Query strategy và query-count result.
5. Legacy inventory đầy đủ.
6. Danh sách route/endpoint/template/JS/service đã xóa.
7. Route map sau removal.
8. Targeted test result.
9. Full regression result.
10. npm/compile/node/pip/security results.
11. Migration current/head.
12. Manual desktop/mobile result.
13. Commit A hash.
14. Commit B hash.
15. Working tree cuối cùng sạch.

Không chuyển STEP 9.10 nếu legacy route vẫn tồn tại, có link 404 nội bộ, manual smoke chưa PASS hoặc working tree chưa sạch.
