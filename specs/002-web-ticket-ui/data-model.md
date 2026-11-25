# Data Model: Interface web

Toutes les entités vivent dans le navigateur. Aucune n'est stockée par le serveur.

## Block

Un bloc **est** une commande du contrat `/v1/print` (mêmes champs, mêmes bornes), plus un
identifiant local `id` retiré avant envoi. Types proposés : `text`, `separator`, `feed`, `qr`,
`barcode`, `image`, `cut`. `style` et `cashdraw` sont acceptés à l'import mais pas proposés.

## Ticket (document d'édition)

| Champ | Type | Règle |
|-------|------|-------|
| `title` | string | déduit du premier texte, sert à l'historique |
| `blocks` | Block[] | 1 à 500 |
| `cut` | bool | true |

`toJob(ticket, printer)` → `{printer, cut, commands}` : retire `id`, ajoute `\n` à la fin d'un
texte qui n'en a pas.

## BuiltinTemplate

| Champ | Type |
|-------|------|
| `id`, `name`, `icon`, `description` | string |
| `fields` | Field[] |
| `build(values, ctx)` | → Block[] ; `ctx = {columns, now}` |

## Field

`{key, label, type: text|textarea|select|checkbox|date|time, default?, options?, max?,
placeholder?, required?}`. `date`/`time` sans défaut → date/heure courantes.

## UserTemplate

`{id, name, blocks, createdAt}`. Champs déduits : chaque `{{nom}}` trouvé dans un champ texte
d'un bloc (`content`) ; remplacé à l'impression. Export/import : fichier JSON
`{"version": 1, "templates": [...]}`.

## HistoryEntry

`{at (ISO), title, printer, job}` ; 30 entrées max, plus récentes d'abord.

## Validation côté UI

- Bornes identiques au contrat (taille 1–8, QR 1–16, hauteur code-barres 1–255…).
- Caractères hors liste blanche → avertissement sur le bloc (n'empêche pas l'impression).
- Erreur 422 avec `details[].index = i` → bloc `i` marqué en erreur avec `reason`.
