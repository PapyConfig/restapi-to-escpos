# Feature Specification: Interface web d'impression de tickets et de mémos

**Feature Branch**: `002-web-ticket-ui`

**Created**: 2026-11-25

**Status**: Draft

**Input**: User description: "Maintenant que l'imprimante thermique fonctionne, créer une interface
web permettant d'imprimer des tickets : un éditeur libre et des modèles à remplir, l'idée étant
d'en faire des mémos. Interface servie par l'API elle-même, publiée sur tickets.rohmer.beer
derrière le SSO du homelab (Authentik), le reverse proxy injectant la clé API. Modèles : surprends-moi."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Imprimer un mémo à partir d'un modèle (Priority: P1)

Depuis son téléphone ou son PC, l'utilisateur ouvre l'interface, choisit un modèle de mémo
(mémo, liste à faire, liste de courses, pense-bête géant, mot pour quelqu'un…), remplit
quelques champs, voit l'aperçu du ticket et l'imprime en un clic.

**Why this priority**: c'est l'usage principal visé (« en faire des mémos ») ; à elle seule
cette histoire rend l'imprimante utile au quotidien sans écrire de JSON.

**Independent Test**: ouvrir l'interface, choisir « À faire », saisir trois tâches, imprimer ;
vérifier que l'imprimante (ou une imprimante factice) reçoit un ticket avec le titre, la date et
trois cases à cocher.

**Acceptance Scenarios**:

1. **Given** l'interface ouverte, **When** l'utilisateur choisit un modèle, **Then** un
   formulaire ne présente que les champs de ce modèle, pré-remplis de valeurs utiles (date et
   heure du jour notamment), et l'aperçu se met à jour à chaque frappe.
2. **Given** un formulaire rempli, **When** l'utilisateur clique « Imprimer », **Then** le
   ticket est imprimé et l'interface confirme le succès en moins de 5 secondes.
3. **Given** l'imprimante éteinte, **When** l'utilisateur imprime, **Then** un message clair
   (« imprimante injoignable ») s'affiche et sa saisie est conservée pour réessayer.
4. **Given** un modèle rempli, **When** l'utilisateur choisit « Ouvrir dans l'éditeur »,
   **Then** le ticket généré devient une suite de blocs modifiables (story 2).

---

### User Story 2 - Composer un ticket libre (Priority: P2)

L'utilisateur compose un ticket bloc par bloc : texte (avec style : alignement, gras, souligné,
taille, police, inversé), séparateur, saut de ligne, QR code, code-barres, image, coupe. Il
réordonne, duplique et supprime les blocs, voit l'aperçu à l'échelle du papier, puis imprime.

**Why this priority**: donne accès à toutes les possibilités de l'imprimante ; les modèles en
sont un raccourci.

**Independent Test**: créer un ticket titre + texte + QR + image, l'imprimer, et vérifier que
l'imprimante reçoit exactement les éléments composés, dans l'ordre.

**Acceptance Scenarios**:

1. **Given** un ticket vide, **When** l'utilisateur ajoute des blocs, **Then** chacun propose
   uniquement les réglages autorisés par l'imprimante (bornes identiques à l'API).
2. **Given** un ticket qui serait refusé par l'API (ex. contenu de code-barres invalide),
   **When** il est imprimé, **Then** rien n'est imprimé et le bloc fautif est mis en évidence
   avec la raison.
3. **Given** une image choisie depuis l'appareil, **When** elle est ajoutée, **Then** l'aperçu
   la montre en noir et blanc à la largeur du papier.
4. **Given** un texte contenant un caractère que l'imprimante ne sait pas imprimer, **When**
   il est saisi, **Then** l'interface le signale avant l'impression.

---

### User Story 3 - Garder ses modèles et réimprimer (Priority: P3)

L'utilisateur enregistre un ticket composé comme modèle personnel ; les zones notées
`{{nom}}` deviennent des champs à remplir. Il retrouve aussi l'historique de ses dernières
impressions pour réimprimer un mémo ou le modifier.

**Why this priority**: confort d'usage ; l'outil est utile sans.

**Independent Test**: enregistrer un ticket contenant `{{client}}` comme modèle, le rouvrir,
saisir une valeur, imprimer ; puis réimprimer depuis l'historique.

**Acceptance Scenarios**:

1. **Given** un ticket contenant `{{prenom}}`, **When** il est enregistré comme modèle,
   **Then** le modèle apparaît dans la liste avec un champ « prenom ».
2. **Given** des impressions passées, **When** l'utilisateur ouvre l'historique, **Then** il
   voit les 30 dernières (date, titre) et peut réimprimer ou ouvrir dans l'éditeur.
3. **Given** des modèles personnels, **When** l'utilisateur les exporte puis les importe sur un
   autre appareil, **Then** il retrouve les mêmes modèles.

---

### Edge Cases

- Interface ouverte directement sur le réseau local (sans le proxy qui injecte la clé) :
  l'interface demande la clé API, la garde pour la session de l'onglet uniquement.
- Plusieurs imprimantes déclarées : l'utilisateur choisit la cible ; la largeur de l'aperçu
  suit la largeur de papier de l'imprimante choisie (80 mm / 58 mm).
- Ticket vide ou formulaire sans contenu : le bouton « Imprimer » est désactivé.
- Image trop lourde : refus avec la taille maximale, sans envoi.
- Interface désactivée (réglage par défaut) : les adresses de l'interface répondent 404 et
  l'API se comporte exactement comme avant.
- Une page tierce ouverte dans le même navigateur tente de déclencher une impression en
  profitant de la session SSO : la demande est refusée.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le service MUST pouvoir servir une interface web, désactivée par défaut et
  activée par un réglage serveur ; désactivée, aucune route nouvelle n'est exposée.
- **FR-002**: L'interface MUST imprimer exclusivement via le contrat public existant
  (impression d'un job, liste des imprimantes) ; aucun chemin d'impression parallèle.
- **FR-003**: L'interface MUST proposer au moins 8 modèles de mémos intégrés, chacun décrit
  par un nom, une description courte et des champs typés (texte court, texte long, choix,
  case à cocher), avec valeurs par défaut.
- **FR-004**: Les champs « date » et « heure » des modèles MUST être pré-remplis avec la date
  et l'heure locales courantes.
- **FR-005**: L'éditeur MUST couvrir tous les types de blocs du contrat sauf l'ouverture du
  tiroir-caisse, avec les mêmes bornes que l'API.
- **FR-006**: L'aperçu MUST respecter le nombre de colonnes du papier de l'imprimante choisie
  et les tailles de caractères, et se mettre à jour en moins de 200 ms après une saisie.
- **FR-007**: Une erreur de l'API MUST être affichée en clair ; une erreur portant sur une
  commande précise MUST être rattachée au bloc correspondant.
- **FR-008**: Les caractères que l'imprimante ne peut pas imprimer MUST être signalés avant
  impression.
- **FR-009**: Les modèles personnels et l'historique (30 derniers tickets) MUST être stockés
  dans le navigateur uniquement ; aucune donnée persistante côté serveur.
- **FR-010**: Les modèles personnels MUST pouvoir être exportés et importés (fichier).
- **FR-011**: Le service MUST refuser toute demande de modification (impression) émise par
  un navigateur depuis une origine autre que la sienne ou que les origines autorisées.
- **FR-012**: L'interface MUST fonctionner sans aucune ressource externe (pas de CDN) et
  être servie avec une politique de sécurité de contenu interdisant scripts tiers et
  intégration dans une autre page.
- **FR-013**: L'interface MUST être utilisable sur téléphone (largeur 360 px) comme sur PC.
- **FR-014**: Si l'API répond « non autorisé », l'interface MUST demander la clé API et ne la
  conserver que pour la session de l'onglet.

### Key Entities

- **Bloc**: un élément du ticket, correspondant 1:1 à une commande du contrat d'impression.
- **Modèle intégré**: nom, description, champs, et règle de construction des blocs à partir
  des valeurs saisies.
- **Modèle personnel**: nom + liste de blocs contenant des variables `{{nom}}` ; les champs
  sont déduits des variables.
- **Entrée d'historique**: date, titre, imprimante, job imprimé.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un mémo à partir d'un modèle s'imprime en moins de 30 secondes depuis l'ouverture
  de l'interface, sur téléphone.
- **SC-002**: 100 % des tickets refusés par l'API n'impriment rien et indiquent la cause.
- **SC-003**: L'aperçu et le ticket imprimé ont le même découpage en lignes pour du texte
  (même nombre de lignes et mêmes retours à la ligne).
- **SC-004**: Avec l'interface désactivée, toutes les vérifications existantes de l'API
  passent sans modification.
- **SC-005**: Une impression déclenchée depuis une autre origine de navigateur est refusée
  dans 100 % des cas testés.

## Assumptions

- Publication sur `tickets.rohmer.beer`, derrière Authentik ; le reverse proxy injecte la clé
  API, la route existante `thermal-printer.rohmer.beer` (utilisée par n8n) est inchangée.
- Un seul utilisateur (l'administrateur du homelab) ; pas de gestion de comptes dans le
  service.
- Pas d'aperçu au pixel près pour QR codes et codes-barres : ils sont représentés à leur
  emplacement et à leur taille approximative.
- Interface en français.
- Les modèles intégrés sont livrés avec le service ; les modifier demande une nouvelle version.
