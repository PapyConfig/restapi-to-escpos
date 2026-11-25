import { test } from "node:test";
import assert from "node:assert/strict";
import { barcodeModules, layout, monochrome, qrModules, wrapChars } from "../../src/escpos_api/ui/preview.js";

const text = (content, style = {}) => ({ type: "text", content, ...style });

test("wrapChars wraps at the column count like the printer", () => {
  assert.deepEqual(wrapChars("", 4), [""]);
  assert.deepEqual(wrapChars("abcdefghij", 4), ["abcd", "efgh", "ij"]);
  assert.deepEqual(wrapChars("éé€€", 2), ["éé", "€€"]);
});

test("text rows follow newlines, columns and size", () => {
  const { rows } = layout([text("a\nb\n"), text("x".repeat(50) + "\n"), text("y".repeat(30) + "\n", { width: 2 })], 576);
  const texts = rows.filter((r) => r.kind === "text").map((r) => r.text);
  assert.deepEqual(texts, ["a", "b", "x".repeat(48), "xx", "y".repeat(24), "y".repeat(6)]);
});

test("empty lines produce blank rows; height grows with size", () => {
  const small = layout([text("a\n\nb\n")], 576);
  assert.equal(small.rows.length, 3);
  const big = layout([text("a\n", { height: 3 })], 576);
  assert.ok(big.height > layout([text("a\n")], 576).height * 2);
});

test("58 mm paper has 32 columns", () => {
  const { rows } = layout([text("z".repeat(40) + "\n")], 384);
  assert.deepEqual(rows.map((r) => r.text.length), [32, 8]);
});

test("separator fills the line for the current style", () => {
  const { rows } = layout([{ type: "style", font: "b" }, { type: "separator", char: "=" }], 576);
  assert.equal(rows[0].text, "=".repeat(64));
  assert.equal(rows[0].style.font, "b");
});

test("style persists until reset; text style is local", () => {
  const { rows } = layout([
    { type: "style", bold: true },
    text("a\n", { underline: 1 }),
    text("b\n"),
    { type: "style", reset: true, align: "right" },
    text("c\n"),
  ], 576);
  assert.deepEqual(rows.map((r) => [r.text, r.style.bold, r.style.underline, r.style.align]), [
    ["a", true, 1, "left"], ["b", true, 0, "left"], ["c", false, 0, "right"],
  ]);
});

test("feeds, qr, barcode, image and cut rows", () => {
  const blocks = [
    { type: "feed", lines: 2 },
    { type: "qr", content: "https://example.org", size: 6 },
    { type: "barcode", content: "12345", symbology: "CODE128", height: 60, module_width: 2, text_position: "both" },
    { type: "image", data: "x", align: "left" },
    { type: "image", data: "y", width: 200 },
    { type: "cut" },
  ];
  const sizes = { x: { width: 100, height: 50 }, y: { width: 1000, height: 500 } };
  const { rows } = layout(blocks, 576, (b) => sizes[b.data]);
  assert.deepEqual(rows.map((r) => r.kind), ["space", "qr", "barcode", "image", "image", "cut"]);
  assert.equal(rows[0].height, 60);
  assert.equal(rows[1].size, qrModules("https://example.org") * 6);
  assert.equal(rows[2].width, barcodeModules("12345", "CODE128") * 2);
  assert.deepEqual([rows[3].width, rows[3].height], [100, 50], "small images are not enlarged");
  assert.deepEqual([rows[4].width, rows[4].height], [200, 100], "large images are scaled to width");
  assert.ok(rows.every((r, i) => i === 0 || r.y === rows[i - 1].y + rows[i - 1].height));
});

test("images scale to paper width and placeholder before decoding", () => {
  const { rows } = layout([{ type: "image", data: "z" }], 384, () => ({ width: 1200, height: 600 }));
  assert.deepEqual([rows[0].width, rows[0].height], [384, 192]);
  const pending = layout([{ type: "image", data: "z" }], 384);
  assert.equal(pending.rows[0].ready, false);
});

test("qr version grows with content", () => {
  assert.equal(qrModules("a"), 21);
  assert.ok(qrModules("a".repeat(200)) > qrModules("a".repeat(20)));
  assert.ok(qrModules("a".repeat(5000)) <= 17 + 4 * 40);
  assert.equal(barcodeModules("123456789012", "EAN13"), 95);
});

test("monochrome threshold and dither", () => {
  assert.deepEqual([...monochrome(Uint8Array.from([0, 100, 200, 255]), 4, 1, "threshold", 150)], [0, 0, 255, 255]);
  const gray = new Uint8Array(100).fill(128);
  const out = monochrome(gray, 10, 10, "dither");
  const black = out.filter((v) => v === 0).length;
  assert.ok(black > 30 && black < 70, `mid-grey dithers to ~50% black, got ${black}`);
  assert.ok(out.every((v) => v === 0 || v === 255));
});
