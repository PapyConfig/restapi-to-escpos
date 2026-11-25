# Quickstart: interface web

```bash
nc -lk 9100 > out.bin &                       # imprimante factice
API_KEY=dev PRINTER_HOST=127.0.0.1 UI_ENABLED=true \
  uvicorn escpos_api.main:create_app --factory
```

Ouvrir http://localhost:8000/ → redirection vers `/ui/`. Sans proxy, l'interface demande la clé
(`dev`) au premier appel.

Vérifications :

1. Modèle « À faire » → 3 tâches → Imprimer → `out.bin` grossit, toast « Imprimé ».
2. Éditeur : code-barres EAN13 `123` → Imprimer → le bloc passe en erreur, `out.bin` inchangé.
3. `curl -X POST -H 'Origin: https://evil.example' -H 'X-API-Key: dev' localhost:8000/v1/print`
   → 403 `forbidden_origin`.
4. Sans `UI_ENABLED` : `curl -i localhost:8000/ui/` → 404.

Tests :

```bash
pytest
node --test tests/js
```
