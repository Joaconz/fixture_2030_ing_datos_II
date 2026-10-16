#!/usr/bin/env bash
# ============================================================
#  Fixture 2030 — Hito 10 · API REST integrada
#  ARCHIVO: scripts/prueba_dependencia_caida.sh
#  PROPÓSITO: evidencia de RNF8/RNF9 (§5.12 "dependencia caída"): con una fuente
#  detenida, la API responde 503 con el formato único de error dentro del timeout
#  configurado (DEP_TIMEOUT_S + 1 s de margen) y no se cuelga; al volver la fuente,
#  la API se recupera sola, sin reiniciarse.
#  PASOS:
#    1. fuente ARRIBA: mide código y tiempo de un endpoint de esa fuente;
#    2. `docker stop <contenedor>`: repite (esperado 503 en < DEP_TIMEOUT_S+1 s);
#       para redis además GET /partidos/PAR-A-1 sigue 200 con `X-Cache: BYPASS`
#       (la caché es optimización, no fuente) y /health/dependencias da 503;
#    3. `docker start <contenedor>`: espera healthy y repite (esperado != 503).
#  USO:  bash scripts/prueba_dependencia_caida.sh [redis|mongodb|neo4j|cassandra|influxdb]
#  SEGURIDAD DE DATOS: sólo `docker stop` / `docker start`. Nunca `down -v`, `rm`
#  ni borrado de volúmenes. Si el script se interrumpe, un trap vuelve a arrancar
#  el contenedor detenido.
#  SALIDA: consola + docs/evidencia/dependencia_caida_<fuente>_<fecha>.md
#  Exit code 1 si alguna expectativa no se cumple.
# ============================================================
set -uo pipefail
source "$(dirname "$0")/_comun.sh"

FUENTE="${1:-redis}"
case "$FUENTE" in
  mongodb)   RUTA="/equipos/ARG" ;;
  neo4j)     RUTA="/partidos/PAR-A-1/eventos?limit=5" ;;
  cassandra) RUTA="/partidos/PAR-A-1/comentarios?limit=5" ;;
  redis)     RUTA="/sesiones/demo-ses-0000001-1" ;;
  influxdb)  RUTA="/partidos/PAR-A-1/estadisticas?desde=2030-06-09T13:00:00Z&hasta=2030-06-09T13:30:00Z&agregacion=1m" ;;
  *) echo "Fuente desconocida: $FUENTE (redis|mongodb|neo4j|cassandra|influxdb)" >&2; exit 2 ;;
esac
CONTENEDOR="$(contenedor_de "$FUENTE")"
TIMEOUT_S="${DEP_TIMEOUT_S:-2.0}"
LIMITE_S="$(awk -v t="$TIMEOUT_S" 'BEGIN { printf "%.1f", t + 1 }')"

EVID="$API_DIR/docs/evidencia"; mkdir -p "$EVID"
SALIDA="$EVID/dependencia_caida_${FUENTE}_$(sello_fecha).md"
TMP="$(mktemp -d)"
DETENIDO=0
FALLAS=0

restaurar() {
  if [ "$DETENIDO" -eq 1 ]; then
    echo "(trap) docker start $CONTENEDOR" >&2
    docker start "$CONTENEDOR" >/dev/null 2>&1 || true
  fi
  rm -rf "$TMP"
}
trap restaurar EXIT INT TERM

log() { printf '%s\n' "$*" | tee -a "$SALIDA"; }

# pedir ETIQUETA RUTA → deja COD, SEG, CACHE y el cuerpo en $TMP/cuerpo
pedir() {
  local rid="caida-${FUENTE}-$1"
  local salida
  salida="$(curl -s -o "$TMP/cuerpo" -D "$TMP/cab" -m 30 -H "X-Request-Id: $rid" \
            -w '%{http_code} %{time_total}' "$API_URL$2" 2>/dev/null || echo "000 0")"
  COD="${salida%% *}"; SEG="${salida##* }"
  CACHE="$(grep -i '^x-cache:' "$TMP/cab" 2>/dev/null | tr -d '\r' | awk '{print $2}')"
  log "| $1 | \`GET $2\` | $COD | $SEG | ${CACHE:--} | $rid | $(head -c 160 "$TMP/cuerpo" | tr '\n|' '  ') |"
}

menor_que() { awk -v a="$1" -v b="$2" 'BEGIN { exit !(a < b) }'; }
esperar_estado() {   # esperar_estado → 0 cuando el contenedor está healthy (o running si no tiene healthcheck)
  local i est
  for i in $(seq 1 90); do
    est="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$CONTENEDOR" 2>/dev/null)"
    case "$est" in healthy|running) return 0 ;; esac
    sleep 2
  done
  return 1
}
verificar() { if eval "$1"; then log "- OK: $2"; else log "- **FALLA**: $2"; FALLAS=$((FALLAS + 1)); fi; }

[ "$(curl -s -o /dev/null -m 3 -w '%{http_code}' "$API_URL/health" || true)" = "200" ] || {
  echo "La API no responde en $API_URL (bash scripts/iniciar_api.sh)" >&2; exit 1; }
contenedor_corriendo "$CONTENEDOR" || { echo "El contenedor $CONTENEDOR no está corriendo." >&2; exit 1; }

: > "$SALIDA"
log "# Prueba de dependencia caída — $FUENTE"
log ""
log "- Fecha (UTC): $(date -u +%Y-%m-%dT%H:%M:%SZ)"
log "- Máquina: $(uname -srm)"
log "- API: $API_URL · DEP_TIMEOUT_S = $TIMEOUT_S s · límite aceptado = $LIMITE_S s"
log "- Contenedor: $CONTENEDOR (sólo docker stop / docker start)"
log ""
log "| Fase | Request | HTTP | Tiempo (s) | X-Cache | X-Request-Id | Cuerpo (recortado) |"
log "|---|---|---:|---:|---|---|---|"

# 1) fuente arriba
pedir "1-arriba" "$RUTA"; COD1="$COD"
[ "$FUENTE" = "redis" ] && pedir "1-arriba-detalle" "/partidos/PAR-A-1"

# 2) fuente detenida
docker stop "$CONTENEDOR" >/dev/null && DETENIDO=1
sleep 1
pedir "2-caida" "$RUTA"; COD2="$COD"; SEG2="$SEG"
CUERPO2="$(cat "$TMP/cuerpo")"
pedir "2-caida-repite" "$RUTA"; SEG2B="$SEG"
if [ "$FUENTE" = "redis" ]; then
  pedir "2-caida-detalle" "/partidos/PAR-A-1"; CODD="$COD"; CACHED="$CACHE"
fi
pedir "2-caida-salud" "/health/dependencias"; CODS="$COD"

# 3) fuente de vuelta
docker start "$CONTENEDOR" >/dev/null && DETENIDO=0
esperar_estado || log "- **FALLA**: el contenedor no quedó healthy en 180 s"
for _ in $(seq 1 30); do   # el driver reconecta solo: hasta 60 s
  [ "$(curl -s -o /dev/null -m 10 -w '%{http_code}' "$API_URL$RUTA" || true)" != "503" ] && break
  sleep 2
done
pedir "3-recuperada" "$RUTA"; COD3="$COD"

log ""
log "## Verificaciones"
log ""
verificar '[ "$COD1" != "503" ] && [ "$COD1" != "000" ]' "con la fuente arriba el endpoint no da 503 (dio $COD1)"
verificar '[ "$COD2" = "503" ]' "con la fuente detenida el endpoint da 503 (dio $COD2)"
verificar 'printf "%s" "$CUERPO2" | grep -q "\"code\":\"DEPENDENCY_UNAVAILABLE\""' "el 503 usa el formato único con code DEPENDENCY_UNAVAILABLE"
verificar 'menor_que "$SEG2" "$LIMITE_S" && menor_que "$SEG2B" "$LIMITE_S"' "el 503 llega en menos de $LIMITE_S s ($SEG2 s y $SEG2B s)"
verificar '[ "$CODS" = "503" ]' "/health/dependencias da 503 con la fuente DOWN (dio $CODS)"
if [ "$FUENTE" = "redis" ]; then
  verificar '[ "$CODD" = "200" ] && [ "$CACHED" = "BYPASS" ]' "/partidos/PAR-A-1 sigue 200 con X-Cache: BYPASS (dio $CODD, ${CACHED:--})"
fi
verificar '[ "$COD3" != "503" ] && [ "$COD3" != "000" ]' "al volver la fuente la API se recupera sin reiniciarse (dio $COD3)"
log ""
log "Resultado: $([ "$FALLAS" -eq 0 ] && echo 'todas las verificaciones OK' || echo "$FALLAS falla(s)")"
echo "Evidencia: $SALIDA"
[ "$FALLAS" -eq 0 ]
