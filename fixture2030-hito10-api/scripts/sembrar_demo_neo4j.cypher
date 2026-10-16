// ============================================================================
//  Fixture 2030 — Hito 10 · API REST integrada
//  ARCHIVO: scripts/sembrar_demo_neo4j.cypher
//  PROPÓSITO: partido de demostración para las escrituras de la API
//             (CU6 registrar evento, CU7 cerrar partido).
//
//  EJECUCIÓN (desde fixture2030-hito10-api/, con el grafo del Hito 5 cargado):
//      docker exec -i fixture2030-neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" \
//          < scripts/sembrar_demo_neo4j.cypher
//
//  POR QUÉ UN PARTIDO APARTE
//  -------------------------
//  Los 96 partidos de grupos de carga.cypher están FINALIZADO y los 16
//  dieciseisavos (PAR-D16-*) no tienen eventos. Escribir sobre ellos alteraría
//  el grafo que es evidencia del Hito 5. `PAR-DEMO-API` (fase 'DEMO') queda
//  fuera de cualquier consulta por fase GRUPOS/DIECISEISAVOS.
//
//  IDEMPOTENTE Y RESETEABLE
//  ------------------------
//  Todo se escribe con MERGE sobre clave natural (igual que carga.cypher) y,
//  además, cada corrida DEJA EL PARTIDO EN EL ESTADO INICIAL de la demo:
//    · estado 'PROGRAMADO', sin golesLocal/golesVisitante/cerradoEn;
//    · se borran todos sus eventos salvo los 3 de carga (los de origen 'API'
//      que dejó una demo anterior, y también los que crearía el paso 7 de
//      carga.cypher si se re-ejecuta después de este script, porque ese paso
//      recorre TODOS los :Partido con sede);
//    · quedan exactamente PAR-DEMO-API-EV-01..03, sin FIN_PARTIDO.
//
//  FLUJO DE DEMO ESPERADO (Postman / curl)
//  ---------------------------------------
//   1. POST /partidos/PAR-DEMO-API/eventos (clave K1)        → 201, secuencia 4
//   2. mismo POST, misma clave K1                            → 200 + Idempotent-Replayed
//   3. PATCH /partidos/PAR-DEMO-API/estado                   → 409 MISSING_FIN_PARTIDO
//   4. POST evento FIN_PARTIDO (clave K2)                    → 201
//   5. PATCH /partidos/PAR-DEMO-API/estado                   → 200, marcador derivado
//   6. PATCH otra vez                                        → 409 INVALID_TRANSITION
//   7. POST otro evento (clave K3)                           → 409 MATCH_FINALIZED
//  Para repetirla: volver a ejecutar este archivo.
// ============================================================================


// ----------------------------------------------------------------------------
// 1. PARTIDO: Argentina (LOCAL) vs Brasil (VISITANTE) en el Centenario.
//    Los tres nodos referenciados existen en carga.cypher (pasos 2 y 4); si no
//    estuvieran, el MATCH no devuelve filas y el script no crea nada a medias.
// ----------------------------------------------------------------------------
MATCH (loc:Equipo {equipoId: 'ARG'}), (vis:Equipo {equipoId: 'BRA'}), (s:Sede {sedeId: 'URU-CEN'})
MERGE (p:Partido {partidoId: 'PAR-DEMO-API'})
SET p.fase = 'DEMO', p.estado = 'PROGRAMADO',
    p.fechaHora = datetime('2030-07-20T16:00:00Z')
REMOVE p.golesLocal, p.golesVisitante, p.cerradoEn, p.grupo, p.jornada, p.ordenGlobal, p._lockApi
MERGE (loc)-[:PARTICIPA_EN {condicion: 'LOCAL'}]->(p)
MERGE (vis)-[:PARTICIPA_EN {condicion: 'VISITANTE'}]->(p)
MERGE (p)-[:SE_JUEGA_EN]->(s);


// ----------------------------------------------------------------------------
// 2. RESET: borrar todo evento del partido que no sea de la carga de demo.
//    Se buscan por la propiedad de partición y por la relación, para no dejar
//    huérfanos aunque alguno haya quedado sin una de las dos.
// ----------------------------------------------------------------------------
MATCH (n:Evento)
WHERE (n.partidoId = 'PAR-DEMO-API'
       OR EXISTS { (n)-[:OCURRE_EN]->(:Partido {partidoId: 'PAR-DEMO-API'}) })
  AND NOT n.eventoId IN ['PAR-DEMO-API-EV-01', 'PAR-DEMO-API-EV-02', 'PAR-DEMO-API-EV-03']
DETACH DELETE n;


// ----------------------------------------------------------------------------
// 3. EVENTOS DE CARGA (3): inicio, pase y gol del local. Sin FIN_PARTIDO, para
//    que la demo pueda mostrar el 409 MISSING_FIN_PARTIDO antes del cierre.
//    INICIO_PARTIDO va sin protagonista, igual que exige la regla N8 de la API.
//    Se eliminan relaciones previas de los 3 nodos y se recrean, así una corrida
//    sobre un estado alterado vuelve exactamente al mismo subgrafo.
// ----------------------------------------------------------------------------
MATCH (p:Partido {partidoId: 'PAR-DEMO-API'})-[:SE_JUEGA_EN]->(s:Sede)
UNWIND [
  {sec: 1, tipo: 'INICIO_PARTIDO', min: 0,  cond: null,    dorsal: null},
  {sec: 2, tipo: 'PASE',           min: 10, cond: 'LOCAL', dorsal: 5},
  {sec: 3, tipo: 'GOL',            min: 11, cond: 'LOCAL', dorsal: 9}
] AS ev
MERGE (n:Evento {eventoId: 'PAR-DEMO-API-EV-0' + toString(ev.sec)})
SET n.partidoId = p.partidoId, n.secuencia = ev.sec, n.tipo = ev.tipo, n.minuto = ev.min,
    n.condicionEquipo = ev.cond, n.dorsalProtagonista = ev.dorsal,
    n.timestamp = p.fechaHora + duration({minutes: ev.min}),
    n.regionOrigen = s.region
REMOVE n.origen, n.huella, n.registradoEn
WITH n, p
OPTIONAL MATCH (n)-[r:OCURRE_EN|ES_DE_TIPO|PROTAGONIZADO_POR|SIGUIENTE_EVENTO]-()
DELETE r
WITH DISTINCT n, p
MERGE (n)-[:OCURRE_EN]->(p)
WITH n
MATCH (t:TipoEvento {tipoEventoId: n.tipo})
MERGE (n)-[:ES_DE_TIPO]->(t);


// ----------------------------------------------------------------------------
// 4. PROTAGONISTAS: mismo recorrido de resolución que el paso 9 de carga.cypher
//    (condición → equipo del partido → plantel por dorsal).
// ----------------------------------------------------------------------------
MATCH (n:Evento)-[:OCURRE_EN]->(p:Partido {partidoId: 'PAR-DEMO-API'})<-[part:PARTICIPA_EN]-(eq:Equipo)
WHERE part.condicion = n.condicionEquipo
MATCH (j:Jugador)-[jn:JUEGA_EN]->(eq)
WHERE jn.dorsal = n.dorsalProtagonista
MERGE (n)-[:PROTAGONIZADO_POR]->(j);


// ----------------------------------------------------------------------------
// 5. ORDEN TOTAL DENTRO DE LA PARTICIÓN: EV-01 → EV-02 → EV-03.
// ----------------------------------------------------------------------------
MATCH (a:Evento)-[:OCURRE_EN]->(:Partido {partidoId: 'PAR-DEMO-API'})<-[:OCURRE_EN]-(b:Evento)
WHERE b.secuencia = a.secuencia + 1
MERGE (a)-[:SIGUIENTE_EVENTO]->(b);


// ----------------------------------------------------------------------------
// 6. VERIFICACIÓN: correrlo dos veces seguidas debe mostrar lo mismo
//    (PROGRAMADO, 3 eventos, secuencias 1..3, sin FIN_PARTIDO).
// ----------------------------------------------------------------------------
MATCH (p:Partido {partidoId: 'PAR-DEMO-API'})
OPTIONAL MATCH (n:Evento)-[:OCURRE_EN]->(p)
OPTIONAL MATCH (n)-[:PROTAGONIZADO_POR]->(j:Jugador)
WITH p, n, j ORDER BY n.secuencia
RETURN p.partidoId AS partido, p.estado AS estado, p.golesLocal AS golesLocal,
       collect(toString(n.secuencia) + ':' + n.tipo + coalesce(' (' + j.apellido + ')', '')) AS eventos;
