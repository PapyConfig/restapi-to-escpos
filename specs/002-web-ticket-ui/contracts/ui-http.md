# Contract: routes HTTP ajoutées

Le contrat `/v1` est **inchangé**. Ajouts :

## Réglage

| Variable | Défaut | Effet |
|----------|--------|-------|
| `UI_ENABLED` | `false` | Sert l'interface web sur `/ui/` |

## Routes (uniquement si `UI_ENABLED=true`)

| Méthode | Route | Réponse |
|---------|-------|---------|
| GET | `/` | `307` → `/ui/` |
| GET | `/ui` | `307` → `/ui/` |
| GET | `/ui/` | `index.html` |
| GET | `/ui/<fichier>` | fichier statique, 404 sinon |

Pas d'authentification sur ces routes (contenu statique public, sans secret) ; les appels `/v1`
faits par la page restent authentifiés.

En-têtes sur toutes les réponses `/ui` :

```
Content-Security-Policy: default-src 'none'; script-src 'self'; style-src 'self';
  img-src 'self' data: blob:; connect-src 'self'; manifest-src 'self';
  base-uri 'none'; form-action 'none'; frame-ancestors 'none'
X-Content-Type-Options: nosniff
Referrer-Policy: no-referrer
Cache-Control: no-cache
```

Avec `UI_ENABLED=false` : `/`, `/ui`, `/ui/...` → 404 (comportement actuel).

## Contrôle d'origine (toujours actif)

Pour `POST`, `PUT`, `PATCH`, `DELETE` :

- pas d'en-tête `Origin` → inchangé ;
- `Origin` dont `host[:port]` égale l'en-tête `Host` → inchangé ;
- `Origin` présent dans `CORS_ORIGINS` → inchangé ;
- sinon (y compris `Origin: null`) → `403`
  `{"error": "forbidden_origin", "message": "Cross-origin request refused."}`, rien n'est imprimé.
