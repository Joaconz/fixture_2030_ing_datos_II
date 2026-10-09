#!/bin/sh
# ============================================================================
#  Fixture 2030 — Hito 8 · Series temporales (InfluxDB 3 Core)
#  ARCHIVO: scripts/prueba_persistencia.sh
#  PROPÓSITO: demostrar RNF2 y §5.1 ("detener o reiniciar el ambiente sin perder
#  datos"): cuenta puntos, hace `docker compose down` + `up -d`, y vuelve a contar.
#  USO (con la muestra ya cargada):   sh scripts/prueba_persistencia.sh
#  SALIDA: docs/evidencia/02_persistencia.txt
# ============================================================================
set -eu
cd "$(dirname "$0")/.."
EVID="docs/evidencia/02_persistencia.txt"
TOKEN=$(sed -n 's/.*"token"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' secrets/admin-token.json)
SQL="SELECT count(*) AS puntos FROM estadisticas_equipo
WHERE partido_id = 'PAR-A-1' AND time >= '2030-06-09T12:45:00Z' AND time < '2030-06-09T15:10:00Z'"
contar() {
  docker compose exec -T -e INFLUXDB3_AUTH_TOKEN="$TOKEN" influxdb \
    influxdb3 query --database fixture2030_vivo "$SQL"
}
esperar() {
  i=0
  until [ "$(docker inspect -f '{{.State.Health.Status}}' fixture2030-influxdb 2>/dev/null)" = "healthy" ]; do
    i=$((i + 1)); [ $i -gt 60 ] && { echo "✖ no volvió a arrancar"; exit 1; }; sleep 2
  done
}
{
  echo "# Prueba de persistencia — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo; echo "## Antes (esperado: 11400 puntos de PAR-A-1)"; contar
  echo; echo "## docker compose down"; docker compose down 2>&1
  echo; echo "## docker compose up -d"; t0=$(date +%s); docker compose up -d influxdb 2>&1; esperar
  echo "   healthy en $(( $(date +%s) - t0 )) s (incluye volver a leer el WAL del disco)"
  echo; echo "## Después del reinicio (mismo conteo, mismo token)"; contar
  echo; echo "## Volumen"
  docker volume inspect fixture2030_influxdb_data -f '{{.Name}} -> {{.Options.device}}' | sed -E 's%-> .*(/docker/data/influxdb)%-> ~\1%'
  echo; echo "## Contenido de la carpeta del host (catálogo, WAL y Parquet del nodo)"
  ls "${INFLUX_DATA_DIR:-$HOME/docker/data/influxdb}" 2>&1
  ls "${INFLUX_DATA_DIR:-$HOME/docker/data/influxdb}"/fixture2030-local 2>&1
} > "$EVID" 2>&1
cat "$EVID"
