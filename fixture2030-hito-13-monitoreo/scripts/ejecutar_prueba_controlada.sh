#!/usr/bin/env bash
# ============================================================================
#  Fixture 2030 — Hito 13 · prueba de falla controlada (RF10).
#  USO: bash scripts/ejecutar_prueba_controlada.sh [redis|mongodb|cassandra|neo4j]
#       (por defecto redis: sesiones de usuario, Hito 7)
#
#  Qué hace, sobre contenedores de LABORATORIO (RNF11):
#    1. ANTES:   verifica que la base esté arriba y genera tráfico de lectura a
#                la ruta de la API que la usa (si la API está levantada).
#    2. FALLA:   `docker stop` del contenedor. Mide cuándo Prometheus ve la
#                caída (probe_success = 0) y cuándo la alerta BaseNoResponde
#                pasa a firing; registra qué responde la API.
#    3. RECUPERACIÓN: `docker start` y mide cuándo vuelve probe_success = 1.
#    4. Deja el informe en evidencia/prueba_de_falla_<base>_<fecha>.md con la
#       línea de tiempo y las series de Prometheus del intervalo.
#  No borra volúmenes ni datos: stop/start conserva todo. Solo lecturas (GET).
# ============================================================================
. "$(dirname "$0")/_comun.sh"

BASE="${1:-redis}"
case "$BASE" in
  redis)     CONT=fixture2030-redis;     RUTA="/sesiones/demo-ses-0000001-1" ;;
  mongodb)   CONT=fixture2030_mongo;     RUTA="/equipos/ARG" ;;
  cassandra) CONT=fixture2030-cassandra; RUTA="/partidos/PAR-A-1/comentarios" ;;
  neo4j)     CONT=fixture2030-neo4j;     RUTA="/partidos/PAR-A-1" ;;
  *) falla "Base no soportada: $BASE (redis | mongodb | cassandra | neo4j)" ;;
esac
CONTROL="/equipos/ARG"; [ "$BASE" = mongodb ] && CONTROL="/sesiones/demo-ses-0000001-1"

curl -fsS -m 3 "$PROM_URL/-/ready" >/dev/null 2>&1 || falla "Prometheus no responde: correr scripts/iniciar_monitoreo.sh"
docker ps --format '{{.Names}}' | grep -qx "$CONT" || falla "$CONT no está corriendo: levantalo antes de la prueba."
[ "$(prom_query "probe_success{base=\"$BASE\"}" | awk '{print $NF}')" = "1" ] || falla "Prometheus todavía no ve $BASE arriba; esperá un scrape (15 s)."

API_OK=0; curl -fsS -m 3 "$API_URL/health" >/dev/null 2>&1 && API_OK=1
TRAFICO_PID=""
terminar() { [ -n "$TRAFICO_PID" ] && kill "$TRAFICO_PID" 2>/dev/null || true; }
trap terminar EXIT
if [ "$API_OK" = 1 ]; then
  ( while true; do
      curl -s -o /dev/null -m 3 "$API_URL$RUTA"; curl -s -o /dev/null -m 3 "$API_URL$CONTROL"; sleep 0.2
    done ) &
  TRAFICO_PID=$!
else
  echo "Aviso: la API no responde en $API_URL; la prueba mide solo la disponibilidad de la base."
fi

estado_api() {  # status HTTP y code del error de la ruta afectada
  [ "$API_OK" = 1 ] || { echo "API no levantada"; return; }
  curl -s -m 5 -w ' HTTP %{http_code}' "$API_URL$RUTA" | python3 -c '
import json, sys
t = sys.stdin.read(); cuerpo, _, http = t.rpartition(" HTTP ")
try: code = json.loads(cuerpo).get("code", "-")
except Exception: code = "-"
print(f"HTTP {http} · code={code}")'
}
esperar_probe() {  # $1 = valor esperado (0/1) · $2 = segundos máx
  local i
  for i in $(seq 1 "$2"); do
    [ "$(prom_query "probe_success{base=\"$BASE\"}" | awk '{print $NF}')" = "$1" ] && return 0; sleep 1
  done; return 1
}
esperar_alerta() {  # $1 = firing | ausente · $2 = segundos máx
  local i v
  for i in $(seq 1 "$2"); do
    v="$(prom_query "ALERTS{alertname=\"BaseNoResponde\",base=\"$BASE\",alertstate=\"firing\"}")"
    if [ "$1" = firing ] && [ -n "$v" ]; then return 0; fi
    if [ "$1" = ausente ] && [ -z "$v" ]; then return 0; fi
    sleep 1
  done; return 1
}

echo "== ANTES ($BASE arriba, 30 s de tráfico)"
T0=$(date +%s); A_INICIO="$(ahora_utc)"; API_ANTES="$(estado_api)"; echo "   API $RUTA → $API_ANTES"
sleep 30

echo "== FALLA: docker stop $CONT"
T_STOP=$(date +%s); A_STOP="$(ahora_utc)"; docker stop "$CONT" >/dev/null
sleep 2; API_DURANTE="$(estado_api)"; echo "   API $RUTA → $API_DURANTE"
esperar_probe 0 60 && { T_DET=$(date +%s); A_DET="$(ahora_utc)"; } || { T_DET=""; A_DET="no detectada en 60 s"; }
echo "   Prometheus ve la caída: $A_DET"
esperar_alerta firing 150 && { T_ALE=$(date +%s); A_ALE="$(ahora_utc)"; } || { T_ALE=""; A_ALE="no disparó en 150 s"; }
echo "   Alerta BaseNoResponde firing: $A_ALE"

echo "== RECUPERACIÓN: docker start $CONT"
T_START=$(date +%s); A_START="$(ahora_utc)"; docker start "$CONT" >/dev/null
esperar_probe 1 240 && { T_REC=$(date +%s); A_REC="$(ahora_utc)"; } || { T_REC=""; A_REC="no volvió en 240 s"; }
echo "   Prometheus la ve arriba: $A_REC"
esperar_alerta ausente 60 || true; A_RES="$(ahora_utc)"
sleep 20; API_DESPUES="$(estado_api)"; echo "   API $RUTA → $API_DESPUES"
T_FIN=$(date +%s); A_FIN="$(ahora_utc)"
terminar; TRAFICO_PID=""

seg() { [ -n "$2" ] && echo "$(( $2 - $1 )) s" || echo "-"; }
serie() {  # tabla de una consulta en el intervalo de la prueba, paso 15 s
  curl -fsS -G "$PROM_URL/api/v1/query_range" --data-urlencode "query=$1" \
    --data-urlencode "start=$T0" --data-urlencode "end=$T_FIN" --data-urlencode "step=15" | python3 -c '
import json, sys, datetime
res = json.load(sys.stdin)["data"]["result"]
if not res: print("_sin datos (la API no estaba levantada o no hubo tráfico)_"); sys.exit()
print("| hora (UTC) | " + " | ".join(" ".join(f"{k}={v}" for k, v in r["metric"].items() if k not in ("__name__", "job", "instance")) or "valor" for r in res) + " |")
print("|---" * (len(res) + 1) + "|")
filas = {}
for i, r in enumerate(res):
    for ts, v in r["values"]: filas.setdefault(ts, [""] * len(res))[i] = f"{float(v):.3g}"
for ts in sorted(filas): print(f"| {datetime.datetime.utcfromtimestamp(ts):%H:%M:%S} | " + " | ".join(filas[ts]) + " |")'
}

mkdir -p "$EVID"
INF="$EVID/prueba_de_falla_${BASE}_$(sello).md"
{
  echo "# Prueba de falla controlada — $BASE"
  echo
  echo "Ejecutada con \`scripts/ejecutar_prueba_controlada.sh $BASE\` · commit \`$(git -C "$H13_DIR" rev-parse --short HEAD 2>/dev/null || echo -)\` · contenedor \`$CONT\` (laboratorio). Falla inducida con \`docker stop\`; recuperación con \`docker start\`. No se borró ningún volumen."
  echo
  echo "## Línea de tiempo"
  echo
  echo "| momento | hora (UTC) | desde la falla |"
  echo "|---|---|---|"
  echo "| inicio (tráfico de lectura a \`$RUTA\` y \`$CONTROL\`) | $A_INICIO | - |"
  echo "| \`docker stop $CONT\` | $A_STOP | 0 s |"
  echo "| Prometheus ve \`probe_success{base=\"$BASE\"} = 0\` | $A_DET | $(seg "$T_STOP" "$T_DET") |"
  echo "| alerta \`BaseNoResponde\` en firing (for: 1m) | $A_ALE | $(seg "$T_STOP" "$T_ALE") |"
  echo "| \`docker start $CONT\` | $A_START | $(seg "$T_STOP" "$T_START") |"
  echo "| Prometheus ve \`probe_success = 1\` | $A_REC | $(seg "$T_STOP" "$T_REC") |"
  echo "| alerta resuelta | $A_RES | - |"
  echo
  echo "## Respuesta de la API en \`$RUTA\`"
  echo
  echo "| antes | durante | después |"
  echo "|---|---|---|"
  echo "| $API_ANTES | $API_DURANTE | $API_DESPUES |"
  echo
  echo "## Series de Prometheus en el intervalo (paso 15 s)"
  echo
  echo "### Disponibilidad — \`probe_success{base=\"$BASE\"}\` (1 = responde)"
  echo; serie "probe_success{base=\"$BASE\"}"; echo
  echo "### Llamadas de la API a $BASE por resultado — \`sum by (resultado) (rate(fixture2030_dependencia_duration_seconds_count{dependencia=\"$BASE\"}[1m]))\` (llamadas/s)"
  echo; serie "sum by (resultado) (rate(fixture2030_dependencia_duration_seconds_count{dependencia=\"$BASE\"}[1m]))"; echo
  echo "### Respuestas de la API por status — \`sum by (status) (rate(fixture2030_http_requests_total[1m]))\` (req/s)"
  echo; serie 'sum by (status) (rate(fixture2030_http_requests_total[1m]))'; echo
  echo "## Ver en Grafana"
  echo
  echo "$GRAFANA_URL/d/fixture2030-monitoreo?from=${T0}000&to=${T_FIN}000"
} > "$INF"
echo
echo "Informe: ${INF#$REPO_DIR/}"
