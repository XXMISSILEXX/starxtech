# Test plan

## Automated lifecycle tests

- Partner: archive, exclusion from active, inclusion in archived/all, restore,
  archived detail, audit old/new state, view-only UI/POST denial.
- Company: archive/restore, active/archived/all filters, no Partner cascade,
  archived Company badge on Partner detail, create Partner cannot select
  inactive Company, edit existing Partner retains inactive current Company.
- Department: Company inactive rejects new/edit; if public archive/restore is
  implemented, test active/archived/all and historical Partner department badge.
- Relationship: archive excludes active tree/list, restore only for permission;
  confirm inactive Partner/Company is not rendered in active tree.

## RBAC/security

- SUPER_ADMIN bypass; ADMIN archive/restore according registry.
- VIEWER_ADMIN can view active/archived/all but sees no mutation controls and
  receives 403 on POST.
- PROJECT_MANAGER and REPORTER have no default Partner module access.
- Missing `*.delete` or `*.restore` yields 403 and leaves DB unchanged.
- All archive/restore forms include CSRF; CSRF-enabled integration test rejects
  missing/invalid token. Assert no mutation GET route exists.

## Manual and regression checklist

- Search, status filter and pagination preserve each other.
- Archived badges/messages use “Lưu trữ”, never “Xóa” for business records.
- Existing create/edit Partner, Company, Department, Relationship, cycle checks,
  dynamic fields and relationship tree remain green.
- Verify audit actor, action, entity type/id, old/new lifecycle snapshot and
  human-readable name. Verify no hard delete and no S3/storage impact.
