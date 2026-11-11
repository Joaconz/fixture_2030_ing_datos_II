#!/usr/bin/env bash
# ============================================================================
#  Fixture 2030 — Replicación y CAP · Cassandra Peer-to-Peer: levantar y cargar
#  USO: bash scripts/cassandra_iniciar.sh
#
#  1. Levanta los 3 nodos (perfil `cassandra`), de a uno: cas2 espera a que
#     cas1 acepte CQL, cas3 a cas2 (dos bootstraps simultáneos no se admiten).
#  2. Crea el keyspace fixture2030_comentarios con NetworkTopologyStrategy y
#     RF=3 en datacenter1 ANTES de correr el esquema del Hito 6: el
#     `CREATE KEYSPACE IF NOT EXISTS` de esquema.cql (RF=1, pensado para un
#     nodo) queda sin efecto y el resto del archivo se usa tal cual.
#  3. Aplica fixture2030-cassandra/scripts/esquema.cql y carga
#     carga_muestra.cql (112 configuraciones + 80 comentarios, Hito 6) con
#     CONSISTENCY ALL, para arrancar con las tres réplicas iguales.
#  4. Verifica: anillo (3 nodos UN), propiedad efectiva 100 % por nodo (= cada
#     nodo tiene una copia de todo), réplicas de una partición, conteos y RAM.
#
#  IDEMPOTENTE: CREATE ... IF NOT EXISTS, ALTER KEYSPACE al mismo RF (no-op) y
#  la carga de muestra son UPSERT con claves deterministas.
# ============================================================================
. "$(dirname "$0")/_comun.sh"
evidencia cassandra_iniciar "bash scripts/cassandra_iniciar.sh"

titulo "1. Levantar los 3 nodos (perfil cassandra, uno por vez)"
T0=$(date +%s)
$DC --profile cassandra up -d cas1 cas2 cas3
for c in $CASS; do esperar_healthy "$c" 400 || falla "$c no aceptó CQL"; echo "   $c acepta CQL"; done
echo "   anillo listo en $(( $(date +%s) - T0 )) s"
nodetool fixture2030-rep-cas1 status | sed 's/^/   /'

titulo "2. Keyspace con RF=3 (antes del esquema del Hito 6)"
dk exec fixture2030-rep-cas1 cqlsh -e "
CREATE KEYSPACE IF NOT EXISTS $KS
  WITH replication = {'class': 'NetworkTopologyStrategy', 'datacenter1': 3} AND durable_writes = true;
ALTER KEYSPACE $KS
  WITH replication = {'class': 'NetworkTopologyStrategy', 'datacenter1': 3} AND durable_writes = true;"
dk exec fixture2030-rep-cas1 cqlsh -e "SELECT keyspace_name, replication FROM system_schema.keyspaces WHERE keyspace_name = '$KS';" | sed 's/^/   /'

titulo "3a. Esquema del Hito 6 (fixture2030-cassandra/scripts/esquema.cql)"
dk exec fixture2030-rep-cas1 cqlsh -f /fuente/cassandra-scripts/esquema.cql | grep -E '^CREATE (KEYSPACE|TABLE|CUSTOM INDEX|INDEX)' | sed 's/ (.*//; s/^/   /'

titulo "3b. Carga de muestra del Hito 6 (carga_muestra.cql) con CONSISTENCY ALL"
T0=$(date +%s)
dk exec fixture2030-rep-cas1 cqlsh -e "CONSISTENCY ALL; SOURCE '/fuente/cassandra-scripts/carga_muestra.cql';" | grep -v '^Consistency level' | sed 's/^/   /' || true
echo "   carga terminada en $(( $(date +%s) - T0 )) s"

titulo "4. Verificación"
echo "-- propiedad efectiva del keyspace (con RF=3 y 3 nodos, cada nodo guarda el 100 %):"
nodetool fixture2030-rep-cas1 status "$KS" | grep -E 'Address|^UN|^DN' | sed 's/^/   /'
echo "-- réplicas de la partición 'PAR-A-1' de config_particion_partido (nodetool getendpoints):"
for ip in $(nodetool fixture2030-rep-cas1 getendpoints "$KS" config_particion_partido PAR-A-1); do
  echo "   $ip -> $(docker ps --format '{{.Names}}' | grep '^fixture2030-rep-cas' | while read c; do [ "$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$c")" = "$ip" ] && echo "$c"; done)"
done
echo "-- conteos leídos con CONSISTENCY ALL (responden las tres réplicas):"
for t in config_particion_partido comentarios_por_partido comentarios_por_usuario; do
  printf '   %-26s %s\n' "$t" "$(cql fixture2030-rep-cas1 ALL "SELECT count(*) FROM $KS.$t;" | grep -E '^ +[0-9]+$' | tr -d ' ')"
done

titulo "5. RAM usada (docker stats) — heap de cada nodo: MAX_HEAP_SIZE=256M"
memoria
for c in $CASS; do
  echo "   $c: $(nodetool "$c" info | grep -E '^Heap Memory' | sed 's/  */ /g')"
done
echo
echo "✔ Anillo de 3 nodos listo. Evidencia: ${EVID_FILE#$MOD_DIR/}"
