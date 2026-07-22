# Phase 6.2 — Three-layer authorization

Authorization is split into three independent decisions.

1. **Global RBAC** maps one canonical `users.role_id` to global permissions. It is used for administration, Users/Roles, Partner Management and Company Media. Custom global roles are supported end-to-end; `users.role` is a compatibility mirror only.
2. **Project Membership** (`project_users`) decides project visibility and project actions. `project_role_code` is an admin-facing preset; capability flags are authoritative. This replaces global `PROJECT_MANAGER` and `REPORTER` logic.
3. **Resource ACL** further restricts a project-document folder/subtree or a Company Media album. Files inherit their folder and media inherit their album.

Examples: a media-only role sees Company Media; a Partner+Media role sees those two cards; a reporter membership for project A can create reports only in A; a document-controller membership for B can upload only in B; a legal folder still requires folder ACL; an album such as Flamingo still requires album ACL when restricted.

Module switch uses the union of applicable layers: report/document cards require an active membership (or admin policy); Partner uses global RBAC; Company Media uses global RBAC or an active album ACL. Backend routes always repeat the relevant checks.

Migration removes the legacy `users.role` CHECK constraint, retains it only as a non-authoritative mirror, converts old project assignments to capability flags, maps old `PROJECT_MANAGER`/`REPORTER` users to `PROJECT_STAFF`, and hides their old global roles from normal operation. Take a database backup before `flask db upgrade`.

Not included: direct per-user global permissions, global multi-role assignment, custom project roles, file/media-level ACL, ZIP download, or storage namespace changes.
