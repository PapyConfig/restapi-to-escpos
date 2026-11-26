# Contract: routes des modèles

Toutes exigent `X-API-Key` ; les `POST` passent par le contrôle d'origine.

## GET /v1/templates → 200

```json
[{"id": "todo", "name": "À faire", "glyph": "[ ]",
  "description": "Une liste de tâches à cocher au stylo.",
  "fields": [{"key": "taches", "label": "Tâches (une par ligne)", "type": "textarea",
              "required": true, "max": 3000, "default": null, "options": null,
              "placeholder": "Sortir les poubelles\n…", "auto": null}, "…"]}, "…"]
```

## GET /v1/templates/{id} → 200 `TemplateInfo` | 404 `unknown_template`

## POST /v1/templates/{id}/render → 200 `PrintJob`

```http
POST /v1/templates/todo/render
{"values": {"taches": "Pain\nLait"}, "printer": "ticket", "now": "2026-11-26T08:30:00", "seed": 3}
```

```json
{"printer": "ticket", "cut": true, "commands": [{"type": "text", "content": "À faire\n", "bold": true, "width": 2, "height": 2}, "…"]}
```

Rien n'est envoyé à l'imprimante. Le job est accepté tel quel par `POST /v1/print`.
`"partial": true` admet des champs obligatoires vides (aperçu pendant la saisie) ; refusé par
`print` (422).

## POST /v1/templates/{id}/print → 200 `PrintResult`

Même corps que `render`. Réponse identique à `/v1/print`.

## Erreurs

- 404 `unknown_template`, 404 `unknown_printer`
- 422 `invalid_job` : `details[].loc` = `["body", "values", "taches"]` (champ obligatoire vide,
  champ inconnu, type, longueur, choix, format)
- 401, 403 `forbidden_origin`, 413, 502, 504 : inchangés
