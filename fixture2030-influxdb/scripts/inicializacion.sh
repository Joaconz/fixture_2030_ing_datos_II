#!/bin/sh
# ============================================================================
#  Fixture 2030 — Hito 8 · Series temporales (InfluxDB 3 Core)
#  ARCHIVO: scripts/inicializacion.sh
#  PROPÓSITO: dejar el ambiente listo, de punta a punta y de forma repetible:
#    1. carpeta ~/docker/data/influxdb (respalda el volumen, RNF2)
#    2. servidor con `docker compose up -d` y espera a "healthy"          (§5.1)
#    3. disponibilidad verificada con la CLI incluida en el contenedor     (RF1)
#    4. autorización local -> scripts/autorizacion_local.sh (token admin) (RNF3, RNF7)
#    5. las tres bases de datos con su período de retención               (RF10)
#    6. evidencia: versión observada de influxdb:3-core, bases, retención,
#       volumen y recursos de Docker                                      (RNF10)
#
#  USO (desde la carpeta fixture2030-influxdb):   sh scripts/inicializacion.sh
#  IDEMPOTENTE: correrlo de nuevo reutiliza la autorización y las bases.
# ============================================================================
set -eu

cd "$(dirname "$0")/.."
BASE_DIR="${INFLUX_DATA_DIR:-$HOME/docker/data/influxdb}"
EVID="docs/evidencia/01_inicializacion.txt"

echo "== 1. Carpeta de datos (RNF2)"
mkdir -p "$BASE_DIR" secrets data docs/evidencia
# El proceso del contenedor corre con el usuario influxdb3 (uid 1500): necesita
# poder escribir en la carpeta montada (Clase 9, error PermissionDenied).
chmod 777 "$BASE_DIR" 2>/dev/null || true
echo "   $BASE_DIR"

echo "== 2. Servidor: docker compose up -d"
docker compose up -d influxdb
printf "   esperando a que esté healthy"
i=0
until [ "$(docker inspect -f '{{.State.Health.Status}}' fixture2030-influxdb 2>/dev/null)" = "healthy" ]; do
  i=$((i + 1)); [ $i -gt 60 ] && { echo " ✖ no arrancó. Ver: docker compose logs influxdb"; exit 1; }
  printf "."; sleep 2
done
echo " ok"

echo "== 3. Disponibilidad con la CLI del contenedor (RF1)"
docker compose exec -T influxdb influxdb3 --version
docker compose exec -T influxdb curl -fsS http://127.0.0.1:8181/health; echo

echo "== 4. Autorización local"
sh scripts/autorizacion_local.sh
TOKEN=$(sed -n 's/.*"token"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' secrets/admin-token.json)
cli() { docker compose exec -T -e INFLUXDB3_AUTH_TOKEN="$TOKEN" influxdb influxdb3 "$@"; }

echo "== 5. Bases de datos y retención (RF10)"
# En InfluxDB 3 Core la retención se fija AL CREAR la base y no se puede cambiar
# después: si una base ya existía, se informa su retención real (la verifica V4).
base() {  # $1 = base, $2 = retención ("" = sin vencimiento)
  if cli show databases --format json | grep -q "\"$1\""; then
    echo "   $1 ya existía"
  elif [ -n "$2" ]; then
    cli create database --retention-period "$2" "$1" > /dev/null && echo "   $1 creada, retención $2"
  else
    cli create database "$1" > /dev/null && echo "   $1 creada, sin vencimiento"
  fi
}
base fixture2030_vivo 45d                 # detalle por segundo: torneo + revisión
base fixture2030_historico ""             # resúmenes por minuto y por partido: se conservan
base fixture2030_prueba_retencion 1h      # solo para DEMOSTRAR la expiración (validacion.py V5)
cli show retention

echo "== 6. Evidencia del ambiente -> $EVID"
{
  echo "# Inicialización — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo
  echo "## Versión observada de influxdb:3-core (RNF1)"
  docker compose exec -T influxdb influxdb3 --version
  docker image inspect influxdb:3-core -f 'Imagen: {{index .RepoDigests 0}}  creada {{.Created}}' 2>/dev/null || true
  echo
  echo "## Disponibilidad del servicio (RF1)"
  docker compose exec -T influxdb curl -fsS http://127.0.0.1:8181/health; echo
  docker compose ps influxdb
  echo
  echo "## Bases de datos y período de retención (RF10)"
  cli show databases
  cli show retention
  echo
  echo "## Persistencia (RNF2): volumen nombrado y carpeta que lo respalda"
  docker volume inspect fixture2030_influxdb_data -f '{{.Name}} -> {{.Options.device}}' | sed -E 's%-> .*(/docker/data/influxdb)%-> ~\1%'
  echo
  echo "## Recursos de Docker"
  docker info --format 'CPUs: {{.NCPU}}  Memoria: {{.MemTotal}} bytes  SO: {{.OperatingSystem}}'
} > "$EVID" 2>&1
cat "$EVID"
echo
echo "API: http://localhost:8181 (token en secrets/admin-token.json)"
echo "Siguiente paso: docker compose run --rm herramientas scripts/generacion_puntos.py --perfil muestra"
