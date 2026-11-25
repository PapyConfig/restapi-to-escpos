# 🖨️ ESC/POS Print API

REST API that prints **receipts and images** on network thermal printers (ESC/POS over raw
TCP, port 9100).

- Typed JSON print jobs: text and styles, separators, QR codes, barcodes, images, cut, cash drawer
- **Image printing**: upload a file, or embed it in a receipt (base64), auto-scaled to the paper
  width, dithered or thresholded
- Atomic jobs: the whole job is rendered and validated **before** anything is sent, so an invalid
  job prints nothing
- Several named printers, jobs serialized per printer, non-blocking I/O
- API key required, no CORS by default, the client can't choose arbitrary hosts, files or URLs
- Docker image (non-root, healthcheck, amd64 + arm64), interactive docs at `/docs`
- Optional **web UI** to print memos from templates or a block editor, with live preview

---

## 🚀 Quick start

```bash
cp .env.example .env          # set API_KEY and PRINTER_HOST
docker compose up -d
curl localhost:8000/health
```

Then print the examples:

```bash
export API_KEY=...            # same value as in .env
./examples/print.sh printers                 # printer list + reachability
./examples/print.sh receipt                  # text receipt (accents, €)
./examples/print.sh full-receipt             # logo + lines + QR + barcode
./examples/print.sh image examples/logo.png  # image only (upload)
./examples/print.sh render receipt > out.bin # ESC/POS bytes, nothing printed
```

No printer at hand? Run a fake one: `nc -lk 9100 > out.bin`.

### Without Docker

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'
API_KEY=dev PRINTER_HOST=192.168.1.100 uvicorn escpos_api.main:create_app --factory
```

---

## ⚙️ Configuration (environment variables)

| Variable | Default | Description |
|----------|---------|-------------|
| `API_KEY` | – | **Required.** Expected in the `X-API-Key` header of every `/v1` route |
| `ALLOW_NO_AUTH` | `false` | Allow starting without `API_KEY` (not recommended) |
| `PRINTER_HOST` | – | Single printer (named `default`) |
| `PRINTER_PORT` | `9100` | |
| `PRINTER_WIDTH` | `576` | Printable dots: `576` = 80 mm, `384` = 58 mm paper |
| `PRINTER_PROFILE` | `default` | [python-escpos profile](https://python-escpos.readthedocs.io/en/latest/printer_profiles/available-profiles.html) (code pages, e.g. `TM-T88V`) |
| `PRINTER_IMAGE_IMPL` | `bitImageRaster` | Image command: `bitImageRaster` (`GS v 0`), `bitImageColumn` (`ESC *`, most tolerant) or `graphics` (`GS ( L`) |
| `PRINTER_IMAGE_FRAGMENT_HEIGHT` | `128` | Images taller than this many dots are sent as several image commands (small printer buffers) |
| `PRINTER_CLOSE_GRACE` | `5` | Seconds to wait, after sending, for the printer to close the connection (keeps the job's tail from being lost). The next job on the same printer waits meanwhile |
| `PRINTERS` | – | Several printers, JSON (replaces `PRINTER_HOST`), see below |
| `DEFAULT_PRINTER` | first one | Printer used when a request names none |
| `PRINTER_TIMEOUT` | `10` | Seconds to connect and send a job |
| `CORS_ORIGINS` | empty | Comma-separated browser origins allowed to call the API |
| `UI_ENABLED` | `false` | Serve the web UI on `/ui/` (see below) |
| `MAX_REQUEST_BYTES` | `15728640` | Max request body (15 MB) |
| `MAX_IMAGE_BYTES` | `10485760` | Max image file (10 MB) |
| `MAX_IMAGE_PIXELS` | `25000000` | Max source image pixels |
| `MAX_IMAGE_HEIGHT` | `4000` | Max printed image height in dots |
| `LOG_LEVEL` | `INFO` | |

```bash
PRINTERS='[{"name":"caisse","host":"192.168.1.100"},
           {"name":"cuisine","host":"192.168.1.101","width":384,"profile":"TM-T20II",
            "image_impl":"bitImageColumn","image_fragment_height":96}]'
DEFAULT_PRINTER=caisse
```

The container needs a writable `/tmp` (python-escpos caches its profiles there). The provided
`docker-compose.yml` runs it read-only with a `tmpfs` on `/tmp`.

---

## 📡 API

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/health` | Health check (no auth) |
| GET | `/v1/printers` | Declared printers and whether they are reachable |
| POST | `/v1/print` | Print a JSON job |
| POST | `/v1/print/image` | Print an uploaded image (multipart) |
| POST | `/v1/render` | Return the ESC/POS bytes of a job without printing |
| GET | `/docs` | Interactive documentation (OpenAPI) |
| GET | `/ui/` | Web UI, only with `UI_ENABLED=true` (`/` redirects there) |

### Print job

```json
{
  "printer": "caisse",
  "cut": true,
  "commands": [
    {"type": "text", "content": "MY SHOP\n", "align": "center", "bold": true, "width": 2, "height": 2},
    {"type": "separator"},
    {"type": "text", "content": "Coffee                2.50 €\n"},
    {"type": "qr", "content": "https://example.com/t/123"},
    {"type": "cut"}
  ]
}
```

`printer` is optional (default printer). `cut: true` (default) appends a partial cut unless the
job already ends with one.

### Commands

| `type` | Fields (default) |
|--------|------------------|
| `text` | `content`, plus optional style fields applied **to this text only** |
| `style` | style fields, persistent until the next `style`; `reset: true` restores defaults |
| `feed` | `lines` (1) |
| `separator` | `char` (`-`), fills the line for the current font/width |
| `qr` | `content`, `size` 1–16 (6), `ec` L/M/Q/H (M), `align` (center) |
| `barcode` | `content`, `symbology` EAN13/EAN8/UPC-A/UPC-E/CODE39/CODE93/CODE128/ITF/CODABAR (CODE128), `height` (80), `module_width` 2–6 (3), `text_position` none/above/below/both (below), `align` (center) |
| `image` | `data` (base64 or data URL), `align` (center), `mode` dither/threshold (dither), `threshold` (128), `width` (paper width), `upscale` (false) |
| `cut` | `mode` partial/full (partial), `feed` (true) |
| `cashdraw` | `pin` 2 or 5 (2) |

Style fields: `align` left/center/right, `bold`, `underline` 0–2, `font` a/b, `width` 1–8,
`height` 1–8, `invert`.

### Images

Accepted formats are PNG, JPEG, GIF (first frame), BMP and WebP. Images are rotated according
to EXIF and transparency becomes white. Images wider than the paper (or than `width`) are
scaled down; smaller ones are never enlarged unless `upscale` is set. Images are converted to
black and white with Floyd–Steinberg dithering (photos) or a threshold (logos, text).

```bash
curl -H "X-API-Key: $API_KEY" \
  -F file=@photo.jpg -F align=center -F mode=dither -F cut=true \
  http://localhost:8000/v1/print/image
```

Form fields: `printer`, `align`, `mode`, `threshold`, `width`, `upscale`, `cut` (true).

### Errors

Every error has the form `{"error": "<code>", "message": "...", "details": [...]}`.

| HTTP | `error` | When |
|------|---------|------|
| 401 | `unauthorized` | Missing or wrong `X-API-Key` |
| 403 | `forbidden_origin` | Browser request from an origin that is neither this host nor in `CORS_ORIGINS` |
| 404 | `unknown_printer` | Printer name not declared |
| 413 | `payload_too_large` | Request or image too big |
| 422 | `invalid_job` / `invalid_image` | Invalid job; `details[].index` points at the faulty command. Nothing is printed |
| 502 | `printer_unreachable` | Connection refused or host unreachable |
| 504 | `printer_timeout` | Printer did not accept the data within `PRINTER_TIMEOUT` |

---

## 🧾 Web UI

`UI_ENABLED=true` serves a static page on `/ui/` (no build, no external resource, strict CSP):

- **Templates**: memo, to-do list, shopping list, XXL sticky note, note in a frame, reminder
  with a QR link, guest Wi-Fi QR code, Kanban card with a barcode, daily journal, quote of the day.
- **Editor**: text with styles, separators, spaces, QR codes, barcodes, images, cuts; reorder,
  duplicate, delete. API validation errors are shown on the faulty block.
- **Preview** at the paper width of the selected printer (80/58 mm), with dithered images and a
  warning for characters the printer can't print.
- **My templates**: save a ticket as a template; `{{name}}` becomes a field to fill in.
  Export/import as JSON. The last 30 prints can be reprinted. Everything stays in the browser.

The page calls `/v1` like any client. Behind an SSO reverse proxy, let the proxy add the
`X-API-Key` header so the browser never holds the key; opened directly, the page asks for the
key and keeps it for the tab only. Example with Traefik (keep the key out of git, e.g. render
this file from a secret store):

```yaml
http:
  middlewares:
    tickets-apikey:
      headers:
        customRequestHeaders:
          X-API-Key: "<API_KEY>"
  routers:
    tickets:
      rule: "Host(`tickets.example.com`)"
      middlewares: [sso-forward-auth, tickets-apikey]
      service: escpos-api
```

Because the proxy authenticates the browser, the API refuses write requests whose `Origin` is
another site (`403 forbidden_origin`), so a third-party page can't print through your session.

---

## 🔁 Migrating from v1

v2 is a rewrite with a new, versioned contract:

- `POST /print` → `POST /v1/print`. Commands are objects with a `type`: `{"bold": true}` +
  `{"text": "..."}` becomes `{"type": "text", "content": "...", "bold": true}`.
- The `"content, key=value"` mini-syntax is gone: `{"qr": "https://x, size=4"}` becomes
  `{"type": "qr", "content": "https://x", "size": 4}`.
- Images are no longer fetched from URLs or read from local paths. Send them as base64 or upload
  them to `/v1/print/image`.
- The `printer_ip`/`printer_port` query parameters are gone. Declare printers with
  `PRINTER_HOST` or `PRINTERS` and pass `"printer": "<name>"`.
- `PRINTER_IP` is now called `PRINTER_HOST`, and `API_KEY` is required.
- `/jobs/{id}` and `/examples` are removed. Printing is synchronous, and examples live in
  `examples/` and `/docs`.

---

## 🧑‍💻 Development

The project uses [Spec Kit](https://github.com/github/spec-kit) (spec-driven development):

- `.specify/memory/constitution.md`: project principles (security, typed contract, atomic
  printing, hardware-free tests, simplicity)
- `specs/001-escpos-print-api/`: spec, plan, research, data model, HTTP contract, tasks
- `specs/002-web-ticket-ui/`: web UI
- `.claude/skills/speckit-*`: the `/speckit-*` commands for Claude Code

```bash
pip install -e '.[dev]'
ruff check . && ruff format --check .
pytest --cov=escpos_api
node --test 'tests/js/*.test.mjs'   # web UI logic (Node 22+, no npm install)
```

Tests run without a printer: rendering is checked as bytes, and delivery against a fake TCP
printer. CI runs lint and tests, builds the image, smoke-tests the container, and only then
pushes to `ghcr.io` (`latest` from `main`, semver tags from `v*`).

## 📄 License

MIT. See [LICENSE](./LICENSE).
