#!/bin/sh
# ============================================================================
#  Fixture 2030 — Hito 8 · Series temporales (InfluxDB 2)
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
FLUX='from(bucket: "fixture2030_vivo")
  |> range(start: 2030-06-09T12:45:00Z, stop: 2030-06-09T15:10:00Z)
  |> filter(fn: (r) => r._measurement == "estadisticas_equipo" and r.partido_id == "PAR-A-1" and r._field == "posesion_pct")
  |> group() |> count()'
contar() { docker compose exec -T -e INFLUX_TOKEN="$TOKEN" -e INFLUX_ORG=fixture2030 influxdb influx query "$FLUX"; }
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
  echo; echo "## docker compose up -d"; docker compose up -d influxdb 2>&1; esperar
  echo; echo "## Después del reinicio (mismo conteo, misma autorización)"; contar
  echo; echo "## Volúmenes"
  docker volume inspect fixture2030_influxdb_data fixture2030_influxdb_config -f '{{.Name}} -> {{.Options.device}}'
} > "$EVID" 2>&1
cat "$EVID"
