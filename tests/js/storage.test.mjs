import { test } from "node:test";
import assert from "node:assert/strict";
import { addHistory, compactJob, exportTemplates, HISTORY_MAX, importTemplates, makeStore } from "../../src/escpos_api/ui/storage.js";

function memory() {
  const m = new Map();
  return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, v), removeItem: (k) => m.delete(k), m };
}

test("store round-trips JSON with a prefix", () => {
  const backend = memory();
  const s = makeStore(backend);
  assert.equal(s.read("x", 1), 1);
  assert.ok(s.write("x", { a: [1] }));
  assert.deepEqual(s.read("x"), { a: [1] });
  assert.ok(backend.m.has("escpos-ui:x"));
  s.remove("x");
  assert.equal(s.read("x", null), null);
});

test("store survives a broken or missing backend", () => {
  const broken = { getItem() { throw new Error("denied"); }, setItem() { throw new Error("quota"); }, removeItem() { throw new Error("x"); } };
  const s = makeStore(broken);
  assert.equal(s.read("x", "fallback"), "fallback");
  assert.equal(s.write("x", 1), false);
  s.remove("x");
  const none = makeStore(undefined);
  assert.equal(none.read("x", 2), 2);
  const corrupt = memory();
  corrupt.setItem("escpos-ui:x", "{not json");
  assert.equal(makeStore(corrupt).read("x", 3), 3);
});

test("history keeps the 30 most recent entries first", () => {
  let h = [];
  for (let i = 0; i < 35; i += 1) h = addHistory(h, { title: `t${i}`, job: { commands: [{ type: "text", content: "x\n" }] } });
  assert.equal(h.length, HISTORY_MAX);
  assert.equal(h[0].title, "t34");
  assert.equal(h.at(-1).title, "t5");
});

test("big jobs lose their images in history", () => {
  const job = { commands: [{ type: "text", content: "x\n" }, { type: "image", data: "A".repeat(500_000) }] };
  const small = compactJob(job);
  assert.deepEqual(small.commands, [{ type: "text", content: "x\n" }]);
  assert.equal(small.imagesRemoved, true);
  const tiny = { commands: [{ type: "image", data: "AAAA" }] };
  assert.equal(compactJob(tiny), tiny);
});

test("templates export / import", () => {
  const templates = [{ id: "u1", name: "Badge", blocks: [{ type: "text", content: "{{nom}}" }], createdAt: "2026-11-25T00:00:00Z" }];
  assert.deepEqual(importTemplates(exportTemplates(templates)), templates);
  const mixed = JSON.stringify({ version: 1, templates: [...templates, { name: "vide", blocks: [] }, { name: 3, blocks: [{ type: "text" }] }, { name: "bad", blocks: [null] }] });
  assert.equal(importTemplates(mixed).length, 1);
  assert.throws(() => importTemplates(JSON.stringify({ version: 2, templates: [] })), /non reconnu/);
  assert.throws(() => importTemplates("nope"), SyntaxError);
});
