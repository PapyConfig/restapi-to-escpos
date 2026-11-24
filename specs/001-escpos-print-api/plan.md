# Implementation Plan: API REST d'impression ESC/POS (v2)

**Branch**: `v2-rewrite` | **Date**: 2026-11-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-escpos-print-api/spec.md`

## Summary

Service HTTP qui reçoit un job JSON typé (ou un fichier image), le rend intégralement en
mémoire en flux ESC/POS via l'imprimante virtuelle `Dummy` de python-escpos, puis l'envoie en
un seul bloc sur une socket TCP asynchrone vers une imprimante déclarée côté serveur. Les
images sont pré-traitées avec Pillow (EXIF, transparence, mise à l'échelle, tramage/seuil,
alignement par marge blanche). Clé API obligatoire, pas de CORS par défaut, livré en image
Docker non-root avec exemples exécutables.

## Technical Context

**Language/Version**: Python 3.13 (image Docker) ; compatible 3.12+

**Primary Dependencies**: FastAPI, Pydantic v2, pydantic-settings, python-escpos 3.1 (rendu
uniquement), Pillow, python-multipart, uvicorn

**Storage**: N/A (aucun état persistant)

**Testing**: pytest + pytest-asyncio + httpx (ASGI), serveur TCP factice pour l'imprimante,
pytest-cov ; ruff pour lint/format

**Target Platform**: conteneur Linux (amd64 + arm64 pour Raspberry Pi)

**Project Type**: web-service

**Performance Goals**: image 3000×2000 préparée + envoyée < 2 s (SC-003) ; boucle d'événements
jamais bloquée par une imprimante lente (SC-004)

**Constraints**: zéro octet envoyé si le job est invalide ; jobs sérialisés par imprimante ;
requête ≤ 15 Mo ; image ≤ 10 Mo / 25 Mpx

**Scale/Scope**: quelques imprimantes, quelques jobs/minute (LAN / homelab / petit commerce)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principe | Vérification | Statut |
|----------|--------------|--------|
| I. Sécurité par défaut | Clé API `X-API-Key` obligatoire (démarrage refusé sinon, sauf `ALLOW_NO_AUTH`) ; imprimantes par nom uniquement ; images en base64/upload, jamais d'URL ni de chemin ; limites taille/pixels/commandes ; CORS désactivé par défaut ; erreurs génériques | ✅ |
| II. Contrat typé | Union discriminée Pydantic sur `type` ; 422 avec index de l'instruction ; exemples OpenAPI | ✅ |
| III. Impression atomique | Rendu complet `Dummy` → bytes, puis un seul `write` ; `asyncio.Lock` par imprimante ; 502/504 distincts | ✅ |
| IV. Tests sans matériel | Tests du rendu en octets + serveur TCP factice ; CI lint+tests+build+smoke avant push d'image | ✅ |
| V. Simplicité | Pas de DB/file/téléchargement ; dépendances déclarées dans `pyproject.toml` et vérifiées par le smoke test | ✅ |

Re-check post-design : ✅ aucune violation (voir Complexity Tracking vide).

## Project Structure

### Documentation (this feature)

```text
specs/001-escpos-print-api/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/http-api.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
src/escpos_api/
├── __init__.py          # version
├── main.py              # création de l'app FastAPI, middlewares, handlers d'erreurs
├── config.py            # Settings (pydantic-settings), déclaration des imprimantes
├── security.py          # dépendance clé API
├── models.py            # contrat : commandes (union discriminée), job, réponses
├── imaging.py           # pré-traitement Pillow (décodage sûr, échelle, tramage, alignement)
├── renderer.py          # job → bytes ESC/POS (Dummy), état de style
├── transport.py         # envoi TCP asynchrone, verrou par imprimante, sonde de joignabilité
└── api.py               # routes /health, /v1/printers, /v1/print, /v1/print/image, /v1/render

tests/
├── conftest.py          # settings de test, client ASGI, imprimante TCP factice
├── test_models.py
├── test_imaging.py
├── test_renderer.py
├── test_transport.py
└── test_api.py

examples/
├── receipt.json, full-receipt.json, qr-barcode.json, styles.json
├── logo.png
└── print.sh             # envoie les exemples (curl), y compris image seule et base64

Dockerfile, docker-compose.yml, pyproject.toml, .github/workflows/ci.yml
```

**Structure Decision**: projet unique, layout `src/` installable (`pip install .`), ce qui
garantit que les dépendances déclarées sont exactement celles utilisées.

## Complexity Tracking

Aucune violation à justifier.
