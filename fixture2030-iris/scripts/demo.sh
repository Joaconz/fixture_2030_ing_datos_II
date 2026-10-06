#!/usr/bin/env bash
# ============================================================================
#  Fixture 2030 — Hito 9 · InterSystems IRIS
#  ARCHIVO: scripts/demo.sh
#  PROPÓSITO: la demostración de la §5.3 (y RF7, RF8, RF9) desde la terminal de IRIS.
#  Equivale a:  do ##class(Fixture.Demo).Todo()
#  USO:  bash scripts/demo.sh          SALIDA: docs/evidencia/03_demo.txt
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/_iris.sh
{
  encabezado_evidencia "Demostración (Fixture.Demo.Todo)"
  iris_ejecutar 'do ##class(Fixture.Demo).Todo()'
} | tee docs/evidencia/03_demo.txt
