# Research: API REST d'impression ESC/POS (v2)

## R1. Génération du flux ESC/POS

- **Decision**: utiliser `escpos.printer.Dummy(profile=...)` de python-escpos pour produire
  les octets, sans jamais utiliser ses classes de connexion.
- **Rationale**: réutilise la gestion éprouvée des commandes (styles, QR, codes-barres, raster)
  et de l'encodage ; le rendu devient une fonction pure testable ; atomicité garantie (on a
  tous les octets avant d'ouvrir la socket).
- **Alternatives**: écrire les séquences ESC/POS à la main (beaucoup de code, risque
  d'erreurs) ; `escpos.printer.Network` comme en v1 (envoi incrémental, bloquant, non atomique).

## R2. Transport réseau

- **Decision**: `asyncio.open_connection` + `writer.write(data)` + `drain()` sous
  `asyncio.timeout(PRINTER_TIMEOUT)` ; un `asyncio.Lock` par imprimante.
- **Rationale**: ne bloque pas la boucle d'événements (SC-004) ; timeout couvre aussi le cas
  « connexion acceptée mais buffer plein » ; le verrou empêche l'entrelacement (SC-005).
- **Erreurs**: `ConnectionRefusedError`/`OSError` → 502 `printer_unreachable` ;
  `TimeoutError` → 504 `printer_timeout`.
- **Alternatives**: thread pool + socket bloquante (fonctionne, mais moins lisible) ; file
  persistante (hors périmètre, principe V).

## R3. Encodage du texte (accents, €)

- **Decision**: laisser le « magic encoder » de python-escpos choisir la page de code selon
  le **profil d'imprimante** configurable (`profile`, défaut `default`).
- **Constat**: avec le profil `default`, `é` → CP437 et `€` → bascule automatique de page de
  code. Les imprimantes ne supportent pas toutes les mêmes pages ; le profil (ex. `TM-T88V`,
  `TM-T20II`) est le levier documenté. La v1 forçait `ESC t 16` en dur, en conflit avec cet
  encodeur.
- **Alternatives**: page de code fixe configurable (moins portable).

## R4. Pré-traitement des images

- **Decision**: Pillow : `ImageOps.exif_transpose` → aplatissement de la transparence sur
  fond blanc → niveaux de gris → réduction (LANCZOS) à `min(width demandée, largeur
  imprimante)` → `convert("1")` avec tramage Floyd-Steinberg ou seuil → collage sur une bande
  blanche de la largeur imprimante selon l'alignement → `Dummy.image(..., impl="bitImageRaster")`.
- **Rationale**: l'alignement par marge blanche est déterministe quel que soit le modèle
  (`center=` de python-escpos dépend du profil et `ESC a` n'est pas honoré partout pour le
  raster). Largeur arrondie à un multiple de 8 points.
- **Sécurité**: lecture limitée en octets ; `Image.open` (paresseux) puis contrôle de
  `width*height` ≤ `MAX_IMAGE_PIXELS` avant `load()` ; `Image.MAX_IMAGE_PIXELS` aligné ;
  hauteur finale ≤ `MAX_IMAGE_HEIGHT` ; formats autorisés en liste blanche.

## R5. Configuration des imprimantes

- **Decision**: pydantic-settings. Raccourci mono-imprimante `PRINTER_HOST` / `PRINTER_PORT`
  / `PRINTER_WIDTH` / `PRINTER_PROFILE` → imprimante `default` ; multi-imprimantes via
  `PRINTERS` (JSON : liste d'objets). `DEFAULT_PRINTER` désigne celle par défaut (sinon la
  première).
- **Alternatives**: fichier YAML monté (une dépendance de plus, moins 12-factor) ; mini-format
  `nom=hote:port` (ambigu dès qu'on ajoute largeur/profil).

## R6. Authentification

- **Decision**: en-tête `X-API-Key`, comparaison `secrets.compare_digest`. `API_KEY` vide et
  `ALLOW_NO_AUTH` faux → arrêt au démarrage. `/health` reste public (healthcheck Docker).
- **Alternatives**: OAuth/JWT (disproportionné pour un LAN).

## R7. Limites de requête

- **Decision**: middleware ASGI qui rejette en 413 si `Content-Length` > `MAX_REQUEST_BYTES`
  (défaut 15 Mo) ou si le flux dépasse en l'absence d'en-tête ; max 500 commandes par job ;
  texte ≤ 10 000 caractères par instruction.

## R8. Packaging et CI

- **Decision**: `pyproject.toml` (setuptools) avec dépendances bornées ; Docker multi-étapes
  `python:3.13-slim`, venv copié, utilisateur `app`, `HEALTHCHECK` via Python (pas de curl) ;
  CI GitHub Actions : ruff + pytest (cov) → build → smoke test (`/health` dans le conteneur)
  → push ghcr.io avec `GITHUB_TOKEN`, multi-arch amd64/arm64 sur tag `v*` et `main`.
