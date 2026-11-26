# Feature Specification: Modèles de mémos accessibles par l'API

**Feature Branch**: `003-api-templates`

**Created**: 2026-11-26

**Status**: Draft

**Input**: User description: "Est-ce que les templates de tickets.rohmer.beer peuvent aussi être
utilisés via l'API ?" Réponse retenue : déplacer les modèles intégrés côté serveur (Python, seule
source de vérité), les exposer en lecture, rendu sans impression et impression directe ; l'interface
web consomme ces routes. Les modèles personnels (`{{variable}}`) restent dans le navigateur.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Imprimer un mémo depuis un automate (Priority: P1)

Un automate (workflow n8n, domotique, raccourci de téléphone, `curl`) imprime un mémo intégré
(« À faire », « Courses », « Rappel »…) en envoyant seulement le nom du modèle et ses valeurs,
sans connaître les commandes ESC/POS ni la mise en page.

**Why this priority**: c'est la question posée ; à elle seule elle rend les modèles utiles
en dehors du navigateur.

**Independent Test**: `POST /v1/templates/todo/print` avec `{"values": {"taches": "Pain\nLait"}}`
et la clé API ; l'imprimante factice reçoit un ticket avec le titre « À faire » et deux cases.

**Acceptance Scenarios**:

1. **Given** la clé API, **When** un client imprime un modèle avec ses valeurs, **Then** le ticket
   est imprimé et la réponse est la même que celle de `/v1/print` (identifiant, imprimante, octets,
   durée).
2. **Given** un champ obligatoire absent ou vide, un champ inconnu, une valeur hors liste ou une date
   mal formée, **When** le client imprime, **Then** la réponse est 422 et désigne le champ fautif ;
   rien n'est imprimé.
3. **Given** un identifiant de modèle inconnu, **When** le client imprime, **Then** la réponse est
   404 `unknown_template`.
4. **Given** des champs omis, **When** le client imprime, **Then** les valeurs par défaut du modèle
   s'appliquent, y compris les valeurs automatiques (date du jour, identifiant de carte).

---

### User Story 2 - Découvrir les modèles et prévisualiser (Priority: P2)

Un client liste les modèles disponibles avec la description de leurs champs (type, obligatoire,
longueur maximale, valeur par défaut, choix possibles), puis obtient les commandes d'un modèle
rempli sans imprimer, pour les vérifier, les modifier ou les envoyer plus tard à `/v1/print`.

**Why this priority**: rend l'API auto-descriptive (un workflow n8n se construit sans lire le code)
et permet à l'interface web de ne plus embarquer sa propre copie des modèles.

**Independent Test**: `GET /v1/templates` liste au moins les 10 modèles ; `POST
/v1/templates/memo/render` renvoie un job valide que `/v1/print` accepte tel quel.

**Acceptance Scenarios**:

1. **Given** la clé API, **When** le client liste les modèles, **Then** chaque modèle a un
   identifiant stable, un nom, une description et la liste de ses champs.
2. **Given** deux rendus avec les mêmes valeurs, la même date (`now`) et la même graine (`seed`),
   **When** ils sont comparés, **Then** ils sont identiques (aperçu = impression).
3. **Given** une imprimante 58 mm, **When** un modèle est rendu, **Then** aucune ligne ne dépasse
   la largeur du papier (mise en page adaptée au nombre de colonnes).

---

### User Story 3 - L'interface web utilise les modèles du serveur (Priority: P3)

L'interface `tickets.rohmer.beer` affiche la liste fournie par l'API, prévisualise et imprime via
le serveur. Pour l'utilisateur, rien ne change : mêmes modèles, mêmes formulaires, aperçu fidèle.

**Why this priority**: supprime la double maintenance ; un modèle ajouté côté serveur apparaît
automatiquement dans l'interface.

**Independent Test**: ouvrir l'interface, choisir « Courses », saisir des articles : l'aperçu se
met à jour et l'impression produit le ticket affiché.

**Acceptance Scenarios**:

1. **Given** l'interface ouverte, **When** l'utilisateur choisit un modèle et tape, **Then**
   l'aperçu se met à jour en moins d'une demi-seconde après la dernière frappe.
2. **Given** un rendu refusé (422), **When** l'utilisateur tape, **Then** le champ fautif est
   signalé sans bloquer la saisie.
3. **Given** « Pensée du jour », **When** l'utilisateur imprime, **Then** la citation imprimée est
   celle de l'aperçu.

---

### Edge Cases

- Valeurs vides partout : avec `partial` (aperçu en cours de saisie), chaque modèle se rend sans
  erreur ; à l'impression, les champs obligatoires restent exigés.
- Texte contenant des caractères non imprimables (emoji) : le rendu les conserve ; l'imprimante
  les remplace par « ? » comme pour `/v1/print`, l'interface continue de les signaler.
- `now` absent : le serveur prend son heure locale (variable `TZ` du conteneur).
- `seed` absent : citation tirée au hasard.
- Valeurs de types inattendus (nombre au lieu de texte, texte au lieu de booléen) : 422.
- Corps de requête trop gros : 413 comme les autres routes.
- Requête de navigateur d'une origine étrangère : 403 `forbidden_origin` comme les autres routes.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Les modèles intégrés MUST être définis une seule fois, côté serveur ; l'interface web
  MUST les obtenir par l'API.
- **FR-002**: `GET /v1/templates` MUST lister les modèles (identifiant, nom, pictogramme,
  description, champs) ; `GET /v1/templates/{id}` MUST décrire un modèle.
- **FR-003**: `POST /v1/templates/{id}/render` MUST renvoyer le job d'impression (format de
  `/v1/print`) sans rien envoyer à l'imprimante.
- **FR-004**: `POST /v1/templates/{id}/print` MUST imprimer le modèle de façon atomique et répondre
  comme `/v1/print`.
- **FR-005**: Les valeurs MUST être validées selon les champs du modèle (type, obligatoire,
  longueur, choix, format date `AAAA-MM-JJ` et heure `HH:MM`, champs inconnus refusés) ; les
  erreurs MUST utiliser l'enveloppe 422 existante avec le chemin du champ.
- **FR-006**: Un champ omis MUST prendre la valeur par défaut du modèle ou sa valeur automatique ;
  un champ présent mais vide MUST rester vide.
- **FR-007**: La mise en page MUST dépendre de la largeur de l'imprimante ciblée et aucune ligne ne
  MUST dépasser le nombre de colonnes.
- **FR-008**: Le rendu MUST être déterministe pour des valeurs, une imprimante, un `now` et un
  `seed` donnés.
- **FR-009**: Toutes les routes MUST exiger la clé API et passer par le contrôle d'origine existant.
- **FR-010**: Les dates imprimées MUST être en français, indépendamment de la locale du système.
- **FR-011**: Les modèles personnels de l'interface MUST continuer de fonctionner dans le
  navigateur, sans changement.

### Key Entities

- **Modèle intégré**: identifiant, nom, pictogramme, description, champs, fonction de construction
  (valeurs, contexte) → commandes.
- **Champ**: clé, libellé, type (`text`, `textarea`, `date`, `time`, `select`, `checkbox`),
  obligatoire, longueur maximale, valeur par défaut, choix, exemple, valeur automatique.
- **Contexte de rendu**: colonnes du papier, date/heure `now`, graine `seed`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un mémo s'imprime depuis un automate avec une seule requête HTTP.
- **SC-002**: Les 10 modèles se rendent à 80 et 58 mm sans ligne trop longue ni caractère
  non imprimable introduit par le modèle.
- **SC-003**: Le job renvoyé par `render` est accepté tel quel par `/v1/print` (100 % des modèles).
- **SC-004**: L'interface n'embarque plus aucune définition de modèle intégré.
- **SC-005**: Toutes les vérifications existantes (pytest, tests JS) restent vertes.

## Assumptions

- Le stockage côté serveur des modèles personnels est hors périmètre (la constitution exclut toute
  base de données) ; à reconsidérer plus tard sous forme de fichiers montés en lecture seule.
- Les textes des modèles restent en français.
- Le conteneur déclare `TZ` (ex. `Europe/Paris`) ; l'image de base contient les fuseaux.
- Les routes existantes ne changent pas : version mineure 2.2.0.
