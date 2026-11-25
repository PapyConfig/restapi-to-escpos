// Ticket model shared by the UI: blocks are /v1/print commands plus a local `id`.
// Pure module (no DOM), tested with `node --test tests/js`.

export const LIMITS = {
  text: 10000,
  size: [1, 8],
  underline: [0, 2],
  feed: [1, 255],
  qrSize: [1, 16],
  barcodeHeight: [1, 255],
  moduleWidth: [2, 6],
  threshold: [0, 255],
  commands: 500,
};

export const SYMBOLOGIES = [
  "CODE128", "EAN13", "EAN8", "UPC-A", "UPC-E", "CODE39", "CODE93", "ITF", "CODABAR",
];

// Characters the server can encode with the python-escpos "default" profile (code page
// switching). Derived by rendering every code point U+00A0..U+25FF; tests/test_ui.py checks
// the bounds of every range against the real renderer.
// prettier-ignore
export const PRINTABLE_RANGES = [
  [0x00A0, 0x00AC], [0x00AE, 0x0107], [0x010C, 0x0113], [0x0116, 0x011B], [0x011E, 0x011F],
  [0x0122, 0x0123], [0x0128, 0x012B], [0x012E, 0x0131], [0x0136, 0x0137], [0x0139, 0x013E],
  [0x0141, 0x0148], [0x014C, 0x014D], [0x0150, 0x015B], [0x015E, 0x0165], [0x0168, 0x016B],
  [0x016E, 0x0173], [0x0178, 0x017E], [0x0192, 0x0192], [0x01A0, 0x01A1], [0x01AF, 0x01B0],
  [0x02C6, 0x02C7], [0x02D8, 0x02D9], [0x02DB, 0x02DD], [0x037A, 0x037A], [0x0384, 0x0386],
  [0x0388, 0x038A], [0x038C, 0x038C], [0x038E, 0x03A1], [0x03A3, 0x03CE], [0x0401, 0x040C],
  [0x040E, 0x044F], [0x0451, 0x045C], [0x045E, 0x045F], [0x0490, 0x0491], [0x05BE, 0x05BE],
  [0x05C0, 0x05C0], [0x05C3, 0x05C3], [0x05D0, 0x05EA], [0x05F0, 0x05F4], [0x060C, 0x060C],
  [0x061B, 0x061B], [0x061F, 0x061F], [0x0621, 0x063A], [0x0640, 0x064A], [0x0660, 0x0669],
  [0x0679, 0x0679], [0x067E, 0x067E], [0x0686, 0x0686], [0x0688, 0x0688], [0x0691, 0x0691],
  [0x0698, 0x0698], [0x06A9, 0x06A9], [0x06AF, 0x06AF], [0x06BA, 0x06BA], [0x06BE, 0x06BE],
  [0x06C1, 0x06C1], [0x06D2, 0x06D2], [0x0E01, 0x0E30], [0x0E32, 0x0E33], [0x0E3F, 0x0E46],
  [0x0E4F, 0x0E5B], [0x1EA0, 0x1EF9], [0x2013, 0x2015], [0x2017, 0x201A], [0x201C, 0x201E],
  [0x2020, 0x2022], [0x2026, 0x2026], [0x2030, 0x2030], [0x2039, 0x203A], [0x207F, 0x207F],
  [0x20A7, 0x20A7], [0x20AA, 0x20AC], [0x20AF, 0x20AF], [0x2116, 0x2116], [0x2122, 0x2122],
  [0x2219, 0x221A], [0x221E, 0x221E], [0x2229, 0x2229], [0x2248, 0x2248], [0x2261, 0x2261],
  [0x2264, 0x2265], [0x2310, 0x2310], [0x2320, 0x2321], [0x2500, 0x2500], [0x2502, 0x2502],
  [0x250C, 0x250C], [0x2510, 0x2510], [0x2514, 0x2514], [0x2518, 0x2518], [0x251C, 0x251C],
  [0x2524, 0x2524], [0x252C, 0x252C], [0x2534, 0x2534], [0x253C, 0x253C], [0x2550, 0x256C],
  [0x2580, 0x2580], [0x2584, 0x2584], [0x2588, 0x2588], [0x258C, 0x258C], [0x2590, 0x2593],
  [0x25A0, 0x25A0],
];

export function isPrintable(ch) {
  const cp = ch.codePointAt(0);
  if (cp === 0x0a || (cp >= 0x20 && cp <= 0x7e)) return true;
  for (const [lo, hi] of PRINTABLE_RANGES) {
    if (cp < lo) return false;
    if (cp <= hi) return true;
  }
  return false;
}

/** Unique characters of `text` that would print as "?". */
export function unprintable(text) {
  const bad = new Set();
  for (const ch of text ?? "") if (!isPrintable(ch)) bad.add(ch);
  return [...bad];
}

/** Characters per line, same formula as PrinterConfig.columns on the server. */
export function columnsFor(width, font = "a", charWidth = 1) {
  const dots = font === "b" ? 9 : 12;
  return Math.max(1, Math.floor(width / (dots * charWidth)));
}

const DEFAULTS = {
  text: { content: "", align: "left", bold: false, underline: 0, font: "a", width: 1, height: 1, invert: false },
  separator: { char: "-" },
  feed: { lines: 1 },
  qr: { content: "", size: 6, ec: "M", align: "center" },
  barcode: { content: "", symbology: "CODE128", height: 80, module_width: 3, text_position: "below", align: "center" },
  image: { data: "", align: "center", mode: "dither", threshold: 128 },
  cut: { mode: "partial" },
};

export const BLOCK_TYPES = Object.keys(DEFAULTS);

let counter = 0;
export function newId() {
  counter += 1;
  return `b${Date.now().toString(36)}${counter}`;
}

/** A new block of `type`, with defaults overridden by `fields`. */
export function newBlock(type, fields = {}) {
  if (!(type in DEFAULTS)) throw new Error(`unknown block type ${type}`);
  return { id: newId(), type, ...structuredClone(DEFAULTS[type]), ...fields };
}

/** Give ids to raw commands (template output, history, import). */
export function withIds(commands) {
  return commands.map((c) => ({ ...structuredClone(c), id: newId() }));
}

const TEXT_DEFAULTS = DEFAULTS.text;

/** Blocks → the /v1/print command list (local ids and default styles stripped). */
export function toCommands(blocks) {
  // With a persistent `style` command in the ticket, explicit default values matter.
  const keepDefaults = blocks.some((b) => b.type === "style");
  return blocks.map((block) => {
    const { id: _id, ...cmd } = block;
    if (cmd.type === "text") {
      if (!cmd.content.endsWith("\n")) cmd.content += "\n";
      for (const [k, v] of Object.entries(TEXT_DEFAULTS)) {
        if (!keepDefaults && k !== "content" && cmd[k] === v) delete cmd[k];
      }
    }
    if (cmd.type === "image") delete cmd.name;
    return cmd;
  });
}

export function toJob(blocks, { printer = null, cut = true } = {}) {
  const job = { cut, commands: toCommands(blocks) };
  if (printer) job.printer = printer;
  return job;
}

/** Blocks that would be rejected or print nothing useful. */
export function isEmptyTicket(blocks) {
  return !blocks.some((b) =>
    (b.type === "text" && b.content.trim()) ||
    (b.type === "qr" && b.content) ||
    (b.type === "barcode" && b.content) ||
    (b.type === "image" && b.data),
  );
}

/** First non-empty text line, used as the history title. */
export function ticketTitle(blocks, fallback = "Ticket") {
  for (const b of blocks) {
    if (b.type !== "text") continue;
    const line = b.content.split("\n").map((l) => l.trim()).find(Boolean);
    if (line) return line.replace(/[═─│║╔╗╚╝┌┐└┘]/g, "").trim().slice(0, 60) || fallback;
  }
  return fallback;
}

const VAR = /\{\{\s*([\p{L}\p{N}_-]{1,40})\s*\}\}/gu;
const VAR_FIELDS = ["content"];

/** Variable names `{{name}}` found in text-like fields, in order of appearance. */
export function findVariables(blocks) {
  const names = [];
  for (const b of blocks) {
    for (const f of VAR_FIELDS) {
      if (typeof b[f] !== "string") continue;
      for (const m of b[f].matchAll(VAR)) if (!names.includes(m[1])) names.push(m[1]);
    }
  }
  return names;
}

/** Replace `{{name}}` with values (missing → empty string). Returns new blocks. */
export function fillVariables(blocks, values) {
  return blocks.map((b) => {
    const copy = { ...b };
    for (const f of VAR_FIELDS) {
      if (typeof copy[f] === "string") copy[f] = copy[f].replace(VAR, (_, n) => values[n] ?? "");
    }
    return copy;
  });
}

/** Map a 422 error body to {blockIndex: reason}. */
export function errorsByBlock(body) {
  const out = {};
  for (const d of body?.details ?? []) {
    let index = d.index;
    if (index === undefined && Array.isArray(d.loc)) {
      const i = d.loc.indexOf("commands");
      if (i >= 0 && Number.isInteger(d.loc[i + 1])) index = d.loc[i + 1];
    }
    if (Number.isInteger(index)) out[index] = out[index] ? `${out[index]} ; ${d.reason}` : d.reason;
  }
  return out;
}

/** Human message for an API error response. */
export function errorMessage(status, body) {
  switch (body?.error) {
    case "printer_unreachable": return "Imprimante injoignable : vérifie qu'elle est allumée et sur le réseau.";
    case "printer_timeout": return "L'imprimante ne répond pas (délai dépassé). Vérifie le papier et réessaie.";
    case "unknown_printer": return "Cette imprimante n'est plus déclarée sur le serveur.";
    case "payload_too_large": return "Ticket trop lourd : réduis ou retire une image.";
    case "invalid_job":
    case "invalid_image": return "Le ticket contient un bloc invalide : il est signalé en rouge. Rien n'a été imprimé.";
    case "unauthorized": return "Clé API manquante ou incorrecte.";
    case "forbidden_origin": return "Requête refusée : origine non autorisée.";
    default: return status ? `Erreur du serveur (${status}).` : "Serveur injoignable.";
  }
}
