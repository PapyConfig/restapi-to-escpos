# Implementation Plan: Interface web d'impression de tickets et de mémos

**Branch**: `002-web-ticket-ui` | **Date**: 2026-11-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/002-web-ticket-ui/spec.md`

## Summary

Une interface web statique (HTML/CSS/JavaScript natif, sans build ni dépendance) est livrée dans
le paquet Python et servie par FastAPI sur `/ui/` quand `UI_ENABLED=true`. Elle construit des
jobs du contrat `/v1/print` existant (modèles de mémos ou éditeur de blocs), affiche un aperçu
calculé côté navigateur sur un `<canvas>` à la largeur du papier, et stocke modèles personnels
et historique dans `localStorage`. Côté serveur, seuls trois ajouts : montage statique avec en-têtes
de sécurité (CSP stricte), redirection `/` → `/ui/`, et une vérification d'origine qui refuse
les requêtes d'écriture venant d'une autre origine de navigateur (protection CSRF nécessaire
dès que le proxy injecte la clé API).

## Technical Context

**Language/Version**: Python 3.12+ (serveur), JavaScript ES2022 en modules natifs (navigateur)

**Primary Dependencies**: FastAPI/Starlette (`StaticFiles`, déjà présent) ; aucune nouvelle
dépendance Python ; aucune dépendance JavaScript

**Storage**: `localStorage` / `sessionStorage` du navigateur ; rien côté serveur

**Testing**: pytest (routes UI, en-têtes, contrôle d'origine, non-régression UI désactivée) ;
`node --test` pour les modules JS purs (modèles, construction des jobs, mise en page de
l'aperçu, jeu de caractères) — Node est présent sur les runners GitHub, aucun `npm install`

**Target Platform**: conteneur Linux existant ; navigateurs récents (mobile et bureau)

**Project Type**: web-service + page statique servie par le même service

**Performance Goals**: aperçu < 200 ms après saisie (FR-006) ; page < 150 Ko non compressée

**Constraints**: aucune ressource externe (FR-012) ; CSP `script-src 'self'` → aucun script
ni style inline ; compatible avec le `read_only` du conteneur

**Scale/Scope**: 1 utilisateur, ~10 modèles intégrés, 30 entrées d'historique

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principe | Statut | Notes |
|----------|--------|-------|
| I. Sécurité par défaut | ✅ | UI désactivée par défaut ; `/v1` garde l'auth par clé ; ajout d'un contrôle d'origine (CSRF) ; CSP stricte, `frame-ancestors 'none'` ; l'UI n'envoie jamais d'IP/URL/fichier serveur — elle choisit une imprimante par son nom déclaré |
| II. Contrat typé | ✅ | Aucun changement du contrat ; l'UI produit des jobs validés par les mêmes modèles Pydantic ; les erreurs 422 (`details[].index`) sont rattachées aux blocs |
| III. Impression atomique | ✅ | Inchangé : l'UI appelle `/v1/print` |
| IV. Tests sans matériel | ✅ | pytest + imprimante factice pour le serveur ; `node --test` pour la logique JS ; CI étendue (étape Node + smoke test `/ui/`) |
| V. Simplicité | ⚠️ → amendement | « Une seule responsabilité » : on ajoute une page statique optionnelle. Pas de base, pas de file, pas de build front. Amendement MINOR 1.1.0 (voir Complexity Tracking) |

Post-design re-check : ✅ (aucune nouvelle dépendance, aucun état serveur).

## Project Structure

### Documentation (this feature)

```text
specs/002-web-ticket-ui/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/ui-http.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
src/escpos_api/
├── config.py          # + ui_enabled
├── main.py            # + OriginCheckMiddleware, montage UI
├── ui.py              # NEW : StaticFiles avec en-têtes de sécurité, redirection /
└── ui/                # NEW : fichiers statiques (package data)
    ├── index.html
    ├── style.css
    ├── app.js         # DOM, état, appels API (non testé en Node)
    ├── job.js         # blocs → job, variables {{x}}, jeu de caractères (pur)
    ├── preview.js     # mise en page des lignes (pur) + dessin canvas
    ├── templates.js   # modèles intégrés (pur)
    └── storage.js     # localStorage avec try/catch
tests/
├── test_ui.py         # NEW
└── js/                # NEW : *.test.mjs exécutés par `node --test tests/js`
```

**Structure Decision**: les fichiers statiques vivent dans le paquet (`escpos_api/ui/`) pour être
installés par `pip install .` dans l'image, via `package-data`.

## Déploiement homelab (hors de ce dépôt)

1. Catalogue : nouvelle entrée `tickets` (même conteneur `thermal-printer`, `record_name`
   `tickets`, rbac Admin) → DNS + application Authentik `forward_single` par le flow existant.
2. Traefik : `tickets.yml` **rendu depuis un template Ansible** (clé lue dans le vault
   `vault_thermal_printer_api_key`, fichier 0640) — les providers actuels sont copiés tels quels
   et ne doivent pas contenir de secret. Middlewares : `security@file`, `auth@file`,
   `tickets-apikey` (`customRequestHeaders.X-API-Key`).
3. `thermal_printer.env.j2` : `UI_ENABLED=true` ; nouvelle version d'image épinglée.
4. La route `thermal-printer.rohmer.beer` (n8n) est inchangée.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Principe V : le service sert aussi une page statique | Besoin utilisateur explicite (« dans l'API ») ; un seul conteneur à déployer | Conteneur nginx séparé : un service de plus à maintenir, même code statique, aucun gain de sécurité (la clé est injectée par Traefik dans les deux cas) |
