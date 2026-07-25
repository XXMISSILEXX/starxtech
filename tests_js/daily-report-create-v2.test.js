const assert = require("node:assert/strict");
const fs = require("node:fs");
const test = require("node:test");
const { JSDOM } = require("jsdom");

const source = fs.readFileSync("app/static/js/daily-report-create-v2.js", "utf8");
function page() {
  const dom = new JSDOM(`<!doctype html><form data-daily-report-create-v2 data-api-base="/api/projects/1/daily-reports" data-upload-limits='{"max_files":30,"max_file_bytes":9,"max_files_per_section":3}' data-csrf-token="x"><input name="report_date" value="2026-07-25"><select name="overall_status"><option value="UPDATED" selected></option></select><textarea name="highlight">x</textarea><textarea name="summary_note"></textarea><div data-daily-report-sections></div><template id="daily-report-section-v2-template"><section data-report-section><input data-client-section-id><span data-section-number></span><button data-remove-section type="button"></button><select data-section-category required><option value=""></option><option value="1">One</option><option value="2">Two</option></select><div data-category-error></div><i data-section-status-icon></i><select data-section-status><option value="INFO" selected></option></select><textarea data-section-content required></textarea><div data-content-error></div><label><input type="file" data-report-attachment-input></label><div data-attachment-preview></div></section></template><button type="button" data-add-section></button><button type="submit" data-report-submit></button></form><div data-report-save-overlay hidden><i data-save-icon></i><span data-save-title></span><span data-save-message></span><span data-save-uploaded></span><span data-save-verified></span><span data-save-failed></span><span data-save-bytes></span><span data-save-filename></span><span data-save-progress></span><button data-save-retry></button><button data-save-cancel></button></div><button data-category-shortcut="1"></button><button data-category-shortcut="2"></button>`, {runScripts: "outside-only", url: "https://starx.test"});
  let id = 0; dom.window.crypto.randomUUID = () => `uuid-${++id}`; dom.window.matchMedia = () => ({matches: true}); dom.window.HTMLElement.prototype.scrollIntoView = () => {}; dom.window.fetch = () => Promise.reject(new Error("not used")); dom.window.eval(source); return dom;
}
test("V2 initializes one blank section and appends below it", () => { const dom = page(), doc = dom.window.document; const first = doc.querySelectorAll("[data-report-section]"); assert.equal(first.length, 1); assert.equal(first[0].dataset.clientSectionId, "uuid-1"); assert.ok(first[0].querySelector("[data-section-category]")); doc.querySelector("[data-add-section]").click(); const sections = doc.querySelectorAll("[data-report-section]"); assert.equal(sections.length, 2); assert.notEqual(sections[0].dataset.clientSectionId, sections[1].dataset.clientSectionId); assert.equal(doc.querySelector("[data-daily-report-sections]").lastElementChild, sections[1]); });
test("category chip fills a blank section and removing only section leaves one", () => { const dom = page(), doc = dom.window.document; doc.querySelector("[data-category-shortcut='1']").click(); assert.equal(doc.querySelector("[data-section-category]").value, "1"); dom.window.confirm = () => true; doc.querySelector("[data-remove-section]").click(); assert.equal(doc.querySelectorAll("[data-report-section]").length, 1); });

test("characterization: real V2 409 duplicate-date flow reaches the failed overlay terminal state", async () => {
  const dom = page(), { document: doc } = dom.window;
  const section = doc.querySelector("[data-report-section]");
  section.querySelector("[data-section-category]").value = "1";
  section.querySelector("[data-section-content]").value = "Nội dung";
  const overlay = doc.querySelector("[data-report-save-overlay]");
  const spinner = doc.createElement("div"); spinner.className = "spinner-border"; overlay.prepend(spinner);
  const responseBody = { ok: false, error: { code: "duplicate_report_date", message: "Dự án đã có báo cáo cho ngày này.", field_errors: { report_date: "Dự án đã có báo cáo cho ngày này." } } };
  dom.window.fetch = async () => new Response(JSON.stringify(responseBody), { status: 409, headers: { "Content-Type": "application/json" } });
  doc.querySelector("form").dispatchEvent(new dom.window.Event("submit", { bubbles: true, cancelable: true }));
  await new Promise(resolve => setTimeout(resolve, 0));
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.equal(overlay.hidden, false);
  assert.equal(overlay.getAttribute("aria-busy"), "false");
  assert.equal(spinner.hidden, true);
  assert.match(overlay.querySelector("[data-save-message]").textContent, /đã có báo cáo/i);
  assert.equal(overlay.querySelector("[data-save-retry]").hidden, true);
  assert.equal(overlay.querySelector("[data-save-cancel]").hidden, false);
  assert.equal(doc.querySelector("[name=report_date]").classList.contains("is-invalid"), true);
  assert.equal(doc.activeElement, doc.querySelector("[name=report_date]"));
  assert.equal(doc.querySelector("[data-report-submit]").disabled, false);
  assert.equal(dom.window.onbeforeunload, null);
});

test("V2 422 preflight preserves entered report and section state without starting upload", async () => {
  const dom = page(), { document: doc } = dom.window;
  const section = doc.querySelector("[data-report-section]");
  doc.querySelector("[name=highlight]").value = "Highlight giữ lại";
  doc.querySelector("[name=summary_note]").value = "Ghi chú giữ lại";
  section.querySelector("[data-section-category]").value = "1";
  section.querySelector("[data-section-content]").value = "Nội dung giữ lại";
  let calls = 0;
  dom.window.fetch = async () => { calls += 1; return new Response(JSON.stringify({ok:false,error:{code:"invalid_section",message:"Phần báo cáo bị trùng hoặc thiếu dữ liệu.",field_errors:{sections:"Kiểm tra hạng mục."}}}), {status:422,headers:{"Content-Type":"application/json"}}); };
  doc.querySelector("form").dispatchEvent(new dom.window.Event("submit", {bubbles:true,cancelable:true}));
  await new Promise(resolve => setTimeout(resolve, 0));
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.equal(calls, 1);
  assert.equal(doc.querySelector("[name=highlight]").value, "Highlight giữ lại");
  assert.equal(doc.querySelector("[name=summary_note]").value, "Ghi chú giữ lại");
  assert.equal(section.querySelector("[data-section-content]").value, "Nội dung giữ lại");
  assert.equal(doc.querySelector("[data-report-save-overlay]").getAttribute("aria-busy"), "false");
});
