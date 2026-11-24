# Contract: HTTP API v1

Authentification : en-tête `X-API-Key: <clé>` sur toutes les routes `/v1/*`.
Le schéma OpenAPI complet est servi par l'application sur `/openapi.json` (doc : `/docs`).

| Méthode | Route | Auth | Corps | Succès |
|---------|-------|------|-------|--------|
| GET | `/health` | non | – | 200 `{"status":"ok","version":"2.x"}` |
| GET | `/v1/printers` | oui | – | 200 `[{"name","host","port","width","profile","default","reachable"}]` |
| POST | `/v1/print` | oui | `PrintJob` (JSON) | 200 `PrintResult` |
| POST | `/v1/print/image` | oui | multipart : `file` + `ImageOptions` | 200 `PrintResult` |
| POST | `/v1/render` | oui | `PrintJob` (JSON) | 200 `application/octet-stream` (flux ESC/POS), en-tête `X-Escpos-Bytes` |

## Codes d'erreur (corps `ErrorResponse`)

| HTTP | error | Cas |
|------|-------|-----|
| 401 | unauthorized | clé absente ou invalide |
| 404 | unknown_printer | nom d'imprimante non déclaré |
| 413 | payload_too_large | requête > `MAX_REQUEST_BYTES` ou image > `MAX_IMAGE_BYTES` |
| 422 | invalid_job | schéma invalide ou instruction impossible à rendre (index fourni) |
| 422 | invalid_image | fichier illisible, format refusé, trop de pixels, trop haut |
| 502 | printer_unreachable | connexion refusée / hôte injoignable |
| 504 | printer_timeout | délai `PRINTER_TIMEOUT` dépassé |
| 500 | internal_error | inattendu (message générique, détail dans les logs) |

## Exemple

```json
POST /v1/print
{
  "printer": "caisse",
  "commands": [
    {"type": "text", "content": "MA BOUTIQUE\n", "align": "center", "bold": true, "width": 2, "height": 2},
    {"type": "separator"},
    {"type": "text", "content": "Café             2,50 €\n"},
    {"type": "qr", "content": "https://example.com/t/123, merci"},
    {"type": "cut"}
  ]
}
```

## Configuration (variables d'environnement)

| Variable | Défaut | Rôle |
|----------|--------|------|
| `API_KEY` | – | clé exigée sur `/v1/*` |
| `ALLOW_NO_AUTH` | `false` | autorise le démarrage sans clé (déconseillé) |
| `PRINTER_HOST` / `PRINTER_PORT` / `PRINTER_WIDTH` / `PRINTER_PROFILE` | – / 9100 / 576 / default | imprimante unique `default` |
| `PRINTERS` | – | JSON : `[{"name":"caisse","host":"10.0.0.5","width":576}, ...]` |
| `DEFAULT_PRINTER` | première | nom de l'imprimante par défaut |
| `PRINTER_TIMEOUT` | `10` | secondes (connexion + envoi) |
| `CORS_ORIGINS` | vide | origines autorisées, séparées par des virgules |
| `MAX_REQUEST_BYTES` | 15 Mo | |
| `MAX_IMAGE_BYTES` | 10 Mo | |
| `MAX_IMAGE_PIXELS` | 25 000 000 | |
| `MAX_IMAGE_HEIGHT` | 4000 | points, après mise à l'échelle |
| `LOG_LEVEL` | `INFO` | |
