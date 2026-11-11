#!/usr/bin/env bash
# ============================================================================
#  Fixture 2030 — Replicación y CAP · MongoDB Master-Slave: levantar y cargar
#  USO: bash scripts/mongo_iniciar.sh
#
#  1. Levanta los 3 nodos (perfil `mongo`) y espera a que respondan.
#  2. Configura el replica set rs-fixture2030 (scripts/mongo_init_rs.js).
#  3. Aplica el esquema del Hito 4 (fixture2030-mongodb/init/01-validators.js)
#     en el primario, solo si la colección `equipos` todavía no existe.
#  4. Carga equipos y jugadores con fixture2030-mongodb/load/seed.js (Hito 4)
#     conectado al replica set (escribe en el primario, writeConcern majority).
#  5. Verifica que los TRES nodos tengan los mismos datos (lectura directa a
#     cada uno) y registra la RAM usada.
#
#  IDEMPOTENTE: reejecutarlo no reconfigura el replica set, no recrea las
#  colecciones y el seed hace upsert (64 equipos / 1472 jugadores siempre).
# ============================================================================
. "$(dirname "$0")/_comun.sh"
evidencia mongo_iniciar "bash scripts/mongo_iniciar.sh"

titulo "1. Levantar los 3 nodos (perfil mongo)"
$DC --profile mongo up -d mongo1 mongo2 mongo3
for c in $MONGOS; do esperar_healthy "$c" 120 || falla "$c no respondió"; echo "   $c healthy"; done

titulo "2. Replica set (idempotente)"
docker exec fixture2030-rep-mongo1 mongosh --quiet --file /scripts/mongo_init_rs.js
for i in $(seq 1 60); do [ -n "$(primario_mongo)" ] && break; sleep 1; done
P="$(primario_mongo)"; [ -n "$P" ] || falla "no hay primario después de 60 s"
estado_rs fixture2030-rep-mongo1

titulo "3. Esquema del Hito 4 (validadores + índices) en el primario"
if [ "$(msh_rs fixture2030-rep-mongo1 'print(db.getSiblingDB("fixture2030").getCollectionNames().includes("equipos"))')" = true ]; then
  echo "   las colecciones ya existen: no se reaplica (createCollection no es idempotente)"
else
  docker exec fixture2030-rep-mongo1 mongosh --quiet "$RS_URI" --file /fuente/mongodb-init/01-validators.js
fi

titulo "4. Carga de equipos y jugadores (fixture2030-mongodb/load/seed.js)"
$DC --profile carga run --rm mongo-carga

titulo "5. Mismos datos en los tres nodos (lectura directa a cada uno)"
for c in $MONGOS; do
  msh "$c" 'db.getMongo().setReadPref("secondaryPreferred"); const f=db.getSiblingDB("fixture2030");
    print("   " + db.hello().me.padEnd(13) + (db.hello().isWritablePrimary ? "PRIMARIO   " : "SECUNDARIO ") +
          "equipos=" + f.equipos.countDocuments() + " jugadores=" + f.jugadores.countDocuments() +
          " dni distintos=" + f.jugadores.distinct("dni").length)'
done

titulo "6. RAM usada (docker stats)"
memoria
echo
echo "✔ Replica set listo. Primario actual: $(primario_mongo). Evidencia: ${EVID_FILE#$MOD_DIR/}"
