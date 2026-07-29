# StarX production deployment (Ubuntu 24.04 LTS)

This is the authoritative production topology. It supports Ubuntu 24.04 LTS,
Docker Engine 26+ with Compose v2.24+ (healthcheck conditions and secrets),
and Python 3.12 inside the reviewed application image.

```text
Internet -> Nginx + Certbot (host) -> 127.0.0.1:6655 -> Compose web
host PostgreSQL <------------------------------------ Compose migrate/web/worker/Beat
Compose Redis (private bridge, authenticated, AOF) <- Compose web/worker/Beat
external S3-compatible private bucket <------------- Compose web/worker
```

Cloudflared is not production ingress. The legacy `.env.docker.example` is a
non-production migration notice only.

## Host preparation

Install Docker Engine/Compose from Docker's supported Ubuntu instructions, then
install host services:

```bash
sudo apt update
sudo apt install -y postgresql postgresql-contrib nginx certbot python3-certbot-nginx
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

Do not expose PostgreSQL, Redis, or port 6655 in the firewall. Create an
application-only PostgreSQL role/database, restrict PostgreSQL to localhost or
the Docker host gateway as selected, and grant no superuser/createdb/createrole
privileges. Keep the PostgreSQL URL only in the protected secret file.

Create `/srv/starx-report/secrets` as described in [secrets/README.md](secrets/README.md).
Generate secret values with a password manager or `openssl rand -base64 48`; do
not place them in shell history, Git, Compose environment files, or logs.

## S3-compatible storage

Provision one private bucket and a least-privilege credential limited to the
StarX bucket/prefix. Require TLS endpoint, bucket, region, access key and
secret key. Configure bucket CORS only for the explicit HTTPS Nginx origin,
with `POST, PUT, HEAD` and `Content-Type, x-amz-meta-sha256`; never use wildcard
origins. Define lifecycle/retention/versioning with the storage provider.
Provider durability and backup replication are external operational decisions;
this repository does not implement object-store backups.

## Immutable release procedure

Every release is a reviewed Git commit. Build and push an immutable image tag
such as `registry.example.invalid/starx-report:<full-git-sha>`; record both the
Git SHA and registry image digest in the release ticket. Do not use `latest` as
the only deployment or rollback point. The Dockerfile currently uses the valid
`python:3.12-slim` tag because a registry digest was not verified in this repo;
pin its reviewed digest as a release-gate action.

On the host, create a protected Compose environment file with non-secret
values: `APP_IMAGE`, `SECRETS_DIR`, `STORAGE_ENDPOINT_URL`, `STORAGE_BUCKET`,
`STORAGE_REGION`, `STORAGE_CORS_ALLOWED_ORIGINS`, and `TRUSTED_HOSTS`. Use
`docker compose --env-file /etc/starx-report/compose.env config` before every
release. Never copy `.env.example` unchanged into production.

`migrate` is the sole migration owner. `docker compose up -d` runs it once;
web, worker and Beat have `service_completed_successfully` dependencies and
therefore fail closed if migration fails. Normal startup never seeds users or
permissions. Bootstrap a first admin only via a separately approved, audited
one-shot command after migration; never put its password in Compose secrets.

## Nginx and TLS

### Private media cache

Before deploying the Compose change, create the writable host directory owned
by the account that runs Docker:

```bash
sudo install -d -m 0750 -o starxreport -g starxreport /opt/starxtech/cache/media
```

The web container alone mounts this path at `/app/cache/media`. Keep the Nginx
location in `deploy/nginx/starx-report.conf` internal with the exact trailing
slash pair `location /_protected_media_cache/` and
`alias /opt/starxtech/cache/media/`; do not add a public location or a global
Cache-Control header there. Flask authorises every request before issuing
`X-Accel-Redirect` and sets the media-specific cache policy itself.

After release, run `flask media-cache-cleanup --dry-run` from the web container
and only use `--apply` after reviewing its counters.

Install [deploy/nginx/starx-report.conf](deploy/nginx/starx-report.conf) after
replacing the example hostname, run `sudo nginx -t`, enable the site, then run
`sudo certbot --nginx -d report.example.invalid` using the real hostname.
Nginx is the single trusted proxy hop and forwards only to `127.0.0.1:6655`.

## Verification and monitoring

Before production: deploy the immutable image to staging with real PostgreSQL,
Redis and a non-production S3 bucket; verify migration, `/healthz`, worker
`inspect ping`, Beat schedule, direct upload, derivatives, bulk ZIP cleanup,
and backup restore. In production, run the same non-destructive checks plus
[PRODUCTION_SMOKE_TEST.md](PRODUCTION_SMOKE_TEST.md). Inspect `docker compose
ps`, `docker compose logs web worker scheduler`, Nginx access/error logs, and
`journalctl -u starx-report-backup.service`.

## Backup, restore, rollback, and disaster recovery

The host timer examples under `deploy/systemd/` run `scripts/backup_db.sh`.
Store encrypted PostgreSQL backups and a configuration inventory (image tag,
digest, commit, Compose env variable names, secret location metadata) off-host;
the inventory must not contain plaintext secrets. Test restore into an isolated
database before declaring a backup usable. `scripts/restore_db.sh` is a manual,
destructive restore tool and must run only against an explicitly selected empty
or recovery database.

- Deleted web/worker containers lose only their filesystem and temporary jobs;
  PostgreSQL, S3 objects and Redis named volume survive.
- Lost Redis data can lose queued tasks/results/rate-limit counters. Re-run the
  tracked reconciliation after recovery; do not assume every queued job is
  recoverable.
- Lost VPS disk loses host PostgreSQL and local Redis/Compose state unless the
  off-host backup/release record is available.
- Lost PostgreSQL host data requires verified database restore before starting
  web/worker. S3 alone cannot reconstruct metadata.
- S3 outage leaves metadata available but uploads/downloads/derivatives fail;
  do not substitute fake/local storage.
- Git remote outage does not block rollback only if immutable images and
  release metadata were retained; it blocks rebuilds otherwise.

Rollback means selecting the recorded prior immutable image, verifying its
database compatibility, restoring/rolling back the database only with an
approved migration plan, then `docker compose up -d`. Recovery ownership is:
incident lead freezes writes, DBA restores/verifies PostgreSQL, platform owner
restores secrets/release metadata and S3 access, then application owner starts
the release and validates health/worker/Beat.

To install the tracked backup timer on a real target (do not run these on a
workstation), copy `deploy/systemd/backup.env.example` to
`/etc/starx-report/backup.env` with mode 0600, copy the service/timer to
`/etc/systemd/system/`, then run `sudo systemctl daemon-reload` and `sudo
systemctl enable --now starx-report-backup.timer`. Confirm with `systemctl
list-timers starx-report-backup.timer` and test a restore in isolation.
