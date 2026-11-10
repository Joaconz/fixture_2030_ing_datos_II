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

# memoria — RAM real de cada contenedor de este módulo (docker stats).
memoria() {
  docker stats --no-stream --format '   {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}' $(docker ps --format '{{.Names}}' | grep '^fixture2030-rep-' | sort)
}
