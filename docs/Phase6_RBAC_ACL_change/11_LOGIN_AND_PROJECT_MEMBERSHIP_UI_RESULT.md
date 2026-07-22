# Phase 6.2.1 — Login landing and Project Membership UI

Successful login now lands on `/modules`, unless a safe `next` URL is supplied. This prevents Media-only and Partner-only users from being sent to the Reports dashboard and receiving a 403. Users without any module still see the module empty state.

Project membership administration now lists only active memberships for the selected project. Administrators add an active user through the “Thêm thành viên dự án” modal, select a Vietnamese project preset, and may adjust the Vietnamese capability checkboxes. Existing rows open the same edit experience; “Bỏ khỏi dự án” posts a CSRF-protected deactivation, so the membership can be re-added later without hard deletion.

Preset labels are Vietnamese: Người xem dự án, Người lập báo cáo, Người biên tập báo cáo, Quản lý hồ sơ dự án, Điều phối vấn đề, and Chủ trì dự án. Capability labels cover Dự án, Báo cáo, Vấn đề, Danh mục báo cáo, and Hồ sơ. A zero-capability save is rejected and the explicit removal action must be used instead.

The UI and backend continue to use project membership flags, not global PROJECT_MANAGER/REPORTER. Folder ACL, album ACL, Company Media, Partner, Report Attachments, and storage behavior are unchanged. This phase does not add file-level ACL, ZIP download, storage namespace changes, or per-user global permissions.
