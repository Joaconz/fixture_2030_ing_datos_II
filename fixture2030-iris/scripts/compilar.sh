#!/usr/bin/env bash
# ============================================================================
#  Fixture 2030 — Hito 9 · IRIS
#  ARCHIVO: scripts/compilar.sh
#  PROPÓSITO: cargar y compilar las clases de src/ en el namespace USER (RNF2, RNF4).
#  USO (con el servidor levantado):   bash scripts/compilar.sh
#  Sale con código 1 si alguna clase no compila.
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/_iris.sh

salida=$(iris_ejecutar   'set sc = $SYSTEM.OBJ.LoadDir("/home/irisowner/fixture/src", "ck", .errores, 1)'   'write !,"Clases cargadas y compiladas: ",$select($SYSTEM.Status.IsOK(sc): "OK", 1: "CON ERRORES"),!'   'if $SYSTEM.Status.IsError(sc) do $SYSTEM.Status.DisplayError(sc)')
echo "$salida"
echo "$salida" | grep -q "compiladas: OK" || exit 1
