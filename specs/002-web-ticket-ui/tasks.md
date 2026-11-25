# Tasks: Interface web d'impression de tickets et de mémos

**Input**: `specs/002-web-ticket-ui/` (spec, plan, research, data-model, contracts)

Format : `[ID] [P?] [Story] Description` — `[P]` = parallélisable.

## Phase 1: Setup

- [x] T001 Amender `.specify/memory/constitution.md` (1.1.0 : principe V autorise une interface statique optionnelle ; principe I ajoute contrôle d'origine et CSP)
- [x] T002 `pyproject.toml` : `package-data` pour `escpos_api/ui/*` ; vérifier `pip install .` non éditable
- [x] T003 `config.py` : `ui_enabled: bool = False` + test dans `tests/test_config.py`

## Phase 2: Foundational (serveur)

- [x] T004 Test d'abord : `tests/test_ui.py` — UI désactivée → 404 ; activée → `/` et `/ui` redirigent, `/ui/` sert `index.html` avec CSP/nosniff/no-referrer, fichier inconnu → 404, traversée de chemin → 404
- [x] T005 Test d'abord : contrôle d'origine — sans `Origin` OK, même hôte OK, origine CORS OK, autre origine / `null` → 403 `forbidden_origin` sans connexion imprimante, GET non concerné
- [x] T006 `src/escpos_api/ui.py` : `SecureStaticFiles` + `mount_ui(app)`
- [x] T007 `src/escpos_api/main.py` : `OriginCheckMiddleware` (toujours actif), montage conditionnel de l'UI

## Phase 3: User Story 1 — Modèles de mémos (P1) 🎯 MVP

- [x] T008 [P] [US1] `ui/job.js` : `toJob`, `ticketTitle`, `findVariables`, `fillVariables`, `unprintable`, `columnsFor` + `tests/js/job.test.mjs`
- [x] T009 [P] [US1] `ui/templates.js` : 10 modèles de R6 + `tests/js/templates.test.mjs` (chaque modèle produit des blocs valides, caractères imprimables, champs requis vides → pas de crash)
- [x] T010 [P] [US1] `ui/preview.js` : `layout(blocks, printer)` pur (lignes, retour au caractère, tailles) + `draw(canvas, layout)` + `tests/js/preview.test.mjs`
- [x] T011 [US1] `ui/index.html`, `ui/style.css`, `ui/app.js` : choix d'imprimante (`/v1/printers`), galerie de modèles, formulaire, aperçu, Imprimer, toasts d'erreur, demande de clé sur 401 (`sessionStorage`)

## Phase 4: User Story 2 — Éditeur libre (P2)

- [x] T012 [US2] Éditeur de blocs dans `app.js` : ajout/suppression/duplication/déplacement, réglages par type avec bornes du contrat, image depuis fichier (data URL), « Ouvrir dans l'éditeur » depuis un modèle
- [x] T013 [US2] Erreurs 422 rattachées au bloc (`details[].index`) ; avertissement caractères non imprimables

## Phase 5: User Story 3 — Modèles perso et historique (P3)

- [x] T014 [P] [US3] `ui/storage.js` : lecture/écriture protégées, historique 30 entrées / 400 Ko + tests
- [x] T015 [US3] `app.js` : enregistrer comme modèle (variables `{{x}}`), export/import JSON, historique (réimprimer, ouvrir)

## Phase 6: Polish

- [x] T016 CI : étape `node --test tests/js` ; smoke test conteneur avec `UI_ENABLED=true` (`/ui/` 200 + CSP, `Origin` étranger → 403)
- [x] T017 README (section interface web, `UI_ENABLED`, exemple Traefik), CHANGELOG, `.env.example`, `CLAUDE.md` (layout + feature courante), version 2.1.0
- [x] T018 Vérification navigateur (Playwright local, mobile 360 px + bureau) avec imprimante factice ; captures
- [x] T019 `ruff check`, `ruff format --check`, `pytest --cov` ≥ 90 %, `docker build` + smoke test local
