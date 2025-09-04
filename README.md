# Thermal Printer API

API REST pour envoyer des commandes ESC/POS à une imprimante thermique via réseau.

## Fonctionnalités

- Impression via réseau (TCP/IP)
- Support des commandes ESC/POS standard
- API RESTful avec FastAPI
- Conteneur Docker
- CI/CD avec GitHub Actions

## Installation

### Avec Docker

```bash
docker build -t thermal-printer-api .
docker run -p 8000:8000 thermal-printer-api
