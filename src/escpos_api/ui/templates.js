// Built-in memo templates. Each `build(values, ctx)` returns /v1/print commands (no ids).
// ctx = { columns: characters per line in font A at size 1, now: Date, random: () => [0, 1) }.
// Only characters printable by the server are used (see job.js PRINTABLE_RANGES).

const txt = (content, style = {}) => ({ type: "text", content: content.endsWith("\n") ? content : `${content}\n`, ...style });
const feed = (lines = 1) => ({ type: "feed", lines });
const sep = (char = "-") => ({ type: "separator", char });

export function wrapWords(text, width, indent = "") {
  const out = [];
  for (const paragraph of String(text).split("\n")) {
    let line = "";
    for (const word of paragraph.split(/\s+/).filter(Boolean)) {
      let w = word;
      while (w.length > width) {
        if (line) { out.push(line); line = ""; }
        out.push(w.slice(0, width));
        w = w.slice(width);
      }
      if (!line) line = w;
      else if (line.length + 1 + w.length <= width) line += ` ${w}`;
      else { out.push(line); line = w; }
    }
    out.push(line);
  }
  return out.map((l, i) => (i && indent ? indent + l : l));
}

/** Wrap with a hanging indent: "[ ] long task" → continuation aligned after the prefix. */
function hanging(prefix, text, columns) {
  const pad = " ".repeat(prefix.length);
  const lines = wrapWords(text, columns - prefix.length);
  return lines.map((l, i) => (i ? pad : prefix) + l).join("\n");
}

function centerPad(text, width) {
  const t = text.slice(0, width);
  const left = Math.floor((width - t.length) / 2);
  return " ".repeat(left) + t + " ".repeat(width - t.length - left);
}

/** Full-width inverted band (centered label). */
function band(label, columns, size = 1) {
  const width = Math.floor(columns / size);
  return txt(centerPad(label, width), { invert: true, bold: true, width: size, height: size });
}

function twoSides(left, right, width) {
  const space = Math.max(1, width - left.length - right.length);
  return left + " ".repeat(space) + right;
}

function lines(text) {
  return String(text ?? "").split("\n").map((l) => l.trim()).filter(Boolean);
}

const capital = (s) => s.charAt(0).toUpperCase() + s.slice(1);

export function longDate(d) {
  return capital(d.toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long", year: "numeric" }));
}

function parseDate(value) {
  // "2026-11-27" → local date (not UTC midnight)
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value ?? "");
  return m ? new Date(+m[1], +m[2] - 1, +m[3]) : null;
}

export function isoDate(d) {
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export function isoTime(d) {
  const p = (n) => String(n).padStart(2, "0");
  return `${p(d.getHours())}:${p(d.getMinutes())}`;
}

function stamp(ctx) {
  return txt(`${longDate(ctx.now)}, ${isoTime(ctx.now).replace(":", "h")}`, { font: "b", align: "right" });
}

export const QUOTES = [
  ["Il faut cultiver notre jardin.", "Voltaire"],
  ["Rien ne sert de courir ; il faut partir à point.", "Jean de La Fontaine"],
  ["Patience et longueur de temps font plus que force ni que rage.", "Jean de La Fontaine"],
  ["Le cœur a ses raisons que la raison ne connaît point.", "Blaise Pascal"],
  ["Que sais-je ?", "Michel de Montaigne"],
  ["Je pense, donc je suis.", "René Descartes"],
  ["Ceux qui vivent, ce sont ceux qui luttent.", "Victor Hugo"],
  ["Ce que l'on conçoit bien s'énonce clairement.", "Nicolas Boileau"],
  ["Hâtez-vous lentement, et sans perdre courage.", "Nicolas Boileau"],
  ["Le travail éloigne de nous trois grands maux : l'ennui, le vice et le besoin.", "Voltaire"],
  ["Le temps est un grand maître, dit-on. Le malheur est qu'il tue ses élèves.", "Hector Berlioz"],
];

const MOODS = {
  rayonnant: "(^o^)  Rayonnant",
  bien: "(^_^)  Bien",
  moyen: "(-_-)  Bof",
  fatigue: "(=_=)  Fatigué",
  orageux: "(>_<)  Orageux",
};

function wifiEscape(s) {
  return String(s).replace(/([\\;,:"])/g, "\\$1");
}

export const TEMPLATES = [
  {
    id: "memo",
    name: "Mémo",
    glyph: "▀▀",
    description: "Un titre, un message, la date. Le classique.",
    fields: [
      { key: "titre", label: "Titre", type: "text", max: 60, placeholder: "Appeler le plombier" },
      { key: "message", label: "Message", type: "textarea", max: 2000, required: true, placeholder: "Avant jeudi, pour la fuite sous l'évier." },
      { key: "signature", label: "Signé", type: "text", max: 40 },
      { key: "date", label: "Ajouter la date", type: "checkbox", default: true },
    ],
    build(v, ctx) {
      const out = [band("MÉMO", ctx.columns, 2), feed()];
      if (v.titre) out.push(txt(wrapWords(v.titre, Math.floor(ctx.columns / 2)).join("\n"), { bold: true, width: 2, height: 2 }), feed());
      if (v.message) out.push(txt(wrapWords(v.message, ctx.columns).join("\n")));
      if (v.signature) out.push(feed(), txt(`- ${v.signature}`, { align: "right" }));
      if (v.date) out.push(sep(), stamp(ctx));
      return out;
    },
  },
  {
    id: "todo",
    name: "À faire",
    glyph: "[ ]",
    description: "Une liste de tâches à cocher au stylo.",
    fields: [
      { key: "titre", label: "Titre", type: "text", default: "À faire", max: 40 },
      { key: "taches", label: "Tâches (une par ligne)", type: "textarea", required: true, max: 3000, placeholder: "Sortir les poubelles\nRépondre à Paul\nRéserver le train" },
      { key: "echeance", label: "Échéance", type: "date" },
      { key: "priorite", label: "Priorité", type: "select", default: "normale", options: [["basse", "Basse"], ["normale", "Normale"], ["haute", "Haute"]] },
    ],
    build(v, ctx) {
      const out = [];
      if (v.priorite === "haute") out.push(band("! URGENT !", ctx.columns, 2), feed());
      out.push(txt(v.titre || "À faire", { bold: true, width: 2, height: 2 }));
      const due = parseDate(v.echeance);
      if (due) out.push(txt(wrapWords(`Pour le ${longDate(due).toLowerCase()}`, ctx.columns).join("\n"), { underline: 1 }));
      out.push(sep("═"));
      const tasks = lines(v.taches);
      for (const t of tasks) out.push(txt(hanging("[ ] ", t, ctx.columns)), feed());
      out.push(sep("═"), txt(twoSides(`${tasks.length} tâche${tasks.length > 1 ? "s" : ""}`, `Priorité ${v.priorite ?? "normale"}`, ctx.columns), { font: "a" }), stamp(ctx));
      return out;
    },
  },
  {
    id: "shopping",
    name: "Courses",
    glyph: "▒▒",
    description: "La liste à emporter. Deux colonnes si les articles sont courts.",
    fields: [
      { key: "articles", label: "Articles (un par ligne)", type: "textarea", required: true, max: 3000, placeholder: "Lait\nPain\nTomates\nCafé" },
      { key: "magasin", label: "Magasin", type: "text", max: 40 },
    ],
    build(v, ctx) {
      const items = lines(v.articles);
      const out = [txt("COURSES", { bold: true, width: 3, height: 3, align: "center" })];
      if (v.magasin) out.push(txt(v.magasin, { align: "center", font: "b" }));
      out.push(sep("─"));
      const half = Math.floor(ctx.columns / 2);
      if (items.length > 4 && items.every((i) => i.length <= half - 5)) {
        const rows = Math.ceil(items.length / 2);
        const col = [];
        for (let r = 0; r < rows; r += 1) {
          const left = `[ ] ${items[r]}`.padEnd(half);
          const right = items[r + rows] ? `[ ] ${items[r + rows]}` : "";
          col.push((left + right).trimEnd());
        }
        out.push(txt(col.join("\n\n")));
      } else {
        out.push(txt(items.map((i) => hanging("[ ] ", i, ctx.columns)).join("\n\n")));
      }
      out.push(sep("─"), txt(`${items.length} article${items.length > 1 ? "s" : ""}`, { align: "right", font: "b" }));
      return out;
    },
  },
  {
    id: "postit",
    name: "Pense-bête XXL",
    glyph: "██",
    description: "Trois mots en énorme, à coller sur le frigo ou l'écran.",
    fields: [
      { key: "texte", label: "Texte", type: "text", required: true, max: 40, placeholder: "CLÉS !" },
      { key: "taille", label: "Taille", type: "select", default: "4", options: [["3", "Grand"], ["4", "Très grand"], ["6", "Énorme"]] },
      { key: "inverse", label: "Blanc sur noir", type: "checkbox", default: false },
    ],
    build(v, ctx) {
      const size = Number(v.taille) || 4;
      const width = Math.max(1, Math.floor(ctx.columns / size));
      const content = wrapWords(v.texte || "", width).map((l) => (v.inverse ? centerPad(l, width) : l)).join("\n");
      return [feed(), txt(content, { bold: true, width: size, height: size, align: "center", invert: !!v.inverse }), feed()];
    },
  },
  {
    id: "note",
    name: "Petit mot",
    glyph: "╔╗",
    description: "Pour quelqu'un, dans un cadre. À glisser sous une porte.",
    fields: [
      { key: "pour", label: "Pour", type: "text", max: 30, placeholder: "Camille" },
      { key: "message", label: "Message", type: "textarea", required: true, max: 1000, placeholder: "Il reste des lasagnes dans le frigo." },
      { key: "de", label: "De", type: "text", max: 30 },
    ],
    build(v, ctx) {
      const inner = ctx.columns - 4;
      const row = (s) => `║ ${s.padEnd(inner)} ║`;
      const body = [];
      if (v.pour) body.push(`Pour ${v.pour},`, "");
      body.push(...wrapWords(v.message || "", inner));
      if (v.de) body.push("", `${v.de}`.padStart(inner));
      const box = [`╔${"═".repeat(ctx.columns - 2)}╗`, row(""), ...body.map(row), row(""), `╚${"═".repeat(ctx.columns - 2)}╝`];
      return [txt(box.join("\n"))];
    },
  },
  {
    id: "reminder",
    name: "Rappel + lien",
    glyph: "▄▀",
    description: "Quoi, quand, et un QR code pour ouvrir le lien.",
    fields: [
      { key: "quoi", label: "Quoi", type: "text", required: true, max: 60, placeholder: "Renouveler le passeport" },
      { key: "quand", label: "Date", type: "date", auto: true },
      { key: "heure", label: "Heure", type: "time" },
      { key: "lien", label: "Lien (QR code)", type: "text", max: 500, placeholder: "https://…" },
      { key: "note", label: "Détails", type: "textarea", max: 1000 },
    ],
    build(v, ctx) {
      const out = [band("RAPPEL", ctx.columns, 2), feed(), txt(wrapWords(v.quoi || "", Math.floor(ctx.columns / 2)).join("\n"), { bold: true, width: 2, height: 2, align: "center" })];
      const day = parseDate(v.quand);
      if (day) out.push(txt(wrapWords(`${longDate(day)}${v.heure ? ` à ${v.heure.replace(":", "h")}` : ""}`, ctx.columns).join("\n"), { align: "center", underline: 1 }));
      if (v.note) out.push(feed(), txt(wrapWords(v.note, ctx.columns).join("\n")));
      if (v.lien) out.push(feed(), { type: "qr", content: v.lien, size: 6, ec: "M", align: "center" }, txt("Scanne pour ouvrir", { align: "center", font: "b" }));
      return out;
    },
  },
  {
    id: "wifi",
    name: "Wi-Fi invités",
    glyph: "((·))",
    description: "Le QR code qui connecte les invités sans rien taper.",
    fields: [
      { key: "ssid", label: "Nom du réseau", type: "text", required: true, max: 32 },
      { key: "password", label: "Mot de passe", type: "text", max: 63 },
      { key: "security", label: "Sécurité", type: "select", default: "WPA", options: [["WPA", "WPA/WPA2/WPA3"], ["WEP", "WEP"], ["nopass", "Aucune"]] },
      { key: "hidden", label: "Réseau masqué", type: "checkbox", default: false },
    ],
    build(v, ctx) {
      const security = v.security || "WPA";
      const pass = security === "nopass" ? "" : `P:${wifiEscape(v.password ?? "")};`;
      const qr = `WIFI:T:${security};S:${wifiEscape(v.ssid ?? "")};${pass}${v.hidden ? "H:true;" : ""};`;
      const out = [txt("Bienvenue !", { bold: true, width: 2, height: 2, align: "center" }), txt(wrapWords("Scanne pour te connecter au Wi-Fi", ctx.columns).join("\n"), { align: "center" }), feed(), { type: "qr", content: qr, size: 8, ec: "M", align: "center" }, feed(), sep("─")];
      out.push(txt(twoSides("Réseau", v.ssid ?? "", ctx.columns)));
      if (security !== "nopass") out.push(txt(twoSides("Mot de passe", v.password ?? "", ctx.columns), { bold: true }));
      return out;
    },
  },
  {
    id: "kanban",
    name: "Carte tâche",
    glyph: "|||",
    description: "Une carte de tableau Kanban, avec un code-barres d'identifiant.",
    fields: [
      { key: "titre", label: "Tâche", type: "text", required: true, max: 80, placeholder: "Migrer Traefik en v3" },
      { key: "projet", label: "Projet", type: "text", max: 24, placeholder: "homelab" },
      { key: "taille", label: "Estimation", type: "select", default: "M", options: [["XS", "XS"], ["S", "S"], ["M", "M"], ["L", "L"], ["XL", "XL"]] },
      { key: "id", label: "Identifiant", type: "text", max: 20, auto: "id" },
    ],
    build(v, ctx) {
      const out = [txt(twoSides(` ${(v.projet || "tâche").toUpperCase()} `, ` ${v.taille || "M"} `, ctx.columns), { invert: true, bold: true }), feed()];
      out.push(txt(wrapWords(v.titre || "", Math.floor(ctx.columns / 2)).join("\n"), { bold: true, width: 2, height: 2 }), feed());
      if (v.id) out.push({ type: "barcode", content: v.id, symbology: "CODE128", height: 60, module_width: 2, text_position: "below", align: "center" });
      out.push(txt(`Créée le ${isoDate(ctx.now).split("-").reverse().join("/")}`, { font: "b", align: "right" }));
      return out;
    },
  },
  {
    id: "journal",
    name: "Journal du jour",
    glyph: "≡",
    description: "Trois victoires, un merci, une humeur. Pour finir la journée.",
    fields: [
      { key: "jour", label: "Jour", type: "date", auto: true },
      { key: "victoires", label: "Trois victoires (une par ligne)", type: "textarea", max: 1000, placeholder: "Fini le rapport\nCouru 5 km\nAppelé mamie" },
      { key: "merci", label: "Merci pour…", type: "text", max: 120 },
      { key: "humeur", label: "Humeur", type: "select", default: "bien", options: [["rayonnant", "Rayonnant"], ["bien", "Bien"], ["moyen", "Bof"], ["fatigue", "Fatigué"], ["orageux", "Orageux"]] },
    ],
    build(v, ctx) {
      const day = parseDate(v.jour) ?? ctx.now;
      const out = [txt("Journal", { bold: true, width: 2, height: 2, align: "center" }), txt(longDate(day), { align: "center" }), sep("·")];
      const wins = lines(v.victoires).slice(0, 5);
      if (wins.length) {
        out.push(txt("Victoires du jour", { bold: true, underline: 1 }));
        wins.forEach((w, i) => out.push(txt(hanging(`${i + 1}. `, w, ctx.columns))));
        out.push(feed());
      }
      if (v.merci) out.push(txt("Merci pour", { bold: true, underline: 1 }), txt(wrapWords(v.merci, ctx.columns).join("\n")), feed());
      out.push(txt(MOODS[v.humeur] ?? MOODS.bien, { align: "center", width: 2 }));
      return out;
    },
  },
  {
    id: "quote",
    name: "Pensée du jour",
    glyph: "« »",
    description: "Une citation tirée au hasard, ou la tienne.",
    fields: [
      { key: "citation", label: "Citation (vide = au hasard)", type: "textarea", max: 500 },
      { key: "auteur", label: "Auteur", type: "text", max: 60 },
    ],
    build(v, ctx) {
      let [quote, author] = [v.citation, v.auteur];
      if (!quote) {
        const seed = ctx.quoteIndex ?? Math.floor(ctx.random() * QUOTES.length);
        [quote, author] = QUOTES[seed % QUOTES.length];
      }
      return [
        txt("«", { width: 3, height: 3, bold: true }),
        txt(wrapWords(quote, ctx.columns - 4).map((l) => `  ${l}`).join("\n"), { bold: true }),
        txt("»", { width: 3, height: 3, bold: true, align: "right" }),
        author ? txt(`- ${author}`, { align: "right" }) : null,
        sep("·"),
        txt(longDate(ctx.now), { font: "b", align: "center" }),
      ].filter(Boolean);
    },
  },
];

/** Initial form values: defaults, auto dates/times, generated ids. */
export function initialValues(template, now = new Date()) {
  const values = {};
  for (const f of template.fields) {
    if (f.default !== undefined) values[f.key] = f.default;
    else if (f.type === "checkbox") values[f.key] = false;
    else if (f.auto === "id") values[f.key] = `T-${isoDate(now).slice(5).replace("-", "")}-${isoTime(now).replace(":", "")}`;
    else if (f.type === "date" && f.auto) values[f.key] = isoDate(now);
    else if (f.type === "time" && f.auto) values[f.key] = isoTime(now);
    else values[f.key] = "";
  }
  return values;
}

export function missingRequired(template, values) {
  return template.fields.filter((f) => f.required && !String(values[f.key] ?? "").trim()).map((f) => f.key);
}

export function buildTemplate(template, values, ctx) {
  const full = { random: Math.random, now: new Date(), ...ctx };
  return template.build(values, full);
}
