#!/usr/bin/env bash
# ============================================================================
#  Fixture 2030 — Hito 9 · Entidades complejas (InterSystems IRIS)
#  ARCHIVO: scripts/inicializacion.sh
#  PROPÓSITO: dejar el ambiente listo de punta a punta, de forma repetible:
#    1. carpeta ~/docker/data/iris (Durable %SYS, RNF1)
#    2. servidor con `docker compose up -d` y espera a "healthy"
#    3. carga y compilación de las clases de src/ (RNF2, RNF4)
#    4. evidencia: versión observada de latest-cd, Durable %SYS, compilación
#  USO (desde la carpeta fixture2030-iris):   bash scripts/inicializacion.sh
#  SALIDA: docs/evidencia/01_inicializacion.txt
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/_iris.sh
DATOS="${IRIS_DATA_DIR:-$HOME/docker/data/iris}"
EVID="docs/evidencia/01_inicializacion.txt"

echo "== 1. Carpeta de datos durable (RNF1): $DATOS"
mkdir -p "$DATOS"

echo "== 2. Servidor: docker compose up -d"
docker compose up -d
printf "   esperando a que esté healthy"
for i in $(seq 1 60); do
  [ "$(docker inspect -f '{{.State.Health.Status}}' fixture2030-iris 2>/dev/null)" = "healthy" ] && break
  [ "$i" = 60 ] && { echo " ✖ no arrancó. Ver: docker compose logs iris"; exit 1; }
  printf "."; sleep 5
done
echo " ok"

echo "== 3. Carga y compilación de las clases"
{
  encabezado_evidencia "Inicialización — Hito 9"
  echo "## Instancia (iris qlist)"
  docker compose exec -T iris iris qlist IRIS | tr -d '\r'
  echo
  echo "## Durable %SYS (RNF1): los datos viven fuera del contenedor"
  docker compose exec -T iris sh -c 'echo "ISC_DATA_DIRECTORY=$ISC_DATA_DIRECTORY"; ls /durable/iris' | tr -d '\r'
  # La ruta del host se muestra como ~ para no publicar el usuario de la notebook
  docker volume inspect fixture2030_iris_durable -f 'Volumen {{.Name}} -> {{.Options.device}}' \
    | sed -E 's#-> .*(/docker/data/iris)$#-> ~\1#'
  echo
  echo "## Compilación de src/ (RNF2)"
  bash scripts/compilar.sh
  echo
  echo "## Recursos de Docker"
  docker info --format 'CPUs: {{.NCPU}}  Memoria: {{.MemTotal}} bytes  SO: {{.OperatingSystem}}'
} | tee "$EVID"
grep -q "compiladas: OK" "$EVID" || { echo "✖ Hubo errores de compilación"; exit 1; }
echo
echo "Siguiente paso: bash scripts/carga.sh"
