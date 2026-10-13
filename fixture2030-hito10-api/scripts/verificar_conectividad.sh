#!/usr/bin/env bash
# ============================================================
#  Fixture 2030 — Hito 10 · API REST integrada
#  ARCHIVO: scripts/verificar_conectividad.sh
#  PROPÓSITO: comprobar, fuente por fuente, que la API tiene a qué conectarse
#  (RF1 / §5.12). Por cada una de las cinco fuentes:
#    a) el contenedor está corriendo (`docker inspect`);
#    b) el puerto publicado responde en la notebook;
#    c) un comando NATIVO mínimo del motor responde:
#         MongoDB    mongosh --eval 'db.runCommand({ping:1})'   (docker exec)
#         Neo4j      cypher-shell 'RETURN 1'                     (docker exec; credencial por variable)
#         Cassandra  cqlsh -e 'SELECT release_version FROM system.local'
#         Redis      redis-cli PING
#         InfluxDB   curl /health (no requiere token)
#  Al final, si la API está arriba, GET /health/dependencias.
#  SALIDA: una línea OK/FALLA por comprobación; exit code 1 si algo falla.
#  USO:  bash scripts/verificar_conectividad.sh
#  RNF7: la contraseña de Neo4j viaja como variable de entorno al contenedor
#  (no en la línea de comandos) y nunca se imprime.
# ============================================================
set -uo pipefail
source "$(dirname "$0")/_comun.sh"

FALLAS=0
ok()    { printf 'OK     %-10s %s\n' "$1" "$2"; }
falla() { printf 'FALLA  %-10s %s\n' "$1" "$2"; FALLAS=$((FALLAS + 1)); }

if ! command -v docker >/dev/null 2>&1; then
  echo "FALLA  docker     el comando docker no está disponible"; exit 1
fi

comando_nativo() {   # comando_nativo FUENTE CONTENEDOR → imprime una línea corta de respuesta
  case "$1" in
    mongodb)   docker exec "$2" mongosh --quiet --eval 'db.runCommand({ping:1}).ok' 2>/dev/null | tail -n1 ;;
    neo4j)     NEO4J_USERNAME="$NEO4J_USER" NEO4J_PASSWORD="${NEO4J_PASSWORD:-}" \
                 docker exec -e NEO4J_USERNAME -e NEO4J_PASSWORD "$2" \
                 cypher-shell --format plain 'RETURN 1 AS ok' 2>/dev/null | tail -n1 ;;
    cassandra) docker exec "$2" cqlsh -e 'SELECT release_version FROM system.local' 2>/dev/null \
                 | grep -E '^[[:space:]]*[0-9]+\.' | tr -d ' ' | head -n1 ;;
    redis)     docker exec "$2" redis-cli PING 2>/dev/null | tail -n1 ;;
    influxdb)  curl -fsS -m 3 "$INFLUX_URL_HOST/health" 2>/dev/null | head -c 80 ;;
  esac
}

esperado() {   # esperado FUENTE RESPUESTA → 0 si la respuesta es la esperada
  case "$1" in
    mongodb)   [ "$2" = "1" ] ;;
    neo4j)     [ "$2" = "1" ] ;;
    cassandra) [ -n "$2" ] ;;
    redis)     [ "$2" = "PONG" ] ;;
    influxdb)  [ -n "$2" ] ;;
  esac
}

for fuente in mongodb neo4j cassandra redis influxdb; do
  c="$(contenedor_de "$fuente")"
  p="$(puerto_de "$fuente")"
  if contenedor_corriendo "$c"; then ok "$fuente" "contenedor $c corriendo"
  else falla "$fuente" "contenedor $c no está corriendo"; continue; fi

  if puerto_abierto 127.0.0.1 "$p"; then ok "$fuente" "puerto $p abierto"
  else falla "$fuente" "puerto $p cerrado"; fi

  resp="$(comando_nativo "$fuente" "$c")"
  if esperado "$fuente" "$resp"; then ok "$fuente" "comando nativo responde (${resp})"
  else falla "$fuente" "comando nativo sin respuesta esperada"; fi
done

codigo="$(curl -s -o /dev/null -m 3 -w '%{http_code}' "$API_URL/health" 2>/dev/null || true)"
if [ "$codigo" = "200" ]; then
  cuerpo="$(mktemp)"
  codigo="$(curl -s -o "$cuerpo" -m 10 -w '%{http_code}' "$API_URL/health/dependencias" || true)"
  if [ "$codigo" = "200" ]; then ok "api" "/health/dependencias 200 (todas UP)"
  else falla "api" "/health/dependencias $codigo"; fi
  cat "$cuerpo"; echo
  rm -f "$cuerpo"
else
  echo "OMITIDO api        la API no responde en $API_URL (bash scripts/iniciar_api.sh)"
fi

echo
if [ "$FALLAS" -eq 0 ]; then echo "Resultado: todo OK"; else echo "Resultado: $FALLAS falla(s)"; fi
[ "$FALLAS" -eq 0 ]
