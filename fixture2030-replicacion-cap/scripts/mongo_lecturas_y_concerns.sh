#!/usr/bin/env bash
# ============================================================================
#  Fixture 2030 — Replicación y CAP · MongoDB: lecturas desde secundarios,
#  writeConcern y readConcern
#  USO: bash scripts/mongo_lecturas_y_concerns.sh   (después de mongo_iniciar.sh)
#
#  1. Qué nodo atiende cada readPreference (explain().serverInfo.host).
#  2. Latencia de una escritura con w:1, w:"majority" y w:3.
#  3. Lectura vieja en un secundario y readConcern, de forma DETERMINISTA:
#     se congela la replicación de los dos secundarios con db.fsyncLock()
#     (bloquea la aplicación del oplog) y se cambia el DT de Argentina con w:1.
#     Se compara lo que devuelve cada readConcern y el secundario; después se
#     libera la replicación y se mide cuánto tarda el secundario en converger.
#  El dato modificado (equipos.ARG.entrenador) se RESTAURA al final, y un
#  trap libera los secundarios aunque el script falle.
# ============================================================================
. "$(dirname "$0")/_comun.sh"
evidencia mongo_lecturas_y_concerns "bash scripts/mongo_lecturas_y_concerns.sh"

P="$(primario_mongo)"; [ -n "$P" ] || falla "no hay primario: correr scripts/mongo_iniciar.sh"
PC="$(contenedor_de "$P")"
SECS=""; for c in $MONGOS; do [ "$c" != "$PC" ] && SECS="$SECS $c"; done
S1="$(echo $SECS | cut -d' ' -f1)"

liberar() { for c in $SECS; do msh "$c" 'try { while (db.fsyncUnlock().lockCount > 0); } catch (e) {}' >/dev/null 2>&1 || true; done; }
ORIGINAL=""
restaurar() {   # deja equipos.ARG.entrenador como estaba (también si el script falla)
  [ -n "$ORIGINAL" ] || return 0
  msh_rs "$PC" "db.getSiblingDB('fixture2030').equipos.updateOne({ _id: 'ARG' }, { \$set: { entrenador: '$ORIGINAL' } }, { writeConcern: { w: 'majority' } });
    print('   equipos.ARG.entrenador = \"' + db.getSiblingDB('fixture2030').equipos.findOne({ _id: 'ARG' }).entrenador + '\"')"
  ORIGINAL=""
}
trap 'liberar; restaurar' EXIT

titulo "Estado del replica set (primario: $P)"
estado_rs "$PC"

titulo "1. Lecturas: qué nodo atiende cada readPreference (5 lecturas de equipos.ARG c/u)"
msh_rs "$PC" '
const f = db.getSiblingDB("fixture2030");
for (const rp of ["primary", "primaryPreferred", "secondary", "secondaryPreferred", "nearest"]) {
  const hosts = [];
  for (let i = 0; i < 5; i++) hosts.push(f.equipos.find({ _id: "ARG" }).readPref(rp).explain().serverInfo.host);
  print("   " + rp.padEnd(19) + "-> " + hosts.join(", "));
}'

titulo "2. writeConcern: latencia de 20 escrituras (updateOne de equipos.ARG) con cada nivel"
msh_rs "$PC" '
const f = db.getSiblingDB("fixture2030");
const original = f.equipos.findOne({ _id: "ARG" }).entrenador;
for (let i = 0; i < 10; i++) f.equipos.updateOne({ _id: "ARG" }, { $set: { entrenador: original } }, { writeConcern: { w: 3 } });  // calentamiento
for (const wc of [{ w: 1 }, { w: "majority" }, { w: 3 }]) {
  const ms = [];
  for (let i = 0; i < 20; i++) {
    const t0 = Date.now();
    f.equipos.updateOne({ _id: "ARG" }, { $set: { entrenador: original + " " } }, { writeConcern: wc });
    f.equipos.updateOne({ _id: "ARG" }, { $set: { entrenador: original } }, { writeConcern: wc });
    ms.push((Date.now() - t0) / 2);
  }
  ms.sort((a, b) => a - b);
  print("   " + JSON.stringify(wc).padEnd(18) + "mediana " + ms[10].toFixed(1) + " ms · máx " + ms[19].toFixed(1) +
        " ms   (confirma: " + (wc.w === 1 ? "solo el primario" : wc.w === 3 ? "los 3 nodos" : "2 de 3 nodos") + ")");
}'

titulo "3. Replicación congelada: db.fsyncLock() en los secundarios ($SECS )"
for c in $SECS; do msh "$c" 'print("   " + db.hello().me + " -> " + db.fsyncLock().info)'; done

ORIGINAL="$(msh_rs "$PC" 'print(db.getSiblingDB("fixture2030").equipos.findOne({_id:"ARG"}).entrenador)')"
echo "   valor original de equipos.ARG.entrenador: \"$ORIGINAL\""

titulo "3a. Escritura con w:1 (la confirma solo el primario)"
msh_rs "$PC" '
const r = db.getSiblingDB("fixture2030").equipos.updateOne({ _id: "ARG" }, { $set: { entrenador: "DT nuevo (w:1)" } }, { writeConcern: { w: 1 } });
print("   " + JSON.stringify({ acknowledged: r.acknowledged, modifiedCount: r.modifiedCount }))'

titulo "3b. Qué devuelve cada lectura con la replicación congelada"
msh_rs "$PC" '
const f = db.getSiblingDB("fixture2030");
for (const rc of ["local", "majority", "linearizable"]) {
  let res;
  try {
    const r = f.runCommand({ find: "equipos", filter: { _id: "ARG" }, readConcern: { level: rc }, maxTimeMS: 3000 });
    res = "\"" + r.cursor.firstBatch[0].entrenador + "\"";
  } catch (e) { res = e.codeName + " (no responde en 3 s: prefiere no contestar a contestar algo viejo)"; }
  print("   primario  readConcern " + rc.padEnd(13) + "-> " + res);
}'
msh "$S1" 'db.getMongo().setReadPref("secondary");
print("   " + db.hello().me + " (secundario, readPreference secondary) -> \"" + db.getSiblingDB("fixture2030").equipos.findOne({ _id: "ARG" }).entrenador + "\"   <- lectura vieja")'

titulo "3c. Escritura con w:\"majority\" (wtimeout 3 s) sin mayoría disponible"
msh_rs "$PC" '
try {
  db.getSiblingDB("fixture2030").equipos.updateOne({ _id: "ARG" }, { $set: { entrenador: "DT nuevo (w:majority)" } },
    { writeConcern: { w: "majority", wtimeout: 3000 } });
  print("   confirmada");
} catch (e) {
  print("   -> " + e.codeName + ": " + e.message);
  print("   el primario la aplicó igual (readConcern local): \"" + db.getSiblingDB("fixture2030").equipos.findOne({ _id: "ARG" }).entrenador + "\"");
  print("   el cliente NO recibió confirmación: no puede asumir que sobrevive a una caída del primario");
}'

titulo "3d. Se libera la replicación (db.fsyncUnlock) y se mide la convergencia de $S1"
liberar
msh "$S1" '
db.getMongo().setReadPref("secondary");
const t0 = Date.now(); let v;
while ((v = db.getSiblingDB("fixture2030").equipos.findOne({ _id: "ARG" }).entrenador) !== "DT nuevo (w:majority)" && Date.now() - t0 < 30000) sleep(20);
print("   " + db.hello().me + " ve \"" + v + "\" a los " + (Date.now() - t0) + " ms del desbloqueo");'
msh_rs "$PC" '
const r = db.getSiblingDB("fixture2030").runCommand({ find: "equipos", filter: { _id: "ARG" }, readConcern: { level: "majority" } });
print("   primario readConcern majority -> \"" + r.cursor.firstBatch[0].entrenador + "\"")'

titulo "Restauración del dato original (w:majority)"
restaurar
estado_rs "$PC"
echo
echo "✔ Fin. Evidencia: ${EVID_FILE#$MOD_DIR/}"
