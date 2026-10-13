#!/usr/bin/env bash
# ============================================================
#  Fixture 2030 — Hito 10 · API REST integrada
#  ARCHIVO: scripts/ejecutar_pruebas.sh
#  PROPÓSITO: punto único para correr cada tipo de prueba (§5.12, ver tests/README.md).
#  USO:  bash scripts/ejecutar_pruebas.sh [unit|integration|contrato|newman|todo]
#    unit         pytest tests/unit — sin Docker (adaptadores falsos)
#    integration  pytest tests/integration -m integration — necesita las 5 fuentes
#    contrato     schemathesis 4.31 contra la API corriendo en $API_URL usando
#                 openapi/openapi.yaml. Por defecto SÓLO operaciones de lectura
#                 (GET): las de escritura generarían eventos/comentarios basura en
#                 las bases de demo. CONTRATO_ESCRITURAS=1 las incluye.
#                 CONTRATO_MAX_EJEMPLOS (default 30) y CONTRATO_SEMILLA (default 2030)
#                 hacen la corrida acotada y reproducible.
#    newman       colección Postman (postman/) contra la API corriendo
#    todo         unit → integration → contrato → newman (se detiene en la 1ª falla)
#  Los reportes quedan en docs/evidencia/pruebas_<tipo>_<fecha>.* (sin secretos).
# ============================================================
set -euo pipefail
source "$(dirname "$0")/_comun.sh"
cd "$API_DIR"

PY="$API_DIR/.venv/bin/python"
[ -x "$PY" ] || { echo "Falta .venv: bash scripts/iniciar_api.sh lo crea." >&2; exit 1; }
EVID="$API_DIR/docs/evidencia"
mkdir -p "$EVID"

api_arriba() {
  [ "$(curl -s -o /dev/null -m 3 -w '%{http_code}' "$API_URL/health" || true)" = "200" ] || {
    echo "La API no responde en $API_URL. Levantarla con: bash scripts/iniciar_api.sh" >&2; return 1; }
}

unit()        { "$PY" -m pytest tests/unit -q; }
integration() { "$PY" -m pytest tests/integration -m integration -p no:cacheprovider -q; }

contrato() {
  api_arriba
  local filtros=()
  if [ "${CONTRATO_ESCRITURAS:-0}" != "1" ]; then
    filtros=(--include-method GET)
  fi
  "$API_DIR/.venv/bin/schemathesis" run openapi/openapi.yaml \
    --url "$API_URL" \
    ${filtros[@]+"${filtros[@]}"} \
    --checks not_a_server_error,status_code_conformance,content_type_conformance,response_headers_conformance,response_schema_conformance,negative_data_rejection \
    --phases examples,coverage,fuzzing \
    --max-examples "${CONTRATO_MAX_EJEMPLOS:-30}" \
    --seed "${CONTRATO_SEMILLA:-2030}" \
    --generation-database none \
    --request-timeout 10 \
    --workers 1 \
    --report junit --report-junit-path "$EVID/pruebas_contrato_$(sello_fecha).xml"
}

newman_run() {
  api_arriba
  command -v newman >/dev/null 2>&1 || { echo "Falta newman: npm install -g newman" >&2; return 1; }
  newman run postman/fixture2030_collection.json -e postman/fixture2030_environment.json \
    --env-var "baseUrl=$API_URL" \
    --reporters cli,junit --reporter-junit-export "$EVID/pruebas_newman_$(sello_fecha).xml"
}

case "${1:-unit}" in
  unit) unit ;;
  integration) integration ;;
  contrato) contrato ;;
  newman) newman_run ;;
  todo) unit && integration && contrato && newman_run ;;
  *) echo "Uso: $0 [unit|integration|contrato|newman|todo]" >&2; exit 2 ;;
esac
