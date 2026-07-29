const assert = require("node:assert/strict");
const fs = require("node:fs");
const test = require("node:test");
const { JSDOM } = require("jsdom");

const source = fs.readFileSync("app/static/js/report-direct-upload.js", "utf8");
function page() {
  const dom = new JSDOM(`<!doctype html><form data-report-direct-upload data-upload-limits='{"enabled":true,"concurrency":3,"max_files":30,"max_file_bytes":26214400,"max_total_bytes":314572800,"max_files_per_section":10}' data-csrf-token="x" data-project-id="1" data-report-id="1" data-session-url="/sessions" data-presign-url="/sessions/0/presign" data-complete-url="/sessions/0/complete" data-session-state-url="/sessions/0"><input name="report_date" required value="2026-07-24"><input name="overall_status" required value="UPDATED"><textarea name="highlight" required>x</textarea><div data-section-row><input data-client-section-id name="sections-0-client-section-id" value=""><select name="sections-0-category_id" required><option value="1" selected>One</option></select><select name="sections-0-status" required><option value="GOOD" selected>Good</option></select><textarea name="sections-0-content" required>x</textarea><input name="sections-0-images" type="file" data-report-attachment-input><div data-attachment-preview></div></div><input data-upload-session-id name="upload_session_id"><input data-attachment-manifest name="attachment_manifest"><input data-direct-upload-expected name="direct_upload_expected"><button data-report-submit type="submit">Save</button><div data-report-save-overlay hidden><span data-save-message></span><span data-save-count></span><span data-save-bytes></span><span data-save-progress></span><button data-save-retry></button><button data-save-cancel></button></div></form>`, {runScripts: "outside-only", url: "https://starx.test/reports/create"});
  dom.window.fetch = () => new Promise(() => {});
  dom.window.crypto.randomUUID = () => "section-test";
  dom.window.eval(source);
  return dom;
}
test("submit listener prevents native submit before asynchronous save work", () => {
  const dom = page(), event = new dom.window.Event("submit", {bubbles: true, cancelable: true});
  dom.window.document.querySelector("form").dispatchEvent(event);
  assert.equal(event.defaultPrevented, true);
  assert.equal(dom.window.document.querySelector("[data-report-save-overlay]").hidden, false);
});
test("orchestrator keeps guarded final submit and metadata-only request", () => {
  assert.match(source, /event\.preventDefault\(\); save\(\)/);
  assert.match(source, /data\.delete\(input\.name\)/);
  assert.match(source, /Math\.min\(3, Number\(limits\.concurrency\)/);
  assert.match(source, /data-attachment-manifest/);
  assert.doesNotMatch(source, /form\.submit\(/);
});
