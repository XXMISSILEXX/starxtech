const test = require("node:test");
const assert = require("node:assert/strict");
const date = require("../app/static/js/vietnamese-date.js");

test("Vietnamese date parser accepts strict DD/MM/YYYY", () => {
  assert.deepEqual(date.parse("27/07/2026"), { day: 27, month: 7, year: 2026, iso: "2026-07-27" });
  assert.equal(date.format(new Date(2026, 6, 27)), "27/07/2026");
});

test("Vietnamese date parser rejects invalid and ambiguous input", () => {
  for (const value of ["31/02/2026", "00/07/2026", "7/8/2026", "07/08/26", "08/07/2026x"]) {
    assert.equal(date.parse(value), null, value);
  }
});
