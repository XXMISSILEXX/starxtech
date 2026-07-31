const assert = require("node:assert/strict");
const fs = require("node:fs");
const test = require("node:test");
const { JSDOM } = require("jsdom");

const source = fs.readFileSync("app/static/js/project-document-preview.js", "utf8");
const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

async function page({ response, preview = false } = {}) {
  const dom = new JSDOM(`<!doctype html>
    <section data-project-document-preview data-csrf-token="csrf-test">
      <button data-signed-download="1" data-download-url="/signed-download">Tải xuống</button>
      ${preview ? '<button data-preview-file-id="1" data-preview-url="/signed-preview" data-preview-variant="preview" data-preview-name="Preview">Xem</button>' : ""}
    </section>`, { runScripts: "outside-only", url: "https://starx.test/project-documents/folders/1" });
  const alerts = [];
  const requests = [];
  const navigations = [];
  const previews = [];
  dom.window.alert = (message) => alerts.push(message);
  dom.window.openMediaPreview = (value) => previews.push(value);
  dom.window.fetch = async (...args) => {
    requests.push(args);
    return response(...args);
  };
  // Location is intentionally unforgeable in some JSDOM versions. Instrument
  // only the evaluated test copy; the source assertion below protects the
  // production handler's required call to window.location.assign(result.url).
  dom.window.__navigate = (url) => navigations.push(url);
  const executable = source.replace("window.location.assign(result.url)", "window.__navigate(result.url)");
  dom.window.eval(executable);
  dom.window.document.dispatchEvent(new dom.window.Event("DOMContentLoaded"));
  await flush();
  return { dom, alerts, navigations, previews, requests };
}

function jsonResponse(status, data) {
  return { ok: status >= 200 && status < 300, status, json: async () => data };
}

test("single-download handler navigates to top-level signed URL for both modules", async () => {
  assert.match(source, /window\.location\.assign\(result\.url\)/);
  for (const url of ["https://storage.example/company", "https://storage.example/document"]) {
    const result = await page({ response: async () => jsonResponse(200, { ok: true, url }) });
    result.dom.window.document.querySelector("[data-signed-download]").click();
    await flush();
    assert.deepEqual(result.navigations, [url]);
    assert.equal(result.requests[0][1].method, "POST");
    assert.equal(result.requests[0][1].headers["X-CSRFToken"], "csrf-test");
  }
});

test("single-download rejects missing ok, bad URL, malformed JSON, and HTTP errors safely", async () => {
  const cases = [
    [async () => jsonResponse(200, { url: "https://storage.example/file" }), "Không thể tạo liên kết tải xuống."],
    [async () => jsonResponse(200, { ok: false, error: { message: "Backend từ chối" } }), "Backend từ chối"],
    [async () => jsonResponse(200, { ok: true }), "Không thể tạo liên kết tải xuống."],
    [async () => ({ ok: true, status: 200, json: async () => { throw new Error("invalid JSON"); } }), "Không thể tạo liên kết tải xuống."],
    [async () => jsonResponse(403, { error: { message: "Không có quyền" } }), "Không có quyền"],
    [async () => jsonResponse(404, {}), "Không thể tạo liên kết tải xuống."],
    [async () => jsonResponse(500, {}), "Không thể tạo liên kết tải xuống."],
  ];
  for (const [response, message] of cases) {
    const result = await page({ response });
    const button = result.dom.window.document.querySelector("[data-signed-download]");
    button.click();
    await flush();
    assert.deepEqual(result.navigations, []);
    assert.equal(result.alerts.at(-1), message);
    assert.equal(button.disabled, false);
    assert.equal(button.dataset.signedDownloadBusy, undefined);
  }
});

test("single-download ignores a double click while a request is pending", async () => {
  let resolveResponse;
  const result = await page({ response: () => new Promise((resolve) => { resolveResponse = resolve; }) });
  const button = result.dom.window.document.querySelector("[data-signed-download]");
  button.click();
  button.click();
  assert.equal(result.requests.length, 1);
  assert.equal(button.disabled, true);
  resolveResponse(jsonResponse(500, {}));
  await flush();
  assert.equal(button.disabled, false);
  assert.equal(button.dataset.signedDownloadBusy, undefined);
});

test("preview keeps its own fallback message and still opens a preview", async () => {
  const success = await page({
    preview: true,
    response: async (url) => jsonResponse(200, url === "/signed-preview"
      ? { ok: true, url: "https://storage.example/preview", kind: "image" }
      : { ok: true, url: "https://storage.example/download" }),
  });
  success.dom.window.document.querySelector("[data-preview-file-id]").click();
  await flush();
  assert.equal(success.previews[0].url, "https://storage.example/preview");

  const failure = await page({ preview: true, response: async () => jsonResponse(500, {}) });
  failure.dom.window.document.querySelector("[data-preview-file-id]").click();
  await flush();
  assert.equal(failure.alerts.at(-1), "Không thể tải preview.");
});
