const assert = require("node:assert/strict");
const fs = require("node:fs");
const test = require("node:test");

const read = (path) => fs.readFileSync(path, "utf8");

test("thumbnail lists use lazy, async stable thumbnail URLs", () => {
  const report = read("app/templates/reports/detail.html");
  const reportForm = read("app/templates/reports/form.html");
  const document = read("app/templates/project_documents/folder.html");
  const mediaIndex = read("app/templates/company_media/index.html");
  assert.match(report, /attachments\.thumbnail/);
  assert.match(report, /loading="lazy" decoding="async"/);
  assert.match(reportForm, /attachments\.thumbnail/);
  assert.doesNotMatch(reportForm, /<img[^>]+attachments\.view/);
  assert.match(document, /project_documents\.thumbnail/);
  assert.match(document, /loading="lazy" decoding="async"/);
  assert.match(mediaIndex, /company_media\.thumbnail/);
  assert.match(mediaIndex, /loading="lazy" decoding="async"/);
});

test("branding remains eager while avatars decode asynchronously", () => {
  const base = read("app/templates/base.html");
  assert.match(base, /alt="StarX logo" decoding="async" fetchpriority="high"/);
  assert.doesNotMatch(base, /StarX logo"[^>]*loading="lazy"/);
  assert.match(base, /account\.avatar[^>]+decoding="async"/);
});

test("document and company media no longer request signed previews on page load", () => {
  const preview = read("app/static/js/project-document-preview.js");
  const covers = read("app/static/js/company-media-covers.js");
  assert.doesNotMatch(preview, /querySelectorAll\("\.document-card-preview"\)\.forEach\(thumb\)/);
  assert.match(preview, /data-preview-file-id/);
  assert.match(preview, /\/company-media\/files\/\$\{encodeURIComponent\(card\.dataset\.previewFileId\)\}\/thumbnail/);
  assert.equal(covers, "");
});
