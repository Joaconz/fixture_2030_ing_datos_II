#!/usr/bin/env bash
# ============================================================================
#  Fixture 2030 — Hito 13 · funciones compartidas por los scripts
#  (se incluye con `source`, no se ejecuta solo). Bash portable (macOS 3.2).
# ============================================================================
set -euo pipefail
H13_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="$(cd "$H13_DIR/.." && pwd)"
CAS_DIR="$REPO_DIR/fixture2030-cassandra"
API_DIR="$REPO_DIR/fixture2030-hito10-api"
EVID="$H13_DIR/evidencia"

PROM_URL="${PROM_URL:-http://localhost:9090}"
GRAFANA_URL="${GRAFANA_URL:-http://localhost:3000}"
API_URL="${API_URL:-http://localhost:8000}"

ahora_utc() { date -u +%Y-%m-%dT%H:%M:%SZ; }
sello() { date +%Y%m%d-%H%M%S; }
falla() { echo "✖ $*" >&2; exit 1; }

docker info >/dev/null 2>&1 || falla "Docker no está corriendo: abrí Docker Desktop."

# prom_query 'PROMQL' — imprime "etiquetas valor" por serie (consulta instantánea).
prom_query() {
  curl -fsS -G "$PROM_URL/api/v1/query" --data-urlencode "query=$1" | python3 -c '
import json, sys
for r in json.load(sys.stdin)["data"]["result"]:
    m = {k: v for k, v in r["metric"].items() if k != "__name__"}
    print(" ".join(f"{k}={v}" for k, v in sorted(m.items())) or "-", r["value"][1])'
}

# esperar_url URL SEGUNDOS — espera a que la URL responda 2xx.
esperar_url() {
  local i
  for i in $(seq 1 "$2"); do curl -fsS -m 3 "$1" >/dev/null 2>&1 && return 0; sleep 1; done
  return 1
}
