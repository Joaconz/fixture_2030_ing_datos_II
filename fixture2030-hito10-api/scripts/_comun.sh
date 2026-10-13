#!/usr/bin/env bash
# ============================================================
#  Fixture 2030 — Hito 10 · API REST integrada
#  ARCHIVO: scripts/_comun.sh  (se incluye con `source`, no se ejecuta solo)
#  PROPÓSITO: piezas compartidas por los scripts de operación y prueba:
#    - rutas del proyecto;
#    - carga de `.env` SIN evaluarlo como código (sólo líneas CLAVE=valor;
#      una variable ya definida en el entorno tiene prioridad);
#    - contraseña de Neo4j: entorno → .env de la API → .env de fixture2030-neo4j;
#    - nombres de contenedor (sobrescribibles por variable de entorno).
#  RNF7: ninguna función imprime contraseñas ni tokens.
#  Bash portable (macOS bash 3.2 y Linux/WSL).
# ============================================================

API_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="$(cd "$API_DIR/.." && pwd)"
export API_DIR REPO_DIR

# cargar_env ARCHIVO — exporta CLAVE=valor que todavía no estén definidas.
cargar_env() {
  local archivo="$1" linea clave valor
  [ -f "$archivo" ] || return 0
  while IFS= read -r linea || [ -n "$linea" ]; do
    linea="${linea%$'\r'}"
    case "$linea" in ''|'#'*) continue ;; esac
    clave="${linea%%=*}"
    valor="${linea#*=}"
    clave="$(printf '%s' "$clave" | tr -d '[:space:]')"
    printf '%s' "$clave" | grep -Eq '^[A-Za-z_][A-Za-z0-9_]*$' || continue
    # quitar comillas envolventes simples o dobles
    case "$valor" in
      \"*\") valor="${valor#\"}"; valor="${valor%\"}" ;;
      \'*\') valor="${valor#\'}"; valor="${valor%\'}" ;;
    esac
    if [ -z "${!clave+x}" ]; then
      export "$clave=$valor"
    fi
  done < "$archivo"
}

cargar_env "$API_DIR/.env"

# Neo4j: si la API no la definió, la credencial de desarrollo del Hito 5.
if [ -z "${NEO4J_PASSWORD:-}" ] && [ -f "$REPO_DIR/fixture2030-neo4j/.env" ]; then
  NEO4J_PASSWORD="$(grep -E '^NEO4J_PASSWORD=' "$REPO_DIR/fixture2030-neo4j/.env" | tail -n1 | cut -d= -f2-)"
  export NEO4J_PASSWORD
fi
export NEO4J_USER="${NEO4J_USER:-neo4j}"

API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-8000}"
API_URL="${API_URL:-http://localhost:${API_PORT}}"
export API_HOST API_PORT API_URL

# Contenedores (Hitos 4–8). Mongo admite dos nombres: el del compose del
# Hito 4 (fixture2030_mongo) y el de un levantamiento anterior (fixture2030-mongodb).
MONGO_CONTAINERS="${MONGO_CONTAINER:-fixture2030_mongo fixture2030-mongodb}"
NEO4J_CONTAINER="${NEO4J_CONTAINER:-fixture2030-neo4j}"
CASSANDRA_CONTAINER="${CASSANDRA_CONTAINER:-fixture2030-cassandra}"
REDIS_CONTAINER="${REDIS_CONTAINER:-fixture2030-redis}"
INFLUX_CONTAINER="${INFLUX_CONTAINER:-fixture2030-influxdb}"
INFLUX_URL_HOST="${INFLUX_URL_HOST:-http://127.0.0.1:8181}"

contenedor_corriendo() {   # contenedor_corriendo NOMBRE → 0 si está "running"
  [ "$(docker inspect -f '{{.State.Running}}' "$1" 2>/dev/null)" = "true" ]
}

# contenedor_de FUENTE → nombre del contenedor (para mongo, el primero que corra)
contenedor_de() {
  case "$1" in
    mongodb)
      local c
      for c in $MONGO_CONTAINERS; do
        if contenedor_corriendo "$c"; then echo "$c"; return 0; fi
      done
      echo "${MONGO_CONTAINERS%% *}" ;;
    neo4j) echo "$NEO4J_CONTAINER" ;;
    cassandra) echo "$CASSANDRA_CONTAINER" ;;
    redis) echo "$REDIS_CONTAINER" ;;
    influxdb) echo "$INFLUX_CONTAINER" ;;
    *) return 1 ;;
  esac
}

puerto_de() {
  case "$1" in
    mongodb) echo 27017 ;; neo4j) echo 7687 ;; cassandra) echo 9042 ;;
    redis) echo 6379 ;; influxdb) echo 8181 ;; *) return 1 ;;
  esac
}

puerto_abierto() {   # puerto_abierto HOST PUERTO
  if command -v nc >/dev/null 2>&1; then
    nc -z -w 2 "$1" "$2" >/dev/null 2>&1
  else
    (exec 3<>"/dev/tcp/$1/$2") >/dev/null 2>&1
  fi
}

sello_fecha() { date -u +%Y%m%d-%H%M%S; }
