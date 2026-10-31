#!/usr/bin/env bash
# ============================================================================
#  Fixture 2030 — Hito 13 · carga observada con Prometheus (RF11, RF12).
#  USO: bash scripts/ejecutar_carga_observada.sh      (API y Cassandra levantadas)
#
#  Corre k6 (solo GET, ver carga_lectura_k6.js) contra la API y, al final del
#  sostenimiento, lee de Prometheus la latencia de la API y la de Cassandra
#  vista desde la API y desde el propio Cassandra. Responde con datos la
#  pregunta "¿el cuello está en la API o en la base?" que el Hito 12 dejó
#  como hipótesis (H2). La CPU de la API se muestrea con `ps` (en macOS
#  prometheus-client no expone métricas del proceso) y la de Cassandra con
#  `docker stats`. Deja el informe en evidencia/carga_observada_<fecha>.md.
# ============================================================================
. "$(dirname "$0")/_comun.sh"

VUS="${VUS:-20}"; RAMPA_S="${RAMPA_S:-20}"; SOSTEN_S="${SOSTEN_S:-90}"
K6_IMAGEN="${K6_IMAGEN:-grafana/k6:2.3.0}"
RUTA_PLANTILLA="/partidos/{partido_id}/comentarios"

curl -fsS -m 3 "$PROM_URL/-/ready" >/dev/null 2>&1 || falla "Prometheus no responde: correr scripts/iniciar_monitoreo.sh"
curl -fsS -m 3 "$API_URL/health" >/dev/null 2>&1 || falla "La API no responde en $API_URL"
API_PID="$(lsof -ti tcp:"${API_URL##*:}" -sTCP:LISTEN 2>/dev/null | head -1)"
[ -n "$API_PID" ] || falla "No encuentro el proceso de la API"

SAL="$(mktemp -d)"
trap 'kill $(jobs -p) 2>/dev/null || true; rm -rf "$SAL"' EXIT

echo "== Carga: $VUS usuarios, rampa ${RAMPA_S}s, sostenimiento ${SOSTEN_S}s (solo GET)"
T0=$(date +%s); A0="$(ahora_utc)"
( while true; do
    printf '%s %s\n' "$(date +%s)" "$(ps -o %cpu= -p "$API_PID" 2>/dev/null | tr -d ' ')" >> "$SAL/cpu_api"
    docker stats --no-stream --format '{{.CPUPerc}}' fixture2030-cassandra 2>/dev/null | tr -d '%' | sed "s/^/$(date +%s) /" >> "$SAL/cpu_cas"
    sleep 2
  done ) &
docker run --rm -e VUS="$VUS" -e RAMPA_S="$RAMPA_S" -e SOSTEN_S="$SOSTEN_S" \
  -v "$H13_DIR/scripts:/scripts:ro" "$K6_IMAGEN" run --quiet /scripts/carga_lectura_k6.js > "$SAL/k6.txt" 2>&1 || true
T_FIN_SOSTEN=$(( T0 + RAMPA_S + SOSTEN_S )); T1=$(date +%s); A1="$(ahora_utc)"
kill %1 2>/dev/null || true

# Ventana de análisis: el sostenimiento (sin rampa). Se evalúa en su último instante.
VENT="${SOSTEN_S}s"
q() { curl -fsS -G "$PROM_URL/api/v1/query" --data-urlencode "query=$1" --data-urlencode "time=$T_FIN_SOSTEN" \
      | python3 -c 'import json,sys; r=json.load(sys.stdin)["data"]["result"]; print(r[0]["value"][1] if r else "nan")'; }
ms() { python3 -c "import sys; v=float(sys.argv[1]); print('-' if v!=v else f'{v*1000:.1f} ms')" "$1"; }
prom_cpu() { python3 -c "
import sys
t0, t1 = int(sys.argv[2]), int(sys.argv[3]); v = []
for l in open(sys.argv[1]):
    p = l.split()
    if len(p) == 2 and t0 <= int(p[0]) <= t1:
        try: v.append(float(p[1]))
        except ValueError: pass
print(f'{sum(v)/len(v):.0f} % prom / {max(v):.0f} % máx ({len(v)} muestras)' if v else '-')" "$1" $(( T0 + RAMPA_S )) "$T_FIN_SOSTEN"; }

RPS=$(q "sum(rate(fixture2030_http_requests_total{ruta=\"$RUTA_PLANTILLA\",status=\"200\"}[$VENT]))")
ERR=$(q "sum(rate(fixture2030_http_requests_total{ruta=\"$RUTA_PLANTILLA\",status!=\"200\"}[$VENT])) or vector(0)")
API50=$(q "histogram_quantile(0.50, sum by (le) (rate(fixture2030_http_request_duration_seconds_bucket{ruta=\"$RUTA_PLANTILLA\"}[$VENT])))")
API95=$(q "histogram_quantile(0.95, sum by (le) (rate(fixture2030_http_request_duration_seconds_bucket{ruta=\"$RUTA_PLANTILLA\"}[$VENT])))")
DEP50=$(q "histogram_quantile(0.50, sum by (le) (rate(fixture2030_dependencia_duration_seconds_bucket{dependencia=\"cassandra\"}[$VENT])))")
DEP95=$(q "histogram_quantile(0.95, sum by (le) (rate(fixture2030_dependencia_duration_seconds_bucket{dependencia=\"cassandra\"}[$VENT])))")
DEPRPS=$(q "sum(rate(fixture2030_dependencia_duration_seconds_count{dependencia=\"cassandra\"}[$VENT]))")
CAS99=$(q 'cassandra_clientrequest_latency_seconds{operacion="Read",quantile="0.99"}')
CASRPS=$(q 'rate(cassandra_clientrequest_total{operacion="Read"}['"$VENT"'])')

mkdir -p "$EVID"
INF="$EVID/carga_observada_$(sello).md"
{
  echo "# Carga de lectura observada con Prometheus — $(ahora_utc)"
  echo
  echo "\`scripts/ejecutar_carga_observada.sh\` · commit \`$(git -C "$H13_DIR" rev-parse --short HEAD 2>/dev/null || echo -)\` · k6 \`$K6_IMAGEN\`, $VUS usuarios en lazo cerrado, rampa ${RAMPA_S}s + sostenimiento ${SOSTEN_S}s, solo \`GET /partidos/PAR-D16-01/comentarios?limit=50\` (no escribe). Inicio $A0, fin $A1. Métricas evaluadas sobre la ventana del sostenimiento (\`[$VENT]\`)."
  echo
  echo "| Medición | Valor | Fuente |"
  echo "|---|---|---|"
  echo "| Throughput (200/s) | $(printf '%.1f' "$RPS") req/s | API · \`fixture2030_http_requests_total\` |"
  echo "| Respuestas no 200 | $(printf '%.2f' "$ERR") req/s | idem |"
  echo "| **Latencia de la API** p50 / p95 | **$(ms "$API50") / $(ms "$API95")** | API · \`fixture2030_http_request_duration_seconds\` |"
  echo "| **Cassandra vista desde la API** p50 / p95 | **$(ms "$DEP50") / $(ms "$DEP95")** | adaptador · \`fixture2030_dependencia_duration_seconds\` |"
  echo "| Llamadas de la API a Cassandra | $(printf '%.1f' "$DEPRPS") llamadas/s | idem |"
  echo "| Cassandra por dentro: lectura p99 | $(ms "$CAS99") | agente JMX · \`cassandra_clientrequest_latency_seconds\` |"
  echo "| Lecturas que recibió Cassandra | $(printf '%.1f' "$CASRPS") req/s | agente JMX · \`cassandra_clientrequest_total\` |"
  echo "| CPU del proceso de la API | $(prom_cpu "$SAL/cpu_api") | \`ps\` cada 2 s (100 % = un núcleo) |"
  echo "| CPU del contenedor de Cassandra | $(prom_cpu "$SAL/cpu_cas") | \`docker stats\` cada 2 s |"
  echo
  echo "## Resumen de k6"
  echo
  echo '```'
  grep -E "checks|http_req_duration|http_reqs|http_req_failed" "$SAL/k6.txt" | sed 's/^ *//'
  echo '```'
  echo
  echo "Ver en Grafana: $GRAFANA_URL/d/fixture2030-monitoreo?from=${T0}000&to=${T1}000"
} > "$INF"
cat "$INF"
echo; echo "Informe: ${INF#$REPO_DIR/}"
