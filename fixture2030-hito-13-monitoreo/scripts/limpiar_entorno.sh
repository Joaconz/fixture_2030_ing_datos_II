#!/usr/bin/env bash
# ============================================================================
#  Fixture 2030 — Hito 13 · apaga el stack de monitoreo (RNF11).
#  USO: bash scripts/limpiar_entorno.sh                 apaga los contenedores, CONSERVA
#                                                       las series de Prometheus y Grafana
#       bash scripts/limpiar_entorno.sh --borrar-datos  además borra SOLO los datos del
#                                                       monitoreo (pide confirmación)
#  Nunca toca las bases ni sus volúmenes: cada módulo se apaga desde su carpeta.
# ============================================================================
. "$(dirname "$0")/_comun.sh"

( cd "$H13_DIR" && docker compose down )

if [ "${1:-}" = "--borrar-datos" ]; then
  PD="${PROMETHEUS_DATA_DIR:-$HOME/docker/data/prometheus}"
  GD="${GRAFANA_DATA_DIR:-$HOME/docker/data/grafana}"
  echo "Se borrarán las series de Prometheus y la base interna de Grafana:"
  echo "  volúmenes fixture2030_prometheus_data, fixture2030_grafana_data"
  echo "  carpetas  $PD  $GD"
  echo "Los dashboards y el datasource se vuelven a provisionar solos al levantar."
  read -r -p "¿Confirmar? (si/no) " r
  [ "$r" = "si" ] || { echo "cancelado (los contenedores ya quedaron apagados)"; exit 0; }
  docker volume rm fixture2030_prometheus_data fixture2030_grafana_data >/dev/null 2>&1 || true
  rm -rf "$PD" "$GD"
  echo "Datos del monitoreo borrados."
fi
echo "Monitoreo apagado. Para volver: bash scripts/iniciar_monitoreo.sh"
