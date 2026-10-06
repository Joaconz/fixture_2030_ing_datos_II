#!/usr/bin/env bash
# Funciones comunes: ejecutar ObjectScript en la terminal de IRIS del contenedor.
# Las líneas se pasan por la entrada estándar de `iris session` (namespace USER)
# y se filtran los prompts para que la salida quede limpia.
export MSYS_NO_PATHCONV=1   # Git Bash en Windows: no reescribir rutas del contenedor

iris_ejecutar() {
  # SetIO("UTF8"): la terminal escribe en UTF-8 (acentos, ✔/✖) y no en Latin-1
  { printf '%s\n' 'do ##class(%SYS.NLS.Device).SetIO("UTF8")' "$@"; printf 'halt\n'; } \
    | docker compose exec -T iris iris session IRIS -U USER 2>&1 \
    | tr -d '\r' \
    | sed -e '/^Node: .*Instance: IRIS$/d' -e 's/^USER>//' -e '/^$/d'
}

# Encabezado común de los archivos de evidencia: fecha y versión observada.
encabezado_evidencia() {
  echo "# $1"
  echo "# Fecha (UTC): $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "# Imagen intersystems/iris-community:latest-cd → $(iris_ejecutar 'write $ZVERSION,!' | tail -1)"
  echo
}
