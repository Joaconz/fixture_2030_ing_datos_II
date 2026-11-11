#!/usr/bin/env bash
# ============================================================================
#  Fixture 2030 — Hito 13 · token de InfluxDB para Prometheus (job "influxdb").
#  USO: bash scripts/preparar_token_influxdb.sh   (lo llama iniciar_monitoreo.sh)
#
#  El /metrics de InfluxDB 3 Core exige el token de administración. Ese token
#  ya existe en fixture2030-influxdb/secrets/admin-token.json (lo crea
#  fixture2030-influxdb/scripts/inicializacion.sh) pero en JSON, y Prometheus
#  lee el archivo de credenciales tal cual: este script copia SOLO el token a
#  fixture2030-influxdb/secrets/prometheus-token. Los dos archivos están
#  ignorados por git (secrets/*) y el token nunca se imprime.
#
#  Permisos 644 (no 600): Prometheus corre como el usuario `nobody` dentro del
#  contenedor y en Linux no podría leer un archivo 600 del usuario de la
#  notebook. Es un token de laboratorio local (ver secrets/README.md del Hito 8).
# ============================================================================
. "$(dirname "$0")/_comun.sh"

SECRETS="$REPO_DIR/fixture2030-influxdb/secrets"
ORIGEN="$SECRETS/admin-token.json"
DESTINO="$SECRETS/prometheus-token"

if [ ! -s "$ORIGEN" ]; then
  echo "Aviso: no existe $ORIGEN (InfluxDB sin inicializar en esta notebook)."
  echo "       El target 'influxdb' de Prometheus va a quedar DOWN hasta correr:"
  echo "         sh fixture2030-influxdb/scripts/inicializacion.sh"
  echo "         bash fixture2030-hito-13-monitoreo/scripts/preparar_token_influxdb.sh"
  exit 0
fi

TOKEN="$(sed -n 's/.*"token"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$ORIGEN")"
[ -n "$TOKEN" ] || falla "$ORIGEN no tiene un campo \"token\""

printf '%s\n' "$TOKEN" > "$DESTINO"
chmod 644 "$DESTINO"
echo "Token de InfluxDB para Prometheus -> ${DESTINO#$REPO_DIR/} (no se muestra)"
