// Ticket preview: `layout()` is pure (tested in Node), `draw()` paints it on a canvas.
// Units are printer dots (203 dpi): font A cell 12×24, font B 9×17, default line pitch 30.

import { columnsFor } from "./job.js";

const CELL = { a: [12, 24], b: [9, 17] };
const PITCH = { a: 30, b: 22 };
const BASE_STYLE = { align: "left", bold: false, underline: 0, font: "a", width: 1, height: 1, invert: false };
const STYLE_KEYS = Object.keys(BASE_STYLE);

function merge(style, fields) {
  const out = { ...style };
  for (const k of STYLE_KEYS) if (fields[k] !== undefined && fields[k] !== null) out[k] = fields[k];
  return out;
}

/** Split a logical line into printed rows: the printer wraps at the column count. */
export function wrapChars(line, columns) {
  const chars = [...line];
  if (chars.length === 0) return [""];
  const rows = [];
  for (let i = 0; i < chars.length; i += columns) rows.push(chars.slice(i, i + columns).join(""));
  return rows;
}

// Byte-mode QR capacity per version for each error-correction level (versions 1..20).
const QR_CAPACITY = {
  L: [17, 32, 53, 78, 106, 134, 154, 192, 230, 271, 321, 367, 425, 458, 520, 586, 644, 718, 792, 858],
  M: [14, 26, 42, 62, 84, 106, 122, 152, 180, 213, 251, 287, 331, 362, 412, 450, 504, 560, 624, 666],
  Q: [11, 20, 32, 46, 60, 74, 86, 108, 130, 151, 177, 203, 241, 258, 292, 322, 364, 394, 442, 482],
  H: [7, 14, 24, 34, 44, 58, 64, 84, 98, 119, 137, 155, 177, 194, 220, 250, 280, 310, 338, 382],
};

export function qrModules(content, ec = "M") {
  const bytes = new TextEncoder().encode(content).length;
  const caps = QR_CAPACITY[ec] ?? QR_CAPACITY.M;
  let version = caps.findIndex((c) => c >= bytes) + 1;
  if (version === 0) version = 20 + Math.ceil((bytes - caps[19]) / 40);
  return 17 + 4 * Math.min(version, 40);
}

export function barcodeModules(content, symbology) {
  const n = content.length;
  switch (symbology) {
    case "EAN13": case "UPC-A": return 95;
    case "EAN8": return 67;
    case "UPC-E": return 51;
    case "CODE39": return (n + 2) * 13;
    case "CODE93": return (n + 4) * 9 + 1;
    case "ITF": return n * 9 + 9;
    case "CODABAR": return (n + 2) * 10;
    default: return 11 * (n + 3) + 2; // CODE128 subset B: start + data + checksum + stop
  }
}

/**
 * Compute printed rows.
 * @param blocks  ticket blocks (commands)
 * @param paper   paper width in dots
 * @param imageSize (block) => {width, height} | null — source size of a decoded image
 * @returns {{rows: object[], height: number}}
 */
export function layout(blocks, paper, imageSize = () => null) {
  let style = { ...BASE_STYLE };
  const rows = [];
  let y = 0;
  const push = (row) => {
    rows.push({ ...row, y });
    y += row.height;
  };
  const textRows = (content, st, index) => {
    const columns = columnsFor(paper, st.font, st.width);
    const [, cellH] = CELL[st.font] ?? CELL.a;
    const pitch = Math.max(PITCH[st.font] ?? 30, cellH * st.height + 6);
    const logical = content.endsWith("\n") ? content.slice(0, -1) : content;
    for (const line of logical.split("\n")) {
      for (const text of wrapChars(line, columns)) push({ kind: "text", text, style: st, height: pitch, index });
    }
  };

  blocks.forEach((b, index) => {
    switch (b.type) {
      case "text":
        textRows(b.content ?? "", merge(style, b), index);
        break;
      case "style":
        style = merge(b.reset ? { ...BASE_STYLE } : style, b);
        break;
      case "feed":
        push({ kind: "space", height: PITCH.a * (b.lines ?? 1), index });
        break;
      case "separator": {
        const columns = columnsFor(paper, style.font, style.width);
        textRows((b.char || "-").repeat(columns), style, index);
        break;
      }
      case "qr": {
        const size = qrModules(b.content || " ", b.ec) * (b.size ?? 6);
        push({ kind: "qr", size: Math.min(size, paper), align: b.align ?? "center", content: b.content ?? "", height: Math.min(size, paper) + 8, index });
        break;
      }
      case "barcode": {
        const width = Math.min(barcodeModules(b.content ?? "", b.symbology) * (b.module_width ?? 3), paper);
        const label = b.text_position && b.text_position !== "none";
        const extra = label ? (b.text_position === "both" ? 2 : 1) * 26 : 0;
        push({ kind: "barcode", width, barHeight: b.height ?? 80, align: b.align ?? "center", content: b.content ?? "", textPosition: b.text_position ?? "below", height: (b.height ?? 80) + extra + 8, index });
        break;
      }
      case "image": {
        const src = imageSize(b);
        let w = b.width ? Math.min(b.width, paper) : paper;
        let h = 120;
        if (src) {
          if (src.width <= w && !b.upscale) w = src.width;
          h = Math.max(1, Math.round((src.height * w) / src.width));
        }
        push({ kind: "image", width: w, height: h, align: b.align ?? "center", block: b, ready: !!src, index });
        break;
      }
      case "cut":
        push({ kind: "cut", height: 40, index });
        break;
      default:
        break;
    }
  });
  return { rows, height: y };
}

/** Grayscale (0..255) → black/white in place. Returns Uint8Array of 0 (black) / 255. */
export function monochrome(gray, width, height, mode = "dither", threshold = 128) {
  const out = new Uint8Array(width * height);
  if (mode === "threshold") {
    for (let i = 0; i < gray.length; i += 1) out[i] = gray[i] < threshold ? 0 : 255;
    return out;
  }
  const buf = Float32Array.from(gray);
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const i = y * width + x;
      const v = buf[i] < 128 ? 0 : 255;
      const err = buf[i] - v;
      out[i] = v;
      if (x + 1 < width) buf[i + 1] += (err * 7) / 16;
      if (y + 1 < height) {
        if (x > 0) buf[i + width - 1] += (err * 3) / 16;
        buf[i + width] += (err * 5) / 16;
        if (x + 1 < width) buf[i + width + 1] += err / 16;
      }
    }
  }
  return out;
}

// -- drawing (browser only) -------------------------------------------------------------

const INK = "#1d1d1f";

function hash(str) {
  let h = 2166136261;
  for (const ch of str) h = Math.imul(h ^ ch.codePointAt(0), 16777619);
  return h >>> 0;
}

function rng(seed) {
  let s = seed || 1;
  return () => {
    s ^= s << 13; s ^= s >>> 17; s ^= s << 5;
    return ((s >>> 0) % 1000) / 1000;
  };
}

function alignX(align, width, paper) {
  if (align === "center") return Math.round((paper - width) / 2);
  if (align === "right") return paper - width;
  return 0;
}

function drawText(ctx, row, paper) {
  const st = row.style;
  const [cw, ch] = CELL[st.font] ?? CELL.a;
  const w = cw * st.width;
  const h = ch * st.height;
  const chars = [...row.text];
  const x0 = alignX(st.align, chars.length * w, paper);
  const top = row.y + Math.round((row.height - h) / 2);
  if (st.invert && chars.length) {
    ctx.fillStyle = INK;
    ctx.fillRect(x0, row.y, chars.length * w, row.height);
  }
  ctx.fillStyle = st.invert ? "#fff" : INK;
  ctx.font = `${st.bold ? 700 : 500} ${ch}px ui-monospace, "DejaVu Sans Mono", Menlo, Consolas, monospace`;
  ctx.textBaseline = "top";
  const glyphW = ctx.measureText("M").width || cw;
  chars.forEach((c, i) => {
    if (c === " ") return;
    ctx.save();
    ctx.translate(x0 + i * w, top);
    ctx.scale(w / glyphW, st.height);
    ctx.fillText(c, 0, 1);
    ctx.restore();
  });
  if (st.underline && chars.length) {
    ctx.fillRect(x0, top + h - 1, chars.length * w, st.underline * 2);
  }
}

function drawQr(ctx, row, paper) {
  const x0 = alignX(row.align, row.size, paper);
  const y0 = row.y + 4;
  const n = Math.max(21, Math.round(row.size / 6));
  const m = row.size / n;
  const rand = rng(hash(row.content));
  ctx.fillStyle = INK;
  const finder = (fx, fy) => {
    ctx.fillRect(x0 + fx * m, y0 + fy * m, 7 * m, 7 * m);
    ctx.clearRect(x0 + (fx + 1) * m, y0 + (fy + 1) * m, 5 * m, 5 * m);
    ctx.fillStyle = "#fff";
    ctx.fillRect(x0 + (fx + 1) * m, y0 + (fy + 1) * m, 5 * m, 5 * m);
    ctx.fillStyle = INK;
    ctx.fillRect(x0 + (fx + 2) * m, y0 + (fy + 2) * m, 3 * m, 3 * m);
  };
  for (let y = 0; y < n; y += 1) {
    for (let x = 0; x < n; x += 1) {
      const inFinder = (x < 8 && y < 8) || (x >= n - 8 && y < 8) || (x < 8 && y >= n - 8);
      if (!inFinder && rand() < 0.5) ctx.fillRect(x0 + x * m, y0 + y * m, Math.ceil(m), Math.ceil(m));
    }
  }
  finder(0, 0);
  finder(n - 7, 0);
  finder(0, n - 7);
}

function drawBarcode(ctx, row, paper) {
  const x0 = alignX(row.align, row.width, paper);
  let y = row.y + 4;
  ctx.fillStyle = INK;
  ctx.font = `500 20px ui-monospace, monospace`;
  ctx.textBaseline = "top";
  const label = () => {
    const tw = ctx.measureText(row.content).width;
    ctx.fillText(row.content, x0 + (row.width - tw) / 2, y + 2);
    y += 26;
  };
  if (row.textPosition === "above" || row.textPosition === "both") label();
  const rand = rng(hash(row.content));
  for (let x = 0; x < row.width; ) {
    const bar = 2 + Math.floor(rand() * 3) * 2;
    if (rand() < 0.55) ctx.fillRect(x0 + x, y, bar, row.barHeight);
    x += bar;
  }
  y += row.barHeight;
  if (row.textPosition === "below" || row.textPosition === "both") label();
}

function drawCut(ctx, row, paper) {
  ctx.strokeStyle = "#9aa0a6";
  ctx.setLineDash([10, 8]);
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(0, row.y + row.height / 2);
  ctx.lineTo(paper, row.y + row.height / 2);
  ctx.stroke();
  ctx.setLineDash([]);
}

/**
 * Paint a layout. `bitmaps` maps an image block to a ready canvas (already monochrome).
 */
export function draw(canvas, result, paper, bitmapFor = () => null, highlight = null) {
  const height = Math.max(result.height, 60);
  canvas.width = paper;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#fff";
  ctx.fillRect(0, 0, paper, height);
  for (const row of result.rows) {
    if (highlight && highlight.has(row.index)) {
      ctx.fillStyle = "rgba(214, 51, 108, 0.16)";
      ctx.fillRect(0, row.y, paper, row.height);
    }
    switch (row.kind) {
      case "text": drawText(ctx, row, paper); break;
      case "qr": drawQr(ctx, row, paper); break;
      case "barcode": drawBarcode(ctx, row, paper); break;
      case "cut": drawCut(ctx, row, paper); break;
      case "image": {
        const bmp = bitmapFor(row.block, row.width);
        const x = alignX(row.align, row.width, paper);
        if (bmp) ctx.drawImage(bmp, x, row.y, row.width, row.height);
        else {
          ctx.fillStyle = "#e6e6e6";
          ctx.fillRect(x, row.y, row.width, row.height);
        }
        break;
      }
      default: break;
    }
  }
}

/** Decode an image block into {width, height, source}. Browser only. */
export async function decodeImage(dataUrl) {
  const img = new Image();
  img.decoding = "async";
  img.src = dataUrl.startsWith("data:") ? dataUrl : `data:image/png;base64,${dataUrl}`;
  await img.decode();
  return { width: img.naturalWidth, height: img.naturalHeight, source: img };
}

/** Scale + monochrome conversion of a decoded image, like the server does. Browser only. */
export function toBitmap(decoded, width, mode, threshold) {
  const height = Math.max(1, Math.round((decoded.height * width) / decoded.width));
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  ctx.fillStyle = "#fff";
  ctx.fillRect(0, 0, width, height);
  ctx.drawImage(decoded.source, 0, 0, width, height);
  const data = ctx.getImageData(0, 0, width, height);
  const gray = new Uint8Array(width * height);
  for (let i = 0; i < gray.length; i += 1) {
    const p = i * 4;
    gray[i] = Math.round(0.299 * data.data[p] + 0.587 * data.data[p + 1] + 0.114 * data.data[p + 2]);
  }
  const mono = monochrome(gray, width, height, mode, threshold);
  for (let i = 0; i < mono.length; i += 1) {
    const p = i * 4;
    data.data[p] = data.data[p + 1] = data.data[p + 2] = mono[i];
    data.data[p + 3] = 255;
  }
  ctx.putImageData(data, 0, 0);
  return canvas;
}
