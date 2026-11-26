# Research: Modèles de mémos accessibles par l'API

## R1 — Où vivent les modèles

**Decision**: module Python `escpos_api/templates.py`, seule source de vérité ; `ui/templates.js` ne
garde que les aides de formulaire génériques (`initialValues`, `missingRequired`).

**Rationale**: l'API doit les servir ; deux copies (JS + Python) divergeraient. Python est déjà
testé contre le vrai moteur de rendu.

**Alternatives**: exécuter `templates.js` côté serveur (moteur JS embarqué : dépendance lourde,
rejeté) ; décrire les modèles en JSON déclaratif (moins expressif : colonnes à deux côtés, cadre,
QR Wi-Fi ; rejeté).

## R2 — Forme des routes

**Decision**: `GET /v1/templates`, `GET /v1/templates/{id}`, `POST /v1/templates/{id}/render`
(→ job JSON), `POST /v1/templates/{id}/print` (→ `PrintResult`). Corps commun :
`{printer?, values?, cut?, now?, seed?}`.

**Rationale**: `render` renvoie le job JSON (et non les octets de `/v1/render`) : c'est ce dont
l'aperçu a besoin et ce qu'un client peut retoucher avant `/v1/print`. Les octets restent
accessibles en chaînant `render` puis `/v1/render`.

## R3 — Validation des valeurs

**Decision**: un modèle Pydantic est construit par modèle de ticket à partir de ses champs
(`create_model`, `extra="forbid"`, mode strict sur les types). Les erreurs sont converties en
`RequestValidationError` avec `loc = ["body", "values", <clé>]`, donc l'enveloppe 422 existante.

**Rationale**: mêmes messages et même format que le reste du contrat ; aucune validation maison.

## R4 — Date, fuseau, hasard

**Decision**: `now` facultatif (date-heure locale, ISO 8601) ; à défaut
`datetime.now().astimezone()` (fuseau du conteneur via `TZ`). Dates en français par tables de
noms (pas de `locale`). `seed` entier ≥ 0 facultatif ; à défaut `secrets.randbelow`.

**Rationale**: le navigateur envoie son heure locale, l'aperçu et l'impression concordent ; un
automate n'a rien à fournir. `locale.setlocale` est global au processus et dépend des locales
installées : rejeté. `python:3.13-slim` contient `/usr/share/zoneinfo` (vérifié).

## R5 — Valeurs automatiques

**Decision**: `auto` vaut `today` (date du jour), `now` (heure) ou `id` (`T-MMJJ-HHMM`). Appliquée
uniquement si la clé est **absente** ; une chaîne vide reste vide.

**Rationale**: l'interface envoie toujours toutes les clés (l'utilisateur peut effacer la date) ;
un automate omet ce qu'il ne connaît pas.

## R6 — Impression depuis l'interface

**Decision**: au clic, l'interface relance un rendu frais (`render`), puis imprime ce job via
`/v1/print` et l'enregistre dans l'historique.

**Rationale**: ce qui est imprimé est exactement ce qui est affiché et archivé ; un seul chemin
d'impression côté interface. Les automates utilisent `/print` directement.

## R6b — Aperçu d'un formulaire incomplet

**Decision**: `render` accepte `partial: true` (champs obligatoires vides admis) ; `print` ne
l'accepte pas.

**Rationale**: l'aperçu doit s'afficher dès l'ouverture d'un modèle, comme avant le portage.

## R7 — Fidélité du portage

**Decision**: portage ligne à ligne de `templates.js` (mêmes textes, mêmes styles, même coupure de
mots) ; tests pytest : chaque modèle à 576 et 384 points, lignes ≤ colonnes par police et largeur,
caractères imprimables vérifiés par le vrai moteur, job accepté par `/v1/print`.
