# Quickstart: validation de bout en bout

## Prérequis

Docker (ou Python 3.12+), et soit une imprimante ESC/POS réseau, soit l'imprimante factice
(`nc -lk 9100 > out.bin`).

## 1. Tests automatisés (sans matériel)

```bash
pip install -e '.[dev]'
ruff check . && ruff format --check .
pytest --cov=escpos_api
```

Attendu : tout vert, couverture de `renderer.py` / `imaging.py` ≥ 90 %.

## 2. Service en conteneur

```bash
cp .env.example .env   # renseigner API_KEY et PRINTER_HOST
docker compose up -d --build
curl -s localhost:8000/health                    # {"status":"ok",...}
curl -s -H "X-API-Key: $API_KEY" localhost:8000/v1/printers   # reachable: true
```

## 3. Scénarios (examples/print.sh)

| Scénario | Commande | Attendu |
|----------|----------|---------|
| US1 ticket texte | `./examples/print.sh receipt` | ticket centré, accents et € corrects, coupé |
| US2 image seule | `./examples/print.sh image examples/logo.png` | logo centré à la largeur papier, coupé |
| US2 image dans ticket | `./examples/print.sh full-receipt` | logo en tête + lignes + QR + code-barres |
| US3 codes | `./examples/print.sh qr-barcode` | QR et code-barres scannables |
| US5 aperçu | `./examples/print.sh render receipt > out.bin` | fichier non vide, rien imprimé |
| Sécurité | `curl -X POST localhost:8000/v1/print -d '{}'` | 401 |
| Imprimante éteinte | arrêter l'imprimante, relancer `receipt` | 502/504 en ≤ timeout + 1 s ; `/health` répond pendant ce temps |
