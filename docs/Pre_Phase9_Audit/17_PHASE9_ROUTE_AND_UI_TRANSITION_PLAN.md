# TARGET: route and UI transition plan

Current evidence: Reports module routes begin `/reports`, `/projects`, and `/api/projects/...`; module sidebar is request-first. Gap: no Today/customer/contractor routes.

Recommend additive Reports routes: `/reports/today`, `/reports/projects-contractors`, `/reports/admin-dashboard`, `/reports/config`; resource routes below `/reports/customers` and `/projects/<id>/contractors`. Keep existing dashboard/list/create/report URLs stable; use aliases/redirects only after automated bookmark tests. Breadcrumbs should preserve project/report context. Desktop and mobile use the same sidebar contract from `get_sidebar_items`; do not create a global fourth navigation system.

Migration impact none unless route data needs new tables. RBAC impact new permissions control visibility and backend. Test impact direct routes, module switching, mobile markup, legacy bookmarks. Compatibility impact existing reports nav remains functional.
