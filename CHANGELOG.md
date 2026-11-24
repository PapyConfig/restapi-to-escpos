# Changelog

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
