# Runtime identity

Repository identity observed in this workspace:

| Item | Evidence |
|---|---|
| Branch | `investigate/daily-report-v2-runtime-failures` |
| HEAD | `d2ed32f3093861b1f46b305edc0bda6b20bb7529` |
| Dirty state at start | clean; later only the characterization test is modified |
| Configured static asset version | `20260724-83` (`app/config.py:34`) |
| Migration script head | `20260725_0026` |
| Flask PID / command / CWD / executable | unavailable: no Flask/Gunicorn/Python server and no listener on TCP 5666 was found |
| APP_ENV of a Flask process | unavailable; source default is `local` |

Disk SHA-256 after `npm run build:heic-preview`:

```text
33178e6f36a707d797639f4329c8a2dc185596fe8c726a25aed8a3c004ea53a0  app/static/js/daily-report-create-v2.js
ec024db617959737c342c2937814bda6a14d6862deca589ac4b5e868c45ce5b1  app/static/js/app.js
38b031b99f2e98731a3a647ffaef534955bba471eb476f720e562614f7772bc7  app/static/css/app.css
11f641905d8e7319bdcd665bd5659f1eb369eab6e584d893b36cb7d6e0384620  app/static/vendor/heic-to/heic-preview.min.js
```

The served-file hashes and rendered Create HTML script URLs cannot be obtained without the runtime. This means stale Flask code, browser cache, service worker, and duplicate runtime scripts are **not ruled out**. Source rendering specifies `app.js` then only `daily-report-create-v2.js` for Create (`app/templates/base.html:212-219`); Edit loads legacy `report-direct-upload.js` instead (`214-216`). There is no service-worker source found in the repository.

Required capture on the actual host: record `lsof -nP -iTCP:5666 -sTCP:LISTEN`, `/proc/<pid>/{cwd,cmdline,exe}`, `flask db current`, `flask db heads`, HTML script `src` values, and the four `curl | sha256sum` comparisons before approving any production fix.
