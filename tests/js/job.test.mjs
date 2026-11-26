import { test } from "node:test";
import assert from "node:assert/strict";
import {
  columnsFor, errorsByBlock, errorMessage, fillVariables, findVariables, isEmptyTicket, isPrintable,
  newBlock, PRINTABLE_RANGES, ticketTitle, toJob, unprintable, withIds,
} from "../../src/escpos_api/ui/job.js";

test("columns match the server formula", () => {
  assert.equal(columnsFor(576), 48);
  assert.equal(columnsFor(576, "b"), 64);
  assert.equal(columnsFor(576, "a", 2), 24);
  assert.equal(columnsFor(384), 32);
  assert.equal(columnsFor(64, "a", 8), 1);
});

test("printable characters", () => {
  for (const ch of "aZ09 é€œ•…«»─═║╔░▓■\n") assert.ok(isPrintable(ch), ch);
  assert.deepEqual(unprintable("ok ☐ ✓ ★ → ♥ ☐"), ["☐", "✓", "★", "→", "♥"]);
  assert.deepEqual(unprintable(""), []);
  assert.deepEqual(unprintable(undefined), []);
});

test("printable ranges are sorted and disjoint", () => {
  for (let i = 0; i < PRINTABLE_RANGES.length; i += 1) {
    const [lo, hi] = PRINTABLE_RANGES[i];
    assert.ok(lo <= hi);
    if (i) assert.ok(lo > PRINTABLE_RANGES[i - 1][1]);
  }
});

test("toJob strips ids and default styles, ends texts with a newline", () => {
  const blocks = [newBlock("text", { content: "Hello", bold: true }), newBlock("separator"), newBlock("image", { data: "AAAA", name: "x.png" })];
  const job = toJob(blocks, { printer: "caisse" });
  assert.deepEqual(job, {
    cut: true,
    printer: "caisse",
    commands: [
      { type: "text", content: "Hello\n", bold: true },
      { type: "separator", char: "-" },
      { type: "image", data: "AAAA", align: "center", mode: "dither", threshold: 128 },
    ],
  });
  assert.equal(blocks[0].content, "Hello", "blocks are not mutated");
  assert.equal(toJob(blocks).printer, undefined);
});

test("explicit defaults are kept when a style block exists", () => {
  const blocks = withIds([{ type: "style", bold: true }, { type: "text", content: "x\n", bold: false, align: "left" }]);
  assert.equal(toJob(blocks).commands[1].bold, false);
});

test("newBlock rejects unknown types", () => {
  assert.throws(() => newBlock("cashdraw"));
});

test("empty ticket detection", () => {
  assert.ok(isEmptyTicket([]));
  assert.ok(isEmptyTicket([newBlock("text", { content: "  \n" }), newBlock("separator"), newBlock("cut")]));
  assert.ok(!isEmptyTicket([newBlock("qr", { content: "x" })]));
});

test("ticket title", () => {
  assert.equal(ticketTitle([newBlock("separator"), newBlock("text", { content: "\n  Courses du jour \nlait" })]), "Courses du jour");
  assert.equal(ticketTitle([newBlock("text", { content: "╔══╗" })], "Mémo"), "Mémo");
  assert.equal(ticketTitle([newBlock("text", { content: "«\n" }), newBlock("text", { content: "  Que sais-je ?\n" })]), "Que sais-je ?");
  assert.equal(ticketTitle([], "Mémo"), "Mémo");
});

test("variables", () => {
  const blocks = withIds([
    { type: "text", content: "Bonjour {{prenom}} {{ nom }}, {{prenom}}" },
    { type: "qr", content: "https://x/{{id}}" },
    { type: "separator", char: "{" },
  ]);
  assert.deepEqual(findVariables(blocks), ["prenom", "nom", "id"]);
  const filled = fillVariables(blocks, { prenom: "Léa", id: "42" });
  assert.equal(filled[0].content, "Bonjour Léa , Léa");
  assert.equal(filled[1].content, "https://x/42");
  assert.equal(blocks[0].content.includes("{{prenom}}"), true, "original untouched");
});

test("422 details are mapped to blocks", () => {
  assert.deepEqual(errorsByBlock({ details: [{ index: 2, reason: "bad ean" }] }), { 2: "bad ean" });
  assert.deepEqual(
    errorsByBlock({ details: [{ loc: ["body", "commands", 1, "qr", "size"], reason: "too big" }, { loc: ["body", "commands", 1, "qr", "ec"], reason: "nope" }] }),
    { 1: "too big ; nope" },
  );
  assert.deepEqual(errorsByBlock({ details: [{ loc: ["body", "printer"], reason: "x" }] }), {});
  assert.deepEqual(errorsByBlock(null), {});
});

test("error messages", () => {
  assert.match(errorMessage(502, { error: "printer_unreachable" }), /injoignable/);
  assert.match(errorMessage(0, null), /Serveur injoignable/);
  assert.match(errorMessage(500, { error: "internal_error" }), /500/);
});
