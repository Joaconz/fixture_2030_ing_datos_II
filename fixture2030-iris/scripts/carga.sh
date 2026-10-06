#!/usr/bin/env bash
# ============================================================================
#  Fixture 2030 — Hito 9 · InterSystems IRIS
#  ARCHIVO: scripts/carga.sh
#  PROPÓSITO: ejecutar el script de carga del árbol de objetos (RF6).
#  Equivale a escribir en la terminal de IRIS:  do ##class(Fixture.Carga).Ejecutar()
#  USO:  bash scripts/carga.sh          SALIDA: docs/evidencia/02_carga.txt
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/_iris.sh
{
  encabezado_evidencia "Carga (Fixture.Carga.Ejecutar)"
  iris_ejecutar 'do ##class(Fixture.Carga).Ejecutar()'
} | tee docs/evidencia/02_carga.txt
