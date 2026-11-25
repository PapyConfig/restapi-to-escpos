# restapi-to-escpos Constitution

## Core Principles

### I. Sécurité par défaut

Le service pilote du matériel physique (imprimante, tiroir-caisse) sur un réseau local.

- Toute route qui imprime ou agit sur le matériel MUST exiger une clé API dès qu'une clé est
  configurée ; le service MUST refuser de démarrer sans clé sauf opt-out explicite
  (`ALLOW_NO_AUTH=true`).
- Les imprimantes cibles MUST provenir de la configuration serveur ; un client ne peut jamais
  fournir une IP/port arbitraire.
- Le service MUST NOT lire de fichiers locaux à la demande d'un client, ni télécharger d'URL
  distantes (pas de SSRF) : les images arrivent dans la requête.
- Les entrées MUST être bornées (taille de requête, nombre de commandes, dimensions d'image).
- Les messages d'erreur renvoyés au client MUST NOT exposer de détails internes (traces, chemins).
- Une requête d'écriture émise par un navigateur depuis une origine non autorisée MUST être
  refusée (le reverse proxy peut injecter la clé API) ; les pages servies MUST porter une CSP
  stricte sans ressource externe.

Rationale : la v1 permettait l'impression/ouverture de tiroir depuis n'importe quelle page web
(CORS `*`), le relais TCP vers n'importe quel hôte et la lecture de fichiers du conteneur.

### II. Contrat typé et validé

- Chaque commande d'impression MUST être décrite par un modèle Pydantic distinct (union
  discriminée) ; aucun `Dict[str, Any]` dans le contrat public, aucun mini-langage dans des
  chaînes.
- Un job invalide MUST être rejeté en 422 avant tout octet envoyé à l'imprimante.
- La documentation OpenAPI générée MUST être utilisable telle quelle (exemples inclus).

### III. Impression atomique

- Un job MUST être entièrement rendu en mémoire (flux ESC/POS) avant ouverture de la connexion
  imprimante, puis envoyé en un seul bloc.
- Une erreur de rendu MUST produire zéro octet imprimé ; une erreur réseau MUST être signalée
  par un code HTTP distinct (502/504), jamais un 500 générique.
- Les envois vers une même imprimante MUST être sérialisés.

### IV. Tests sans matériel (NON-NEGOTIABLE)

- Le rendu MUST être testable sans imprimante (rendu en octets, imprimante TCP factice).
- Toute fonctionnalité MUST arriver avec ses tests ; la CI MUST exécuter lint + tests + build
  Docker + test de démarrage du conteneur avant toute publication d'image.

### V. Simplicité

- Une seule responsabilité : JSON/HTTP → ESC/POS/TCP. Pas de base de données, pas de file
  persistante, pas de téléchargement d'images.
- Seule exception admise : une interface web **statique** optionnelle (désactivée par défaut),
  sans build ni dépendance, qui n'imprime que via le contrat public `/v1` et ne garde ses
  données que dans le navigateur.
- Dépendances minimales, toutes déclarées et épinglées ; une dépendance importée mais non
  déclarée (ou l'inverse) est un défaut bloquant.

## Contraintes techniques

- Python 3.12+, FastAPI, Pydantic v2, python-escpos (rendu via l'imprimante `Dummy`), Pillow.
- Livrables : image Docker (utilisateur non-root, `HEALTHCHECK`), `docker-compose.yml`
  d'exemple, exemples de requêtes exécutables dans `examples/`.
- Configuration exclusivement par variables d'environnement (12-factor).
- Code et API en anglais ; documentation de spécification en français.

## Flux de développement

- Spec-Driven Development via Spec Kit : `/speckit-specify` → `/speckit-plan` →
  `/speckit-tasks` → `/speckit-implement`. Toute évolution de comportement passe d'abord par
  la spec.
- Lint : `ruff check` et `ruff format --check` sans erreur.
- Tests : `pytest` vert ; couverture du module de rendu ≥ 90 %.

## Governance

Cette constitution prime sur toute autre pratique du dépôt. Un amendement se fait par PR
modifiant ce fichier, avec incrément de version sémantique (MAJOR : principe retiré ou
redéfini ; MINOR : principe ajouté ; PATCH : formulation). Chaque revue de PR MUST vérifier
la conformité aux principes I à V ; toute entorse MUST être justifiée dans le plan
(section « Complexity Tracking »).

**Version**: 1.1.0 | **Ratified**: 2026-11-24 | **Last Amended**: 2026-11-25
