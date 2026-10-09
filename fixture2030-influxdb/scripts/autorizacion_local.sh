#!/bin/sh
# ============================================================================
#  Fixture 2030 — Hito 8 · Series temporales (InfluxDB 3 Core)
#  ARCHIVO: scripts/autorizacion_local.sh
#  PROPÓSITO: crear la AUTORIZACIÓN LOCAL (RNF3, RNF7, RNF9) con la CLI incluida
#  en el contenedor: `influxdb3 create token --admin` crea el token de
#  administración de la instancia. InfluxDB 3 Core lo muestra UNA sola vez:
#  se captura directo a secrets/admin-token.json (permisos 600, ignorado por
#  git) y nunca se imprime.
#
#  USO: lo llama inicializacion.sh. Suelto: sh scripts/autorizacion_local.sh
#  REQUIERE: el servidor arriba (docker compose up -d).
# ============================================================================
set -eu
cd "$(dirname "$0")/.."
TOKEN_FILE="secrets/admin-token.json"
mkdir -p secrets

leer() { sed -n 's/.*"token"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$TOKEN_FILE"; }
token_valido() {
  docker compose exec -T -e INFLUXDB3_AUTH_TOKEN="$(leer)" influxdb \
    influxdb3 show databases > /dev/null 2>&1
}

if [ -s "$TOKEN_FILE" ] && token_valido; then
  echo "   $TOKEN_FILE existe y el servidor lo acepta: se reutiliza"
  exit 0
fi

# La salida del comando trae el token: se guarda en una variable, nunca en pantalla.
if SALIDA=$(docker compose exec -T influxdb influxdb3 create token --admin --format json 2>&1); then
  TOKEN=$(printf '%s' "$SALIDA" | grep -o 'apiv3_[A-Za-z0-9_-]*' | head -1)
fi
if [ -n "${TOKEN:-}" ]; then
  umask 077
  printf '{\n  "token": "%s"\n}\n' "$TOKEN" > "$TOKEN_FILE"
  echo "   influxdb3 create token --admin: token de administración -> $TOKEN_FILE (no se muestra)"
else
  echo "   ✖ No se pudo crear el token: el servidor ya tiene un token de administración"
  echo "     (datos de una instalación anterior) y no está en $TOKEN_FILE."
  echo "     Para empezar de cero (borra los datos locales):"
  echo "       sh scripts/limpieza.sh todo && sh scripts/inicializacion.sh"
  exit 1
fi
token_valido || { echo "   ✖ El token creado no es aceptado por el servidor"; exit 1; }
