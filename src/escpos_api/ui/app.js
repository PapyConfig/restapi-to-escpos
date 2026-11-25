// Web UI: DOM, state and API calls. Pure logic lives in job.js / templates.js / preview.js.

import {
  BLOCK_TYPES, LIMITS, SYMBOLOGIES, columnsFor, errorMessage, errorsByBlock, fillVariables,
  findVariables, isEmptyTicket, newBlock, ticketTitle, toJob, unprintable, withIds,
} from "./job.js";
import { TEMPLATES, buildTemplate, initialValues, missingRequired } from "./templates.js";
import { decodeImage, draw, layout, toBitmap } from "./preview.js";
import { addHistory, exportTemplates, importTemplates, makeStore } from "./storage.js";

const store = makeStore(globalThis.localStorage);
const session = makeStore(globalThis.sessionStorage);

const MAX_IMAGE_BYTES = 10 * 1024 * 1024;

const state = {
  tab: "templates",
  printers: [],
  printer: store.read("printer", null),
  template: null, // {kind: "builtin"|"user", def}
  values: {},
  blocks: store.read("draft", null) ?? starterBlocks(),
  userTemplates: store.read("templates", []),
  history: store.read("history", []),
  historyPick: null,
  errors: {},
  busy: false,
};

function starterBlocks() {
  return withIds([
    { type: "text", content: "Mon ticket", bold: true, width: 2, height: 2, align: "center" },
    { type: "separator", char: "─" },
    { type: "text", content: "Écris ici, ajoute un QR code, une image…" },
  ]);
}

// -- tiny DOM helper (never innerHTML with user data) ------------------------------------

function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === undefined || v === null || v === false) continue;
    if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "class") el.className = v;
    else if (k === "value") el.value = v;
    else if (k === "checked") el.checked = !!v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) if (c !== null && c !== undefined && c !== false) el.append(c);
  return el;
}

const $ = (id) => document.getElementById(id);

// -- printers -----------------------------------------------------------------------------

function currentPrinter() {
  return state.printers.find((p) => p.name === state.printer) ?? state.printers.find((p) => p.default) ?? null;
}

function paperWidth() {
  return currentPrinter()?.width ?? 576;
}

async function loadPrinters() {
  const select = $("printer-select");
  try {
    state.printers = await api("/v1/printers");
  } catch (err) {
    select.replaceChildren(h("option", { value: "" }, "Imprimantes indisponibles"));
    $("printer-dot").dataset.state = "down";
    toast(err.message, "error");
    return;
  }
  if (!state.printers.some((p) => p.name === state.printer)) state.printer = currentPrinter()?.name ?? null;
  select.replaceChildren(
    ...state.printers.map((p) =>
      h("option", { value: p.name, selected: p.name === state.printer }, `${p.name}${p.reachable ? "" : " (hors ligne)"}`),
    ),
  );
  updatePrinterDot();
  render();
}

function updatePrinterDot() {
  const p = currentPrinter();
  $("printer-dot").dataset.state = p ? (p.reachable ? "ok" : "down") : "";
  $("printer-dot").title = p ? (p.reachable ? "Imprimante en ligne" : "Imprimante injoignable") : "";
}

// -- API --------------------------------------------------------------------------------

class ApiFailure extends Error {
  constructor(status, body) {
    super(errorMessage(status, body));
    this.status = status;
    this.body = body;
  }
}

async function api(path, options = {}, retried = false) {
  const headers = { ...(options.headers ?? {}) };
  const key = session.read("key", null);
  if (key) headers["X-API-Key"] = key;
  let response;
  try {
    response = await fetch(path, { ...options, headers, credentials: "same-origin" });
  } catch {
    throw new ApiFailure(0, null);
  }
  const body = await response.json().catch(() => null);
  if (response.status === 401 && !retried) {
    const entered = await askKey();
    if (entered) return api(path, options, true);
  }
  if (!response.ok) throw new ApiFailure(response.status, body);
  return body;
}

function askKey() {
  const dialog = $("key-dialog");
  const input = $("key-input");
  input.value = "";
  return new Promise((resolve) => {
    const done = (ok) => {
      dialog.close();
      if (ok && input.value.trim()) {
        session.write("key", input.value.trim());
        resolve(true);
      } else resolve(false);
    };
    $("key-form").onsubmit = (e) => { e.preventDefault(); done(true); };
    $("key-cancel").onclick = () => done(false);
    dialog.showModal();
    input.focus();
  });
}

function askName(help) {
  const dialog = $("name-dialog");
  const input = $("name-input");
  input.value = "";
  $("name-help").textContent = help;
  return new Promise((resolve) => {
    $("name-form").onsubmit = (e) => { e.preventDefault(); dialog.close(); resolve(input.value.trim() || null); };
    $("name-cancel").onclick = () => { dialog.close(); resolve(null); };
    dialog.showModal();
    input.focus();
  });
}

// -- current ticket -----------------------------------------------------------------------

function ctx() {
  return { columns: columnsFor(paperWidth()), now: new Date(), quoteIndex: state.quoteIndex };
}

/** Blocks shown in the preview and printed, for the active tab. */
function currentBlocks() {
  if (state.tab === "editor") return state.blocks;
  if (state.tab === "history") return state.historyPick?.job.commands ?? [];
  if (!state.template) return [];
  if (state.template.kind === "user") return fillVariables(state.template.def.blocks, state.values);
  return buildTemplate(state.template.def, state.values, ctx());
}

function canPrint() {
  if (state.busy || !currentPrinter()) return false;
  const blocks = currentBlocks();
  if (!blocks.length || isEmptyTicket(blocks)) return false;
  if (state.tab === "templates" && state.template?.kind === "builtin") {
    return missingRequired(state.template.def, state.values).length === 0;
  }
  return true;
}

async function printCurrent() {
  if (!canPrint()) return;
  const blocks = currentBlocks();
  const printer = currentPrinter();
  const job = toJob(blocks, { printer: printer.name });
  state.busy = true;
  state.errors = {};
  renderPrintBar();
  $("print-button").textContent = "Impression…";
  try {
    await api("/v1/print", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(job),
    });
    state.history = addHistory(state.history, { at: new Date().toISOString(), title: ticketTitle(blocks, state.template?.def.name ?? "Ticket"), printer: printer.name, job });
    store.write("history", state.history);
    toast("Imprimé");
    const paper = $("paper");
    paper.classList.remove("feeding");
    void paper.offsetWidth;
    paper.classList.add("feeding");
  } catch (err) {
    if (err.status === 422 && err.body) {
      state.errors = errorsByBlock(err.body);
      if (state.tab !== "editor" && Object.keys(state.errors).length) {
        toast(`${err.message} Ouvre le ticket dans l'éditeur pour corriger.`, "error");
      } else toast(err.message, "error");
    } else toast(err.message, "error");
    if (err.body?.error === "printer_unreachable" || err.body?.error === "printer_timeout") {
      const p = currentPrinter();
      if (p) p.reachable = false;
      updatePrinterDot();
    }
  } finally {
    state.busy = false;
    $("print-button").textContent = "Imprimer";
    if (state.tab === "editor") renderEditor();
    render();
  }
}

// -- preview ------------------------------------------------------------------------------

const decoded = new Map(); // data → {width, height, source} | "pending" | "error"
const bitmaps = new Map();

function imageSize(block) {
  const d = decoded.get(block.data);
  if (d && typeof d === "object") return d;
  if (!d && block.data) {
    decoded.set(block.data, "pending");
    decodeImage(block.data)
      .then((img) => { decoded.set(block.data, img); render(); })
      .catch(() => decoded.set(block.data, "error"));
  }
  return null;
}

function bitmapFor(block, width) {
  const d = decoded.get(block.data);
  if (!d || typeof d !== "object") return null;
  const key = `${block.data.length}:${block.data.slice(-32)}:${width}:${block.mode}:${block.threshold}`;
  if (!bitmaps.has(key)) {
    if (bitmaps.size > 20) bitmaps.clear();
    bitmaps.set(key, toBitmap(d, width, block.mode ?? "dither", block.threshold ?? 128));
  }
  return bitmaps.get(key);
}

let frame = 0;
function render() {
  cancelAnimationFrame(frame);
  frame = requestAnimationFrame(() => {
    const blocks = currentBlocks();
    const paper = paperWidth();
    const result = layout(blocks, paper, imageSize);
    const highlight = state.tab === "editor" ? new Set(Object.keys(state.errors).map(Number)) : null;
    draw($("preview"), result, paper, bitmapFor, highlight);
    const p = currentPrinter();
    const mm = Math.round(result.height / 8);
    $("paper-info").textContent = p ? `${p.width === 384 ? "58" : "80"} mm · ${columnsFor(paper)} colonnes · ~${mm} mm de papier` : "";
    const bad = unprintable(blocks.filter((b) => b.type === "text" || b.type === "separator").map((b) => b.content ?? b.char ?? "").join(""));
    $("warnings").textContent = bad.length ? `Ces caractères sortiront en « ? » : ${bad.join(" ")}` : "";
    renderPrintBar();
  });
}

function renderPrintBar() {
  $("print-button").disabled = !canPrint();
}

// -- tabs ---------------------------------------------------------------------------------

function setTab(tab) {
  state.tab = tab;
  for (const name of ["templates", "editor", "history"]) {
    $(`tab-${name}`).setAttribute("aria-selected", String(name === tab));
    $(`tab-${name}`).tabIndex = name === tab ? 0 : -1;
    $(`panel-${name}`).hidden = name !== tab;
  }
  if (tab === "templates") renderTemplates();
  if (tab === "editor") renderEditor();
  if (tab === "history") renderHistory();
  render();
}

// -- templates tab ------------------------------------------------------------------------

function renderTemplates() {
  const panel = $("panel-templates");
  if (state.template) {
    panel.replaceChildren(templateForm());
    return;
  }
  const item = (glyph, name, desc, onclick) =>
    h("li", {},
      h("button", { class: "template-item", type: "button", onclick },
        h("span", { class: "glyph", "aria-hidden": "true" }, glyph),
        h("span", {}, h("span", { class: "template-name" }, name), h("span", { class: "template-desc" }, desc))));

  const builtin = TEMPLATES.map((t) => item(t.glyph, t.name, t.description, () => openTemplate({ kind: "builtin", def: t })));
  const mine = state.userTemplates.map((t) =>
    h("li", { class: "user-template" },
      h("button", { class: "template-item", type: "button", onclick: () => openTemplate({ kind: "user", def: t }) },
        h("span", { class: "glyph", "aria-hidden": "true" }, "{ }"),
        h("span", {},
          h("span", { class: "template-name" }, t.name),
          h("span", { class: "template-desc" }, fieldsSummary(t))),
      ),
      h("div", { class: "row-actions" },
        h("button", { class: "secondary small danger", type: "button", onclick: () => deleteTemplate(t) }, "Supprimer")),
    ));

  const importInput = h("input", { type: "file", accept: "application/json,.json", onchange: (e) => importFile(e.target) });
  panel.replaceChildren(
    h("h2", { class: "section-title" }, "Mémos"),
    h("ul", { class: "template-list" }, builtin),
    h("h2", { class: "section-title" }, "Mes modèles"),
    mine.length
      ? h("ul", { class: "template-list" }, mine)
      : h("p", { class: "empty" }, "Compose un ticket dans l'éditeur puis « Enregistrer comme modèle ». Écris {{prenom}} pour créer un champ à remplir."),
    h("div", { class: "actions" },
      h("button", { class: "secondary", type: "button", onclick: exportFile, disabled: !state.userTemplates.length }, "Exporter mes modèles"),
      h("label", { class: "file-button" }, "Importer des modèles", importInput)),
  );
}

function fieldsSummary(t) {
  const vars = findVariables(t.blocks);
  return vars.length ? `Champs : ${vars.join(", ")}` : `${t.blocks.length} blocs, sans champ`;
}

function openTemplate(tpl) {
  state.template = tpl;
  state.quoteIndex = Math.floor(Math.random() * 1000); // stable between preview and print
  if (tpl.kind === "builtin") state.values = initialValues(tpl.def);
  else state.values = Object.fromEntries(findVariables(tpl.def.blocks).map((v) => [v, ""]));
  renderTemplates();
  render();
  $("panel-templates").querySelector("input, textarea, select")?.focus();
}

function templateFields() {
  const t = state.template;
  if (t.kind === "builtin") return t.def.fields;
  return findVariables(t.def.blocks).map((key) => ({ key, label: key, type: "text", max: 500 }));
}

function templateForm() {
  const t = state.template;
  const onInput = (key, value) => {
    state.values[key] = value;
    render();
  };
  const fields = templateFields().map((f) => {
    const id = `f-${f.key}`;
    if (f.type === "checkbox") {
      return h("label", { class: "check" },
        h("input", { type: "checkbox", id, checked: state.values[f.key], onchange: (e) => onInput(f.key, e.target.checked) }),
        f.label);
    }
    let control;
    if (f.type === "textarea") {
      control = h("textarea", { id, maxlength: f.max, placeholder: f.placeholder, rows: 4, oninput: (e) => onInput(f.key, e.target.value) });
      control.value = state.values[f.key] ?? "";
    } else if (f.type === "select") {
      control = h("select", { id, onchange: (e) => onInput(f.key, e.target.value) },
        f.options.map(([v, label]) => h("option", { value: v, selected: state.values[f.key] === v }, label)));
    } else {
      control = h("input", { id, type: f.type === "date" || f.type === "time" ? f.type : "text", maxlength: f.max, placeholder: f.placeholder, value: state.values[f.key] ?? "", oninput: (e) => onInput(f.key, e.target.value), required: f.required });
    }
    return h("label", { class: "field", for: id }, h("span", {}, f.label, f.required ? " *" : ""), control);
  });

  const extra = [];
  if (t.kind === "builtin" && t.def.id === "quote") {
    extra.push(h("button", { class: "secondary", type: "button", onclick: () => { state.quoteIndex = Math.floor(Math.random() * 1000); render(); } }, "Une autre citation"));
  }

  return h("div", {},
    h("div", { class: "form-head" },
      h("h2", {}, t.def.name),
      h("button", { class: "ghost small", type: "button", onclick: () => { state.template = null; renderTemplates(); render(); } }, "Tous les modèles")),
    t.kind === "builtin" ? h("p", { class: "template-desc" }, t.def.description) : null,
    h("form", { onsubmit: (e) => { e.preventDefault(); printCurrent(); } }, fields),
    h("div", { class: "actions" },
      ...extra,
      h("button", { class: "secondary", type: "button", onclick: openInEditor }, "Ouvrir dans l'éditeur")),
  );
}

function openInEditor() {
  const blocks = currentBlocks();
  if (!blocks.length) return;
  state.blocks = withIds(blocks.map(({ id: _id, ...b }) => b));
  saveDraft();
  setTab("editor");
}

function deleteTemplate(t) {
  if (!confirm(`Supprimer le modèle « ${t.name} » ?`)) return;
  state.userTemplates = state.userTemplates.filter((x) => x.id !== t.id);
  store.write("templates", state.userTemplates);
  renderTemplates();
}

function exportFile() {
  const blob = new Blob([exportTemplates(state.userTemplates)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  h("a", { href: url, download: "modeles-tickets.json" }).click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function importFile(input) {
  const file = input.files?.[0];
  input.value = "";
  if (!file) return;
  try {
    const imported = importTemplates(await file.text());
    const names = new Set(state.userTemplates.map((t) => t.name));
    const fresh = imported.filter((t) => !names.has(t.name));
    state.userTemplates = [...state.userTemplates, ...fresh];
    if (!store.write("templates", state.userTemplates)) throw new Error("Le navigateur refuse d'enregistrer (stockage plein ou bloqué).");
    toast(`${fresh.length} modèle${fresh.length > 1 ? "s" : ""} importé${fresh.length > 1 ? "s" : ""}`);
    renderTemplates();
  } catch (err) {
    toast(err instanceof SyntaxError ? "Fichier illisible : JSON invalide." : err.message, "error");
  }
}

// -- editor tab ---------------------------------------------------------------------------

const BLOCK_LABELS = {
  text: "Texte", separator: "Séparateur", feed: "Espace", qr: "QR code", barcode: "Code-barres",
  image: "Image", cut: "Coupe", style: "Style (persistant)", cashdraw: "Tiroir-caisse",
};

let draftTimer = 0;
function saveDraft() {
  clearTimeout(draftTimer);
  draftTimer = setTimeout(() => {
    const text = JSON.stringify(state.blocks);
    if (text.length < 1_000_000) store.write("draft", state.blocks);
  }, 300);
}

function changed({ rerender = false } = {}) {
  state.errors = {};
  saveDraft();
  if (rerender) renderEditor();
  else for (const el of document.querySelectorAll(".block[data-error]")) {
    el.removeAttribute("data-error");
    el.querySelector(".block-error")?.remove();
  }
  render();
}

function renderEditor() {
  const panel = $("panel-editor");
  const add = h("div", { class: "add-bar", role: "group", "aria-label": "Ajouter un bloc" },
    h("span", {}, "Ajouter"),
    BLOCK_TYPES.map((type) =>
      h("button", { class: "secondary small", type: "button", onclick: () => addBlock(type) }, BLOCK_LABELS[type])));
  const list = h("ol", { class: "blocks" }, state.blocks.map((b, i) => blockEditor(b, i)));
  panel.replaceChildren(
    add,
    state.blocks.length ? list : h("p", { class: "empty" }, "Ticket vide. Ajoute un bloc Texte pour commencer."),
    h("div", { class: "actions" },
      h("button", { class: "secondary", type: "button", onclick: saveAsTemplate, disabled: !state.blocks.length }, "Enregistrer comme modèle"),
      h("button", { class: "ghost danger", type: "button", onclick: clearTicket, disabled: !state.blocks.length }, "Vider le ticket")),
  );
}

function addBlock(type) {
  if (state.blocks.length >= LIMITS.commands) return toast("500 blocs au maximum.", "error");
  state.blocks.push(newBlock(type, type === "separator" ? { char: "─" } : {}));
  changed({ rerender: true });
  const last = $("panel-editor").querySelector(".block:last-child");
  last?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  last?.querySelector("textarea, input, select")?.focus();
}

function moveBlock(i, delta) {
  const j = i + delta;
  if (j < 0 || j >= state.blocks.length) return;
  [state.blocks[i], state.blocks[j]] = [state.blocks[j], state.blocks[i]];
  changed({ rerender: true });
  $("panel-editor").querySelectorAll(".block")[j]?.querySelector(`[data-move="${delta}"]`)?.focus();
}

function clearTicket() {
  if (!confirm("Vider le ticket en cours ?")) return;
  state.blocks = [];
  changed({ rerender: true });
}

async function saveAsTemplate() {
  const vars = findVariables(state.blocks);
  const help = vars.length
    ? `Champs détectés : ${vars.join(", ")}. Ils seront à remplir à chaque impression.`
    : "Astuce : écris {{prenom}} dans un texte pour en faire un champ à remplir.";
  const name = await askName(help);
  if (!name) return;
  const tpl = { id: `u${Date.now().toString(36)}`, name, blocks: state.blocks.map(({ id: _id, ...b }) => b), createdAt: new Date().toISOString() };
  state.userTemplates = [...state.userTemplates.filter((t) => t.name !== name), tpl];
  if (store.write("templates", state.userTemplates)) toast(`Modèle « ${name} » enregistré`);
  else toast("Le navigateur refuse d'enregistrer (stockage plein ou bloqué).", "error");
}

function num(block, key, [min, max], label) {
  return h("label", {}, label,
    h("input", { type: "number", min, max, value: block[key], inputmode: "numeric", onchange: (e) => {
      const v = Math.min(max, Math.max(min, Math.round(Number(e.target.value) || min)));
      e.target.value = v;
      block[key] = v;
      changed();
    } }));
}

function choice(block, key, options, label) {
  return h("label", {}, label,
    h("select", { onchange: (e) => { block[key] = /^\d+$/.test(e.target.value) ? Number(e.target.value) : e.target.value; changed(); } },
      options.map(([v, text]) => h("option", { value: v, selected: String(block[key]) === String(v) }, text))));
}

function alignSeg(block) {
  const seg = h("div", { class: "seg", role: "group", "aria-label": "Alignement" });
  for (const [v, label, glyph] of [["left", "Gauche", "⇤"], ["center", "Centre", "↔"], ["right", "Droite", "⇥"]]) {
    seg.append(h("button", { type: "button", title: label, "aria-label": label, "aria-pressed": String(block.align === v), onclick: (e) => {
      block.align = v;
      for (const b of seg.children) b.setAttribute("aria-pressed", "false");
      e.currentTarget.setAttribute("aria-pressed", "true");
      changed();
    } }, glyph));
  }
  return seg;
}

function toggle(block, key, label, glyph) {
  return h("button", { type: "button", title: label, "aria-label": label, "aria-pressed": String(!!block[key]), onclick: (e) => {
    block[key] = key === "underline" ? (block[key] ? 0 : 1) : !block[key];
    e.currentTarget.setAttribute("aria-pressed", String(!!block[key]));
    changed();
  } }, glyph);
}

const SIZES = [1, 2, 3, 4, 5, 6, 7, 8].map((n) => [n, `×${n}`]);

function warnFor(text) {
  const bad = unprintable(text);
  return bad.length ? `Non imprimable : ${bad.join(" ")} (sortira en « ? »)` : "";
}

function blockEditor(block, i) {
  const warn = h("p", { class: "block-warn", role: "status" });
  const setWarn = (text) => { warn.textContent = warnFor(text); };
  let body;
  switch (block.type) {
    case "text": {
      const fit = (el) => { el.rows = Math.min(10, Math.max(1, el.value.split("\n").length)); };
      const area = h("textarea", { rows: 1, maxlength: LIMITS.text, "aria-label": "Texte", oninput: (e) => { block.content = e.target.value; fit(e.target); setWarn(block.content); changed(); } });
      area.value = block.content;
      fit(area);
      setWarn(block.content);
      const preset = (label, style) => h("button", { class: "secondary small", type: "button", onclick: () => { Object.assign(block, style); changed({ rerender: true }); } }, label);
      body = [
        area,
        h("div", { class: "controls" },
          alignSeg(block),
          h("div", { class: "seg", role: "group", "aria-label": "Style" },
            toggle(block, "bold", "Gras", "G"),
            toggle(block, "underline", "Souligné", "S"),
            toggle(block, "invert", "Blanc sur noir", "◐")),
          choice(block, "width", SIZES, "Largeur"),
          choice(block, "height", SIZES, "Hauteur"),
          choice(block, "font", [["a", "Normale"], ["b", "Compacte"]], "Police")),
        h("div", { class: "controls presets" },
          preset("Titre", { bold: true, width: 2, height: 2, font: "a", invert: false }),
          preset("Normal", { bold: false, width: 1, height: 1, font: "a", invert: false, underline: 0 }),
          preset("Petit", { bold: false, width: 1, height: 1, font: "b", invert: false }),
          preset("Bandeau", { bold: true, width: 2, height: 2, invert: true, align: "center" })),
      ];
      break;
    }
    case "separator": {
      const input = h("input", { type: "text", maxlength: 1, value: block.char, "aria-label": "Caractère", oninput: (e) => { block.char = e.target.value || "-"; setWarn(block.char); changed(); } });
      input.style.width = "4em";
      setWarn(block.char);
      body = [h("div", { class: "controls" },
        h("label", {}, "Caractère", input),
        h("div", { class: "presets" }, ["-", "=", "─", "═", "·", "*", "~"].map((c) =>
          h("button", { class: "secondary small", type: "button", onclick: () => { block.char = c; input.value = c; setWarn(c); changed(); } }, c))))];
      break;
    }
    case "feed":
      body = [h("div", { class: "controls" }, num(block, "lines", LIMITS.feed, "Lignes"))];
      break;
    case "qr": {
      const area = h("textarea", { rows: 2, maxlength: 4000, "aria-label": "Contenu du QR code", placeholder: "https://… ou n'importe quel texte", oninput: (e) => { block.content = e.target.value; changed(); } });
      area.value = block.content;
      body = [area, h("div", { class: "controls" },
        num(block, "size", LIMITS.qrSize, "Taille"),
        choice(block, "ec", [["L", "L (7 %)"], ["M", "M (15 %)"], ["Q", "Q (25 %)"], ["H", "H (30 %)"]], "Correction"),
        alignSeg(block))];
      break;
    }
    case "barcode":
      body = [
        h("input", { type: "text", maxlength: 255, value: block.content, "aria-label": "Contenu du code-barres", placeholder: block.symbology === "EAN13" ? "12 ou 13 chiffres" : "Texte ou chiffres", oninput: (e) => { block.content = e.target.value; changed(); } }),
        h("div", { class: "controls" },
          choice(block, "symbology", SYMBOLOGIES.map((s) => [s, s]), "Type"),
          num(block, "height", LIMITS.barcodeHeight, "Hauteur"),
          choice(block, "module_width", [2, 3, 4, 5, 6].map((n) => [n, String(n)]), "Épaisseur"),
          choice(block, "text_position", [["below", "Dessous"], ["above", "Dessus"], ["both", "Les deux"], ["none", "Aucun"]], "Texte"),
          alignSeg(block)),
      ];
      break;
    case "image": {
      const file = h("input", { type: "file", accept: "image/png,image/jpeg,image/gif,image/bmp,image/webp", onchange: (e) => loadImage(block, e.target) });
      body = [h("div", { class: "controls" },
        h("label", { class: "file-button" }, block.data ? `Changer (${block.name ?? "image"})` : "Choisir une image", file),
        choice(block, "mode", [["dither", "Photo (tramé)"], ["threshold", "Logo (seuil)"]], "Rendu"),
        block.mode === "threshold" ? num(block, "threshold", LIMITS.threshold, "Seuil") : null,
        alignSeg(block))];
      body[0].querySelector("select").addEventListener("change", () => renderEditor());
      break;
    }
    case "cut":
      body = [h("div", { class: "controls" }, choice(block, "mode", [["partial", "Partielle"], ["full", "Complète"]], "Coupe"))];
      break;
    default:
      body = [h("p", { class: "template-desc" }, "Bloc importé, non modifiable ici.")];
  }

  const error = state.errors[i];
  return h("li", { class: "block", "data-error": error ? "" : null },
    h("div", { class: "block-head" },
      h("strong", {}, BLOCK_LABELS[block.type] ?? block.type),
      h("button", { type: "button", title: "Monter", "aria-label": "Monter", "data-move": "-1", disabled: i === 0, onclick: () => moveBlock(i, -1) }, "↑"),
      h("button", { type: "button", title: "Descendre", "aria-label": "Descendre", "data-move": "1", disabled: i === state.blocks.length - 1, onclick: () => moveBlock(i, 1) }, "↓"),
      h("button", { type: "button", title: "Dupliquer", "aria-label": "Dupliquer", onclick: () => { state.blocks.splice(i + 1, 0, { ...structuredClone(block), id: newBlock("feed").id }); changed({ rerender: true }); } }, "⧉"),
      h("button", { type: "button", title: "Supprimer", "aria-label": "Supprimer", onclick: () => { state.blocks.splice(i, 1); changed({ rerender: true }); } }, "×")),
    body,
    warn,
    error ? h("p", { class: "block-error" }, error) : null,
  );
}

async function loadImage(block, input) {
  const file = input.files?.[0];
  if (!file) return;
  if (file.size > MAX_IMAGE_BYTES) {
    toast("Image trop lourde : 10 Mo au maximum.", "error");
    return;
  }
  const data = await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
  block.data = data;
  block.name = file.name.slice(0, 40);
  changed({ rerender: true });
}

// -- history tab --------------------------------------------------------------------------

function renderHistory() {
  const panel = $("panel-history");
  if (!state.history.length) {
    panel.replaceChildren(h("p", { class: "empty" }, "Rien d'imprimé pour l'instant. Tes 30 derniers tickets apparaîtront ici."));
    return;
  }
  const fmt = new Intl.DateTimeFormat("fr-FR", { dateStyle: "medium", timeStyle: "short" });
  if (!state.historyPick || !state.history.includes(state.historyPick)) state.historyPick = state.history[0];
  panel.replaceChildren(
    h("ul", { class: "history" }, state.history.map((entry) =>
      h("li", { "aria-current": state.historyPick === entry ? "true" : null },
        h("button", { class: "pick", type: "button", onclick: () => { state.historyPick = entry; renderHistory(); render(); } },
          h("span", { class: "title" }, entry.title),
          h("span", { class: "meta" }, `${fmt.format(new Date(entry.at))} · ${entry.printer}${entry.job.imagesRemoved ? " · images non conservées" : ""}`)),
        h("div", { class: "row-actions" },
          h("button", { class: "secondary small", type: "button", onclick: () => { state.historyPick = entry; printCurrent(); } }, "Réimprimer"),
          h("button", { class: "ghost small", type: "button", onclick: () => { state.blocks = withIds(entry.job.commands); saveDraft(); setTab("editor"); } }, "Modifier"))))),
    h("div", { class: "actions" },
      h("button", { class: "ghost danger", type: "button", onclick: () => {
        if (!confirm("Effacer tout l'historique ?")) return;
        state.history = [];
        state.historyPick = null;
        store.write("history", []);
        renderHistory();
        render();
      } }, "Effacer l'historique")),
  );
}

// -- toast --------------------------------------------------------------------------------

let toastTimer = 0;
function toast(message, kind = "ok") {
  const el = $("toast");
  el.textContent = message;
  el.dataset.kind = kind;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, kind === "error" ? 7000 : 2500);
}

// -- boot ---------------------------------------------------------------------------------

function boot() {
  for (const name of ["templates", "editor", "history"]) {
    $(`tab-${name}`).addEventListener("click", () => setTab(name));
  }
  $("panel-templates").parentElement.querySelector(".tabs").addEventListener("keydown", (e) => {
    const order = ["templates", "editor", "history"];
    const i = order.indexOf(state.tab);
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      const next = order[(i + (e.key === "ArrowRight" ? 1 : order.length - 1)) % order.length];
      setTab(next);
      $(`tab-${next}`).focus();
    }
  });
  $("printer-select").addEventListener("change", (e) => {
    state.printer = e.target.value;
    store.write("printer", state.printer);
    updatePrinterDot();
    render();
  });
  $("print-button").addEventListener("click", printCurrent);
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      printCurrent();
    }
  });
  setTab("templates");
  loadPrinters();
}

boot();
