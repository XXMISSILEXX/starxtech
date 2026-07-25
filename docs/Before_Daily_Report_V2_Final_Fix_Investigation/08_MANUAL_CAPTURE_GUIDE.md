# Manual browser capture guide

1. In DevTools Network, disable cache, preserve log, reload Create. Save HTML and all script URLs; hash downloaded assets and compare to `01_RUNTIME_IDENTITY.md`. Check Application for service workers and unregister only in a disposable local session.
2. Submit a duplicate date. Export the preflight request/409 JSON (redact cookies/CSRF). Record Console exceptions and `unhandledrejection`, overlay `hidden`, `aria-busy`, spinner/failure controls' computed display, Save listeners (`getEventListeners` in Chromium), and `window.onbeforeunload`.
3. Select the exact `chef-with-trumpet.heic`. Preserve Network/Console. Record MIME/name/size, `window.StarXHeicPreview` keys, returned value constructor, image load/error, object URL outcome, and CSP/worker errors. Do not log signed URLs.
4. For each status option run:

```js
[...document.querySelectorAll('.status-control-icon')].map(e => ({className:e.className, content:getComputedStyle(e,'::before').content, font:getComputedStyle(e,'::before').fontFamily}))
```

Also record Bootstrap Icons CSS/font HTTP status, custom wrapper count per select, and duplicate IDs/`aria-controls`.

Diagnostic fetch wrapper (run once in Console; it redacts query strings and logs a response clone):

```js
(() => { const original = window.fetch; window.fetch = async (...args) => { const t = performance.now(), url = String(args[0]).split('?')[0]; try { const r = await original(...args); let body = ''; try { body = await r.clone().text(); } catch {} console.debug('[diag fetch]', {url, status:r.status, ms:Math.round(performance.now()-t), body:body.slice(0,2000)}); return r; } catch (e) { console.debug('[diag fetch rejected]', {url, ms:Math.round(performance.now()-t), name:e?.name, message:e?.message}); throw e; } }; })();
```
