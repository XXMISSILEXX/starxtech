# Implementation options

| Option | Ordinary retry | Race-safe | Counter-safe | Assessment |
| --- | --- | --- | --- | --- |
| Frontend-only reuse | Sometimes | No | No | Queue is transient; retry UI creates new session; direct calls/tabs bypass it. |
| Application query-first | Yes sequentially | No | No | A/B can both see no item. Current code does not even query old item. |
| Session row lock only | Yes | Incomplete | Usually | Works only if every current/future path locks; no declarative invariant. |
| PostgreSQL `INSERT ... ON CONFLICT` | Yes | Yes | Yes if designed carefully | Strong but more dialect-specific for multi-row item/object flow. |
| Unique constraint + `IntegrityError` savepoint | Yes | Yes | Yes | Recommended and matches SQLAlchemy report patterns. |

## Recommendation

Adopt **unique constraint + SQLAlchemy savepoint/IntegrityError replay**, plus short `FOR UPDATE` on session for counters. Existing report creation already uses `begin_nested`, row locks and `IntegrityError` (`app/reports/services.py:193-230`). This needs no idempotency table, browser hash, new service, or queue.

`ON CONFLICT` can be reconsidered only if an implementation spike is demonstrably simpler. Never sign before canonical persistence. Frontend same-tab guard (`app/static/js/company-media-upload.js:276-281`) is useful UX but cannot be integrity control across tabs/reloads/timeouts.
