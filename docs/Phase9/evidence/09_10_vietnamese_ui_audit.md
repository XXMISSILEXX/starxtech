# Step 9.10 — Vietnamese UI audit

- Internal ProjectUpdate, contractor role, and assignment status enum values remain unchanged.
- Shared UI filters provide Vietnamese labels and localized timestamps.
- ProjectUpdate form/timeline, assignment modal/list, contractor dashboard, and scoped dashboard use Vietnamese user-facing wording.
- Source scan test rejects raw update enum display and verifies the shared filters are used.
- API keys, HTML data identifiers, option values, audit actions, and test fixtures are deliberate technical exceptions.
- All editable date fields use native `type="date"` controls with ISO submit
  values. The custom `data-vn-date`, report-date parser, Flatpickr dependency,
  and related JavaScript test were removed. Database values and API keys remain
  ISO; read-only text continues to use the Vietnamese `DD/MM/YYYY` formatter.
- Daily Report and Project Update future-date validation uses the shared
  `Asia/Ho_Chi_Minh` date helper and returns Vietnamese field errors without
  depending on the browser locale.
- Partner date controls and dynamic date fields also use native ISO values.
- The `reports` module display label is **Quản lý dự án**; `Báo cáo ngày`
  remains the name of the report feature and internal module identifiers are
  unchanged.
