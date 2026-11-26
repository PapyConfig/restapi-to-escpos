# Feature Specification: Fin de job confirmée et images à la bonne taille

**Feature Branch**: `004-image-safety`

**Created**: 2026-11-26

**Status**: Draft

**Input**: User description: "Rajouter un resizer d'image afin d'être certain qu'une grosse image
n'ajoute pas de problème : la coupe ne se faisait pas au premier message, mais était prise en
compte dans les prochaines instructions (un ticket était alors coupé au début des appels suivants)."

## Diagnostic

- Logs de production (2026-11-26 09:24) : le job fautif faisait 41 622 octets (image déjà ramenée
  à 576 points, 5 fragments raster), flux vérifié bien formé : l'avance et la coupe sont en fin
  de flux. L'API envoie donc les bons octets.
- L'imprimante (Netum NS-8360L) accuse réception TCP bien avant d'imprimer ; la fin du job
  restait dans son tampon réseau et n'était traitée qu'à la connexion suivante.
- L'imprimante répond à `GS r 1` (état papier, `00`), commande traitée dans l'ordre du flux.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - La coupe a lieu à la fin du bon ticket (Priority: P1)

Après un ticket avec une grande image, le ticket est coupé à sa fin, et le ticket suivant
commence sans coupe parasite.

**Independent Test**: imprimer une image pleine largeur puis un mémo ; le premier est coupé
sous l'image, le second n'a pas de coupe au début. Les logs indiquent
`processed the job in N ms` avec N de l'ordre du temps d'impression.

**Acceptance Scenarios**:

1. **Given** une imprimante qui répond à `GS r`, **When** un job est envoyé, **Then** la
   connexion reste ouverte jusqu'à sa réponse et le job suivant attend.
2. **Given** une imprimante qui ne répond jamais, **When** un job est envoyé, **Then** après
   `PRINTER_DONE_TIMEOUT` la connexion est fermée normalement et un avertissement indique de
   régler `PRINTER_WAIT_DONE=false`.
3. **Given** des octets d'état envoyés spontanément par l'imprimante avant la demande, **Then**
   ils ne sont pas pris pour la réponse.

### User Story 2 - Une grosse image ne pose jamais de problème (Priority: P2)

Une photo de téléphone (plusieurs Mo, plusieurs milliers de pixels) s'imprime à la largeur du
papier, avec une hauteur bornée, sans erreur et sans requête énorme.

**Acceptance Scenarios**:

1. **Given** une image plus haute que `MAX_IMAGE_HEIGHT` après mise à la largeur, **Then** elle
   est réduite pour tenir (proportions gardées) au lieu d'être refusée.
2. **Given** l'interface web, **When** l'utilisateur choisit une photo de 12 Mo, **Then** le
   navigateur l'envoie réduite (largeur de la plus large imprimante, hauteur ≤ 2000 points).
3. **Given** l'aperçu, **Then** il applique la même hauteur maximale que le serveur.

## Requirements *(mandatory)*

- **FR-001**: Après chaque job, si `wait_done`, le transport MUST envoyer `GS r 1` et garder la
  connexion et le verrou de l'imprimante jusqu'à la réponse ou `PRINTER_DONE_TIMEOUT`.
- **FR-002**: Seuls les octets reçus après l'envoi de `GS r 1` comptent comme réponse.
- **FR-003**: La réponse HTTP n'attend pas cette confirmation (latence inchangée).
- **FR-004**: `wait_done` MUST être réglable par imprimante (`PRINTERS`) et globalement
  (`PRINTER_WAIT_DONE`).
- **FR-005**: Une image trop haute MUST être réduite à `MAX_IMAGE_HEIGHT` (2000 par défaut).
- **FR-006**: L'interface MUST réduire les images avant l'envoi et accepter des fichiers jusqu'à
  30 Mo.

## Success Criteria *(mandatory)*

- **SC-001**: Plus aucune coupe décalée après une image (à confirmer sur l'imprimante réelle).
- **SC-002**: Une photo de 12 Mo part en moins de 300 Ko depuis l'interface.
- **SC-003**: Tous les tests existants restent verts.

## Assumptions

- `GS r 1` est traité dans l'ordre du flux (norme ESC/POS) ; si l'imprimante réelle répondait
  immédiatement, le log `processed the job in` l'indiquerait (≈ 0 ms pour une grande image).
