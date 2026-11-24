# CLAUDE.md

REST API → ESC/POS network printers. Python 3.12+, FastAPI, python-escpos (rendering only via
`Dummy`), Pillow.

## Spec-driven workflow (Spec Kit)

- Principles: `.specify/memory/constitution.md` (non-negotiable; check every change against it).
- Current feature: `specs/001-escpos-print-api/` (spec → plan → tasks).
- Behaviour changes go through the spec first: `/speckit-specify` → `/speckit-clarify`
  (optional) → `/speckit-plan` → `/speckit-tasks` → `/speckit-implement`.

## Layout

`src/escpos_api/`: `models.py` (contract), `renderer.py` (job → bytes, pure),
`imaging.py` (Pillow), `transport.py` (async TCP + per-printer lock), `api.py` (routes),
`config.py` (env settings), `main.py` (app factory, `create_app`).

## Commands

```bash
pip install -e '.[dev]'
ruff check . && ruff format --check .
pytest --cov=escpos_api        # no printer needed
docker build -t escpos-api .
```

## Rules

- Never let a client choose a host, a file path or a URL.
- Any new command: a Pydantic model in the `Command` union, rendering in `Renderer._render`,
  tests, an example update if relevant, and the README table.
- Keep the 1:1 match between imported and declared dependencies (`pyproject.toml`).
