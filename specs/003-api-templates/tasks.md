# Tasks: Modèles de mémos accessibles par l'API

**Input**: `specs/003-api-templates/` (spec, plan, research, data-model, contracts)

Format : `[ID] [P?] [Story] Description` — `[P]` = parallélisable.

## Phase 1: Foundational

- [x] T001 `models.py` : `TemplateOption`, `TemplateField`, `TemplateInfo`, `TemplateRequest`
- [x] T002 `templates.py` : aides (`wrap_words`, `hanging`, `band`, `two_sides`, dates françaises), `QUOTES`, registre des 10 modèles portés de `ui/templates.js`
- [x] T003 `templates.py` : `values_model(template)` (Pydantic, strict, `extra="forbid"`), `apply_defaults`, `render_template(template, values, printer, now, seed) → PrintJob`

## Phase 2: User Story 1 & 2 — routes (P1, P2) 🎯 MVP

- [x] T004 Test d'abord : `tests/test_templates.py` — chaque modèle à 576 et 384 points : job valide, lignes ≤ colonnes, caractères imprimables (vrai moteur), valeurs vides sans plantage ; Wi-Fi échappé ; citation stable par `seed` ; dates en français ; valeurs auto si clé absente seulement
- [x] T005 Test d'abord : routes — liste, détail, 404 `unknown_template`, 401 sans clé, 422 avec `loc` du champ (obligatoire, inconnu, type, choix, date), `render` n'ouvre pas de connexion et son job passe sur `/v1/print`, `print` imprime, origine étrangère → 403
- [x] T006 `api.py` : `GET /v1/templates`, `GET /v1/templates/{id}`, `POST …/render`, `POST …/print`

## Phase 3: User Story 3 — interface (P3)

- [x] T007 `ui/templates.js` réduit à `initialValues` / `missingRequired` (nouveau format `options`/`auto`) + `tests/js/templates.test.mjs`
- [x] T008 `ui/app.js` : liste via `GET /v1/templates`, rendu serveur anti-rebond (`now` local, `seed`), impression du job rendu frais, erreurs 422 rattachées au champ
- [x] T009 Vérification navigateur (Playwright) : liste, aperçu, impression vers l'imprimante factice, citation identique aperçu/impression

## Phase 4: Polish

- [x] T010 [P] README (routes, exemple curl/n8n, `TZ`), CHANGELOG 2.2.0, CLAUDE.md, `.env.example`
- [x] T011 [P] Version 2.2.0 (`pyproject.toml`, `__init__.py`)
- [x] T012 `ruff check src tests`, `ruff format --check src tests`, `pytest --cov`, `node --test`
