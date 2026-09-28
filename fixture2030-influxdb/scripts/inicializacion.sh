#!/bin/sh
# ============================================================================
#  Fixture 2030 — Hito 8 · Series temporales (InfluxDB 2)
#  ARCHIVO: scripts/inicializacion.sh
#  PROPÓSITO: dejar el ambiente listo, de punta a punta y de forma repetible:
#    1. carpetas ~/docker/data/influxdb/{data,config} (respaldan los volúmenes, RNF2)
#    2. servidor con `docker compose up -d` y espera a "healthy"          (§5.1)
#    3. disponibilidad verificada con la CLI incluida en el contenedor     (RF1)
#    4. autorización local -> scripts/autorizacion_local.sh (influx setup) (RNF3, RNF7)
#    5. los tres buckets con su política de retención                     (RF10)
#    6. evidencia: versión observada de influxdb:latest, buckets, retención,
#       volúmenes y recursos de Docker                                    (RNF10)
#
#  USO (desde la carpeta fixture2030-influxdb):   sh scripts/inicializacion.sh
#  IDEMPOTENTE: correrlo de nuevo reutiliza la autorización y reaplica la retención.
# ============================================================================
set -eu

cd "$(dirname "$0")/.."
BASE_DIR="${INFLUX_DATA_DIR:-$HOME/docker/data/influxdb}"
EVID="docs/evidencia/01_inicializacion.txt"
ORG="fixture2030"

echo "== 1. Carpetas de datos (RNF2)"
mkdir -p "$BASE_DIR/data" "$BASE_DIR/config" secrets data docs/evidencia
echo "   $BASE_DIR/{data,config}"

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
docker compose exec -T influxdb influx ping
docker compose exec -T influxdb influxd version

echo "== 4. Autorización local"
sh scripts/autorizacion_local.sh
TOKEN=$(sed -n 's/.*"token"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' secrets/admin-token.json)
cli() { docker compose exec -T -e INFLUX_TOKEN="$TOKEN" -e INFLUX_ORG="$ORG" influxdb influx "$@"; }

echo "== 5. Buckets y retención (RF10)"
bucket() {  # $1 = bucket, $2 = retención ("0" = sin vencimiento)
  salida=$(cli bucket create --name "$1" --retention "$2" 2>&1) || true
  case "$salida" in
    *"already exists"*) echo "   $1 ya existía" ;;
    *"$1"*) echo "   $1 creado" ;;
    *) echo "   ✖ $1: $salida"; exit 1 ;;
  esac
  id=$(cli bucket list --name "$1" --hide-headers | awk '{print $1}')
  cli bucket update --id "$id" --retention "$2" > /dev/null
  echo "   $1 retención = $2"
}
bucket fixture2030_vivo 45d                 # detalle por segundo: torneo + revisión
bucket fixture2030_historico 0              # resúmenes por minuto y por partido: se conservan
bucket fixture2030_prueba_retencion 1h      # solo para DEMOSTRAR la expiración (validacion.py V5)

echo "== 6. Evidencia del ambiente -> $EVID"
{
  echo "# Inicialización — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo
  echo "## Versión observada de influxdb:latest (RNF1)"
  docker compose exec -T influxdb influxd version
  docker compose exec -T influxdb influx version
  docker image inspect influxdb:latest -f 'Imagen: {{index .RepoDigests 0}}  creada {{.Created}}' 2>/dev/null || true
  echo
  echo "## Disponibilidad del servicio (RF1)"
  docker compose exec -T influxdb influx ping
  docker compose ps influxdb
  echo
  echo "## Buckets, retención y duración de shard (RF10)"
  cli bucket list
  echo
  echo "## Persistencia (RNF2): volúmenes nombrados y carpetas que los respaldan"
  docker volume inspect fixture2030_influxdb_data fixture2030_influxdb_config -f '{{.Name}} -> {{.Options.device}}'
  echo
  echo "## Recursos de Docker"
  docker info --format 'CPUs: {{.NCPU}}  Memoria: {{.MemTotal}} bytes  SO: {{.OperatingSystem}}'
} > "$EVID" 2>&1
cat "$EVID"
echo
echo "Interfaz web: http://localhost:8086 (usuario y contraseña en secrets/admin-token.json)"
echo "Siguiente paso: docker compose run --rm herramientas scripts/generacion_puntos.py --perfil muestra"
