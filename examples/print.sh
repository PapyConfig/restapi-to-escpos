#!/usr/bin/env bash
# Envoie les exemples à l'API.
#   ./examples/print.sh receipt|full-receipt|qr-barcode|styles   imprime examples/<nom>.json
#   ./examples/print.sh image <fichier> [align] [mode]          imprime une image (upload)
#   ./examples/print.sh render <nom>  > out.bin                  rendu ESC/POS sans impression
#   ./examples/print.sh printers                                 liste des imprimantes
# Variables : API_URL (défaut http://localhost:8000), API_KEY (obligatoire), PRINTER (optionnel)
set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"
: "${API_KEY:?Définir API_KEY}"
DIR="$(cd "$(dirname "$0")" && pwd)"

job() {
  local file="$DIR/$1.json"
  [[ -f "$file" ]] || { echo "Exemple inconnu : $1" >&2; exit 1; }
  if [[ -n "${PRINTER:-}" ]]; then
    python3 -c 'import json,sys; j=json.load(open(sys.argv[1])); j["printer"]=sys.argv[2]; print(json.dumps(j))' \
      "$file" "$PRINTER"
  else
    cat "$file"
  fi
}

case "${1:-}" in
  printers)
    curl -fsS -H "X-API-Key: $API_KEY" "$API_URL/v1/printers"; echo ;;
  image)
    file="${2:?Chemin du fichier image}"
    args=(-F "file=@$file" -F "align=${3:-center}" -F "mode=${4:-dither}")
    [[ -n "${PRINTER:-}" ]] && args+=(-F "printer=$PRINTER")
    curl -sS -H "X-API-Key: $API_KEY" "${args[@]}" "$API_URL/v1/print/image"; echo ;;
  render)
    job "${2:?Nom d un exemple}" | curl -fsS -H "X-API-Key: $API_KEY" \
      -H "Content-Type: application/json" --data-binary @- "$API_URL/v1/render" ;;
  "")
    sed -n '2,7p' "$0"; exit 1 ;;
  *)
    job "$1" | curl -sS -H "X-API-Key: $API_KEY" \
      -H "Content-Type: application/json" --data-binary @- "$API_URL/v1/print"; echo ;;
esac
