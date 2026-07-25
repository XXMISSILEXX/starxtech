# HEIC local preview

The configured bundle is `heic-to` 1.2.0, built from `scripts/heic-preview-entry.js` importing `{ heicTo, isHeic }` from `heic-to/csp`. The controller dynamically loads it from `data-heic-decoder-url`, expects `window.StarXHeicPreview.heicTo`, and calls:

```js
heicTo({ blob: state.file, type: "image/jpeg", quality: .82 })
```

(`daily-report-create-v2.js:57-61`). It accepts `Blob` or first element of `Blob[]`, optionally calls `createImageBitmap`, then `URL.createObjectURL`; any failure becomes `previewStatus="unavailable"` and the generic placeholder.

Bundle inspection proves the built bundle calls `new Worker(URL.createObjectURL(...))`. It does not reference a separately fetched WASM asset, dynamic import, or `instantiateStreaming`. Current CSP has no `worker-src`/`child-src`; `default-src 'self'` and `script-src 'self' https://cdn.jsdelivr.net` are set in `app/__init__.py:216-225`. A Blob Worker is therefore likely blocked by CSP fallback unless an actual browser shows otherwise.

This is a **probable contributing factor**, not a proven root cause: there is no listener/browser console in the workspace, and no `chef-with-trumpet.heic` (or any HEIC) was supplied. `heif-info` is installed; `exiftool` is not. No claim about codec, dimensions, alpha/depth images, orientation, server Pillow/pillow-heif decode, or isolated-harness outcome can be made without the exact file.

The server-side derivative success described in the symptom is compatible with a browser worker/CSP failure; it does not prove local decode works.
