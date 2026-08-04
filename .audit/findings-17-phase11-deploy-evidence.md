# Findings — Phase 11 Delta: Configuration, deployment, migrations and audit evidence

## Summary

- Read all U7/U8/U10 changed files, deployment configuration, changed migrations, history documents and their reached application bootstrap/configuration code.  `PHASE11-DELTA-SCOPE.md` is the complete 111-file inventory and records the deliberate non-delta exclusions.
- No confirmed new production secret exposure, public media mount, migration data-loss operation, startup permission synchronization, or unsafe original-file serving was found.
- Deployment correctness has two release-evidence conditions: validate the host-backed media-cache ownership/routing in the actual target and resolve the Daily Report 3-versus-10 contract mismatch documented as REPORTS-007.

## Deployment/control matrix

| Area | Delta evidence | Result |
|---|---|---|
| Runtime | `Dockerfile:1-30` pins Python 3.12 slim and executes as unprivileged UID/GID 1000 | Clean in source; image digest remains a release operation |
| Secrets | Compose uses Docker secret files for application/database/S3/Redis credentials (`docker-compose.yml:3-23,57-64,157-167`) | Clean; no values recorded here |
| Read-only container | common services are `read_only`; named `/app/tmp` volume is supplied (`:65-68`) | Clean |
| Private media cache | only `web` receives host cache bind mount (`:90-109`); Nginx cache URI is internal (`deploy/nginx/starx-report.conf:9-15`) | Clean in source; host test required |
| Startup validation | configuration errors plus cache validation fail application construction (`app/__init__.py:57-61`) | Clean |
| Migrations | 0027 adds user UI preferences; 0028/0029 establish selection idempotency/cleanup support | Read and structurally consistent; live upgrade not run |
| Audit history | Phase 11 evidence docs describe earlier known issues and resolved work | Read as history, not treated as an approval to alter baseline contract |

## Explicitly checked and found clean

- The new cache does not turn into a public static directory.  `deploy/nginx/starx-report.conf:9-15` uses `internal` and Compose has no published cache volume/port.  Flask cache delivery sets private response/cache-control and `nosniff`; its route callers retain application ACLs before invoking it.
- `Dockerfile:13-25` creates and drops to UID/GID 1000.  `/app/tmp` and `/app/storage` are writable before the root filesystem becomes read-only.  Compose mounts `app_tmp` for all relevant processes, including Celery beat’s schedule (`docker-compose.yml:127-135`).
- Cache configuration is validated for absolute root, allowed delivery mode, valid X-Accel prefix, positive capacity/age (`app/storage/cache.py:60-81`) at bootstrap.  Invalid values fail closed rather than silently selecting a filesystem/public fallback.
- The reports global-gate regression risk was explicitly checked after new blueprint/route registration.  `app/__init__.py:103-152,186-206` registers the new branding rule and blueprints, then still recognizes all changed reports-family endpoint prefixes.  `ENDPOINTS-g5.md` contains the endpoint evidence; no new reports route escaped it.
- The changed migrations contain additive schema/constraint work, not destructive table/column drops.  They were inspected, not applied, in accordance with the audit’s read-only operational rule.
- `git diff --check fc1a117..HEAD` and `python -m compileall -q app tests` completed with exit status 0.  No source files were written by this audit.

## Needs verification

### DEPLOY-OP-001 — Host cache mount must be tested with the production UID and Nginx service account

- **Classification:** Unverified deployment condition; not a source-code finding.
- **Location:** `Dockerfile:13-25`; `docker-compose.yml:45-50,96-99`; `deploy/nginx/starx-report.conf:9-15`; README deployment text around the cache mount.
- **Reason:** The container writes as UID 1000 to `${MEDIA_CACHE_HOST_ROOT:-/opt/starxtech/cache/media}`, while Nginx reads the matching host directory.  Source cannot establish the actual target directory owner/mode, SELinux/AppArmor policy, UID mapping or whether the installed Nginx site is the supplied configuration.
- **Acceptance test:** On staging, create the directory with least-privilege ownership for UID 1000 plus Nginx read access; make an authorized thumbnail request twice (miss/hit); assert unauthenticated/direct `/_protected_media_cache/...` returns inaccessible, and verify `send_file` plus optionally `x_accel` delivery.  Do not use an S3 object or signed URL in the audit log.

### DEPLOY-OP-002 — Compose/documentation describe X-Accel as a production option, but default delivery is `send_file`

- **Classification:** Confirmed documentation/configuration ambiguity; low operational severity.
- **Location:** `.env.example:88-95`; `docker-compose.yml:45-50`; README cache description; `deploy/nginx/starx-report.conf:9-15`.
- **Evidence:** The template comment says Compose overrides with a host-backed X-Accel cache, whereas Compose defaults `MEDIA_CACHE_DELIVERY_MODE` to `send_file`.  Both modes are supported and secure if configured as designed, so this is not an exposure.
- **Impact:** An operator may believe Nginx is serving cache bytes when Flask is doing so, producing unexpected capacity/performance observations or a failed X-Accel rollout test.
- **Disposition:** State the selected production delivery mode explicitly in the release environment/runbook and make documentation match it.

## Scope and test integrity notes

- The repository’s working tree was clean at audit start.  Baseline and delta matched exactly: `fc1a117..e764509c5e2cc174499248c79e7d4ec7fdedfe2a`, 20 commits, 111 files, +7,685/−303 lines.  This rules out auditing the wrong branch.
- This audit created only new files in `.audit/` (including a deliberately failing policy PoC).  No existing Phase 10 audit record was modified.
- The local virtual environment was Python 3.10.  The Dockerfile’s source target is Python 3.12, but a build/Compose/up/migration smoke test was deliberately not run because it would create/mutate deployment state and requires target secrets/infrastructure.
