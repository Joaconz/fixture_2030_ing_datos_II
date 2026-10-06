#!/usr/bin/env bash
# ============================================================================
#  Fixture 2030 — Hito 9 · InterSystems IRIS
#  ARCHIVO: scripts/exportar_desde_mongo.sh
#  PROPÓSITO: generar data/jugadores.csv desde el módulo del Hito 4 (MongoDB),
#  para que IRIS use los mismos jugadores (mismo dni, dorsal y equipo).
#  El CSV ya está en el repositorio: sólo hace falta correr esto si cambian los
#  datos del Hito 4. Requiere el MongoDB del Hito 4 levantado y cargado.
#  USO:  bash scripts/exportar_desde_mongo.sh
#  Variable opcional: MONGO_CONTAINER (por defecto fixture2030_mongo)
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."
MONGO_CONTAINER="${MONGO_CONTAINER:-fixture2030_mongo}"

docker exec "$MONGO_CONTAINER" mongosh --quiet fixture2030 --eval '
print("dni,nombre,apellido,posicion,dorsal,equipo");
db.jugadores.find({dni: {$regex: "^300[0-9]{5}$"}}).sort({dni: 1})
  .forEach(j => print([j.dni, j.nombre, j.apellido, j.posicion, j.dorsal, j.equipoId].join(",")))' \
  | tr -d '\r' > data/jugadores.csv

echo "jugadores exportados: $(($(wc -l < data/jugadores.csv) - 1))"
