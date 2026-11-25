# Data Model: API REST d'impression ESC/POS (v2)

Aucune persistance : ce sont les modèles du contrat et de la configuration.

## PrinterConfig (configuration serveur)

| Champ | Type | Règles |
|-------|------|--------|
| name | str | `^[a-z0-9][a-z0-9_-]{0,31}$`, unique |
| host | str | requis |
| port | int | 1–65535, défaut 9100 |
| width | int | points imprimables, 64–2048, multiple de 8, défaut 576 |
| profile | str | profil python-escpos, défaut `default` ; validé au démarrage |
| image_impl | enum | `bitImageRaster` (défaut), `bitImageColumn`, `graphics` |
| image_fragment_height | int | 24–2048, défaut 128 : hauteur max d'une commande image |

Colonnes de texte dérivées : police A = `width // 12`, police B = `width // 9`.

## PrintJob

| Champ | Type | Règles |
|-------|------|--------|
| printer | str \| null | nom déclaré ; null → imprimante par défaut ; inconnu → 404 |
| commands | list[Command] | 1–500 éléments |
| cut | bool | défaut `true` : ajoute une coupe partielle finale si aucune `cut` n'est en dernière position |

## Command (union discriminée sur `type`)

Champs de style partagés (`StyleFields`, tous optionnels) : `align` (left/center/right),
`bold` (bool), `underline` (0–2), `font` (a/b), `width` (1–8), `height` (1–8), `invert` (bool).

| type | Champs | Notes |
|------|--------|-------|
| `text` | `content` (str, 1–10 000) + StyleFields | style appliqué à ce texte seulement, puis rétabli |
| `style` | StyleFields (au moins un) | persistant jusqu'au prochain `style` ; `reset: true` revient au style par défaut |
| `feed` | `lines` (1–255, défaut 1) | |
| `separator` | `char` (1 caractère, défaut `-`) | ligne pleine selon la police/largeur courante |
| `qr` | `content` (1–4000), `size` (1–16, défaut 6), `ec` (L/M/Q/H, défaut M), `align` (défaut center) | QR natif |
| `barcode` | `content`, `symbology` (EAN13, EAN8, UPC-A, UPC-E, CODE39, CODE93, CODE128, ITF, CODABAR), `height` (1–255, défaut 80), `module_width` (2–6, défaut 3), `text_position` (none/above/below/both, défaut below), `align` (défaut center) | contenu validé par python-escpos ; CODE128 préfixé `{B` automatiquement |
| `image` | `data` (base64), `align` (défaut center), `mode` (dither/threshold, défaut dither), `threshold` (0–255, défaut 128), `width` (points, optionnel) | voir ImageOptions |
| `cut` | `mode` (partial/full, défaut partial), `feed` (bool, défaut true) | |
| `cashdraw` | `pin` (2 ou 5, défaut 2) | |

## ImageOptions (route d'upload)

Mêmes champs que `image` sans `data`, plus `printer` et `cut` (défaut `true`), en champs de
formulaire multipart à côté du fichier `file`.

## PrintResult (réponse 200)

`job_id` (uuid4), `printer` (nom), `bytes` (int), `duration_ms` (int).

## ErrorResponse

`error` (code machine : `invalid_job`, `invalid_image`, `unauthorized`, `unknown_printer`,
`printer_unreachable`, `printer_timeout`, `payload_too_large`, `internal_error`),
`message` (texte lisible), `details` (liste optionnelle, ex. `{"index": 3, "reason": "..."}`).

## Cycle de vie d'un job

`reçu` → `validé` (sinon 422) → `rendu` (sinon 422, 0 octet) → `en attente du verrou` →
`envoyé` (200) | `injoignable` (502) | `timeout` (504).
