# Tasks: API REST d'impression ESC/POS (v2)

**Input**: Design documents from `/specs/001-escpos-print-api/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/http-api.md

**Tests**: requis par la constitution (principe IV) — écrits avec chaque story.

Format : `[ID] [P?] [Story] Description` — `[P]` = parallélisable (fichiers distincts).

## Phase 1: Setup

- [x] T001 Créer `pyproject.toml` (dépendances bornées, extra `dev`, config ruff/pytest/coverage) et le layout `src/escpos_api/`, `tests/`, `examples/`
- [x] T002 [P] Créer `.gitignore`, `.dockerignore`, `.env.example`

## Phase 2: Foundational (bloquant)

- [x] T003 `src/escpos_api/config.py` : `Settings` + `PrinterConfig` (data-model.md `PrinterConfig.name/port/width/profile`), raccourci `PRINTER_HOST`, `PRINTERS` JSON, `DEFAULT_PRINTER`, refus de démarrer sans `API_KEY` (sauf `ALLOW_NO_AUTH`), validation des profils
- [x] T004 [P] `src/escpos_api/security.py` : dépendance `X-API-Key` (`compare_digest`)
- [x] T005 [P] `src/escpos_api/transport.py` : `send()` asyncio avec timeout, verrou par imprimante, `probe()` ; erreurs `PrinterUnreachable` / `PrinterTimeout`
- [x] T006 `src/escpos_api/main.py` : factory `create_app()`, CORS configurable (vide par défaut), middleware limite de taille (413), handlers d'erreurs → `ErrorResponse` (data-model.md `ErrorResponse.error`)
- [x] T007 `tests/conftest.py` : settings de test, client ASGI, imprimante TCP factice ; `tests/test_transport.py`

## Phase 3: User Story 1 — Ticket texte (P1) 🎯 MVP

**Goal**: imprimer un ticket texte stylé. **Independent Test**: `examples/receipt.json` → octets reçus par l'imprimante factice.

- [x] T008 [US1] `src/escpos_api/models.py` : `StyleFields`, `TextCommand`, `StyleCommand`, `FeedCommand`, `SeparatorCommand`, `CutCommand`, `CashdrawCommand`, `PrintJob`, `PrintResult` (data-model.md `PrintJob.commands` 1–500, `PrintJob.cut`, `Command.text.content` ≤ 10 000, `StyleFields.underline/width/height`)
- [x] T009 [US1] `src/escpos_api/renderer.py` : rendu `Dummy`, init `ESC @`, état de style persistant + style inline temporaire, séparateur selon colonnes, coupe finale auto, erreurs indexées `RenderError`
- [x] T010 [US1] `src/escpos_api/api.py` : `GET /health`, `GET /v1/printers`, `POST /v1/print` (rendu en thread, puis envoi), résolution imprimante (404)
- [x] T011 [P] [US1] `tests/test_renderer.py`, `tests/test_models.py`, `tests/test_api.py` : succès, 401, 404, 422 sans octet envoyé, 502, 504, accents/€, sérialisation de 10 jobs concurrents

## Phase 4: User Story 2 — Images (P1)

**Goal**: image seule (upload) et image dans un ticket (base64). **Independent Test**: upload `examples/logo.png` → raster de la largeur imprimante.

- [x] T012 [US2] `src/escpos_api/imaging.py` : décodage borné (octets, pixels, formats), EXIF, transparence → blanc, réduction, tramage/seuil, alignement par marge, hauteur max (data-model.md `Command.image.mode/threshold/width`)
- [x] T013 [US2] `ImageCommand` dans `models.py` (base64 validé) + rendu dans `renderer.py`
- [x] T014 [US2] `POST /v1/print/image` (multipart, `ImageOptions`) dans `api.py`
- [x] T015 [P] [US2] `tests/test_imaging.py` + cas API : formats, transparence, réduction, non-agrandissement, fichier corrompu, bombe de décompression, trop haut, alignements

## Phase 5: User Story 3 — QR / codes-barres (P2)

- [x] T016 [US3] `QrCommand`, `BarcodeCommand` (data-model.md `Command.qr.size/ec`, `Command.barcode.symbology/height/module_width`) + rendu ; contenu avec virgules conservé ; EAN13 invalide → 422
- [x] T017 [P] [US3] tests associés dans `tests/test_renderer.py`

## Phase 6: User Story 4 — Exploitation & livrables (P2)

- [x] T018 [US4] `Dockerfile` multi-étapes non-root + `HEALTHCHECK` ; `docker-compose.yml`
- [x] T019 [P] [US4] `examples/` : `receipt.json`, `full-receipt.json`, `qr-barcode.json`, `styles.json`, `logo.png`, `print.sh`
- [x] T020 [US4] `.github/workflows/ci.yml` : ruff + pytest → build → smoke test conteneur → push ghcr.io multi-arch (`GITHUB_TOKEN`) ; suppression de l'ancien workflow
- [x] T021 [P] [US4] Exemples OpenAPI dans les modèles ; test que chaque `examples/*.json` est un `PrintJob` valide qui se rend

## Phase 7: User Story 5 — Aperçu (P3)

- [x] T022 [US5] `POST /v1/render` → `application/octet-stream` ; test « aucune connexion ouverte »

## Phase 8: Polish

- [x] T023 README (démarrage, config, commandes, images, migration depuis v1), CHANGELOG
- [x] T024 Exécuter quickstart.md (tests, build, smoke, scénarios contre l'imprimante factice)

## Dependencies

Setup → Foundational → US1 → (US2, US3 en parallèle) → US4 → US5 → Polish.
US2/US3 ne dépendent que de `models.py`/`renderer.py` (US1).

## Parallel Example

Après T009 : T012 (imaging) et T016 (codes) peuvent avancer en parallèle ; T019 (exemples)
dès que les modèles sont figés.

## Implementation Strategy

MVP = Phases 1–3 (ticket texte sécurisé et atomique). Puis images (demande principale de la
v2), codes, livrables Docker/CI/exemples, aperçu, documentation.
