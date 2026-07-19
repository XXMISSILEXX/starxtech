# Future module permission matrix

Legend: **A** all scope, **P** assigned project, **O** own (pending business confirmation), **V** view only, **—** none. Every granted action still requires backend domain-scope check.

| Module / baseline actions | SUPER_ADMIN | READONLY_ADMIN / current VIEWER_ADMIN | ADMIN | PROJECT_MANAGER | REPORTER |
|---|---:|---:|---:|---:|---:|
| Daily reports: view/create/edit/delete | A | V | A | P / P / P / P(delete policy) | P / P / O(or P) / — |
| Persistent issues: view/create/edit/close/delete | A | V | A | P / P / P / P / P(delete policy) | V / — / — / — / — |
| Projects/categories/assignments | A | V | A (assignment policy) | categories P if granted | — |
| Partners/companies/relationships | A | V if ticked | A | V if ticked; no write default | — |
| Partner fields/collections | A | — | A | — | — |
| Project documents metadata | A | V if ticked | A | P | O or P if ticked |
| Project documents upload/download | A | download if ticked | A | P | upload/download O or P if ticked |
| Document folders/settings/share | A | — | folders A; settings/share policy | folders P if granted | — |
| Event albums/photos view/upload/edit/delete/download | A | V/download separately ticked | A | as explicitly ticked (normally department scope) | own upload/edit; view/download only if ticked |
| Event album/settings management | A | — | A | — | — |
| Users/project role assignments | A | V | explicitly ticked | — | — |
| Roles/permissions/system settings | A | — | — default | — | — |

Default modules must be deny-by-default. `READONLY_ADMIN` is the future business label; the existing persisted code is `VIEWER_ADMIN` and should remain mapped until a deliberate compatibility migration is approved.
