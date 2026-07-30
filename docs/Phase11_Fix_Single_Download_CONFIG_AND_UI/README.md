# Phase 11 — Independent verification: Company Media download, limits, and UI

## Objective

Independently verify the earlier Company Media audit before any repair work is approved. This phase examines source code, existing safe tests, and an isolated SQLite in-memory/FakeStorage check. It does not alter application behavior.

## Scope

- Company Media single download, bulk download, preview/HEIC, upload limits, upload-session accounting, UI, and related security boundaries.
- Comparison with Project Documents and Daily Report downloads.
- Planning only; no application, JavaScript, template, config, test, migration, database, S3, Compose, Nginx, deployment, or Git changes.

## Read-only/safe verification rules

- No production or local application database was queried or modified.
- No S3 request, presign request, upload, delete, migration, or deployment was performed.
- The only runtime check used `sqlite:///:memory:` and `FakeStorageProvider`; it created and dropped its own in-memory schema in one process.
- Existing pytest coverage ran against the repository's in-memory fixture only.

## Documents

- [Verification report](VERIFICATION_REPORT.md) — findings, competing hypotheses, and conclusions.
- [Evidence map](EVIDENCE_MAP.md) — traceable code/test evidence for each finding.
- [Proposed fix plan](PROPOSED_FIX_PLAN.md) — phased repair plan only; no patch.
- [Test and rollout plan](TEST_AND_ROLLOUT_PLAN.md) — future verification and rollout sequence only.

## Implementation status

- Phase 1: completed in the repository before this implementation.
- Phase 2: completed — dedicated Company Media resolved limits, structured
  upload errors, server-rendered public limits payload, and compatible JS
  consumption are implemented. See [Phase 2 implementation report](PHASE2_IMPLEMENTATION_REPORT.md).
- Phase 3A: completed — Company Media selected/max, client-side pre-validation,
  batch preview, accessible/mobile queue states, and structured error rendering
  are implemented. See [Phase 3A implementation report](PHASE3A_IMPLEMENTATION_REPORT.md).
- Phase 3B remains intentionally out of scope: the approved session/retry
  idempotency lifecycle decision and any migration it requires.

## Original verification outcome

The Company Media single-download contract mismatch is confirmed. The Project Documents menu single-download route has the same mismatch. The retry/session accounting issue is also confirmed by an isolated runtime check. HEIC is not on the original-download code path but can independently affect derivative-based preview.
