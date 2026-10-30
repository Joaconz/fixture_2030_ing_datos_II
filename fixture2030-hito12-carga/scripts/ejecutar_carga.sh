#!/usr/bin/env bash
# ============================================================================
#  Fixture 2030 — Hito 12 · ejecutar UNA corrida del escenario (RF2, RF4–RF6, RF9)
#  USO:  bash scripts/ejecutar_carga.sh <etiqueta> <cache_q0_segundos>
#        (lo llaman ejecutar_linea_base.sh y ejecutar_prueba_optimizada.sh)
#
#  Para que las dos corridas sean COMPARABLES (RNF3), este script controla todo:
#  levanta la API con la configuración indicada, mide, valida y la apaga.
#    1. registra ambiente, versiones y configuración (RNF2)
#    2. levanta la API (COMENTARIOS_CONFIG_CACHE_S = 0 o N)
#    3. calentamiento: 20 GET sin medir
#    4. muestrea CPU/memoria de Cassandra, de la API y del generador (k6) cada 2 s (RF6)
#    5. corre k6 en Docker (grafana/k6) contra la API
#    6. lecturas de la tabla de configuración antes/después (prueba de la hipótesis)
#    7. valida la integridad de lo escrito (RF15)
#    8. apaga la API
# ============================================================================
. "$(dirname "$0")/_comun.sh"
ETIQUETA="${1:?etiqueta: linea_base u optimizada}"
CACHE_S="${2:?segundos de caché de Q0}"
CORRIDA=$(date -u +%d%H%M)                     # día+hora+minuto UTC: identifica usuarios USR-LT<CORRIDA><VU>
SALIDA="$EVID/resultados_${ETIQUETA}"
# No se borra evidencia (RNF11): una corrida anterior con la misma etiqueta se archiva en
# docs/evidencia/anteriores/ (ignorado por git), así su corrida.txt sigue disponible para la limpieza.
if [ -d "$SALIDA" ]; then
  ANTERIOR="$EVID/anteriores/${ETIQUETA}_$(sed -n 's/^corrida=//p' "$SALIDA/corrida.txt" 2>/dev/null || echo sin_id)_$(date -u +%Y%m%dT%H%M%S)"
  mkdir -p "$EVID/anteriores" && mv "$SALIDA" "$ANTERIOR" && echo "   corrida anterior archivada en $ANTERIOR"
fi
mkdir -p "$SALIDA"
printf 'corrida=%s\nvus=%s\n' "$CORRIDA" "$VUS" > "$SALIDA/corrida.txt"
[ -x "$PY_API" ] || falla "Falta el entorno de la API ($PY_API). Corré antes: bash scripts/preparar_datos.sh"

echo "== 1. Ambiente -> $SALIDA/ambiente.md"
{
  echo "# Ambiente — corrida $ETIQUETA"
  echo; echo "| Dato | Valor |"; echo "|---|---|"
  echo "| Fecha (UTC) | $(ahora_utc) |"
  # Commit medido; si la API o los scripts tienen cambios sin commitear, se avisa (el commit no los incluye)
  SUCIO=$(git -C "$REPO_DIR" status --porcelain -- fixture2030-hito10-api/app fixture2030-hito12-carga/scripts fixture2030-hito12-carga/config 2>/dev/null | head -1)
  echo "| Commit | $(git -C "$REPO_DIR" rev-parse --short HEAD 2>/dev/null || echo 'copia sin git (ZIP)')${SUCIO:+ · ⚠️ con cambios sin commitear} |"
  echo "| Corrida / usuarios de prueba | $CORRIDA / USR-LT${CORRIDA}001 … USR-LT${CORRIDA}$(printf %03d "$VUS") |"
  echo "| Escenario | $VUS VUs · rampa ${RAMPA_S}s · sostenimiento ${SOSTEN_S}s · bajada 10s · 80 % GET / 20 % POST |"
  echo "| API | FastAPI del Hito 10, 1 proceso uvicorn · COMENTARIOS_CONFIG_CACHE_S=$CACHE_S · DEP_TIMEOUT_S por defecto |"
  echo "| Cassandra | $(cql 'SHOW VERSION' 2>/dev/null | tr -d '[]' | head -1) |"
  echo "| Generador | $(docker run --rm "$K6_IMAGEN" version 2>/dev/null | head -1) (Docker) |"
  echo "| Docker | $(docker info --format 'CPUs {{.NCPU}} · memoria {{.MemTotal}} bytes · {{.OperatingSystem}}') |"
  echo "| Sistema | $(uname -sm) |"
} > "$SALIDA/ambiente.md"
cat "$SALIDA/ambiente.md"

echo "== 2. API con caché de Q0 = ${CACHE_S}s"
iniciar_api "$CACHE_S" "$SALIDA/api.log"
trap 'detener_api; [ -n "${MUESTREO_PID:-}" ] && kill $MUESTREO_PID 2>/dev/null || true' EXIT

echo "== 3. Calentamiento (20 GET, no se miden)"
for _ in $(seq 1 20); do curl -fsS -o /dev/null "$API_URL_LOCAL/partidos/PAR-D16-01/comentarios?limit=50" || true; done

echo "== 4-5. Carga (k6) + muestreo de recursos"
Q0_ANTES=$(lecturas_q0)
muestrear_recursos "$SALIDA/recursos.csv" & MUESTREO_PID=$!
docker rm -f "$CONTENEDOR_K6" >/dev/null 2>&1 || true
docker run --rm --name "$CONTENEDOR_K6" -v "$H12_DIR/scripts:/scripts:ro" -v "$SALIDA:/resultados" \
  -e BASE_URL="$K6_BASE_URL" -e CORRIDA="$CORRIDA" -e VUS="$VUS" -e RAMPA_S="$RAMPA_S" \
  -e SOSTEN_S="$SOSTEN_S" -e SALIDA=/resultados \
  "$K6_IMAGEN" run --quiet /scripts/escenario_k6.js | tee "$SALIDA/k6_salida.txt" || echo "(k6 terminó con código distinto de 0: ver umbrales)"
kill $MUESTREO_PID 2>/dev/null || true; MUESTREO_PID=
Q0_DESPUES=$(lecturas_q0)
echo "lecturas_q0_antes=$Q0_ANTES" > "$SALIDA/lecturas_q0.txt"
echo "lecturas_q0_despues=$Q0_DESPUES" >> "$SALIDA/lecturas_q0.txt"
echo "   lecturas de config_particion_partido durante la corrida: $(( ${Q0_DESPUES:-0} - ${Q0_ANTES:-0} ))"

echo "== 7. Integridad"
"$PY_API" "$H12_DIR/scripts/validar_integridad.py" --corrida "$CORRIDA" --vus "$VUS" \
  --resumen "$SALIDA/k6_resumen.json" --salida "$SALIDA/integridad" || true

echo "== 8. API detenida. Resultados en $SALIDA"
