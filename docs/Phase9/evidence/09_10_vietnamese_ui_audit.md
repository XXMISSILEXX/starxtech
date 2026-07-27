# Step 9.10 — Vietnamese UI audit

- Internal ProjectUpdate, contractor role, and assignment status enum values remain unchanged.
- Shared UI filters provide Vietnamese labels and localized timestamps.
- ProjectUpdate form/timeline, assignment modal/list, contractor dashboard, and scoped dashboard use Vietnamese user-facing wording.
- Source scan test rejects raw update enum display and verifies the shared filters are used.
- API keys, HTML data identifiers, option values, audit actions, and test fixtures are deliberate technical exceptions.
- All visible date fields in templates now use the shared `data-vn-date`
  component with `dd/mm/yyyy` placeholder. Database dates and API ISO keys are
  unchanged; the backend accepts the Vietnamese form value without swapping
  day and month.
- Partner date controls were migrated from the older DD-MM-YYYY convention to
  DD/MM/YYYY so the user-facing date contract is consistent across modules.
- The `reports` module display label is **Quản lý dự án**; `Báo cáo ngày`
  remains the name of the report feature and internal module identifiers are
  unchanged.
