const assert = require("node:assert/strict");
const fs = require("node:fs");
const test = require("node:test");
const source = fs.readFileSync("app/static/js/construction-progress.js", "utf8");
test("construction progress chart uses vertical bars and money stacks", () => {
  assert.match(source, /type: "bar"/);
  assert.match(source, /stack: "money"/);
  assert.match(source, /percentages/);
});
