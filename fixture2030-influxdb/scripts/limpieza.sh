#!/bin/sh
# ============================================================================
#  Fixture 2030 — Hito 8 · Series temporales (InfluxDB 2)
#  ARCHIVO: scripts/limpieza.sh   (OPCIONAL, RNF9)
#  USO:
#      sh scripts/limpieza.sh archivos   # borra los .lp.gz generados (data/lp)
#      sh scripts/limpieza.sh buckets    # borra los 3 buckets (pide confirmación)
#      sh scripts/limpieza.sh todo       # apaga el servidor y borra datos y autorización local
#  La evidencia de docs/evidencia/ NO se borra nunca.
# ============================================================================
set -eu
cd "$(dirname "$0")/.."
BASE_DIR="${INFLUX_DATA_DIR:-$HOME/docker/data/influxdb}"

case "${1:-}" in
  archivos)
    rm -rf data/lp && echo "data/lp borrado (se regenera con generacion_puntos.py)" ;;
  buckets)
    printf "¿Borrar fixture2030_vivo, fixture2030_historico y fixture2030_prueba_retencion? (si/no) "
    read -r r; [ "$r" = "si" ] || { echo "cancelado"; exit 0; }
    TOKEN=$(sed -n 's/.*"token"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' secrets/admin-token.json)
    for b in fixture2030_vivo fixture2030_historico fixture2030_prueba_retencion; do
      docker compose exec -T -e INFLUX_TOKEN="$TOKEN" -e INFLUX_ORG=fixture2030 influxdb \
        influx bucket delete --name "$b" || true
    done
    echo "Buckets borrados. Para recrearlos: sh scripts/inicializacion.sh" ;;
  todo)
    printf "Esto apaga el servidor y BORRA %s y secrets/admin-token.json. ¿Seguir? (si/no) " "$BASE_DIR"
    read -r r; [ "$r" = "si" ] || { echo "cancelado"; exit 0; }
    docker compose down
    docker volume rm fixture2030_influxdb_data fixture2030_influxdb_config 2>/dev/null || true
    rm -rf "$BASE_DIR" secrets/admin-token.json data/lp
    echo "Ambiente borrado. Para empezar de cero: sh scripts/inicializacion.sh" ;;
  *)
    echo "Uso: sh scripts/limpieza.sh [archivos|buckets|todo]"; exit 1 ;;
esac
