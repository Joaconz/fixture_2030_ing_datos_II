#!/usr/bin/env bash
# ============================================================
#  Fixture 2030 — Hito 10 · API REST integrada
#  ARCHIVO: scripts/medir_latencia.sh
#  PROPÓSITO: medición de latencia de la API de punta a punta (RNF18).
#  MÉTODO (explícito, reproducible):
#    - cliente: curl en la MISMA notebook que la API y las bases (sin red de por medio);
#    - N requests SECUENCIALES por endpoint (default N=200; sin concurrencia), con
#      2 requests de calentamiento descartadas antes de cada serie;
#    - tiempo = `curl -w '%{time_total}'` (desde que curl abre la conexión hasta el
#      último byte; conexión nueva en cada request, sin keep-alive);
#    - percentiles por rango más cercano sobre los N tiempos ordenados:
#      p50 = t[ceil(0,50·N)], p95 = t[ceil(0,95·N)], máx = t[N];
#    - un endpoint representativo por fuente + detalle de partido en HIT (caché
#      Redis caliente) y en MISS: antes de cada request MISS se invalida SÓLO la
#      clave de caché `f30:cache:partido:PAR-A-1` (redis-cli DEL, igual que hace la
#      API al cerrar un partido; no borra datos de ninguna fuente). MEDIR_MISS=0 lo omite;
#    - se registran códigos HTTP y valores de X-Cache observados: una serie con
#      errores se informa, no se oculta.
#  USO:  bash scripts/medir_latencia.sh [N]
#  SALIDA: docs/evidencia/latencia_<fecha>.md con fecha, máquina (uname -a, CPUs,
#  memoria), versión de la API, N y la tabla de resultados.
# ============================================================
set -euo pipefail
source "$(dirname "$0")/_comun.sh"

N="${1:-200}"
case "$N" in ''|*[!0-9]*) echo "N debe ser un entero positivo" >&2; exit 2 ;; esac
MEDIR_MISS="${MEDIR_MISS:-1}"
EVID="$API_DIR/docs/evidencia"; mkdir -p "$EVID"
FECHA="$(sello_fecha)"
SALIDA="$EVID/latencia_${FECHA}.md"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

[ "$(curl -s -o /dev/null -m 3 -w '%{http_code}' "$API_URL/health" || true)" = "200" ] || {
  echo "La API no responde en $API_URL (bash scripts/iniciar_api.sh)" >&2; exit 1; }

VERSION_API="$(curl -s -m 5 "$API_URL/openapi.json" | "$API_DIR/.venv/bin/python" -c 'import json,sys; print(json.load(sys.stdin)["info"]["version"])' 2>/dev/null || echo desconocida)"
CPUS="$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo '?')"
if [ "$(uname -s)" = "Darwin" ]; then
  MEM_GB="$(awk -v b="$(sysctl -n hw.memsize)" 'BEGIN { printf "%.1f", b/1024/1024/1024 }')"
else
  MEM_GB="$(awk '/MemTotal/ { printf "%.1f", $2/1024/1024 }' /proc/meminfo 2>/dev/null || echo '?')"
fi
REDIS_C="$(contenedor_de redis)"

invalidar_cache() {
  docker exec "$REDIS_C" redis-cli DEL "f30:cache:partido:PAR-A-1" >/dev/null 2>&1 || true
}

# serie NOMBRE RUTA [miss] → agrega una fila a $TMP/tabla
serie() {
  local nombre="$1" ruta="$2" modo="${3:-}" i salida
  : > "$TMP/tiempos"; : > "$TMP/codigos"; : > "$TMP/caches"
  for i in 1 2; do curl -s -o /dev/null -m 10 "$API_URL$ruta" || true; done
  for i in $(seq 1 "$N"); do
    [ "$modo" = "miss" ] && invalidar_cache
    salida="$(curl -s -o /dev/null -D "$TMP/cab" -m 10 -H "X-Request-Id: lat-${nombre}-${i}" \
              -w '%{http_code} %{time_total}' "$API_URL$ruta" || echo "000 10")"
    echo "${salida%% *}" >> "$TMP/codigos"
    echo "${salida##* }" >> "$TMP/tiempos"
    grep -i '^x-cache:' "$TMP/cab" 2>/dev/null | tr -d '\r' | awk '{print $2}' >> "$TMP/caches" || true
  done
  local stats codigos caches
  stats="$(sort -n "$TMP/tiempos" | awk '
    { t[NR] = $1 }
    END {
      n = NR
      i50 = int(0.50 * n); if (i50 < 0.50 * n) i50++
      i95 = int(0.95 * n); if (i95 < 0.95 * n) i95++
      printf "%.1f | %.1f | %.1f", t[i50] * 1000, t[i95] * 1000, t[n] * 1000
    }')"
  codigos="$(sort "$TMP/codigos" | uniq -c | awk '{ printf "%s%s×%s", (NR>1?", ":""), $2, $1 }')"
  caches="$(sort "$TMP/caches" | uniq -c | awk '{ printf "%s%s×%s", (NR>1?", ":""), $2, $1 }')"
  echo "| $nombre | \`GET $ruta\` | $N | $stats | $codigos | ${caches:--} |" >> "$TMP/tabla"
  echo "  $nombre: p50 | p95 | máx (ms) = $stats  [$codigos]"
}

echo "Midiendo $N requests secuenciales por endpoint contra $API_URL…"
: > "$TMP/tabla"
serie "mongodb-equipo"       "/equipos/ARG"
serie "neo4j-eventos"        "/partidos/PAR-A-1/eventos?limit=20"
serie "cassandra-comentarios" "/partidos/PAR-A-1/comentarios?limit=20"
serie "redis-sesion"         "/sesiones/demo-ses-0000001-1"
serie "influxdb-estadisticas" "/partidos/PAR-A-1/estadisticas?desde=2030-06-09T13:00:00Z&hasta=2030-06-09T13:30:00Z&agregacion=1m"
serie "partido-HIT"          "/partidos/PAR-A-1"
if [ "$MEDIR_MISS" = "1" ]; then
  serie "partido-MISS"       "/partidos/PAR-A-1" miss
fi

{
  echo "# Latencia de la API — $FECHA"
  echo
  echo "- Fecha (UTC): $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "- Máquina: \`$(uname -a)\`"
  echo "- CPUs visibles: $CPUS · Memoria: $MEM_GB GB"
  echo "- Versión de la API: $VERSION_API · URL: $API_URL · DEP_TIMEOUT_S: ${DEP_TIMEOUT_S:-2.0}"
  echo "- N por endpoint: $N (secuenciales, 2 de calentamiento descartadas)"
  echo
  echo "## Método"
  echo
  echo "curl en la misma notebook que la API y los contenedores; tiempo = \`%{time_total}\` de curl"
  echo "(conexión nueva por request). Percentiles por rango más cercano sobre los N tiempos"
  echo "ordenados. En \`partido-MISS\` se invalida sólo la clave \`f30:cache:partido:PAR-A-1\`"
  echo "antes de cada request (fuera del tiempo medido)."
  echo
  echo "## Resultados"
  echo
  echo "| Serie | Request | N | p50 (ms) | p95 (ms) | máx (ms) | Códigos HTTP | X-Cache |"
  echo "|---|---|---:|---:|---:|---:|---|---|"
  cat "$TMP/tabla"
  echo
  echo "Notas: \`redis-sesion\` puede responder 404 si la sesión de demo ya expiró (TTL de la carga"
  echo "del Hito 7); el tiempo sigue midiendo el camino completo hasta Redis."
} > "$SALIDA"
echo "Evidencia: $SALIDA"
