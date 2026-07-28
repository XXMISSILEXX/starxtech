# Findings — CLI & Ops

## Summary

- **Trust boundary:** These commands run with the deployment/operator identity but can alter the entire database, filesystem backups, schema, and the `SUPER_ADMIN` account. No Unit 1 command is reachable from an HTTP request; findings below are either deployment footguns or operator-only weaknesses unless stated otherwise.
- **Overall posture:** Destructive Flask commands have explicit confirmation gates and the primary shell commands quote their dynamic arguments. However, production-mode enforcement is opt-in, `security-audit` can provide a misleading PASS, and backup/restore lack atomicity and restore safety controls.
- **Files read:** 35, including all seven primary paths in full; required audit context (`ARCHITECTURE`, `FOUNDATION-A1`, `FOUNDATION-A2`, `FOUNDATION-B`, `ENDPOINTS`, `PRE-FINDINGS`, `TOOL-LEAD-MAP`, `MODULES`); CLI/config/worker/bootstrap code; Docker/Compose/deployment guides; and the two raw-SQL lead locations.
- **Files skipped and why:** No primary file was skipped. Actual secret files and values in `.env`/`secrets/` were not opened to avoid exposing credentials; runtime host permissions, the live scheduler, and the deployed Cloudflare/S3/Redis state are outside the repository.

## Findings

### CLI-001 — Production safeguards fail open when `APP_ENV` is absent or malformed

- **Severity:** High
- **Confidence:** High
- **CWE:** CWE-321 (Use of Hard-coded Cryptographic Key)
- **Location:** `app/config.py:35-41`; `app/security.py:61-63`; `app/cli.py:401-413`
- **Reachability:** Deployment footgun with a remotely exploitable outcome. It requires an operator to start a publicly reachable Gunicorn deployment without the exact value `APP_ENV=production` (for example, unset or `APP_ENV=Production`); no authenticated application user is needed after that.
- **Vulnerable code:**

  ```python
  APP_ENV = os.getenv("APP_ENV", "local")
  SECRET_KEY = read_secret("SECRET_KEY", "dev-secret-key")
  ```

  ```python
  def production_configuration_errors(config) -> list[str]:
      if config.get("APP_ENV") != "production":
          return []
  ```

  ```python
  if config.get("APP_ENV") == "production":
      check(not weak_secret, "secret-key", "strong non-default key configured", "missing/default/short SECRET_KEY")
  else:
      _audit_line("PASS", "secret-key", "local default accepted" if weak_secret else "non-default key configured")
  ```
- **Upward/downward call-chain evidence:** `app.config.Config` supplies these values to `create_app()` (`app/__init__.py:11-48`). `create_app()` invokes `production_configuration_errors()` before registering `register_cli()` (`:46-83`), which exposes `flask security-audit` (`app/cli.py:88-93`). The committed Ubuntu systemd unit starts Gunicorn without setting `APP_ENV` itself (`DEPLOY_UBUNTU.md:94-101`); the guide relies on a readable `.env` file instead. Thus an absent, misspelled, or case-variant environment mode bypasses both startup enforcement and the audit command.
- **Impact:** A mistakenly non-production public deployment can use the known `dev-secret-key` and insecure cookie defaults. An attacker can forge a Flask session cookie for a known/guessable account ID and impersonate that account; the bootstrap naming convention makes `admin` particularly predictable. The same deployment's `security-audit` reports the weak key and disabled Secure cookie as PASS for a “local” environment.
- **Concrete reproduction or reasoning:** Start the normal WSGI/Gunicorn application with valid database settings but `APP_ENV=Production` (or unset), `SECRET_KEY` unset, and `SESSION_COOKIE_SECURE` unset. The exact equality test treats it as non-production; application creation succeeds and `flask security-audit` emits `PASS secret-key: local default accepted` and accepts a disabled Secure cookie.
- **Remediation direction, without editing code:** Make production safety fail closed: require an explicit, allow-listed environment mode at startup, use no usable default secret outside test-only configuration, and treat unknown/missing `APP_ENV` as production for security checks or as a startup error. Ensure service units set the mode independently of a project-local dotenv file.

### CLI-002 — `security-audit` can PASS despite absent worker/scheduled cleanup and unverified external controls

- **Severity:** Medium
- **Confidence:** High
- **CWE:** CWE-693 (Protection Mechanism Failure)
- **Location:** `app/cli.py:419-446`, `app/cli.py:448-484`
- **Reachability:** Operator-only false assurance. The documented production invocation is `docker compose exec web flask security-audit` (`DOCKER_DEPLOY.md:67-76`). The supplied Compose file has no Celery worker or scheduler service, while the audit command only checks configuration values.
- **Vulnerable code:**

  ```python
  check(bool(config.get("CELERY_BROKER_URL")) and bool(config.get("CELERY_RESULT_BACKEND")), "celery-config-present", "Celery broker/result configured", "Celery broker/result missing")
  check(config.get("APP_ENV") != "production" or not config.get("CELERY_TASK_ALWAYS_EAGER"), "celery-eager-not-production", "Celery eager disabled in production", "CELERY_TASK_ALWAYS_EAGER enabled in production")
  ```

  ```python
  origins = tuple(config.get("STORAGE_CORS_ALLOWED_ORIGINS") or ())
  check(bool(origins) and all("*" not in origin for origin in origins), "storage-cors-origins", "explicit storage CORS origins configured", "missing or wildcard storage CORS origin")
  ```
- **Upward/downward call-chain evidence:** `docker-entrypoint.sh:56-59` optionally runs `flask security-audit`; `DOCKER_DEPLOY.md:67-70` directs operators to run it manually. `docker-compose.yml:3-145` defines only `web` and `cloudflared`, whereas `scripts/start-media-worker.sh:13-19` is a manual worker wrapper. `FOUNDATION-B.md` confirms no Celery beat schedule and that cleanup/reconciliation tasks require manual CLI invocation. The audit does not call `worker-config-check()`, connect to Redis/S3, inspect bucket CORS, verify a worker/beat process, or verify `TRUSTED_HOSTS`/proxy/TLS configuration.
- **Impact:** A green audit can be mistaken for a production readiness decision while media jobs and cleanup tasks never run, storage CORS differs from its configured intent, or host/proxy controls are absent. Pending uploads and stuck jobs can accumulate indefinitely; the command supplies no signal for those failures.
- **Concrete reproduction or reasoning:** With an otherwise healthy database and valid configured URLs, run the documented audit against the committed Compose deployment. It can PASS `celery-config-present` solely because both strings exist even though no service starts `scripts/start-media-worker.sh`; it can PASS `storage-cors-origins` without reading the bucket policy at all.
- **Remediation direction, without editing code:** Split static configuration linting from a readiness check. Make the production readiness mode verify the intended worker/scheduler registration and broker/storage connectivity, require a deliberate external cleanup schedule, and either test actual S3 CORS or clearly label that check as configuration-only. Include trusted-host/proxy/TLS expectations in the production checklist.

### CLI-003 — Database restore can target the wrong database and report success after a partial restore

- **Severity:** Medium
- **Confidence:** High
- **CWE:** CWE-252 (Unchecked Return Value)
- **Location:** `scripts/restore_db.sh:9-25`
- **Reachability:** Operator-only destructive command. Any user able to run the documented restore command can select any readable regular file and restores it into whichever database is named by the sourced `.env`.
- **Vulnerable code:**

  ```bash
  BACKUP_FILE="$1"
  ...
  source .env
  ...
  gunzip -c "$BACKUP_FILE" | psql "$DATABASE_URL"

  echo "DB restore done from: $BACKUP_FILE"
  ```
- **Upward/downward call-chain evidence:** The required one-argument CLI path reaches this pipeline directly after only `-f` validation (`scripts/restore_db.sh:4-15`). `DEPLOY_UBUNTU.md:176-182` documents invoking it against a production-format path. No code derives or compares a database identity, verifies the dump metadata, requires a target confirmation, uses `psql --set ON_ERROR_STOP=1`, or wraps the restore in a transaction.
- **Impact:** A misplaced `APP_DIR`, `.env`, or shell invocation can overwrite the wrong database. Ordinary SQL errors in a plain dump do not make `psql` fail with its script-error exit status unless `ON_ERROR_STOP` is enabled; `set -o pipefail` therefore does not prevent the success message after earlier statements have already modified the target. Gzip validates its stream CRC, but there is no authenticated checksum/signature or source/target database binding.
- **Concrete reproduction or reasoning:** Supply a syntactically valid gzip SQL dump whose first statements succeed and whose later statement violates a constraint, while `.env` points at a production database. `psql` continues by default; already-applied statements remain, and this script has no independent check before printing “DB restore done”. The same path accepts a backup created for any other database because it checks only that the input is a regular file.
- **Remediation direction, without editing code:** Require an explicit expected target database name and a destructive confirmation, print the resolved target before proceeding, use `ON_ERROR_STOP=1` and an appropriate transaction/restore format, and require a manifest containing a cryptographic checksum plus source database/environment metadata. Restore first into an isolated verification target where operationally possible.

### CLI-004 — Backup jobs leave partial archives in the retention set and accept destructive retention values

- **Severity:** Medium
- **Confidence:** High
- **CWE:** CWE-754 (Improper Check for Unusual or Exceptional Conditions)
- **Location:** `scripts/backup_db.sh:16-19`; `scripts/backup_uploads.sh:17-26`
- **Reachability:** Operator/cron-only. `DEPLOY_UBUNTU.md:165-174` schedules both scripts daily as the application service account.
- **Vulnerable code:**

  ```bash
  OUTPUT_FILE="$BACKUP_DIR/starx_report_db_${TIMESTAMP}.sql.gz"
  pg_dump "$DATABASE_URL" | gzip > "$OUTPUT_FILE"

  ls -1t "$BACKUP_DIR"/*.sql.gz 2>/dev/null | tail -n +"$((RETENTION_COUNT + 1))" | xargs -r rm --
  ```

  ```bash
  OUTPUT_FILE="$BACKUP_DIR/starx_report_uploads_${TIMESTAMP}.tar.gz"
  ...
  tar -czf "$OUTPUT_FILE" -C "$(dirname "$UPLOAD_ROOT")" "$(basename "$UPLOAD_ROOT")"
  ```
- **Upward/downward call-chain evidence:** Both scripts write directly to their final, timestamped filename before retention. `set -euo pipefail` stops the process on a failed `pg_dump`/`tar`, but neither script removes the already-created file, writes to a private temporary file, validates an archive, nor atomically renames it after success. `restore_db.sh:12-23` accepts any existing regular gzip file as a restore candidate. `RETENTION_COUNT` is operator-supplied and evaluated without validation.
- **Impact:** A database or filesystem read error can leave a truncated but plausibly named `*.gz` archive that subsequent retention and restore operations treat as a backup. Two runs beginning in the same second also select the same output path. A negative `RETENTION_COUNT` produces a non-positive `tail -n +N` start value and can select all matching backups for deletion. This is a data-recovery failure, not a remote injection path.
- **Concrete reproduction or reasoning:** Interrupt `pg_dump` after gzip has written output, or make `tar` encounter an unreadable/changing upload file. The final filename remains even though the script exits before its success echo. Separately, export `RETENTION_COUNT=-1`; the arithmetic expression becomes `+0`, so retention can feed the complete matching set to `rm --`.
- **Remediation direction, without editing code:** Validate retention as a non-negative bounded integer; use a lock to prevent same-second concurrent writers; create archives in a restrictive temporary file, validate them, emit a manifest/checksum, and atomically rename only on success. Use null-delimited file enumeration for retention and make archive permissions explicit.

### CLI-005 — Opt-in entrypoint operations race across replicas and reseed the administrator on every start

- **Severity:** Low
- **Confidence:** High
- **CWE:** CWE-362 (Race Condition)
- **Location:** `docker-entrypoint.sh:51-75`; `app/cli.py:347-372`
- **Reachability:** Deployment footgun only when an operator enables `RUN_MIGRATIONS=true` and/or `SEED_ADMIN=true`. The committed Compose defaults are false (`docker-compose.yml:58-64`) and its fixed `container_name` prevents Compose scaling, but the image has no protection if deployed as multiple replicas elsewhere.
- **Vulnerable code:**

  ```sh
  if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
    flask db upgrade
  fi
  ...
  if [ "${SEED_ADMIN:-false}" = "true" ]; then
    flask seed-admin \
      --username "${ADMIN_USERNAME:-admin}" \
      --password "$ADMIN_PASSWORD" \
      --email "${ADMIN_EMAIL:-admin@example.com}" \
      --full-name "${ADMIN_FULL_NAME:-System Admin}"
  fi
  ```

  ```python
  user = user or email_user
  ...
  user.password_hash = generate_password_hash(password)
  user.role = role
  user.is_active = True
  db.session.commit()
  ```
- **Upward/downward call-chain evidence:** Every container invokes the entrypoint before Gunicorn (`Dockerfile:22-27`). Multiple starters independently run Alembic and then execute the read-then-create/update seed path. There is no database/advisory lock, leader election, one-shot job, retry for a uniqueness race, or “seed only when no admin exists” condition. The seed function intentionally updates an existing username or email match.
- **Impact:** Concurrent startup can fail one or more replicas during migration/seed, and a restart with seeding enabled forcibly restores the configured bootstrap password and `SUPER_ADMIN` role on the matching account. This is not remotely reachable from application input and no default password exists, but it can undo an administrator’s password rotation or destabilize deployment.
- **Concrete reproduction or reasoning:** Start two copies of the image against an empty database with both flags true. Both can observe no user and attempt to insert the same default username/email; one can fail on uniqueness. Against an existing account, every restart overwrites its password hash with `ADMIN_PASSWORD`.
- **Remediation direction, without editing code:** Run migrations and initial administrator provisioning as a separately locked, one-shot deployment job. Make normal web entrypoints read-only with respect to schema/admin state; seed only when explicitly requested and only if the intended account does not already exist, unless a separate confirmed rotation operation is used.

## Explicitly checked and found clean

- **All primary files were read in full.** There are no Python `subprocess`, `os.system`, `Popen`, or shell-evaluation calls in `app/cli.py`; `scripts/start-media-worker.sh` executes a fixed `python -m celery` argv with no `eval` or attacker-controlled command fragment.
- **Raw SQL tool leads:** `sync_postgres_sequence()` interpolates only `PARTNER_SEED_TABLES`, a module-level fixed list (`app/cli.py:36-46,487-512`), and is reachable only through `flask seed-partner-demo`. The migration lead likewise joins fixed `FLAGS`/tuple literals (`migrations/versions/20260722_0014_three_layer_authorization.py:14-20,47-53`). No HTTP or CLI option reaches either SQL identifier.
- **Reset safeguards:** `reset-database` and `reset-local-dev` require the exact confirmation string and require `--allow-production` only when the app sees the exact production mode (`app/cli.py:283-326`). Upload deletion resolves the configured root and rejects filesystem/project roots; it does not accept a request path.
- **Shell injection/path traversal:** `DATABASE_URL`, backup paths, upload paths, and restore input are passed quoted. Their values are operator-controlled environment/argument inputs, not HTTP data. `tar` is not given `--dereference`, so it archives upload symlinks as links rather than following them. The scripts do source `.env`; that file must remain trusted because shell syntax in it executes as the backup service account, but no untrusted writer/call chain was found in this unit.
- **Admin/default credentials:** `app/cli.py` has no hardcoded password, token, credential, or default secret. `reset-local-dev` fixes only `admin` / `admin@example.com` / `System Admin` and requires an operator-supplied password subject to the 12-character/three-class policy (`app/cli.py:75-86,329-372`; `app/security.py:20-37`). `_seed_admin` stores a Werkzeug hash, logs only username/email/role in its audit record, and echoes only the username.
- **Temporary passwords:** The separate admin reset route uses `secrets.choice`, length 14, and all character classes (`app/admin/services.py:77-80`), hashes it, audits only the username, and displays the plaintext only in the privileged reset response flash (`app/admin/routes.py:199-208`). It is not a CLI default or an entrypoint seed value; any authorization issue for that route belongs to the Admin/Endpoints audit.
- **Entrypoint secret handling:** unreadable/empty `*_FILE` secrets fail closed without printing the secret; the image runs as non-root `appuser` (`docker-entrypoint.sh:4-37`, `Dockerfile:11-22`). The seed password is not logged or stored in plaintext by application code. It is nevertheless passed as a `flask` argv element while seeding, so local process-list exposure depends on container PID/proc permissions and is listed below for deployment verification.
- **Worker/Gunicorn defaults:** `worker-config-check` verifies database reachability/migration head, broker TCP reachability, storage-provider initialization, and temp-root writability before the fixed worker command (`app/cli.py:95-142`; `scripts/start-media-worker.sh:4-19`). Gunicorn defaults to two gthread workers × two threads, 120-second timeout, and stdout/stderr logs (`gunicorn.conf.py:3-15`); no debug mode or direct public Compose port was found.

## Needs verification

- **Live backup permissions and retention:** Confirm the real `BACKUP_DIR`, cron environment/umask, ownership, and whether any untrusted local principal can create symlinks or whitespace/newline filenames there. The scripts do not set `umask`, do not reject symlink output files, and parse `ls` through whitespace-delimited `xargs`; this is a local privilege/data-loss concern only if the directory is writable by a less-trusted principal.
- **Actual recovery safety:** Perform a controlled restore drill into an isolated database and verify that generated archives are complete, that no process adds a manifest/signature externally, and that PostgreSQL’s `psql` version has the expected default non-`ON_ERROR_STOP` behavior. No restore or database command was run in this audit.
- **Worker supervision:** The committed Compose file and Ubuntu systemd example do not start the media worker; README documents manual startup. Confirm whether a host-level service, container platform job, or scheduler outside the repository runs `scripts/start-media-worker.sh` and the three manual cleanup/reconciliation commands.
- **Effective production configuration:** `flask security-audit` uses the same `Config` class as Gunicorn/Celery, so when invoked inside the same container it sees the same environment and Docker secret files. A host/manual CLI process can instead load a local `.env` and differ from the deployed container. Verify the actual service/container environment, S3 bucket CORS, Redis availability, Cloudflare TLS policy, and trusted-host configuration rather than relying solely on command output.
- **Seed argv visibility:** Confirm the runtime PID namespace and `/proc` `hidepid`/UID policy. `--password "$ADMIN_PASSWORD"` is visible to sufficiently privileged local/container processes while `flask seed-admin` runs, though no unprivileged remote call chain was found.

## Tool leads closed as false positive/info

- **Semgrep `avoid-sqlalchemy-text` — `app/cli.py:498`:** False positive for injection. The only interpolated identifiers come from the fixed `PARTNER_SEED_TABLES` constant; values remain bound parameters.
- **Semgrep `avoid-sqlalchemy-text` — `migrations/versions/20260722_0014_three_layer_authorization.py:52-53`:** False positive for injection. `manager_flags` derives solely from immutable `FLAGS`; `reporter_flags` derives solely from an inline literal tuple in a one-time migration.
- **pip-audit `pillow-heif` encode advisory:** Informational for this unit. `app/cli.py` does not import or encode HEIF; repository cross-reference found only `register_heif_opener()` decode registration and no `save(..., "HEIF")` call.
- **pip-audit `pytest` local temporary-directory advisory:** Informational here. Pytest is not called by the CLI/Ops production paths reviewed.
