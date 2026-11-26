// Form helpers only: the built-in templates are rendered and tested server-side
// (tests/test_templates.py).
import { test } from "node:test";
import assert from "node:assert/strict";
import { autoValue, errorsByField, initialValues, isoDate, localNow, missingRequired } from "../../src/escpos_api/ui/templates.js";

const NOW = new Date(2026, 10, 25, 14, 7);

// Shape served by GET /v1/templates
const REMINDER = {
  id: "reminder",
  fields: [
    { key: "quoi", type: "text", required: true, max: 60, default: null, options: null, auto: null },
    { key: "quand", type: "date", required: false, default: null, options: null, auto: "today" },
    { key: "heure", type: "time", required: false, default: null, options: null, auto: null },
  ],
};
const MEMO = {
  id: "memo",
  fields: [
    { key: "message", type: "textarea", required: true, default: null, auto: null },
    { key: "date", type: "checkbox", required: false, default: true, auto: null },
    { key: "inverse", type: "checkbox", required: false, default: null, auto: null },
    { key: "priorite", type: "select", required: false, default: "normale", options: [{ value: "normale", label: "Normale" }], auto: null },
  ],
};

test("initial values: defaults, auto values, empty", () => {
  assert.deepEqual(initialValues(REMINDER, NOW), { quoi: "", quand: "2026-11-25", heure: "" });
  assert.deepEqual(initialValues(MEMO, NOW), { message: "", date: true, inverse: false, priorite: "normale" });
});

test("auto values match the server", () => {
  assert.equal(autoValue("today", NOW), "2026-11-25");
  assert.equal(autoValue("now", NOW), "14:07");
  assert.equal(autoValue("id", NOW), "T-1125-1407");
  assert.equal(autoValue(null, NOW), "");
  assert.equal(isoDate(NOW), "2026-11-25");
  assert.equal(localNow(NOW), "2026-11-25T14:07:00");
});

test("required fields are reported", () => {
  assert.deepEqual(missingRequired(MEMO, { message: "  " }), ["message"]);
  assert.deepEqual(missingRequired(MEMO, { message: "x" }), []);
});

test("422 details map to fields", () => {
  const body = {
    error: "invalid_job",
    details: [
      { loc: ["body", "values", "priorite"], reason: "Input should be 'basse', 'normale' or 'haute'" },
      { loc: ["body", "printer"], reason: "x" },
      { loc: ["body", "values"], reason: "y" },
    ],
  };
  assert.deepEqual(errorsByField(body), { priorite: "Input should be 'basse', 'normale' or 'haute'" });
  assert.deepEqual(errorsByField(null), {});
});
