#!/usr/bin/env bash
# Fixture 2030 — Hito 12 · PRUEBA OPTIMIZADA (RF9): mismo escenario, caché de Q0 activada.
. "$(dirname "$0")/_comun.sh"
bash "$H12_DIR/scripts/ejecutar_carga.sh" optimizada "$CACHE_Q0_OPTIMIZADA_S"
"$PY_API" "$H12_DIR/scripts/comparar.py" "$EVID/resultados_linea_base" "$EVID/resultados_optimizada" \
  > "$EVID/comparacion.md" && cat "$EVID/comparacion.md"
