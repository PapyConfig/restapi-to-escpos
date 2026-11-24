# Feature Specification: API REST d'impression ESC/POS (v2)

**Feature Branch**: `v2-rewrite`

**Created**: 2026-11-24

**Status**: Draft

**Input**: User description: "Refaire le projet de zéro. Le cahier des charges reste le même : une
API REST qui reçoit des commandes et les imprime sur une imprimante thermique ESC/POS réseau,
avec comme livrables une image Docker et des exemples. En plus : pouvoir imprimer des images."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Imprimer un ticket texte (Priority: P1)

Une application (caisse, domotique, script) envoie à l'API une liste ordonnée d'instructions
(texte, alignement, gras, taille, saut de ligne, coupe) et obtient un ticket imprimé sur
l'imprimante thermique configurée.

**Why this priority**: c'est la raison d'être du projet ; à elle seule elle remplace la v1.

**Independent Test**: envoyer l'exemple `examples/receipt.json` vers une imprimante (ou une
imprimante TCP factice) et vérifier le ticket / le flux reçu.

**Acceptance Scenarios**:

1. **Given** une imprimante configurée et joignable, **When** le client envoie un job valide
   avec une clé API valide, **Then** le ticket est imprimé et l'API répond succès avec un
   identifiant de job et le nombre d'octets envoyés.
2. **Given** un job contenant une instruction inconnue ou un paramètre hors bornes, **When** il
   est envoyé, **Then** l'API répond « requête invalide » en indiquant l'instruction fautive, et
   rien n'est imprimé.
3. **Given** une imprimante éteinte, **When** un job valide est envoyé, **Then** l'API répond
   « imprimante injoignable » (distinct d'une erreur interne) dans le délai de timeout configuré.
4. **Given** un texte contenant des accents et le symbole €, **When** il est imprimé, **Then**
   les caractères apparaissent correctement sur le ticket.

---

### User Story 2 - Imprimer une image (Priority: P1)

Un utilisateur imprime une image (logo, photo, étiquette, ticket pré-rendu) soit seule en
envoyant directement le fichier, soit au milieu d'un ticket (ex. logo en tête).

**Why this priority**: c'est la nouvelle fonctionnalité demandée explicitement.

**Independent Test**: envoyer `examples/logo.png` par téléversement et vérifier qu'il est
imprimé à la largeur du papier, en noir et blanc tramé, centré.

**Acceptance Scenarios**:

1. **Given** un fichier PNG/JPEG/GIF/BMP/WebP, **When** il est téléversé sur la route
   d'impression d'image, **Then** l'image est mise à l'échelle pour ne pas dépasser la largeur
   imprimable, convertie en monochrome et imprimée, suivie d'une coupe (désactivable).
2. **Given** un ticket JSON contenant une instruction image (contenu encodé en base64),
   **When** il est envoyé, **Then** l'image est imprimée à sa position dans le ticket.
3. **Given** une image plus large que le papier, **When** elle est imprimée, **Then** elle est
   réduite proportionnellement ; une image plus petite n'est pas agrandie sauf demande explicite.
4. **Given** un fichier qui n'est pas une image, est corrompu ou dépasse la taille maximale,
   **When** il est envoyé, **Then** la requête est rejetée et rien n'est imprimé.
5. **Given** une image, **When** le client choisit le mode de conversion (tramage ou seuil),
   **Then** ce mode est appliqué.

---

### User Story 3 - QR codes et codes-barres (Priority: P2)

Le client ajoute à un ticket un QR code (URL, texte) ou un code-barres (EAN13, CODE128…).

**Why this priority**: présent dans la v1 et courant sur un ticket, mais pas indispensable au MVP.

**Independent Test**: imprimer `examples/qr-barcode.json` et scanner les codes.

**Acceptance Scenarios**:

1. **Given** une instruction QR avec un contenu contenant des virgules, **When** elle est
   imprimée, **Then** le QR encode exactement ce contenu.
2. **Given** un code-barres EAN13 avec un contenu invalide, **When** il est envoyé, **Then** la
   requête est rejetée et rien n'est imprimé.

---

### User Story 4 - Exploitation et mise en route (Priority: P2)

Un administrateur déploie le service avec Docker, déclare une ou plusieurs imprimantes nommées,
vérifie leur état et teste avec les exemples fournis.

**Why this priority**: les livrables (Docker + exemples) font partie du cahier des charges.

**Independent Test**: `docker compose up`, puis lancer le script d'exemple ; consulter l'état des
imprimantes et la santé du service.

**Acceptance Scenarios**:

1. **Given** le `docker-compose.yml` d'exemple avec une IP d'imprimante, **When** il est lancé,
   **Then** le service démarre, se déclare sain et la doc interactive de l'API est accessible.
2. **Given** plusieurs imprimantes nommées configurées, **When** le client précise le nom d'une
   imprimante, **Then** le job part sur celle-ci ; un nom inconnu est rejeté.
3. **Given** le service démarré, **When** on interroge la liste des imprimantes, **Then** on
   obtient pour chacune son nom, sa largeur et si elle est joignable.
4. **Given** aucune clé API configurée et pas d'opt-out explicite, **When** le service démarre,
   **Then** il refuse de démarrer avec un message explicite.

---

### User Story 5 - Aperçu sans imprimer (Priority: P3)

Un développeur obtient le flux ESC/POS brut d'un job sans l'envoyer, pour déboguer ou tester
sans imprimante.

**Why this priority**: confort de développement et de test.

**Independent Test**: demander le rendu de `examples/receipt.json` et obtenir un flux binaire
non vide, sans connexion à l'imprimante.

**Acceptance Scenarios**:

1. **Given** un job valide, **When** le client demande un rendu seul, **Then** il reçoit les
   octets ESC/POS et aucune connexion à l'imprimante n'est ouverte.

### Edge Cases

- Deux jobs simultanés vers la même imprimante : ils sont imprimés l'un après l'autre, jamais
  entrelacés.
- Job vide (aucune instruction) ou trop long (au-delà de la limite) : rejeté.
- Image très grande en pixels (ex. 10 000 × 10 000) : rejetée avant décodage complet.
- Image avec transparence : le transparent est imprimé en blanc.
- Image en hauteur très longue : acceptée jusqu'à une hauteur maximale configurée, sinon rejetée.
- Imprimante qui accepte la connexion puis ne lit pas (buffer plein) : timeout et erreur dédiée.
- Requête depuis un navigateur d'un autre site : refusée par défaut (aucune origine autorisée).

## Requirements *(mandatory)*

### Functional Requirements

**Impression de tickets**

- **FR-001**: Le système MUST accepter un job constitué d'une liste ordonnée d'instructions
  typées : texte, style (alignement, gras, souligné, police, largeur/hauteur de caractère,
  inversion), saut de lignes, ligne de séparation, QR code, code-barres, image, coupe, ouverture
  de tiroir-caisse.
- **FR-002**: Le système MUST valider l'intégralité du job avant toute impression et rejeter un
  job invalide avec une erreur désignant l'instruction fautive (position + motif).
- **FR-003**: Le système MUST envoyer un job à l'imprimante en un seul bloc : soit le job entier
  est transmis, soit rien n'est transmis en cas d'erreur de préparation.
- **FR-004**: Le système MUST imprimer correctement les caractères accentués du français et le
  symbole €.
- **FR-005**: Le système MUST sérialiser les jobs adressés à une même imprimante.
- **FR-006**: Le système MUST répondre de façon distincte : succès, requête invalide,
  non authentifié, imprimante inconnue, imprimante injoignable/timeout, erreur interne.
- **FR-007**: Le système MUST permettre, en option par job, d'ajouter une coupe finale
  automatique si le job n'en contient pas.

**Images**

- **FR-010**: Le système MUST permettre d'imprimer une image envoyée directement en fichier
  (téléversement), avec options : alignement, mode de conversion (tramage/seuil), seuil,
  largeur cible, coupe finale.
- **FR-011**: Le système MUST permettre d'insérer une image dans un ticket, contenu encodé dans
  la requête (base64), avec les mêmes options.
- **FR-012**: Le système MUST accepter les formats PNG, JPEG, GIF (première image), BMP et WebP.
- **FR-013**: Le système MUST réduire une image trop large à la largeur imprimable de
  l'imprimante cible en conservant les proportions, et appliquer l'orientation EXIF.
- **FR-014**: Le système MUST rejeter les fichiers non-image, corrompus, trop lourds (octets)
  ou trop grands (pixels) avant impression.
- **FR-015**: Le système MUST NOT télécharger d'images depuis une URL ni lire un fichier local
  désigné par le client.

**Configuration, sécurité, exploitation**

- **FR-020**: Les imprimantes MUST être déclarées côté serveur (nom, hôte, port, largeur en
  points) ; le client ne peut désigner qu'un nom déclaré, et une imprimante par défaut est
  utilisée s'il n'en précise pas.
- **FR-021**: Les routes d'impression et de rendu MUST exiger une clé API ; le service MUST
  refuser de démarrer sans clé sauf opt-out explicite.
- **FR-022**: Les appels inter-origines depuis un navigateur MUST être refusés sauf origines
  explicitement configurées.
- **FR-023**: Le système MUST exposer une route de santé (sans authentification) utilisable
  par Docker, et une route listant les imprimantes et leur joignabilité.
- **FR-024**: Le système MUST exposer une documentation interactive de l'API avec des exemples.
- **FR-025**: Le système MUST journaliser chaque job (identifiant, imprimante, nombre
  d'instructions, octets, durée, résultat) sans journaliser le contenu imprimé.
- **FR-026**: Le système MUST proposer un rendu « à blanc » renvoyant le flux ESC/POS sans
  l'envoyer.

**Livrables**

- **FR-030**: Le projet MUST fournir une image Docker publiée par la CI uniquement si lint,
  tests et test de démarrage du conteneur réussissent.
- **FR-031**: Le projet MUST fournir un `docker-compose.yml` d'exemple et un dossier
  `examples/` contenant au moins : ticket simple, ticket complet (logo + QR + code-barres),
  impression d'image seule, et un script pour les envoyer.

### Key Entities

- **Imprimante** : nom unique, hôte, port, largeur imprimable (points), profil de capacités.
- **Job d'impression** : imprimante cible (optionnelle), liste ordonnée d'instructions, option
  de coupe finale ; produit un identifiant, un nombre d'octets, une durée.
- **Instruction** : un type parmi ceux de FR-001, avec ses paramètres bornés.
- **Image** : contenu binaire + options de rendu (alignement, mode, seuil, largeur).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un nouvel utilisateur imprime son premier ticket en moins de 5 minutes à partir
  du README (docker compose + script d'exemple).
- **SC-002**: 100 % des jobs invalides de la suite de tests sont rejetés sans qu'aucun octet
  n'atteigne l'imprimante factice.
- **SC-003**: Une image de 3000 × 2000 pixels est préparée et envoyée en moins de 2 secondes.
- **SC-004**: Une imprimante éteinte est signalée en moins de (timeout configuré + 1) secondes,
  et le service reste réactif pour les autres requêtes pendant ce temps.
- **SC-005**: 10 jobs simultanés vers la même imprimante produisent 10 tickets complets et non
  entrelacés.
- **SC-006**: Aucune requête non authentifiée ne déclenche d'impression ni d'ouverture de tiroir.

## Assumptions

- Imprimantes ESC/POS raw TCP (port 9100) ; l'USB et le série sont hors périmètre.
- Largeur par défaut 576 points (papier 80 mm, 203 dpi) ; 384 pour du 58 mm, configurable par
  imprimante.
- Une seule clé API partagée suffit (usage LAN / homelab) ; pas de gestion d'utilisateurs.
- Impression synchrone : la réponse arrive une fois le job transmis. Pas de file persistante ni
  de suivi de job a posteriori (la route `/jobs/{id}` de la v1 est retirée).
- Rupture assumée avec le format v1 (mini-langage `"contenu, clé=valeur"`) : nouvelle API
  versionnée `/v1/...`. Pas de couche de compatibilité.
- Taille maximale d'image par défaut : 10 Mo et 25 mégapixels ; hauteur maximale imprimée
  après mise à l'échelle : 4000 points.
