# Implementation Plan: Modèles de mémos accessibles par l'API

**Branch**: `003-api-templates` | **Date**: 2026-11-26 | **Spec**: [spec.md](spec.md)

## Summary

Porter les 10 modèles intégrés de `ui/templates.js` vers `src/escpos_api/templates.py`, les exposer
par quatre routes `/v1/templates…`, et faire consommer ces routes par l'interface web (liste,
aperçu par rendu serveur avec anti-rebond, impression du job rendu).

## Technical Context

**Language/Version**: Python 3.12+ ; JS ES modules (navigateur, Node 22 pour les tests)
**Primary Dependencies**: FastAPI, Pydantic v2 (aucune nouvelle dépendance)
**Storage**: aucun côté serveur ; navigateur inchangé
**Testing**: pytest (imprimante factice), `node --test`
**Target Platform**: conteneur Linux (`TZ` à déclarer)
**Performance Goals**: rendu d'un modèle < 50 ms ; aperçu < 500 ms après la dernière frappe
**Constraints**: mêmes limites de corps, d'auth et d'origine que `/v1`
**Scale/Scope**: 10 modèles, 4 routes

## Constitution Check

| Principe | Statut |
|---|---|
| I. Sécurité par défaut | ✅ clé API sur toutes les routes, contrôle d'origine, identifiant de modèle pris dans un registre fixe (aucun chemin/URL choisi par le client), champs inconnus refusés |
| II. Contrat typé et validé | ✅ modèles Pydantic pour la réponse et les valeurs, erreurs dans l'enveloppe existante, OpenAPI à jour |
| III. Impression atomique | ✅ `print` = rendu complet puis envoi en un bloc (même chemin que `/v1/print`) |
| IV. Tests sans matériel | ✅ imprimante factice ; caractères vérifiés par le vrai moteur |
| V. Simplicité | ✅ pas de stockage ni de dépendance ; l'interface reste statique et n'imprime que via `/v1` |

## Project Structure

```text
src/escpos_api/
├── templates.py        # NOUVEAU : registre, champs, constructions, validation des valeurs
├── api.py              # + 4 routes
├── models.py           # + TemplateField, TemplateInfo, TemplateRequest
└── ui/
    ├── templates.js    # réduit à initialValues / missingRequired
    └── app.js          # liste et aperçu via l'API
tests/
├── test_templates.py   # NOUVEAU
└── js/templates.test.mjs  # réduit aux aides de formulaire
```

## Phases

1. Modèles Pydantic + `templates.py` (portage) + tests unitaires (rendu, colonnes, imprimable).
2. Routes + tests HTTP (auth, 404, 422, origine, `render` → `/v1/print`).
3. Interface : chargement de la liste, rendu serveur anti-rebond, impression du job rendu,
   erreurs de champ ; tests JS ; vérification dans un navigateur.
4. Docs : README (section modèles + exemple n8n/curl), CHANGELOG 2.2.0, CLAUDE.md, `.env.example`
   (`TZ`), version 2.2.0.
