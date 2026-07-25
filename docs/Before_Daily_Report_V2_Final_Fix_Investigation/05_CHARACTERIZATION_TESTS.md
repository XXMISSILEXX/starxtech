# Characterization tests

Added one research-only test in `tests_js/daily-report-create-v2.test.js`: it initializes the real V2 controller source, submits the form, provides a real `Response` with HTTP 409 and the API's duplicate-date JSON body, and asserts terminal failure state, spinner hidden, `aria-busy=false`, unlock, date invalid/focused, visible back-to-form action, and no beforeunload handler.

Result: **FAIL**. The direct error is `TypeError: Cannot read properties of undefined (reading 'name')` from `daily-report-create-v2.js:46`, so terminal assertions are unreachable. This is the characterization of Issue A, not a changed expectation to make an existing failure pass.

HEIC characterization: **cannot reproduce** because the exact file and browser runtime are absent. Status characterization: source metadata is complete; browser pseudo-element/font assertions are **environment-dependent** and require the capture guide.

The prior JS fixture has no spinner, no actual CSS/font, no `data-custom-select="status"`, no external script loading, no actual Create rendered HTML, and no save-error test. It therefore provided false confidence about the three runtime cases.
