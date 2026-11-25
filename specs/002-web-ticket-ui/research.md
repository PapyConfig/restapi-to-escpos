# Research: Interface web d'impression de tickets

## R1 — Pile front

- **Decision**: HTML + CSS + JavaScript natif en modules ES, sans framework ni build.
- **Rationale**: principe V (dépendances minimales) ; CSP `script-src 'self'` simple à tenir ;
  rien à mettre à jour (Renovate) ; quelques centaines de lignes suffisent.
- **Alternatives considered**: React/Vue via CDN (interdit par FR-012), bundler (outil de build
  en plus dans la CI et le Dockerfile).

## R2 — Authentification derrière le SSO

- **Decision**: Traefik (`tickets.rohmer.beer`) enchaîne Authentik (`auth@file`) puis un
  middleware `headers` qui ajoute `X-API-Key`. Le service ne change pas son authentification.
  Repli : en cas de 401, l'UI demande la clé et la garde en `sessionStorage`.
- **Rationale**: aucune confiance accordée à des en-têtes d'identité (le port 8430 est joignable
  sur le LAN, un en-tête `X-authentik-*` y serait falsifiable) ; pas de JWT ni de JWKS à vérifier.
- **Alternatives considered**: confiance dans `X-authentik-username` (falsifiable hors proxy) ;
  vérification du JWT Authentik (dépendance + téléchargement de JWKS) ; clé en `localStorage`
  (persistante dans le navigateur).

## R3 — CSRF

- **Decision**: middleware qui, pour `POST/PUT/PATCH/DELETE`, rejette en 403 `forbidden_origin`
  toute requête portant un en-tête `Origin` qui n'est ni l'hôte de la requête (comparaison
  `host[:port]`) ni une origine de `CORS_ORIGINS`. Sans en-tête `Origin` (curl, n8n), rien ne change.
- **Rationale**: dès que le proxy injecte la clé, un site tiers pourrait faire soumettre un
  formulaire multipart vers `/v1/print/image` avec le cookie SSO. Les navigateurs envoient
  toujours `Origin` sur un POST cross-origin. Comparer l'hôte (et pas le schéma) tolère la
  terminaison TLS par Traefik (`passHostHeader` par défaut).
- **Alternatives considered**: jeton CSRF (état serveur, inutile ici) ; `Sec-Fetch-Site` seul
  (absent des vieux navigateurs).

## R4 — Aperçu

- **Decision**: mise en page calculée en JS pur (colonnes = largeur / 12 points police A,
  / 9 police B, divisées par le multiplicateur de largeur ; retour à la ligne au caractère comme
  l'imprimante), dessinée sur un `<canvas>` de la largeur du papier en points. Images : mise à
  l'échelle + tramage Floyd–Steinberg ou seuil côté navigateur. QR et codes-barres : motif
  indicatif à la taille approximative.
- **Rationale**: aperçu instantané sans aller-retour ; même formule de colonnes que
  `PrinterConfig.columns` côté serveur.
- **Alternatives considered**: route serveur rendant un PNG (nouveau contrat, police à émuler côté
  serveur de toute façon) ; aperçu HTML (largeurs de caractères difficiles à maîtriser).

## R5 — Caractères imprimables

- **Decision**: liste blanche côté JS : ASCII imprimable, Latin‑1, `€ œ Œ • … « » ‘ ’ “ ” – —`,
  dessin de cadres et blocs CP437 (`─│┌┐└┘├┤┬┴┼═║╔╗╚╝ ░▒▓█▄▀■`). Mesuré sur le rendu actuel :
  `☐ ✓ ★ → ♥` sortent en `?`. Les modèles n'utilisent que des caractères de la liste.
- **Alternatives considered**: demander au serveur (`/v1/render` et chercher `?`) : faux positifs
  sur un vrai `?`, aller-retour à chaque frappe.

## R6 — Modèles intégrés (« surprends-moi », orientés mémos)

| id | Nom | Contenu |
|----|-----|---------|
| `memo` | Mémo | bandeau inversé « MÉMO », titre, message, date/heure |
| `todo` | À faire | titre, tâches (une par ligne → `[ ]`), échéance, priorité (haute → bandeau « URGENT ») |
| `shopping` | Courses | articles groupés, cases `[ ]`, nombre d'articles |
| `postit` | Pense-bête XXL | 1 à 3 mots en très gros, pour le frigo ou l'écran |
| `note` | Petit mot | Pour / De / message dans un cadre en traits doubles |
| `reminder` | Rappel + lien | quoi, quand, lien → QR code à scanner |
| `wifi` | Wi‑Fi invités | réseau, mot de passe, sécurité → QR de connexion `WIFI:` |
| `kanban` | Carte tâche | titre XXL, projet, estimation, identifiant en code-barres |
| `journal` | Journal du jour | date, 3 victoires, une gratitude, humeur |
| `quote` | Pensée du jour | citation au hasard (auteurs du domaine public) ou la sienne |

## R7 — Stockage navigateur

- **Decision**: `localStorage` (clés préfixées `escpos-ui:`), accès protégés par try/catch ;
  historique limité à 30 entrées et aux jobs de moins de 400 Ko (sinon images retirées).
- **Rationale**: FR-009 et principe V (pas d'état serveur).
