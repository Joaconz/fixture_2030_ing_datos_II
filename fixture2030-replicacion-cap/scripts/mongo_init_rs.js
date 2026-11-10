// ============================================================================
//  Fixture 2030 — Replicación y CAP · configuración del replica set (mongosh)
//  Se ejecuta contra mongo1 desde scripts/mongo_iniciar.sh.
//
//  IDEMPOTENTE: si el replica set ya existe no lo toca (rs.initiate solo se
//  llama cuando el nodo responde NotYetInitialized).
//
//  Topología "Master-Slave" de MongoDB: un PRIMARIO que recibe todas las
//  escrituras y dos SECUNDARIOS que copian su oplog. Las tres prioridades son
//  iguales (1): cualquiera puede ser elegido primario y, cuando el que cayó
//  vuelve, no le quita el lugar al nuevo (no hay "priority takeover").
//  electionTimeoutMillis queda en el valor por defecto (10 000 ms): es lo que
//  mide scripts/mongo_failover.sh.
// ============================================================================
let estado;
try {
  estado = rs.status();
  print("replica set ya iniciado: " + estado.set + " (no se modifica)");
} catch (e) {
  if (e.codeName !== "NotYetInitialized") throw e;
  const cfg = {
    _id: "rs-fixture2030",
    members: [
      { _id: 0, host: "mongo1:27017", priority: 1 },
      { _id: 1, host: "mongo2:27017", priority: 1 },
      { _id: 2, host: "mongo3:27017", priority: 1 },
    ],
  };
  printjson(rs.initiate(cfg));
  print("replica set iniciado: rs-fixture2030");
}

// Espera a que haya un primario (la primera elección tarda unos segundos).
for (let i = 0; i < 60; i++) {
  const h = db.hello();
  if (h.primary) { print("primario: " + h.primary); break; }
  sleep(1000);
}

const conf = rs.conf();
print("configuración vigente (rs.conf):");
print("   electionTimeoutMillis = " + conf.settings.electionTimeoutMillis +
      " · heartbeatIntervalMillis = " + conf.settings.heartbeatIntervalMillis +
      " · writeConcern por defecto = " + JSON.stringify(db.adminCommand({ getDefaultRWConcern: 1 }).defaultWriteConcern));
conf.members.forEach(m => print("   " + m.host + " priority=" + m.priority + " votes=" + m.votes));
