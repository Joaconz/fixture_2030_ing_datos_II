#!/usr/bin/env bash
# Fixture 2030 — Hito 12 · limpieza segura (solo lo escrito por las corridas). Ver limpiar_datos_de_prueba.py
. "$(dirname "$0")/_comun.sh"
read -r -p "¿Borrar los comentarios escritos por las corridas de prueba (no toca los datos del Hito 6)? (si/no) " r
[ "$r" = "si" ] || { echo "cancelado"; exit 0; }
"$PY_API" "$H12_DIR/scripts/limpiar_datos_de_prueba.py"
