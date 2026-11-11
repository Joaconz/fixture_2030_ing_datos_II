#!/usr/bin/env bash
# ============================================================================
#  Fixture 2030 — Replicación y CAP · MongoDB: prueba de failover del primario
#  USO: bash scripts/mongo_failover.sh [kill|stop]      (por defecto kill)
#         kill  docker kill: caída abrupta (SIGKILL), como un corte de luz.
#               Los secundarios lo detectan por falta de heartbeats y llaman
#               a elección al vencer electionTimeoutMillis (10 s).
#         stop  docker stop: apagado ordenado (SIGTERM). El primario renuncia
#               (stepdown) y le pasa el lugar a un secundario al apagarse.
#
#  1. Lanza un escritor continuo (scripts/mongo_escritor.js, w:majority cada
#     200 ms) en un nodo que NO es el primario, conectado al replica set.
#  2. Tira el primario y mide, con el reloj de la VM de Docker:
#       - cuándo los sobrevivientes ven un primario nuevo,
#       - las métricas de la elección que registra el propio servidor
#         (replSetGetStatus.electionCandidateMetrics),
#       - qué vio el escritor: hueco sin confirmaciones y a qué primario fue.
#  3. Vuelve a arrancar el nodo caído y verifica que vuelve como SECUNDARIO
#     (no recupera el lugar: prioridades iguales) y que se pone al día con
#     las escrituras que se hicieron mientras estaba caído.
#  No borra volúmenes. Al final borra la base de prueba fixture2030_pruebas.
# ============================================================================
. "$(dirname "$0")/_comun.sh"
MODO="${1:-kill}"
case "$MODO" in kill|stop) ;; *) falla "modo no soportado: $MODO (kill | stop)" ;; esac
PY="$(command -v python3 >/dev/null 2>&1 && python3 -c 1 2>/dev/null && echo python3 || echo python)"
evidencia "mongo_failover_$MODO" "bash scripts/mongo_failover.sh $MODO"

P="$(primario_mongo)"; [ -n "$P" ] || falla "no hay primario: correr scripts/mongo_iniciar.sh"
PC="$(contenedor_de "$P")"
for c in $MONGOS; do docker ps --format '{{.Names}}' | grep -qx "$c" || falla "$c no está corriendo"; done
W=""; for c in $MONGOS; do [ "$c" != "$PC" ] && { W="$c"; break; }; done
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

titulo "ANTES — primario: $P · el escritor corre en $W"
estado_rs "$W"
msh_rs "$W" 'db.getSiblingDB("fixture2030_pruebas").dropDatabase({ writeConcern: { w: "majority" } })' >/dev/null

docker exec -e DURACION_MS=75000 "$W" mongosh --quiet "$RS_URI" --file /scripts/mongo_escritor.js > "$TMP/escritor.jsonl" 2>&1 &
ESCRITOR=$!
sleep 8
echo "   escrituras confirmadas antes de la falla: $(grep -c '"ok":true' "$TMP/escritor.jsonl" || true)"

titulo "FALLA — docker $MODO $PC"
# Referencia de tiempo (reloj de la VM de Docker):
#   kill -> State.FinishedAt: el proceso muere en ese instante.
#   stop -> la hora de la orden: el primario renuncia apenas recibe SIGTERM,
#           aunque el contenedor tarde varios segundos más en terminar.
T_ORDEN="$(dk exec "$W" date -u +%Y-%m-%dT%H:%M:%S.%3NZ)"
if [ "$MODO" = kill ]; then dk kill "$PC" >/dev/null; else dk stop -t 30 "$PC" >/dev/null; fi
T_FIN="$(dk inspect -f '{{.State.FinishedAt}}' "$PC" | cut -c1-23)Z"
if [ "$MODO" = kill ]; then T_FALLA="$T_FIN"; else T_FALLA="$T_ORDEN"; fi
echo "   orden docker $MODO: $T_ORDEN · el contenedor terminó: $T_FIN (State.FinishedAt)"
echo "   referencia de la falla para las mediciones: $T_FALLA"

# Sondeo desde un sobreviviente: hora (reloj de la VM) en que ve un primario nuevo.
NUEVO="$(msh "$W" "
const viejo = '$P:27017'; const t0 = Date.now(); let h;
do { h = db.hello(); if (h.primary && h.primary !== viejo) break; sleep(100); } while (Date.now() - t0 < 60000);
print((h.primary || 'ninguno') + ' ' + new Date().toISOString())")"
NP="$(echo "$NUEVO" | cut -d' ' -f1 | cut -d: -f1)"; T_NP="$(echo "$NUEVO" | cut -d' ' -f2)"
[ "$NP" != ninguno ] || falla "no se eligió primario en 60 s"
NPC="$(contenedor_de "$NP")"
echo "   $W ve como primario a $NP a las $T_NP"
estado_rs "$W"

titulo "ELECCIÓN — métricas que registra el nuevo primario ($NP)"
msh "$NPC" "
const m = db.adminCommand({ replSetGetStatus: 1 }).electionCandidateMetrics;
const falla = new Date('$T_FALLA');
const s = (d) => ((d - falla) / 1000).toFixed(2) + ' s';
print('   motivo de la elección:            ' + m.lastElectionReason);
print('   término (term):                   ' + m.electionTerm);
print('   electionTimeoutMillis:            ' + m.electionTimeoutMillis);
print('   votos necesarios:                 ' + m.numVotesNeeded + ' de 3');
print('   elección ganada (lastElectionDate): ' + m.lastElectionDate.toISOString() + '  -> ' + s(m.lastElectionDate) + ' desde la falla');
for (const k of ['newTermStartDate', 'wMajorityWriteAvailabilityDate'])   // no siempre presentes en 7.0
  if (m[k]) print('   ' + k + ': ' + m[k].toISOString() + '  -> ' + s(m[k]));
print('   el sondeo de $W lo vio primario a: ' + s(new Date('$T_NP')) + '  (el sondeo arranca cuando docker $MODO devuelve el control)');"
for c in $MONGOS; do [ "$c" != "$PC" ] && [ "$c" != "$NPC" ] && O="$c"; done
msh "$O" "
const v = db.adminCommand({ replSetGetStatus: 1 }).electionParticipantMetrics;
if (v) print('   voto de ' + db.hello().me + ': ' + (v.votedForCandidate ? 'a favor' : 'en contra') + ' del miembro ' +
             v.electionCandidateMemberId + ' a las ' + v.lastVoteDate.toISOString() + ' (term ' + v.electionTerm + ')');"

titulo "ESCRITURAS — qué vio el cliente (escritor continuo, w:majority)"
wait "$ESCRITOR" || true
"$PY" scripts/analizar_escritor.py "$T_FALLA" < "$TMP/escritor.jsonl"

titulo "RECUPERACIÓN — docker start $PC"
dk start "$PC" >/dev/null
VUELTA="$(msh "$NPC" "
const yo = '$P:27017'; const t0 = Date.now(); let m;
do { m = rs.status().members.find(x => x.name === yo); if (m.stateStr === 'SECONDARY') break; sleep(200); } while (Date.now() - t0 < 120000);
print(m.stateStr + ' ' + new Date().toISOString())")"
echo "   $P vuelve como $(echo "$VUELTA" | cut -d' ' -f1) a las $(echo "$VUELTA" | cut -d' ' -f2) (visto desde el primario $NP)"
estado_rs "$NPC"

titulo "VERIFICACIÓN — el nodo que volvió tiene todo lo escrito mientras estaba caído"
TOTAL="$(msh_rs "$NPC" 'print(db.getSiblingDB("fixture2030_pruebas").latidos.countDocuments())')"
echo "   $NP (primario)   latidos=$TOTAL"
docker exec -e TOTAL="$TOTAL" "$PC" mongosh --quiet --eval '
db.getMongo().setReadPref("secondaryPreferred");
const total = Number(process.env.TOTAL), t0 = Date.now();
const n = () => db.getSiblingDB("fixture2030_pruebas").latidos.countDocuments();
while (n() < total && Date.now() - t0 < 60000) sleep(100);
print("   " + db.hello().me.split(":")[0] + " (" + (db.hello().isWritablePrimary ? "PRIMARIO" : "secundario") + ") latidos=" + n() +
      " · equipos=" + db.getSiblingDB("fixture2030").equipos.countDocuments() +
      " · jugadores=" + db.getSiblingDB("fixture2030").jugadores.countDocuments() +
      "  (igualó al primario " + (Date.now() - t0) + " ms después de volver a SECONDARY)")'
echo "   (los latidos escritos durante la caída llegaron por replicación del oplog al reincorporarse)"

titulo "Limpieza de la base de prueba"
msh_rs "$NPC" 'print("   " + JSON.stringify(db.getSiblingDB("fixture2030_pruebas").dropDatabase({ writeConcern: { w: "majority" } })))'
echo
echo "✔ Fin. Primario actual: $NP. Evidencia: ${EVID_FILE#$MOD_DIR/}"
