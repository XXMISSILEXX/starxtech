# Phase 1 — Storage & batch foundation result

## Summary

Implemented an isolated storage foundation for future Project Documents and Company Media. No UI, folder, album, ACL, Celery, derivative, or domain-file record was added. Existing local ReportAttachment and Partner modules remain unchanged.

## Files and migration

- New models: `app/models/storage.py`
- New storage package: `app/storage/{providers,services,validation,keys,exceptions}.py`
- Config/security audit integration: `app/config.py`, `app/security.py`, `app/__init__.py`, `app/cli.py`
- Tests: `tests/test_storage_foundation.py`
- Migration: `migrations/versions/20260720_0010_add_storage_batch_foundation.py`

## Models and config

Models: `StorageObject`, `UploadBatch`, `UploadBatchItem`, with additive checks/indexes/unique constraints. Config adds `STORAGE_PROVIDER`, bucket/endpoint/region/credentials/prefix, upload/download TTL, per-type limits, batch limits and pending age. Signed URLs are never persisted.

## Provider and services

`FakeStorageProvider` is in-memory and makes no network calls. `DisabledStorageProvider` fails safely. `S3StorageProvider` uses boto3 only when configured and installed; it signs direct POST/GET but no tests call it.

Services implement server-generated UUID keys, per-item batch presign with partial reject, per-item HEAD-verified completion, owner/admin Phase-1 authorization hook, short signed download, and dry-run-default pending cleanup. Completion does not create domain files or enqueue workers.

## Object key and flows

Example key: `originals/2026/07/<uuid>.pdf`, optionally `<prefix>/originals/...`; it contains no original filename/project/user/client id. Batch presign creates one pending object/key/policy per accepted file; completion verifies HEAD size/type/checksum where provider exposes it, then activates metadata and updates batch state.

## Known limitations / Phase 2

No S3 integration test, no public routes, no audit event yet, no ACL/domain target validation, no storage quota/rate limiter, no multipart upload, and no worker. Phase 2 adds Redis/Celery, durable processing jobs/derivatives and cleanup/reconcile scheduling. Before Phase 3, target folder/album ACL must replace the owner/admin hook.

## Verification and compatibility

Run `python -m compileall app tests`, `pytest -q`, `flask routes`, and `flask security-audit`. Apply the migration only through an approved local/deploy runbook (`flask db upgrade`); it was not run by this implementation. ReportAttachment/Daily Reports and Partner Management were not changed.
