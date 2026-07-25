import { build } from "esbuild";

await build({
  entryPoints: ["scripts/heic-preview-entry.js"],
  bundle: true,
  format: "iife",
  globalName: "StarXHeicPreview",
  minify: true,
  outfile: "app/static/vendor/heic-to/heic-preview.min.js",
  legalComments: "linked",
});
