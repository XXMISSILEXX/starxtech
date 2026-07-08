# PROMPT 03 — Auth + Permissions

---

Hãy xây module authentication và permission cho StarX Project Daily Report System.

Yêu cầu chức năng:

1. Login:

- GET /login
- POST /login
- Dùng username hoặc email.
- Check password hash.
- Chặn user inactive.
- Set `last_login_at`.

2. Logout:

- POST /logout

3. Change password:

- GET /change-password
- POST /change-password
- User đang login được đổi password.
- Cần nhập current password.

4. Login required:

- Các route khác ngoài /login và /health phải cần đăng nhập.

5. Permission decorators:

- `role_required(*roles)`
- `viewer_or_admin_required()` nếu cần
- `can_read_project(project_id)`
- `can_write_project(project_id)`
- `project_read_required(project_id_arg='project_id')`
- `project_write_required(project_id_arg='project_id')`

Rule:

- SUPER_ADMIN: read/write all.
- VIEWER_ADMIN: read all, write none.
- REPORTER: read/write only assigned projects.

6. UI:

- Login page Bootstrap đơn giản.
- Base layout hiển thị user và role.
- Menu ẩn/hiện theo role.

7. Security:

- CSRF protection nếu có dùng Flask-WTF.
- Session cookie config từ config.py.
- Không log password.

8. Tests tối thiểu:

- login đúng/sai.
- inactive user không login được.
- VIEWER_ADMIN bị chặn route write.
- REPORTER không đọc được project chưa được gán.

Sau khi làm xong, cung cấp command chạy test và cách tạo user admin seed để login.
