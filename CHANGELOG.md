# Changelog

## 2.2.0 (unreleased)

Specified with Spec Kit (`specs/003-api-templates/`).

### Added
- Memo templates in the API: `GET /v1/templates`, `GET /v1/templates/{id}`,
  `POST /v1/templates/{id}/render` (print job, no printing) and `POST /v1/templates/{id}/print`.
  Values are validated per field (`422` naming the field); `now` and `seed` make a render
  reproducible; `partial` allows empty required fields for a live preview.
- `TZ` sets the time zone of the dates printed by the templates.

### Changed
- The 10 built-in templates moved from the web UI to the server (single source of truth). The UI
  lists and renders them through the API; personal `{{variable}}` templates are unchanged.
- Long values no longer overflow the line on 58 mm paper (signature, recipient, Wi-Fi password,
  quote author); a Kanban id too wide for a barcode is printed as text.

## 2.1.0 (unreleased)

Specified with Spec Kit (`specs/002-web-ticket-ui/`).

### Added
- Optional web UI on `/ui/` (`UI_ENABLED=true`, off by default): 10 built-in memo templates
  (memo, to-do, shopping list, XXL sticky note, note in a frame, reminder with QR, guest Wi-Fi,
  Kanban card, daily journal, quote of the day), a block editor covering every command, a
  paper-width live preview, personal templates with `{{variables}}` (export/import) and the
  last 30 prints, all stored in the browser. No build step, no external resource, strict CSP.
- Origin check: browser write requests from a foreign origin are refused with
  `403 forbidden_origin` (CSRF protection when a reverse proxy injects the API key). Clients
  that send no `Origin` header (curl, n8n…) are unaffected.

## 2.0.0 (unreleased)

Complete rewrite, specified with Spec Kit (`specs/001-escpos-print-api/`).

### Added
- Image printing: `POST /v1/print/image` upload and `image` command (base64), with scaling,
  EXIF, transparency, dithering/threshold and alignment.
- Typed commands (`type` discriminator) with validation and indexed errors.
- Several named printers (`PRINTERS`), `GET /v1/printers` with reachability.
- `POST /v1/render` returns the ESC/POS bytes without printing.
- API key authentication, request/image size limits, structured error responses.
- Tests (no hardware needed), CI with lint, tests, container smoke test and multi-arch image.

### Changed
- Jobs are rendered fully in memory and sent in one block, serialized per printer, with
  non-blocking I/O and distinct 502/504 errors.
- Docker image runs as non-root with a healthcheck.

### Removed
- Client-supplied printer IP/port, image URLs and local file paths.
- `"content, key=value"` string syntax, `/jobs/{id}` and `/examples` routes.

### Fixed
- v1 crashed at startup (`requests` missing from dependencies).
