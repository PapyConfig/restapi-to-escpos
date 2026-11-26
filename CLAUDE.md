# CLAUDE.md

REST API → ESC/POS network printers. Python 3.12+, FastAPI, python-escpos (rendering only via
`Dummy`), Pillow.

## Spec-driven workflow (Spec Kit)

- Principles: `.specify/memory/constitution.md` (non-negotiable; check every change against it).
- Features: `specs/001-escpos-print-api/` (API), `specs/002-web-ticket-ui/` (web UI),
  `specs/003-api-templates/` (memo templates in the API).
- Behaviour changes go through the spec first: `/speckit-specify` → `/speckit-clarify`
  (optional) → `/speckit-plan` → `/speckit-tasks` → `/speckit-implement`.

## Layout

`src/escpos_api/`: `models.py` (contract), `renderer.py` (job → bytes, pure),
`imaging.py` (Pillow), `transport.py` (async TCP + per-printer lock), `api.py` (routes),
`config.py` (env settings), `main.py` (app factory, `create_app`, origin check), `templates.py`
(built-in memo templates: fields, value validation, layout), `ui.py` (static mount + CSP), `ui/`
(web UI: vanilla ES modules, no build; pure logic in `job.js`, `templates.js` (form helpers),
`preview.js`, `storage.js`, DOM in `app.js`).

## Commands

```bash
pip install -e '.[dev]'
ruff check . && ruff format --check .
pytest --cov=escpos_api        # no printer needed
node --test 'tests/js/*.test.mjs'   # UI logic, no npm install
docker build -t escpos-api .
```

## Rules

- Never let a client choose a host, a file path or a URL.
- Any new command: a Pydantic model in the `Command` union, rendering in `Renderer._render`,
  tests, an example update if relevant, and the README table.
- The UI only prints through `/v1`, loads nothing external (CSP `script-src 'self'`, no inline
  script/style) and keeps its data in the browser. New printable characters: update
  `PRINTABLE_RANGES` in `ui/job.js` (checked against the renderer by `tests/test_ui.py`).
- Built-in templates live only in `templates.py` (the UI fetches them). A template must fit
  80 and 58 mm and only use printable characters: `tests/test_templates.py` checks both,
  with the longest allowed values.
- Keep the 1:1 match between imported and declared dependencies (`pyproject.toml`).
