# Docker production release gate

This file supplements the authoritative [Ubuntu deployment guide](DEPLOY_UBUNTU.md).
It is the only supported Compose path: `migrate`, `web`, `worker`, `scheduler`,
and authenticated persistent `redis`; PostgreSQL, Nginx, Certbot, firewall and
backup timer are host services; user content is external S3-compatible storage.

Before release, provide protected secret files named `app_secret_key`,
`database_url`, `storage_access_key_id`, `storage_secret_access_key`, and
`redis_password`. Provide a protected non-secret Compose env file with:

```env
APP_IMAGE=registry.example.invalid/starx-report:FULL_GIT_SHA
SECRETS_DIR=/srv/starx-report/secrets
STORAGE_ENDPOINT_URL=https://object-storage.example.invalid
STORAGE_BUCKET=replace-with-private-bucket
STORAGE_REGION=replace-with-region
STORAGE_CORS_ALLOWED_ORIGINS=https://report.example.invalid
TRUSTED_HOSTS=report.example.invalid
```

Run this release gate on staging first:

```bash
docker compose --env-file /etc/starx-report/compose.env config
docker compose --env-file /etc/starx-report/compose.env pull
docker compose --env-file /etc/starx-report/compose.env up -d
docker compose ps
docker compose logs --tail=100 migrate web worker scheduler
```

`migrate` is a one-shot dedicated owner. Do not run `flask db upgrade` from
web/worker replicas and do not set `RUN_MIGRATIONS`, `RUN_SECURITY_AUDIT`, or
`SEED_ADMIN`: production entrypoint rejects them. The app validates APP_ENV,
secrets, PostgreSQL, Redis/Celery, S3, cookies and proxy hosts before serving.

The worker consumes `media_image`, `media_video`, `storage_cleanup`, and
`bulk_download`. Beat schedules expired report-upload cleanup hourly, media-job
reconciliation every 15 minutes, and expired bulk-download cleanup hourly.
Redis is private, password-protected, AOF-persistent, and intentionally has no
host port. Its loss is a recovery event, not a reason to bypass S3/Redis guards.

Record the Git commit, immutable image tag and resolved image digest for each
release. Inspect build context before build; `.dockerignore` excludes Git,
audit material, local env/secrets, backups including `claude-partial-audit-backup/`,
caches and tests. Never rely on mutable `latest` for rollback.
