#!/usr/bin/env bash
# Fixture 2030 — Hito 12 · LÍNEA BASE (RF4): API del Hito 10 sin optimizar (caché de Q0 desactivada).
. "$(dirname "$0")/_comun.sh"
bash "$H12_DIR/scripts/ejecutar_carga.sh" linea_base 0
