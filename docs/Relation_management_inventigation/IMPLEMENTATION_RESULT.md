# Partner & Company lifecycle implementation

## Implemented

- Added shared `active`, `archived`, and `all` lifecycle scopes for Partner and Company lists. Invalid `status` values fall back to `active`.
- Added canonical POST routes: `/partners/<id>/archive`, `/partners/<id>/restore`, `/partner-companies/<id>/archive`, and `/partner-companies/<id>/restore`. The previous `/deactivate` routes remain compatibility aliases.
- Archived Partner and Company details remain readable. Archive only accepts active records; restore only accepts archived records.
- Added dangerous `partners.restore` and `partner_companies.restore` permissions. ADMIN receives them through `sync-permissions --apply-defaults`; viewer and reporting roles do not.
- Added lifecycle audit actions: `partner.archive`, `partner.restore`, `company.archive`, and `company.restore`, with non-secret lifecycle snapshots.
- Partner create forms show only active Company/Department entries. Edit forms retain the currently assigned inactive Company/Department and mark it `Đã lưu trữ`; validation prevents selecting another inactive entry.
- Archived Company pages show an archived warning. Department and Relationship mutations are rejected with HTTP 400 while read-only views remain available. Archiving a Company does not archive its Partners.
- Added lifecycle tabs, archived badges, and RBAC-controlled archive/restore controls. Relationship and Department business-delete wording now uses `Lưu trữ`.

## Files changed

- `app/partners/lifecycle.py`
- `app/partners/routes.py`, `app/partners/services.py`
- `app/partner_companies/routes.py`
- `app/partner_relations/routes.py`
- `app/permissions/registry.py`
- Partner, Company, Department, and Relationship templates

## Verification

Run:

```bash
python -m compileall app tests
pytest -q
flask sync-permissions
flask sync-permissions --apply-defaults
flask security-audit
```

No migration is required: the existing `is_active` and `deleted_at` fields provide the lifecycle state. Department/Relationship restore and archived-list UI are intentionally deferred.
