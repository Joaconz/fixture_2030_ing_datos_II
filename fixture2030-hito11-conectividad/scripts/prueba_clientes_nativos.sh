#!/usr/bin/env bash
# ============================================================
#  Fixture 2030 — Hito 11 · Evaluación de la conectividad
#  ARCHIVO: scripts/prueba_clientes_nativos.sh
#  PROPÓSITO: capa 3-6 con el CLIENTE NATIVO de cada producto (RF6, RNF4),
#  como complemento de prueba_drivers.py (que usa los drivers de la API):
#      MongoDB    mongosh      ping + equipos.findOne (proyección)
#      Neo4j      cypher-shell RETURN 1 + lectura parametrizada de un partido
#      Cassandra  cqlsh        USE keyspace + SELECT … LIMIT 1 por partición
#      Redis      redis-cli    PING + EXISTS/TYPE/TTL de la sesión de demo
#      InfluxDB   influxdb3    query SELECT 1 (token por variable de entorno)
#      IRIS       —            NOT_CONFIGURED (fuera de la arquitectura)
#  ORIGEN (RNF3): si el cliente está instalado en la notebook se usa desde ahí
#  (mismo origen que la API). Si no, se usa el que trae la imagen con
#  `docker exec` y el registro lo marca como "origen: dentro del contenedor":
#  prueba el protocolo y el contexto, NO la ruta notebook → puerto publicado
#  (esa la prueban prueba_tcp.py y prueba_drivers.py).
#  Si no hay cliente ni contenedor: SKIP (= no probado, no "caído").
#  RNF6: sólo lecturas. RNF7: contraseña y token viajan como variables de
#  entorno al proceso hijo, nunca en la línea de comandos ni en la salida.
#  USO:  bash scripts/prueba_clientes_nativos.sh [mongodb neo4j cassandra redis influxdb iris]
# ============================================================
set -uo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PY:-python3}"
cfg() { "$PY" "$DIR/registro.py" config "$1"; }
T="$(cfg CONNECT_TIMEOUT)"; TOP="$(cfg OPERACION_TIMEOUT)"

# reg PRODUCTO CAPA PRUEBA OBJETIVO RESULTADO MS DETALLE INTERPRETACION [NO_DEMUESTRA]
reg() {
  "$PY" "$DIR/registro.py" agregar --archivo resultados_clientes \
    --titulo "Capas 3-6 — protocolo, identidad, contexto y operación" \
    --producto "$1" --capa "$2" --prueba "$3" --objetivo "$4" --resultado "$5" \
    ${6:+--latencia-ms "$6"} --detalle "$7" --interpretacion "$8" --no-demuestra "${9:-}"
}
ms_desde() { "$PY" -c "import time,sys; print(round((time.time()-float(sys.argv[1]))*1000,1))" "$1"; }
ahora() { "$PY" -c "import time; print(time.time())"; }
tiene() { command -v "$1" >/dev/null 2>&1; }
corriendo() { [ "$(docker inspect -f '{{.State.Running}}' "$1" 2>/dev/null)" = "true" ]; }
# con_timeout SEG CMD… — timeout portable (macOS no trae `timeout`)
con_timeout() { local s="$1"; shift; "$PY" - "$s" "$@" <<'EOF'
import subprocess, sys
try:
    r = subprocess.run(sys.argv[2:], timeout=float(sys.argv[1]), stdin=sys.stdin)
    sys.exit(r.returncode)
except subprocess.TimeoutExpired:
    print("TIMEOUT", file=sys.stderr); sys.exit(124)
EOF
}

# elegir CLIENTE CONTENEDOR → "host" | "contenedor" | ""
elegir() {
  if tiene "$1"; then echo host
  elif tiene docker && corriendo "$2"; then echo contenedor
  fi
}

# ------------------------------------------------------------------ MongoDB
mongodb() {
  local db host port cod c origen t0 out
  db="$(cfg MONGO_DB)"; host="$(cfg MONGO_HOST)"; port="$(cfg MONGO_PORT)"; cod="$(cfg MONGO_EQUIPO_DEMO)"
  c="$(cfg MONGO_CONTAINER)"; origen="$(elegir mongosh "$c")"
  local js="const p=db.runCommand({ping:1}).ok; const e=db.equipos.findOne({_id:'$cod'},{_id:1,nombre:1}); print(p+'|'+(e?e._id+':'+e.nombre:'null')+'|'+db.version())"
  t0="$(ahora)"
  case "$origen" in
    host) out="$(con_timeout $((${T%.*} + ${TOP%.*} + 2)) mongosh "mongodb://$host:$port/$db" --quiet \
                   --eval "$js" 2>&1 | tail -n1)"; origen_txt="notebook ($host:$port)";;
    contenedor) out="$(con_timeout 15 docker exec "$c" mongosh "$db" --quiet --eval "$js" 2>&1 | tail -n1)"
                origen_txt="dentro del contenedor $c";;
    *) reg mongodb protocolo "mongosh" "-" SKIP "" "mongosh no está instalado y no hay contenedor $c corriendo" \
         "SKIP = herramienta no disponible, no 'producto caído'"; return;;
  esac
  local ms; ms="$(ms_desde "$t0")"
  if [ "${out%%|*}" = "1" ]; then
    reg mongodb protocolo "mongosh ping" "$origen_txt db=$db" OK "$ms" "MongoDB ${out##*|} · ok=1" \
      "el cliente oficial negocia el protocolo y selecciona la database" "que la API use la misma URI"
    local eq; eq="$(printf '%s' "$out" | cut -d'|' -f2)"
    reg mongodb operacion "mongosh equipos.findOne({_id:'$cod'})" "$db.equipos" \
      "$([ "$eq" != null ] && echo OK || echo FAIL)" "$ms" "$eq" "lectura mínima con proyección desde el cliente nativo"
  else
    reg mongodb protocolo "mongosh ping" "$origen_txt db=$db" FAIL "$ms" "$out" \
      "el cliente nativo no completó el ping: revisar TCP y logs del contenedor"
  fi
}

# ------------------------------------------------------------------ Neo4j
neo4j() {
  local c origen t0 out ms user pid
  c="$(cfg NEO4J_CONTAINER)"; origen="$(elegir cypher-shell "$c")"; user="$(cfg NEO4J_USER)"; pid="$(cfg NEO4J_PARTIDO_DEMO)"
  # contraseña: entorno o .env local del módulo (nunca se imprime)
  NEO4J_PASSWORD="$("$PY" -c "import sys; sys.path.insert(0,'$DIR'); import registro as r; print(r.neo4j_password(r.cargar_config())[0] or '')")"
  export NEO4J_USERNAME="$user" NEO4J_PASSWORD
  if [ -z "$NEO4J_PASSWORD" ]; then
    reg neo4j autenticacion "cypher-shell" "-" SKIP "" "NEO4J_PASSWORD no definida (entorno o NEO4J_ENV_FILE)" \
      "SKIP = falta configuración; no se intenta sin credencial para no sumar intentos fallidos"
    unset NEO4J_PASSWORD NEO4J_USERNAME; return
  fi
  local cy="MATCH (p:Partido {partidoId: \$pid}) OPTIONAL MATCH (e:Evento)-[:OCURRE_EN]->(p) RETURN p.partidoId AS id, count(e) AS eventos"
  local addr="bolt://$(cfg NEO4J_HOST):$(cfg NEO4J_BOLT_PORT)"
  t0="$(ahora)"
  case "$origen" in
    host) out="$(con_timeout 15 cypher-shell -a "$addr" -d "$(cfg NEO4J_DATABASE)" --format plain \
                   --param "pid => '$pid'" "$cy" 2>&1 | tail -n1)"; origen_txt="notebook ($addr)";;
    contenedor) out="$(con_timeout 20 docker exec -e NEO4J_USERNAME -e NEO4J_PASSWORD "$c" cypher-shell \
                   -d "$(cfg NEO4J_DATABASE)" --format plain --param "pid => '$pid'" "$cy" 2>&1 | tail -n1)"
                origen_txt="dentro del contenedor $c (cypher-shell no está instalado en la notebook)";;
    *) reg neo4j protocolo "cypher-shell" "-" SKIP "" "cypher-shell no está instalado y no hay contenedor $c" \
         "SKIP = herramienta no disponible"; unset NEO4J_PASSWORD; return;;
  esac
  ms="$(ms_desde "$t0")"
  if printf '%s' "$out" | grep -q "\"$pid\""; then
    reg neo4j operacion "cypher-shell lectura parametrizada (\$pid)" "$origen_txt database=$(cfg NEO4J_DATABASE)" OK "$ms" \
      "$out" "Bolt + autenticación + database + Cypher parametrizado con el cliente nativo" \
      "la ruta notebook→7687 si el origen es el contenedor"
  elif printf '%s' "$out" | grep -qi "unauthorized\|authentication\|access denied"; then
    reg neo4j autenticacion "cypher-shell" "$origen_txt" FAIL "$ms" "credencial rechazada" \
      "identidad inválida: revisar NEO4J_PASSWORD (no es un problema de red)"
  else
    reg neo4j operacion "cypher-shell lectura parametrizada" "$origen_txt" FAIL "$ms" "$out" "revisar la salida y los logs"
  fi
  unset NEO4J_PASSWORD NEO4J_USERNAME
}

# ------------------------------------------------------------------ Cassandra
cassandra() {
  local c origen t0 out ms ks tabla pid
  c="$(cfg CASSANDRA_CONTAINER)"; origen="$(elegir cqlsh "$c")"; ks="$(cfg CASSANDRA_KEYSPACE)"
  tabla="$(cfg CASSANDRA_TABLA)"; pid="$(cfg CASSANDRA_PARTIDO_DEMO)"
  local cql="USE $ks; SELECT partido_id, ventana, bucket FROM $tabla WHERE partido_id='$pid' AND ventana='2030-06-09 13:00:00+0000' AND bucket=0 LIMIT 1;"
  t0="$(ahora)"
  case "$origen" in
    host) out="$(con_timeout 20 cqlsh "$(cfg CASSANDRA_HOST)" "$(cfg CASSANDRA_PORT)" --connect-timeout="${T%.*}" \
                   --request-timeout="${TOP%.*}" -e "$cql" 2>&1)"; origen_txt="notebook";;
    contenedor) out="$(con_timeout 30 docker exec "$c" cqlsh --connect-timeout="${T%.*}" --request-timeout="${TOP%.*}" -e "$cql" 2>&1)"
                origen_txt="dentro del contenedor $c (cqlsh no está instalado en la notebook)";;
    *) reg cassandra protocolo "cqlsh" "-" SKIP "" "cqlsh no está instalado y no hay contenedor $c" "SKIP = herramienta no disponible"; return;;
  esac
  ms="$(ms_desde "$t0")"
  if printf '%s' "$out" | grep -q "(1 rows)"; then
    reg cassandra operacion "cqlsh USE $ks + SELECT por partición LIMIT 1" "$origen_txt $ks.$tabla" OK "$ms" \
      "1 fila en ($pid, 13:00, bucket 0)" "protocolo CQL, keyspace y lectura acotada con el cliente nativo" \
      "la ruta notebook→9042 si el origen es el contenedor"
  else
    reg cassandra operacion "cqlsh USE $ks + SELECT" "$origen_txt" FAIL "$ms" "$(printf '%s' "$out" | tail -n2 | tr '\n' ' ')" \
      "si dice 'Keyspace … does not exist' es contexto; si dice 'Unable to connect' es red/protocolo"
  fi
}

# ------------------------------------------------------------------ Redis
redis() {
  local c origen t0 out ms clave
  c="$(cfg REDIS_CONTAINER)"; origen="$(elegir redis-cli "$c")"
  clave="$(cfg REDIS_PREFIJO_SESION)$(cfg REDIS_SESION_DEMO)"
  local args=(-h "$(cfg REDIS_HOST)" -p "$(cfg REDIS_PORT)" -n "$(cfg REDIS_DB)" --raw)
  t0="$(ahora)"
  case "$origen" in
    host) out="$(con_timeout "$T" redis-cli "${args[@]}" PING 2>&1)"; origen_txt="notebook ($(cfg REDIS_HOST):$(cfg REDIS_PORT))"
          ex="$(redis-cli "${args[@]}" EXISTS "$clave" 2>&1)"; ty="$(redis-cli "${args[@]}" TYPE "$clave" 2>&1)"
          ttl="$(redis-cli "${args[@]}" TTL "$clave" 2>&1)";;
    contenedor) out="$(docker exec "$c" redis-cli --raw PING 2>&1)"; origen_txt="dentro del contenedor $c"
          ex="$(docker exec "$c" redis-cli --raw EXISTS "$clave")"; ty="$(docker exec "$c" redis-cli --raw TYPE "$clave")"
          ttl="$(docker exec "$c" redis-cli --raw TTL "$clave")";;
    *) reg redis protocolo "redis-cli" "-" SKIP "" "redis-cli no está instalado y no hay contenedor $c" "SKIP = herramienta no disponible"; return;;
  esac
  ms="$(ms_desde "$t0")"
  if [ "$out" = "PONG" ]; then
    reg redis protocolo "redis-cli PING" "$origen_txt" OK "$ms" "PONG" "RESP responde con el cliente oficial" "que exista la clave"
    local det="EXISTS $ex · TYPE $ty · TTL $ttl" interp
    case "$ttl" in
      -2) interp="clave ausente (inexistente o vencida: Redis no las distingue). Redis está disponible: la API dará 404";;
      -1) interp="clave sin expiración: una sesión siempre debería tener TTL";;
      *)  interp="clave presente; vence en $ttl s";;
    esac
    reg redis operacion "redis-cli EXISTS/TYPE/TTL" "$clave" "$([ "$ttl" = "-1" ] && echo WARN || echo OK)" "$ms" "$det" "$interp" \
      "el contenido de la sesión (no se lee)"
  else
    reg redis protocolo "redis-cli PING" "$origen_txt" FAIL "$ms" "$out" \
      "sin PONG: 'Connection refused' = no hay listener; 'NOAUTH' = falta credencial"
  fi
}

# ------------------------------------------------------------------ InfluxDB
influxdb() {
  local c t0 out ms db
  c="$(cfg INFLUX_CONTAINER)"; db="$(cfg INFLUX_DB)"
  if ! { tiene influxdb3 || { tiene docker && corriendo "$c"; }; }; then
    reg influxdb protocolo "influxdb3 query" "-" SKIP "" "influxdb3 no está instalado y no hay contenedor $c" "SKIP = herramienta no disponible"; return
  fi
  INFLUXDB3_AUTH_TOKEN="$("$PY" -c "import sys; sys.path.insert(0,'$DIR'); import registro as r; print(r.influx_token(r.cargar_config())[0] or '')")"
  export INFLUXDB3_AUTH_TOKEN
  if [ -z "$INFLUXDB3_AUTH_TOKEN" ]; then
    reg influxdb autenticacion "influxdb3 query" "-" SKIP "" "token no definido (INFLUX_TOKEN o INFLUX_TOKEN_FILE)" \
      "SKIP = falta configuración, no 'producto caído'"
    unset INFLUXDB3_AUTH_TOKEN; return
  fi
  t0="$(ahora)"
  if tiene influxdb3; then
    out="$(con_timeout 15 influxdb3 query --host "$(cfg INFLUX_URL)" --database "$db" "SELECT 1 AS ok" 2>&1)"; origen_txt="notebook"
  else
    out="$(con_timeout 20 docker exec -e INFLUXDB3_AUTH_TOKEN "$c" influxdb3 query --database "$db" "SELECT 1 AS ok" 2>&1)"
    origen_txt="dentro del contenedor $c (influxdb3 no está instalado en la notebook)"
  fi
  ms="$(ms_desde "$t0")"
  unset INFLUXDB3_AUTH_TOKEN
  if printf '%s' "$out" | grep -q "| 1 "; then
    reg influxdb operacion "influxdb3 query SELECT 1 (token por variable de entorno)" "$origen_txt db=$db" OK "$ms" \
      "1 fila" "CLI oficial: token aceptado y database existente" "que haya puntos en la ventana del partido"
  else
    reg influxdb operacion "influxdb3 query SELECT 1" "$origen_txt db=$db" FAIL "$ms" "$(printf '%s' "$out" | tail -n1)" \
      "401 = token; 'database not found' = contexto; 'connection refused' = red"
  fi
}

# ------------------------------------------------------------------ IRIS
iris() {
  if [ "$(cfg IRIS_HABILITADO)" != "1" ]; then
    reg iris protocolo "iris session (terminal)" "$(cfg IRIS_CONTAINER)" N/C "" \
      "no evaluado: IRIS fuera de la arquitectura vigente; contenedor no levantado" "NOT_CONFIGURED: no se inventan resultados"
    return
  fi
  "${PY_API:-$PY}" "$DIR/prueba_drivers.py" --producto iris
}

PRODUCTOS=("$@"); [ "${#PRODUCTOS[@]}" -eq 0 ] && PRODUCTOS=(mongodb neo4j cassandra redis influxdb iris)
for p in "${PRODUCTOS[@]}"; do
  case "$p" in mongodb|neo4j|cassandra|redis|influxdb|iris) "$p" ;; *) echo "producto desconocido: $p" >&2 ;; esac
done
