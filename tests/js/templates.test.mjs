import { test } from "node:test";
import assert from "node:assert/strict";
import { TEMPLATES, QUOTES, buildTemplate, initialValues, missingRequired, wrapWords, isoDate } from "../../src/escpos_api/ui/templates.js";
import { unprintable, toJob, withIds, columnsFor, findVariables } from "../../src/escpos_api/ui/job.js";
import { layout } from "../../src/escpos_api/ui/preview.js";

const NOW = new Date(2026, 10, 25, 14, 7);
const SAMPLE = {
  memo: { titre: "Appeler le plombier", message: "Avant jeudi, pour la fuite sous l'évier.", signature: "Léo" },
  todo: { taches: "Sortir les poubelles\nRépondre à Paul au sujet de la réunion de jeudi prochain, sans faute\nRéserver le train", echeance: "2026-11-27", priorite: "haute" },
  shopping: { articles: "Lait\nPain\nTomates\nCafé\nBeurre doux", magasin: "Marché" },
  postit: { texte: "CLÉS !", inverse: true },
  note: { pour: "Camille", message: "Il reste des lasagnes dans le frigo. Bon appétit !", de: "Léo" },
  reminder: { quoi: "Renouveler le passeport", heure: "09:30", lien: "https://example.org/rdv", note: "Prendre deux photos." },
  wifi: { ssid: "Maison;Invités", password: 'p@ss:"1"' },
  kanban: { titre: "Migrer Traefik en v3", projet: "homelab" },
  journal: { victoires: "Fini le rapport\nCouru 5 km\nAppelé mamie", merci: "le soleil" },
  quote: {},
};

test("there are at least 8 memo templates with unique ids", () => {
  assert.ok(TEMPLATES.length >= 8);
  assert.equal(new Set(TEMPLATES.map((t) => t.id)).size, TEMPLATES.length);
});

for (const width of [576, 384]) {
  for (const t of TEMPLATES) {
    test(`${t.id} builds a valid, printable ticket at ${width} dots`, () => {
      const values = { ...initialValues(t, NOW), ...SAMPLE[t.id] };
      assert.deepEqual(missingRequired(t, values), []);
      const ctx = { columns: columnsFor(width), now: NOW, random: () => 0.3 };
      const commands = buildTemplate(t, values, ctx);
      assert.ok(commands.length > 0);
      const job = toJob(withIds(commands));
      for (const c of job.commands) {
        assert.ok(["text", "separator", "feed", "qr", "barcode"].includes(c.type), c.type);
        if (c.type === "text") {
          assert.deepEqual(unprintable(c.content), [], `${t.id}: ${c.content}`);
          const w = c.width ?? 1;
          const cols = columnsFor(width, c.font ?? "a", w);
          for (const line of c.content.slice(0, -1).split("\n")) {
            assert.ok([...line].length <= cols, `${t.id}: line too long for ${cols} cols: "${line}"`);
          }
          for (const k of ["width", "height"]) if (c[k] !== undefined) assert.ok(c[k] >= 1 && c[k] <= 8);
        }
        if (c.type === "separator") assert.equal([...c.char].length, 1);
      }
      assert.ok(layout(job.commands, width).height > 0);
    });

    test(`${t.id} does not crash with empty values at ${width} dots`, () => {
      const values = initialValues(t, NOW);
      const commands = buildTemplate(t, values, { columns: columnsFor(width), now: NOW });
      assert.ok(Array.isArray(commands));
    });
  }
}

test("required fields are reported", () => {
  const memo = TEMPLATES.find((t) => t.id === "memo");
  assert.deepEqual(missingRequired(memo, { message: "  " }), ["message"]);
});

test("auto values", () => {
  const reminder = TEMPLATES.find((t) => t.id === "reminder");
  assert.equal(initialValues(reminder, NOW).quand, "2026-11-25");
  const kanban = TEMPLATES.find((t) => t.id === "kanban");
  assert.equal(initialValues(kanban, NOW).id, "T-1125-1407");
  assert.equal(isoDate(NOW), "2026-11-25");
});

test("wifi QR escapes special characters", () => {
  const wifi = TEMPLATES.find((t) => t.id === "wifi");
  const qr = buildTemplate(wifi, { ssid: "a;b", password: 'p:"', security: "WPA", hidden: true }, { columns: 48, now: NOW }).find((c) => c.type === "qr");
  assert.equal(qr.content, String.raw`WIFI:T:WPA;S:a\;b;P:p\:\";H:true;;`);
  const open = buildTemplate(wifi, { ssid: "x", security: "nopass" }, { columns: 48, now: NOW }).find((c) => c.type === "qr");
  assert.equal(open.content, "WIFI:T:nopass;S:x;;");
});

test("quote is stable for a given index and covers the list", () => {
  const quote = TEMPLATES.find((t) => t.id === "quote");
  const a = buildTemplate(quote, {}, { columns: 48, now: NOW, quoteIndex: 3 });
  const b = buildTemplate(quote, {}, { columns: 48, now: NOW, quoteIndex: 3 });
  assert.deepEqual(a, b);
  for (const [q] of QUOTES) assert.deepEqual(unprintable(q), []);
});

test("todo has a box per task and an urgent band", () => {
  const todo = TEMPLATES.find((t) => t.id === "todo");
  const cmds = buildTemplate(todo, { titre: "À faire", taches: "a\nb\n\nc", priorite: "haute" }, { columns: 48, now: NOW });
  assert.equal(cmds.filter((c) => c.type === "text" && c.content.startsWith("[ ] ")).length, 3);
  assert.ok(cmds.some((c) => c.invert && c.content.includes("URGENT")));
});

test("built-in templates have no variables", () => {
  for (const t of TEMPLATES) {
    const commands = buildTemplate(t, { ...initialValues(t, NOW), ...SAMPLE[t.id] }, { columns: 48, now: NOW });
    assert.deepEqual(findVariables(commands), []);
  }
});

test("wrapWords", () => {
  assert.deepEqual(wrapWords("un deux trois", 7), ["un deux", "trois"]);
  assert.deepEqual(wrapWords("abcdefghij", 4), ["abcd", "efgh", "ij"]);
  assert.deepEqual(wrapWords("a\n\nb", 10), ["a", "", "b"]);
});
