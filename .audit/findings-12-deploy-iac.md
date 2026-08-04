# Findings — Docker / Deploy / IaC

## Summary

- The tracked effective Docker deployment is `web` behind a Cloudflare Tunnel, not the decided Nginx/Certbot + Docker (web/Celery/Redis) target. It is not runnable as committed: `APP_ENV=production` is paired with an unset `STORAGE_PROVIDER`, which defaults to `fake` and is rejected at app factory startup.
- No tracked Compose, systemd, entrypoint, or deployment-document path supervises Redis or Celery. `scripts/start-media-worker.sh` is only a manually runnable wrapper.
- The repository has no Git remote and the Docker image is built locally from the checkout; there is no documented registry, immutable promoted artifact, or recovery source of truth.
- Both Compose files were read and diffed line-by-line. The backup preserves finite application defaults for all omitted `DAILY_REPORT_*` controls, but changes the limiter from shared Redis to per-process memory and can therefore approximately double effective limits.
- Files read in full: all primary files and every tracked file in `deploy_backup_2026-07-14_142253/` (7 files), plus the permitted cross-references. `claude-partial-audit-backup/` was not read, searched, or modified.

## Effective deployment architecture

The current tracked Docker path is:

```text
Internet -> Cloudflare Tunnel -> cloudflared container -> web/Gunicorn:6655
                                                     -> PostgreSQL host Unix socket
```

`docker-compose.yml:3-145` defines only `web` and `cloudflared`; `web` has no published host port (`:76-82`) and both services share the private bridge `appnet` (`:97-98`, `:124-125`, `:146-148`). `DOCKER_DEPLOY.md:5-13` documents this same tunnel architecture.

This is not the decided production target of host Nginx, Certbot, PostgreSQL, firewall/backup timer; Docker Flask/Gunicorn, Celery, Redis; and external S3-compatible storage. `DEPLOY_UBUNTU.md` instead documents a separate bare-metal Gunicorn/Nginx/Certbot deployment (`:83-156`) with cron backups (`:158-182`), but no Docker web/Celery/Redis services or object-storage configuration. Its `git pull` update path (`:184-192`) cannot operate from the current repository because `git remote -v` returned no remotes.

## Live versus backup Compose comparison

The only line-level differences from `git diff --no-index -- docker-compose.yml deploy_backup_2026-07-14_142253/docker-compose.yml` are shown below. All other Compose controls are identical.

| Control | Live Compose | Backup Compose | Effective consequence |
|---|---|---|---|
| `DAILY_REPORT_DIRECT_UPLOAD_ENABLED` | `"true"` (`docker-compose.yml:31`) | absent | Defaults to `true` (`app/config.py:49`); no loss of a bound. |
| `DAILY_REPORT_MAX_FILES` | `"30"` (`:32`) | absent | Defaults to 30 (`app/config.py:50`). |
| `DAILY_REPORT_MAX_FILES_PER_SECTION` | `"3"` (`:30`) | absent | Defaults to 3 (`app/config.py:51`). |
| `DAILY_REPORT_MAX_FILE_BYTES` | `"26214400"` / 25 MiB (`:33`) | absent | Defaults to 25 MiB (`app/config.py:52`). |
| `DAILY_REPORT_MAX_TOTAL_BYTES` | `"314572800"` / 300 MiB (`:34`) | absent | Defaults to 300 MiB (`app/config.py:53`). |
| `DAILY_REPORT_UPLOAD_CONCURRENCY` | `"3"` (`:35`) | absent | Defaults to 3 (`app/config.py:54`). |
| `DAILY_REPORT_PRESIGN_TTL_SECONDS` | `"900"` (`:36`) | absent | Defaults to 900 seconds (`app/config.py:55`). |
| `DAILY_REPORT_SESSION_TTL_SECONDS` | `"86400"` (`:37`) | absent | Defaults to 86,400 seconds (`app/config.py:56`). |
| Rate-limit storage URI | `redis://redis:6379/2` (`:43`) | `memory://` (`backup/docker-compose.yml:35`) | Live intends shared storage but supplies no `redis` service; backup works without Redis but gives each Gunicorn process an independent counter. |
| Storage provider | neither file sets `STORAGE_PROVIDER`, S3 endpoint/bucket/credentials | same | Config defaults to `fake` (`app/config.py:66-71`). With `APP_ENV=production`, this stops startup (DEPLOY-001). |
| Upload/finalize limits | explicit eight values above | absent | Backup uses the same finite Config fallbacks; this divergence is documentation/drift, not an unbounded-upload vulnerability. |
| Gunicorn workers / threads | 2 / 2 (`docker-compose.yml:54-55`) | 2 / 2 (`backup:45-46`) | Equal concurrency in the two files. |
| Debug/development | `APP_ENV=production`, `FLASK_DEBUG=false` (`:15-16`) | same (`backup:15-16`) | Debug remains disabled if the exact production mode is retained. |
| Secrets/defaults | three Docker secret files; seed enabled=false; metadata defaults `admin`, `admin@example.com`, `System Admin` (`:21-23`, `:58-69`) | same (`backup:21-23`, `:49-60`) | Secret values are not in Compose. If seed is manually enabled, the default account identifiers apply. |
| Port exposure | only `expose: 6655`; localhost `ports` mapping is commented (`:76-82`) | same (`backup:67-73`) | No direct public backend listener from this Compose file. |
| Network isolation | private bridge `appnet`; web and cloudflared only (`:97-98`, `:124-125`, `:146-148`) | same (`backup:88-89`, `:115-116`, `:137-139`) | Isolation is present, but it also means `redis` cannot exist unless an external container is manually attached to the Compose-created network. |
| Volume persistence | host bind mounts for uploads, tmp, and read-only PostgreSQL Unix socket (`:71-74`) | same (`backup:62-65`) | Uploads/tmp survive container deletion on that VPS; database is host-managed. No Docker named volume is used. |
| Restart policies | `unless-stopped` on web and cloudflared (`:11`, `:109`) | same (`backup:11`, `:100`) | Both restart after daemon/host restart unless explicitly stopped; no worker exists to restart. |
| Health checks | web HTTP `/healthz` healthcheck (`:84-95`); cloudflared waits for it (`:120-122`) | same (`backup:75-86`, `:111-113`) | Compose can gate tunnel startup on web health, but there is no Redis/Celery health signal. |

### Effective Gunicorn rate-limit multiplier

`gunicorn.conf.py:5-8` selects two `gthread` worker **processes** with two threads each from the explicit Compose values. Threads in a single process share that process's in-memory limiter; processes do not. Therefore, under the backup's `memory://` URI, an endpoint set to `5 per minute` is effectively enforceable at approximately **10 requests per minute per limiter key** if requests reach both workers: `2 processes × 5`; the two threads do not add another multiplier.

With a reachable shared Redis limiter, the intended multiplier is **1×** across the two workers. The live URI does not prove shared enforcement: no `redis` service, external network, or `extra_hosts` is declared (`docker-compose.yml:3-148`). Per Foundation-A1's verified limiter behavior, an unreachable Redis server fails rate-limited requests closed at request time rather than falling back to memory.

## Production environment inventory

This is the required production-variable inventory; it is not a new `.env.example` file.

| Area | Hardcoded/current value | Required production decision |
|---|---|---|
| Domain / trusted host | `smart-home.starxvietnam.com` for `TRUSTED_HOSTS` and `PUBLIC_HOSTNAME` (`docker-compose.yml:51-52`) | Set deployment-specific public hostnames; do not retain a tracked production domain. |
| Host IP / storage CORS | `http://192.168.1.159:5666` fallback (`app/config.py:57`; mirrored in `app/__init__.py:35`) | Set explicit HTTPS production origins; remove the LAN fallback from production effective config. |
| Object storage provider | Compose does not set it; Config default is `fake` (`app/config.py:66`) | `STORAGE_PROVIDER=s3`. |
| S3/MinIO endpoint / region / bucket / prefix | endpoint and region unset; bucket defaults `starx-local`; prefix empty (`app/config.py:67-72`) | Set provider endpoint, region, bucket, prefix, and allowed CORS origins. |
| S3 credentials | `STORAGE_ACCESS_KEY_ID` / `STORAGE_SECRET_ACCESS_KEY` are accepted through `*_FILE` (`app/config.py:70-71`) but no Compose secrets map them | Supply least-privilege production credentials as Docker/host secrets. |
| Database | secret path `/srv/construction_relation_management/secrets/database_url`; app sample fallback `postgresql+psycopg://starx:starx@127.0.0.1:5432/starx_daily_report` (`docker-compose.yml:137-138`, `app/config.py:38-41`) | Set actual host socket/TCP URL, host, database, user, TLS/socket policy, and secret rotation ownership. Docker guide's illustrative socket URL names user `ubuntu` and DB `construction_relation_management` (`DOCKER_DEPLOY.md:33-42`). |
| Rate-limit Redis | `redis://redis:6379/2` (`docker-compose.yml:43`) | Deploy an authenticated/persistent Redis service and set a reachable URI; choose TLS/auth and network scope. |
| Celery broker/result Redis | Compose omits both; defaults are `redis://localhost:6379/0` and `/1` (`app/config.py:99-100`) | Set reachable broker/result URIs (normally the deployed Redis) and worker supervision. |
| Cloudflare tunnel | latest image plus token secret file at `/srv/.../cloudflare_tunnel_token` (`docker-compose.yml:107`, `:113-115`, `:143-144`) | Either retire this legacy ingress for Nginx/Certbot target or pin the image and manage the tunnel token/config as an external secret. |
| Ports | app/container `6655` (`docker-compose.yml:19`, `:76-77`); Ubuntu guide Gunicorn `127.0.0.1:8000`, Nginx `80` (`DEPLOY_UBUNTU.md:100`, `:123-137`) | Choose one ingress topology and declare firewall/listener ownership. |
| Proxy hops | `TRUST_PROXY_HOPS=1` (`docker-compose.yml:50`) | Match the selected proxy chain; Nginx and Cloudflare paths are not equivalent. |
| Cookie/security mode | `APP_ENV=production`, debug false, secure/HTTP-only/Lax cookies (`docker-compose.yml:15-16`, `:39-41`) | Retain for HTTPS production and make `APP_ENV` exact/loudly validated. |
| Admin seed identifiers | `admin`, `admin@example.com`, `System Admin`; seed false (`docker-compose.yml:58-64`) | Use an intentional bootstrap identity, one-time secret, and separate provisioning job. |
| Persistent paths | `/srv/construction_relation_management/uploads`, `/srv/.../tmp`, `/var/run/postgresql` (`docker-compose.yml:71-74`) | Define ownership, backup, monitoring, and restore scope for each host path. |

## Findings

### DEPLOY-001 — Current production Compose cannot pass application startup storage validation

- **Severity:** Critical
- **Confidence:** High
- **CWE:** CWE-1188 (Insecure Default Initialization of Resource)
- **Classification:** Phase 11 blocker; reliability gap.
- **Location:** `docker-compose.yml:14-64`; `app/config.py:66-71`; `app/security.py:61-82`; `app/__init__.py:46-48`.
- **Reachability:** Deterministic for a container started from this tracked Compose without an out-of-band environment injection. It occurs before Gunicorn can serve any request.
- **Real configuration quote:**

  ```yaml
  APP_ENV: production
  ```

  ```python
  STORAGE_PROVIDER = os.getenv("STORAGE_PROVIDER", "fake")
  ```

  ```python
  if provider == "fake":
      errors.append("STORAGE_PROVIDER=fake is not allowed in production")
  ```
- **Effective runtime behavior:** Compose sets production mode but neither `STORAGE_PROVIDER` nor S3 endpoint, bucket, or credentials. The Config value becomes `fake`; `create_app()` raises `RuntimeError` when it receives the production-configuration error. The Compose healthcheck cannot become healthy, so `cloudflared`'s `depends_on: service_healthy` prevents tunnel startup.
- **Impact:** The documented Docker deployment is unavailable as committed. Any attempt to make it start by changing only `APP_ENV` risks bypassing the production checks documented in CLI-001 rather than configuring storage correctly.
- **Remediation direction:** Define the selected S3-compatible storage provider, bucket, endpoint/region/prefix, CORS origin policy, and secret-file credentials in the deployment configuration. Make this a preflight/one-shot validation before ingress is enabled.

### DEPLOY-002 — Redis and Celery are not supervised in the actual tracked deployment

- **Severity:** High
- **Confidence:** High for the tracked repository; Medium for an undisclosed host-side service.
- **CWE:** CWE-400 (Uncontrolled Resource Consumption) where unprocessed sessions/jobs accumulate.
- **Classification:** Phase 11 blocker; reliability gap.
- **Location:** `docker-compose.yml:3-148`; `docker-entrypoint.sh:51-75`; `scripts/start-media-worker.sh:4-19`; `DEPLOY_UBUNTU.md:83-193`; `DOCKER_DEPLOY.md:54-114`.
- **Reachability:** All Docker-deployed users of rate-limited routes and all media-processing flows; no authenticated attacker action is required for the operational failure.
- **Real configuration quote:**

  ```yaml
  RATELIMIT_STORAGE_URI: redis://redis:6379/2
  ```

  ```bash
  exec python -m celery \
    -A app.celery_worker:celery_app worker \
    -Q media_image,media_video,storage_cleanup,bulk_download
  ```
- **Effective runtime behavior:** Both live and backup Compose define only `web` and `cloudflared`, no `redis` or worker service. The entrypoint runs only optional migrations/audit/seeding and then `exec "$@"`; it never invokes the worker wrapper. No committed systemd unit starts the wrapper; the Ubuntu service starts only Gunicorn. `DOCKER_DEPLOY.md` documents Compose web/tunnel operations, not a worker. Thus the wrapper is manual-only.
- **Impact:** A missing `redis` hostname makes all explicitly rate-limited endpoints fail closed when first checked. Celery broker/result defaults inside the web container to `localhost:6379/0` and `/1`, where Dockerfile starts no Redis. With no consuming worker: image derivatives and HEIC processing stay pending/queued indefinitely; no previews/thumbnails/video posters appear; queued Celery jobs remain queued. The legacy Celery bulk-ZIP path also remains pending, although Foundation-B proves current routes use the synchronous web-thread ZIP path instead. There is no beat schedule and cleanup/reconciliation tasks have no `.delay()` call sites; cleanup is manual CLI work, so pending/expired records accumulate if operators do not run it.
> **Outdated note:** The beat-schedule assertion became outdated on 2026-07-28: `app/celery_app.py` has `beat_schedule`; the remaining debt is DEPLOY-002 evidence that the `beat` service runs in production, not absence of automated cleanup.
- **Remediation direction:** Implement the chosen target as supervised Docker services for Redis and Celery, with health checks, authenticated/persistent Redis, `depends_on`/readiness, restart policy, and a defined cleanup scheduler or host timer. Alternatively remove/rework the unused asynchronous dependencies, but do not rely on a manual shell wrapper.

### DEPLOY-003 — There is no recoverable source or immutable deployment artifact path

- **Severity:** High
- **Confidence:** High
- **CWE:** Not applicable.
- **Classification:** Phase 11 blocker; reliability gap; outdated documentation.
- **Location:** `docker-compose.yml:5-9`; `DOCKER_DEPLOY.md:54-60`; `DEPLOY_UBUNTU.md:20`, `:184-192`; repository state from read-only `git remote -v`.
- **Reachability:** Operator/recovery scenario; affects the entire service after host, checkout, or artifact loss.
- **Real configuration quote:**

  ```yaml
  build:
    context: .
  image: construction-relation-management:2026.07.14
  ```

  ```bash
  sudo -u starxreport git pull
  ```
- **Effective runtime behavior:** Compose builds from the local checkout; the Docker guide explicitly calls `docker compose build --no-cache`. No remote registry is named, no digest is used for the application image, and `git remote -v` has no output. The `2026.07.14` image tag is a mutable local tag, not evidence of an immutable promoted artifact. The Ubuntu guide's `git pull` is therefore nonfunctional unless an untracked remote is added.
- **Impact:** If the checkout/VPS is lost, source, Docker build context, local image, host secret files, and any local-only database/upload backups are unavailable unless independently copied elsewhere. Container deletion alone does not delete host bind-mounted uploads/tmp or host PostgreSQL, but deleting the VPS disk loses them; deleting a Docker volume is not directly applicable because this Compose uses bind mounts, though any untracked named volume would be equally unrecoverable. External object storage loss makes stored source media/derivatives unavailable even if database metadata and containers survive; repo-host unavailability prevents redeploy/rebuild because there is no configured repository host.
- **Remediation direction:** Establish an access-controlled remote source repository, CI-produced immutable image digests in a registry, retained deployment manifests, tested encrypted off-host backups for database/uploads/secrets, and a documented restoration drill.

### DEPLOY-004 — Tracked backup Compose can weaken rate limiting and omit current deployment controls

- **Severity:** Medium
- **Confidence:** High
- **CWE:** CWE-770 (Allocation of Resources Without Limits or Throttling), limited to the approximately doubled limiter allowance.
- **Classification:** Deployment footgun; configuration drift.
- **Location:** `deploy_backup_2026-07-14_142253/docker-compose.yml:28-55`; `docker-compose.yml:28-64`; `gunicorn.conf.py:5-8`; `app/config.py:49-56`.
- **Reachability:** Any operator who invokes the tracked backup Compose file; then all callers of rate-limited endpoints are affected.
- **Real configuration quote:**

  ```yaml
  RATELIMIT_STORAGE_URI: memory://
  TRUSTED_HOSTS: ${TRUSTED_HOSTS:-}
  ```
- **Effective runtime behavior:** The backup has the same 2 worker × 2 thread Gunicorn configuration but a per-process memory limiter and an empty-default trusted-host variable. It omits all eight `DAILY_REPORT_*` values and `PUBLIC_HOSTNAME`. The report controls still fall back to finite Config limits, so this is not an unbounded-upload finding. The per-worker limiter does multiply the configured limit by about two, however, and the backup can accept an empty trusted-host set.
- **Impact:** A plausible operator error replaces intended cross-worker shared limiting with weaker per-worker limiting and loses current hostname/deployment settings without an obvious Compose error. The duplicate full deployment artifact increases configuration drift risk.
- **Remediation direction:** Remove or archive the runnable backup outside the deployment tree, or make it a non-runnable patch/documented historical artifact. Keep exactly one deployed Compose source and test a configuration fingerprint/preflight that asserts shared rate limiting and host policy.

### DEPLOY-005 — Mutable Cloudflared image can change the ingress binary without a reviewed configuration change

- **Severity:** Medium
- **Confidence:** High
- **CWE:** CWE-829 (Inclusion of Functionality from Untrusted Control Sphere).
- **Classification:** Deployment footgun; supply-chain hardening gap.
- **Location:** `docker-compose.yml:106-115`; `deploy_backup_2026-07-14_142253/docker-compose.yml:97-106`.
- **Reachability:** Every fresh pull/recreation of the tunnel container.
- **Real configuration quote:**

  ```yaml
  image: cloudflare/cloudflared:latest
  command: tunnel --no-autoupdate run
  ```
- **Effective runtime behavior:** `--no-autoupdate` prevents the running process from self-updating, but `latest` still resolves to whatever image the registry serves when the container is created/pulled. It is unlike the application base image, which is digest pinned in `Dockerfile:2`.
- **Impact:** Tunnel behavior, security posture, and compatibility can change during recovery/redeploy without a reviewed repository diff or reproducible rollback reference.
- **Remediation direction:** Pin Cloudflared to a reviewed version digest and record the upgrade/rollback process in the selected deployment architecture.

### DEPLOY-006 — Deployment documentation describes incompatible architectures and omits the decided worker/Redis target

- **Severity:** Medium
- **Confidence:** High
- **CWE:** Not applicable.
- **Classification:** Phase 11 blocker; outdated documentation.
- **Location:** `DEPLOY_UBUNTU.md:3-10`, `:83-193`; `DOCKER_DEPLOY.md:3-114`; `docker-compose.yml:3-145`.
- **Reachability:** Any new deployment, incident recovery, or operator following repository documentation.
- **Real configuration quote:**

  ```text
  This guide deploys ... with PostgreSQL, Gunicorn, Nginx, HTTPS, and daily backups.
  ```

  ```text
  Internet (HTTPS) -> Cloudflare Tunnel -> cloudflared -> web:6655
  ```
- **Effective runtime behavior:** One guide launches bare-metal Gunicorn behind host Nginx/Certbot with cron backups; the other launches locally built Docker web/cloudflared services. Neither starts Redis or Celery. The current Compose makes Cloudflared the effective tracked ingress, not merely old documentation, but it does not implement the decided target.
- **Impact:** Operators can configure different proxy-hop, port, TLS, backup, and update behaviors on the same service. The disagreement materially impedes incident response and makes Phase 11 acceptance non-repeatable.
- **Remediation direction:** Choose and document one production topology: host Nginx/Certbot/PostgreSQL/firewall/backup timer; Docker web/Celery/Redis; external S3-compatible storage. Retire Cloudflared instructions unless it is explicitly retained as part of that approved topology.

### DEPLOY-007 — Container hardening and standalone health semantics are incomplete

- **Severity:** Low
- **Confidence:** High
- **CWE:** CWE-250 (Execution with Unnecessary Privileges), defense-in-depth only.
- **Classification:** Reliability/hardening gap.
- **Location:** `Dockerfile:11-27`; `.dockerignore:1-15`; `docker-compose.yml:71-104`.
- **Reachability:** Post-compromise persistence and orchestration/recovery scenarios; no direct request-level exploit is established here.
- **Real configuration quote:**

  ```dockerfile
  COPY --chown=appuser:appuser . /app
  USER appuser
  ```
- **Effective runtime behavior:** The process runs as non-root UID/GID 1000, but the full copied application tree is owned and writable by that runtime user, and neither Dockerfile nor Compose sets a read-only root filesystem or drops default Linux capabilities. The Dockerfile has no `HEALTHCHECK`; Compose compensates only for `web` with an HTTP check and log rotation. No resource limits or explicit `stop_grace_period` are set.
- **Impact:** This does not create an independent remote exploit, but a code-execution compromise can alter in-container application files until replacement, and standalone image consumers receive no health signal. Resource exhaustion/shutdown behavior is left to engine defaults.
- **Remediation direction:** Make the immutable application tree root-owned/read-only, retain only explicit writable mounts/tmpfs, drop capabilities compatible with Gunicorn, add a Dockerfile health check, and define resource and graceful-stop limits after load testing.

## Phase 11 blockers

1. **DEPLOY-001:** the committed production Compose fails its own storage-provider validation; no S3 production configuration is supplied.
2. **DEPLOY-002:** no tracked Redis/Celery service, systemd unit, entrypoint start, or scheduled cleanup exists. Worker-dependent features are not supervised.
3. **DEPLOY-003:** no remote source, registry artifact, or documented off-host recovery chain exists.
4. **DEPLOY-006:** deployment target is undecided/inconsistently documented; current tracked Cloudflared Compose is not the specified Nginx/Certbot + Docker web/Celery/Redis target.

## Explicitly checked and found clean

- Application Docker base image is digest pinned (`Dockerfile:2`), Python dependencies are installed from a pinned requirements file, and no build-time `ARG` secret is declared.
- The image switches to non-root `appuser` before entrypoint/CMD (`Dockerfile:11-27`). No `privileged`, `network_mode: host`, Docker-socket mount, `cap_add`, host-port publication, or host PID/IPC mode appears in either Compose file.
- Secret **values** are not in Compose environment: `SECRET_KEY`, `DATABASE_URL`, `ADMIN_PASSWORD`, and tunnel token use Docker secret files (`docker-compose.yml:21-23`, `:66-69`, `:112-119`, `:133-144`). `.dockerignore` excludes `.env*`, `secrets/`, `.git`, storage/uploads/tmp, and ordinary backup paths (`.dockerignore:1-15`).
- Both services have `init: true`, `restart: unless-stopped`, local log rotation (10 MiB × 5), and private bridge-network attachment. Web has a Compose HTTP healthcheck and Cloudflared waits for it.
- Entrypoint secret-file reads fail closed on unreadable/empty values and hand off signals using `exec "$@"` (`docker-entrypoint.sh:4-37`, `:75`).
- No tracked CI, Terraform, Kubernetes, Helm, systemd worker/timer, Compose override, or registry configuration was found outside the files enumerated in this report.

## Needs verification

- Whether an untracked host service, manually attached Redis container, systemd unit, scheduler, or platform job runs Redis/Celery. No such mechanism is in the repository; this would be required to weaken the confidence of DEPLOY-002 for the actual running host.
- The deployed Docker image/configuration, host firewall, Nginx/Certbot state, Cloudflare tunnel public-hostname/TLS/cache rules, PostgreSQL socket permissions, backup timer/cron success, and external S3 durability/CORS/lifecycle policies were not contacted under this read-only audit.
- Ownership, retention, encryption, and off-host replication for `/srv/construction_relation_management/uploads`, database backups, secrets, and Docker images; no restoration drill was run.
- Whether the excluded `claude-partial-audit-backup/` exists or affects deployment; it was intentionally neither listed, searched, nor read.
