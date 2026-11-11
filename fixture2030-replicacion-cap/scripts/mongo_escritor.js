// ============================================================================
//  Fixture 2030 — Replicación y CAP · escritor continuo para el failover (mongosh)
//  Lo lanza scripts/mongo_failover.sh conectado al REPLICA SET (no a un nodo):
//  el driver sigue al primario y reintenta una vez si cae (retryWrites).
//
//  Cada 200 ms inserta un "latido" en fixture2030_pruebas.latidos con
//  writeConcern majority e imprime una línea JSON por intento:
//    { seq, ini, fin, ms, ok, primario | error }
//  Base aparte (fixture2030_pruebas) para no tocar equipos/jugadores; el
//  script de failover la borra al terminar.
// ============================================================================
const duracion = Number(process.env.DURACION_MS || 75000);
const col = db.getSiblingDB("fixture2030_pruebas").latidos;
const fin = Date.now() + duracion;
let seq = 0;
while (Date.now() < fin) {
  seq++;
  const t0 = new Date();
  const linea = { seq, ini: t0.toISOString() };
  try {
    col.insertOne({ seq, t_cliente: t0 }, { writeConcern: { w: "majority", wtimeout: 5000 } });
    linea.ok = true;
    linea.primario = db.hello().primary;
  } catch (e) {
    linea.ok = false;
    linea.error = e.codeName || e.name;
  }
  const t1 = new Date();
  linea.fin = t1.toISOString();
  linea.ms = t1 - t0;
  print(JSON.stringify(linea));
  sleep(200);
}
