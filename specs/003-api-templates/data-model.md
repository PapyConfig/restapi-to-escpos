# Data Model: Modèles de mémos accessibles par l'API

## TemplateField (réponse)

| Champ | Type | Notes |
|---|---|---|
| `key` | str | clé dans `values` |
| `label` | str | libellé français |
| `type` | `text` \| `textarea` \| `date` \| `time` \| `select` \| `checkbox` | |
| `required` | bool | non vide après suppression des espaces |
| `max` | int \| null | longueur maximale (texte) |
| `default` | str \| bool \| null | appliqué si la clé est absente |
| `options` | `[{value, label}]` \| null | pour `select` |
| `placeholder` | str \| null | exemple |
| `auto` | `today` \| `now` \| `id` \| null | valeur calculée si la clé est absente |

## TemplateInfo (réponse)

`id` (`^[a-z]+$`), `name`, `glyph`, `description`, `fields: TemplateField[]`.

## TemplateRequest (corps de `render` et `print`)

| Champ | Type | Défaut |
|---|---|---|
| `printer` | str \| null | imprimante par défaut |
| `values` | objet | `{}` ; validé par le modèle (R3) |
| `cut` | bool | `true` |
| `now` | date-heure ISO 8601 \| null | heure du serveur |
| `seed` | int ≥ 0 \| null | hasard |
| `partial` | bool (`render` seulement) | `false` ; `true` : champs obligatoires vides admis (aperçu en cours de saisie) |

Valeurs selon le type : `text`/`textarea`/`date`/`time`/`select` → chaîne ; `checkbox` → booléen ;
`date` vide ou `AAAA-MM-JJ` valide ; `time` vide ou `HH:MM`.

## Réponses

- `render` → `PrintJob` (`printer` = nom résolu, `cut`, `commands`).
- `print` → `PrintResult` (inchangé).

## Erreurs

| Code | `error` | Cas |
|---|---|---|
| 404 | `unknown_template` | identifiant inconnu |
| 404 | `unknown_printer` | imprimante non déclarée |
| 422 | `invalid_job` | valeur invalide (`loc = ["body","values",<clé>]`) |
| 401/403/413/502/504 | inchangés | |
