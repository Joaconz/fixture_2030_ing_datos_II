#!/bin/sh
# ============================================================================
#  Fixture 2030 — Hito 8 · Series temporales (InfluxDB 2)
#  ARCHIVO: scripts/autorizacion_local.sh
#  PROPÓSITO: crear la AUTORIZACIÓN LOCAL (RNF3, RNF7, RNF9) con la CLI incluida
#  en el contenedor: `influx setup` da de alta el usuario administrador, la
#  organización `fixture2030`, el bucket inicial y el token de operador.
#  Usuario, contraseña y token se generan al azar en ESTA notebook y quedan en
#  secrets/admin-token.json (permisos 600, ignorado por git). Nunca se imprimen.
#
#  USO: lo llama inicializacion.sh. Suelto: sh scripts/autorizacion_local.sh
#  REQUIERE: el servidor arriba (docker compose up -d).
# ============================================================================
set -eu
cd "$(dirname "$0")/.."
TOKEN_FILE="secrets/admin-token.json"
ORG="fixture2030"
mkdir -p secrets

leer() { sed -n "s/.*\"$1\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p" "$TOKEN_FILE"; }
token_valido() {
  docker compose exec -T -e INFLUX_TOKEN="$(leer token)" influxdb \
    influx bucket list --org "$ORG" > /dev/null 2>&1
}

if [ -s "$TOKEN_FILE" ] && token_valido; then
  echo "   $TOKEN_FILE existe y el servidor lo acepta: se reutiliza"
  exit 0
fi

azar() { LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c "$1"; }
TOKEN=$(azar 64)
CLAVE=$(azar 24)
USUARIO="admin_lab"

if docker compose exec -T influxdb influx setup \
     --username "$USUARIO" --password "$CLAVE" --org "$ORG" \
     --bucket fixture2030_vivo --retention 45d --token "$TOKEN" --force > /dev/null 2>&1; then
  umask 077
  printf '{\n  "token": "%s",\n  "org": "%s",\n  "usuario": "%s",\n  "password": "%s"\n}\n' \
    "$TOKEN" "$ORG" "$USUARIO" "$CLAVE" > "$TOKEN_FILE"
  echo "   influx setup: usuario $USUARIO, organización $ORG, token de operador -> $TOKEN_FILE (no se muestra)"
else
  echo "   ✖ influx setup no se pudo ejecutar: el servidor ya fue inicializado antes"
  echo "     (datos de una instalación anterior) y sus credenciales no están en $TOKEN_FILE."
  echo "     Para empezar de cero (borra los datos locales):"
  echo "       sh scripts/limpieza.sh todo && sh scripts/inicializacion.sh"
  exit 1
fi
token_valido || { echo "   ✖ El token creado no es aceptado por el servidor"; exit 1; }
