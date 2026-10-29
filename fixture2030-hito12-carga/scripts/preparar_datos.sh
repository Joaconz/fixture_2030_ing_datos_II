#!/usr/bin/env bash
# ============================================================================
#  Fixture 2030 — Hito 12 · preparar el ambiente y los datos (RF3)
#  USO: bash scripts/preparar_datos.sh
#   1. Docker y Cassandra (Hito 6) arriba
#   2. datos base: los 1.050.000 comentarios del Hito 6 (si faltan, corre su carga masiva)
#   3. entorno Python de la API (Hito 10) creado con uv
#   4. imagen del generador de carga (k6) descargada
#  No borra nada: es seguro repetirlo (RNF11).
# ============================================================================
. "$(dirname "$0")/_comun.sh"

echo "== 1. Cassandra (Hito 6)"
docker info >/dev/null 2>&1 || falla "Docker no está corriendo: abrí Docker Desktop."
if ! docker ps --format '{{.Names}}' | grep -qx "$CONTENEDOR_CAS"; then
  mkdir -p "${CASSANDRA_DATA_DIR:-$HOME/docker/data/cassandra}"
  ( cd "$CAS_DIR" && docker compose up -d )
fi
printf "   esperando a que Cassandra responda"
for _ in $(seq 1 60); do cql "DESCRIBE KEYSPACES" >/dev/null 2>&1 && break; printf "."; sleep 3; done; echo
cql "DESCRIBE KEYSPACES" | grep -q fixture2030_comentarios || {
  echo "   creando el esquema del Hito 6"; docker exec -i "$CONTENEDOR_CAS" cqlsh -f /scripts/esquema.cql; }

echo "== 2. Datos base de PAR-D16-01"
contar_pico() {
  local n=0 b
  for b in 0 1 2 3; do
    n=$(( n + $(cql "SELECT count(*) FROM fixture2030_comentarios.comentarios_por_partido WHERE partido_id='PAR-D16-01' AND ventana='2030-06-29 17:30:00+0000' AND bucket=$b;" | awk 'NR==4{print $1+0}') ))
  done; echo "$n"
}
PICO=$(contar_pico)
if [ "${PICO:-0}" -lt 60000 ]; then
  echo "   ventana pico con $PICO filas: faltan los datos del Hito 6 → carga masiva (unos minutos)"
  docker exec -i "$CONTENEDOR_CAS" cqlsh -f /scripts/carga_muestra.cql >/dev/null
  ( cd "$CAS_DIR" && docker compose --profile carga run --rm cargador )
  PICO=$(contar_pico)
fi
echo "   ventana pico 17:30 de PAR-D16-01: $PICO filas (Hito 6: 64.640)"
cql "SELECT partido_id, buckets, ventana_minutos FROM fixture2030_comentarios.config_particion_partido WHERE partido_id='PAR-D16-01';"

echo "== 3. Entorno Python de la API (Hito 10)"
if [ ! -x "$PY_API" ] || ! "$PY_API" -c "import cassandra, fastapi" >/dev/null 2>&1; then
  command -v uv >/dev/null || falla "Falta uv: curl -LsSf https://astral.sh/uv/install.sh | sh  (y abrir otra terminal)"
  ( cd "$API_DIR" && { [ -x .venv/bin/python ] || uv venv --python 3.12 .venv; } && uv pip install --python .venv/bin/python -r requirements.txt )
fi
"$PY_API" -c "import cassandra, fastapi; print('   entorno OK')"
[ -f "$API_DIR/.env" ] || { cp "$API_DIR/.env.example" "$API_DIR/.env"; echo "   creado $API_DIR/.env desde .env.example"; }

echo "== 4. Generador de carga"
docker pull -q "$K6_IMAGEN" >/dev/null && docker run --rm "$K6_IMAGEN" version | head -1

echo; echo "Listo. Siguiente: bash scripts/ejecutar_linea_base.sh"
