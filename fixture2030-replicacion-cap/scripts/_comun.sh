#!/usr/bin/env bash
# ============================================================================
#  Fixture 2030 — Replicación y CAP · funciones compartidas por los scripts
#  (se incluye con `source`, no se ejecuta solo). Bash de Git Bash / Linux / macOS.
# ============================================================================
set -euo pipefail
# Git Bash convierte los argumentos que empiezan con "/" en rutas de Windows
# (docker exec ... cqlsh -f /scripts/x.cql dejaría de funcionar).
export MSYS_NO_PATHCONV=1
export PYTHONIOENCODING=utf-8      # Python de Windows escribe en cp1252 si no

MOD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="$(cd "$MOD_DIR/.." && pwd)"
EVID="$MOD_DIR/evidencia"
# Se trabaja siempre desde la carpeta del módulo: docker compose toma el
# docker-compose.yml de acá (con -f y una ruta /c/... Docker Desktop no lo encuentra).
cd "$MOD_DIR"
DC="docker compose"

RS_URI="mongodb://mongo1:27017,mongo2:27017,mongo3:27017/?replicaSet=rs-fixture2030"
MONGOS="fixture2030-rep-mongo1 fixture2030-rep-mongo2 fixture2030-rep-mongo3"
CASS="fixture2030-rep-cas1 fixture2030-rep-cas2 fixture2030-rep-cas3"
KS="fixture2030_comentarios"

ahora_utc() { date -u +%Y-%m-%dT%H:%M:%S.%3NZ; }
sello() { date +%Y%m%d-%H%M%S; }
falla() { echo "✖ $*" >&2; exit 1; }
titulo() { printf '\n==== %s\n' "$*"; }

for _i in $(seq 1 12); do docker version >/dev/null 2>&1 && break; sleep 5; done
docker version >/dev/null 2>&1 || falla "Docker no responde: abrí Docker Desktop (o esperá si está con poca memoria)."

# evidencia NOMBRE "comando" — desde acá, todo lo que imprime el script va
# también a evidencia/NOMBRE_<fecha>.txt, con fecha, comando y commit.
evidencia() {
  mkdir -p "$EVID"
  EVID_FILE="$EVID/${1}_$(sello).txt"
  local commit sucio=""
  commit="$(git rev-parse --short HEAD 2>/dev/null || echo sin-git)"
  [ -n "$(git status --porcelain -- . ':!evidencia' 2>/dev/null)" ] && sucio=" (+ cambios sin commitear en el módulo)"
  exec > >(tee "$EVID_FILE") 2>&1
  echo "# Fixture 2030 — Replicación y CAP · $1"
  echo "# fecha:    $(date '+%Y-%m-%d %H:%M:%S %z') ($(date -u +%Y-%m-%dT%H:%M:%SZ))"
  echo "# comando:  $2"
  echo "# commit:   $commit$sucio"
  echo "# docker:   $(docker version --format '{{.Server.Version}}') · $(docker info --format '{{.OperatingSystem}}, {{.NCPU}} CPU, {{.MemTotal}} B RAM')"
}

# dk ARGS... — `docker ARGS`, reintentando SOLO si falla la API de Docker.
# Docker Desktop a veces responde "500 Internal Server Error" durante unos
# segundos cuando la VM está con poca memoria; sin el reintento la prueba se
# cortaría a la mitad. Un error del comando en sí (p. ej. mongosh o cqlsh que
# fallan) no se reintenta: se devuelve tal cual.
dk() {
  local i rc out
  for i in $(seq 1 12); do
    rc=0; out="$(docker "$@" 2>&1)" || rc=$?
    if [ $rc -ne 0 ] && printf '%s' "$out" | grep -q 'Internal Server Error\|error during connect\|Cannot connect to the Docker daemon'; then
      echo "   (la API de Docker no respondió a 'docker $1'; reintento $i/12)" >&2; sleep 5; continue
    fi
    [ -n "$out" ] && printf '%s\n' "$out"
    return $rc
  done
  return 1
}

# ---------------------------------------------------------------- MongoDB --
# msh CONTENEDOR 'js' — mongosh contra el nodo local de ese contenedor.
msh() { dk exec "$1" mongosh --quiet --eval "$2"; }
# msh_rs CONTENEDOR 'js' — mongosh contra el replica set (sigue al primario).
msh_rs() { dk exec "$1" mongosh --quiet "$RS_URI" --eval "$2"; }

# primario_mongo — nombre de host (mongo1..3) del primario actual, o vacío.
primario_mongo() {
  local c
  for c in $MONGOS; do
    if docker ps --format '{{.Names}}' | grep -qx "$c"; then
      msh "$c" 'const h=db.hello(); print(h.primary ? h.primary.split(":")[0] : "")' 2>/dev/null && return 0
    fi
  done
  return 0
}
contenedor_de() { echo "fixture2030-rep-$1"; }      # mongo1 -> fixture2030-rep-mongo1

# estado_rs CONTENEDOR — tabla de miembros vista desde ese nodo.
estado_rs() {
  msh "$1" 'rs.status().members.forEach(m => print("   " + m.name.padEnd(14) + m.stateStr.padEnd(11) +
    " salud=" + m.health + " optime=" + (m.optimeDate ? m.optimeDate.toISOString() : "-") +
    (m.lastHeartbeatMessage ? " · " + m.lastHeartbeatMessage : "")))'
}

# esperar_healthy CONTENEDOR SEGUNDOS
esperar_healthy() {
  local i
  for i in $(seq 1 "$2"); do
    [ "$(docker inspect -f '{{.State.Health.Status}}' "$1" 2>/dev/null)" = healthy ] && return 0; sleep 1
  done; return 1
}

# -------------------------------------------------------------- Cassandra --
# cql CONTENEDOR NIVEL 'sentencias' — cqlsh con CONSISTENCY fijado. Devuelve el
# código de salida de cqlsh (≠ 0 si la operación no alcanza el nivel pedido).
cql() {
  local out rc=0
  out="$(dk exec "$1" cqlsh -e "CONSISTENCY $2; $3" 2>&1)" || rc=$?
  printf '%s\n' "$out" | grep -v -e '^Consistency level set to' -e '^$' || true
  return $rc
}
nodetool() { local c="$1"; shift; dk exec "$c" nodetool "$@"; }

ip_de() { docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$1"; }

# esperar_estado_cas OBSERVADOR IP UN|DN SEGUNDOS — espera a que el OBSERVADOR
# vea al nodo de esa IP en ese estado (nodetool status). Imprime los segundos
# que tardó. Se pasa la IP y no el contenedor: un contenedor parado no tiene IP.
esperar_estado_cas() {
  local t0; t0=$(date +%s)
  while [ $(( $(date +%s) - t0 )) -lt "$4" ]; do
    if nodetool "$1" status 2>/dev/null | grep -qE "^$3 +$2 "; then echo $(( $(date +%s) - t0 )); return 0; fi
    sleep 2
  done
  echo "más de $4"; return 1
}

# hints_en_disco NODO — archivos de hints que ese coordinador guarda para
# réplicas caídas. Se mira el directorio porque `nodetool listpendinghints`
# solo lista un archivo cuando el coordinador lo cierra: mientras se sigue
# escribiendo (réplica todavía caída) no aparece, aunque el hint exista.
hints_en_disco() {
  local l
  l="$(dk exec "$1" sh -c 'cd /var/lib/cassandra/hints && ls -l --time-style=+%H:%M:%S *.hints 2>/dev/null || true' | awk '{print $5 " bytes  " $6 "  " $7}')"
  [ -n "$l" ] && echo "$l" | sed 's/^/     /' || echo "     (ninguno)"
}
# esperar_log CONTENEDOR DESDE_ISO 'regex' SEGUNDOS — espera una línea del log
# posterior a DESDE_ISO; la imprime y devuelve los segundos que tardó.
esperar_log() {
  local t0 l; t0=$(date +%s)
  while [ $(( $(date +%s) - t0 )) -lt "$4" ]; do
    l="$(docker logs --since "$2" "$1" 2>&1 | grep -E "$3" | head -1 || true)"
    [ -n "$l" ] && { echo "$(( $(date +%s) - t0 )) s · $l"; return 0; }
    sleep 2
  done
  echo "no apareció en $4 s"; return 1
}

# motivo 'salida de cqlsh' — el porqué de un error de consistencia, en una línea.
motivo() {
  echo "$1" | grep -oE "Unavailable exception|Cannot achieve consistency level [A-Z_]+|required_replicas[^0-9]*[0-9]+|alive_replicas[^0-9]*[0-9]+|Operation timed out[^.]*|NoHostAvailable"     | sed "s/[\\']//g" | awk '!v[$0]++' | paste -sd'|' - | sed 's/|/ · /g'
}

# Filas de prueba: van a una partición real del Hito 6 (PAR-A-1, ventana de
# las 13:00, bucket 0) con comentario_id PAR-A-1-REP-* para distinguirlas de
# la carga de muestra. Los scripts las borran al final.
PART="partido_id = 'PAR-A-1' AND ventana = '2030-06-09 13:00:00.000+0000' AND bucket = 0"
# insertar_comentario COORDINADOR NIVEL ID 'creado_en' 'contenido'
insertar_comentario() {
  cql "$1" "$2" "INSERT INTO $KS.comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id,
    usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, editado, estado_moderacion)
    VALUES ('PAR-A-1', '2030-06-09 13:00:00.000+0000', 0, '$4', '$3',
    'USR-PRUEBA-REP', 'prueba_replicacion', 'NEUTRAL', 5, '$5', 'es', false, 'PUBLICADO');"
}
# leer_comentario COORDINADOR NIVEL ID 'creado_en' — imprime filas encontradas
# (0 o 1) o el error de cqlsh; devuelve ≠ 0 si la lectura no alcanzó el nivel.
leer_comentario() {
  cql "$1" "$2" "SELECT count(*) FROM $KS.comentarios_por_partido WHERE $PART AND creado_en = '$4' AND comentario_id = '$3';"
}

# memoria — RAM real de cada contenedor de este módulo (docker stats).
memoria() {
  docker stats --no-stream --format '   {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}' $(docker ps --format '{{.Names}}' | grep '^fixture2030-rep-' | sort)
}
