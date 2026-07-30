const assert = require("node:assert/strict");
const fs = require("node:fs");
const test = require("node:test");

const source = fs.readFileSync("app/static/js/company-media-upload.js", "utf8");

test("Company Media uploader maps every response by stable client_file_id", () => {
  assert.match(source, /clientFileId: newId\(\)/);
  assert.match(source, /new Map\(result\.items\.map\(\(item\) => \[item\.client_file_id, item\]\)\)/);
  assert.match(source, /byClientId\.get\(entry\.clientFileId\)/);
  assert.doesNotMatch(source, /result\.items\[index\]/);
});

test("Company Media uploader posts browser multipart with progress and bounded concurrency", () => {
  assert.match(source, /new XMLHttpRequest\(\)/);
  assert.match(source, /xhr\.upload\.onprogress/);
  assert.match(source, /Object\.entries\(entry\.presign\.fields \|\| \{\}\).*form\.append\("file", entry\.file\)/s);
  assert.match(source, /Math\.min\(concurrency, items\.length\)/);
  assert.match(source, /Promise\.all\(Array\.from/);
  assert.doesNotMatch(source, /xhr\.setRequestHeader\("Content-Type"/);
});

test("Company Media uploader reads server-resolved batch and concurrency limits with a safe fallback", () => {
  assert.match(source, /dataset\.companyMediaUploadLimits/);
  assert.match(source, /JSON\.parse\(root\.dataset\.companyMediaUploadLimits/);
  assert.match(source, /Number\.isInteger\(value\) && value > 0/);
  assert.match(source, /chunks\(items, uploadLimits\.max_files_per_batch\)/);
  assert.match(source, /const concurrency = uploadLimits\.upload_concurrency/);
  assert.doesNotMatch(source, /chunks\(items, 50\)/);
});

test("Company Media uploader accepts structured and legacy string application errors without exposing provider XML", () => {
  assert.match(source, /const errorMessage = \(error/);
  assert.match(source, /typeof error === "string"/);
  assert.match(source, /typeof error\.message === "string"/);
  assert.match(source, /payload\.ok === false/);
  assert.match(source, /errorMessage\(item\.error \|\| item\.error_message/);
  assert.match(source, /code: "s3_upload_failed"/);
  assert.match(source, /nonRetryableS3Codes\.has\(error\.providerCode\)/);
  assert.doesNotMatch(source, /xhr\.responseText[^\n]*textContent/);
});

test("Company Media uploader distinguishes blocked files and refreshes only after the user closes results", () => {
  assert.match(source, /entry\.status = "blocked"/);
  assert.match(source, /entry\.status = "failed"/);
  assert.match(source, /failed_upload_batch_item_ids/);
  assert.match(source, /data-upload-retry-failed/);
  assert.match(source, /data-upload-close/);
  assert.match(source, /if \(selected\(\)\.some\(\(entry\) => entry\.status === "succeeded"\)\) window\.location\.reload\(\)/);
});

test("Company Media retries transient transport errors but not S3 policy errors", () => {
  assert.match(source, /EntityTooSmall/);
  assert.match(source, /SignatureDoesNotMatch/);
  assert.match(source, /retryableStatus\.has\(error\.status\)/);
  assert.match(source, /await delay\(attempt\)/);
});
