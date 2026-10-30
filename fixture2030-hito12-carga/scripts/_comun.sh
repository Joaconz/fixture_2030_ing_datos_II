#!/usr/bin/env bash
# ============================================================================
#  Fixture 2030 — Hito 12 · funciones compartidas por los scripts
# ============================================================================
set -euo pipefail
H12_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="$(cd "$H12_DIR/.." && pwd)"
API_DIR="$REPO_DIR/fixture2030-hito10-api"
CAS_DIR="$REPO_DIR/fixture2030-cassandra"
CONTENEDOR_CAS="fixture2030-cassandra"
CONTENEDOR_K6="fixture2030-k6"          # nombre fijo del generador, para medir su consumo (RF6)
EVID="$H12_DIR/docs/evidencia"

# Configuración del escenario: config/configuracion-ejemplo.env y, si existe, config/configuracion.env (ignorado por git)
set -a
. "$H12_DIR/config/configuracion-ejemplo.env"
[ -f "$H12_DIR/config/configuracion.env" ] && . "$H12_DIR/config/configuracion.env"
set +a

API_URL_LOCAL="http://127.0.0.1:${API_PORT}"
PY_API="$API_DIR/.venv/bin/python"

ahora_utc() { date -u +%Y-%m-%dT%H:%M:%SZ; }
falla() { echo "✖ $*" >&2; exit 1; }

cql() { docker exec -i "$CONTENEDOR_CAS" cqlsh -e "$1"; }

lecturas_q0() {  # lecturas locales de la tabla de configuración (evidencia de la hipótesis)
  docker exec "$CONTENEDOR_CAS" nodetool tablestats fixture2030_comentarios.config_particion_partido 2>/dev/null \
    | awk -F': ' '/Local read count/ {v=$2} END {print v}' || true
}

api_arriba() { curl -fsS -m 3 "$API_URL_LOCAL/health" >/dev/null 2>&1; }

iniciar_api() {  # $1 = segundos de caché de Q0 (0 = línea base) · $2 = archivo de log
  api_arriba && falla "Ya hay una API escuchando en el puerto $API_PORT. Cerrala (Ctrl+C) para que la prueba la levante con la configuración controlada."
  ( cd "$API_DIR" && COMENTARIOS_CONFIG_CACHE_S="$1" LOG_LEVEL=WARNING API_PORT="$API_PORT" \
      bash scripts/iniciar_api.sh > "$2" 2>&1 ) &
  API_PID_PADRE=$!
  for _ in $(seq 1 60); do api_arriba && return 0; sleep 1; done
  falla "La API no arrancó en 60 s. Ver $2"
}

detener_api() {
  local pid; pid=$(lsof -ti tcp:"$API_PORT" -sTCP:LISTEN 2>/dev/null || true)
  [ -n "$pid" ] && kill $pid 2>/dev/null || true
  [ -n "${API_PID_PADRE:-}" ] && kill "$API_PID_PADRE" 2>/dev/null || true
  sleep 1
}

uso_contenedor() {  # $1 = contenedor → "cpu_pct,memoria" (vacío si no está corriendo)
  docker stats --no-stream --format '{{.CPUPerc}},{{.MemUsage}}' "$1" 2>/dev/null | sed 's/%//' | awk -F'[,/]' '{gsub(/ /,"",$2); print $1","$2}'
}

muestrear_recursos() {  # $1 = CSV de salida · corre hasta que lo maten
  set +e +o pipefail                # el muestreo nunca debe cortar la prueba
  echo "momento_utc,cassandra_cpu_pct,cassandra_mem,api_cpu_pct,api_rss_mb,k6_cpu_pct,k6_mem" > "$1"
  while true; do
    local cs api k6 pid
    cs=$(uso_contenedor "$CONTENEDOR_CAS")
    k6=$(uso_contenedor "$CONTENEDOR_K6")
    pid=$(lsof -ti tcp:"$API_PORT" -sTCP:LISTEN 2>/dev/null | head -1 || true)
    api=$([ -n "$pid" ] && ps -o %cpu=,rss= -p "$pid" | awk '{printf "%s,%.1f", $1, $2/1024}' || echo ",")
    echo "$(ahora_utc),${cs:-,},${api},${k6:-,}" >> "$1"
    sleep 2
  done
}
