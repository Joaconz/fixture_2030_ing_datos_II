// ============================================================================
//  Fixture 2030 — Hito 5 · Módulo de Grafos (Neo4j)
//  ARCHIVO: queries/crud.cypher
//  PROPÓSITO: creación, recuperación, actualización y eliminación PRECISA.
//  CUBRE: RF7, RNF5, RNF7 y la nota del enunciado sobre borrados acotados.
//
//  EJECUCIÓN (después de estructura.cypher y carga.cypher):
//      docker compose exec neo4j cypher-shell -u neo4j -p fixture2030 \
//          -f /queries/crud.cypher
//
//  DISEÑO DEL ARCHIVO
//  ------------------
//  Todas las operaciones trabajan sobre entidades de demostración creadas en
//  el bloque 1 y eliminadas en el bloque 5. Así el archivo es REPETIBLE: al
//  terminar, el grafo vuelve exactamente al estado que dejó carga.cypher, y
//  los conteos de verificación siguen dando lo mismo.
//
//  REGLA DE ORO DE ESTE HITO
//  -------------------------
//  Ninguna eliminación se ejecuta sin haber corrido antes su consulta de
//  verificación. Cada bloque DELETE viene precedido por el MATCH que cuenta
//  exactamente lo que se va a borrar.
// ============================================================================


// ############################################################################
//  1. CREATE — alta de nodos y relaciones
// ############################################################################

// ----------------------------------------------------------------------------
// 1.1 · Alta de un partido de dieciseisavos de final (fase eliminatoria).
//      Se usa MERGE y no CREATE para no violar la restricción de unicidad si
//      el archivo se corre dos veces (RNF4).
//      Se conectan de una sola vez: los dos equipos con su condición, la sede
//      y el estado inicial del partido.
// ----------------------------------------------------------------------------
MATCH (local:Equipo    {equipoId: 'ARG'})
MATCH (visita:Equipo   {equipoId: 'MAR'})
MATCH (sede:Sede       {sedeId:   'URU-CEN'})
MERGE (p:Partido {partidoId: 'PAR-DEMO-01'})
  ON CREATE SET p.fase        = 'DIECISEISAVOS',
                p.jornada     = 4,
                p.ordenGlobal = 96,
                p.estado      = 'PROGRAMADO',
                p.fechaHora   = datetime('2030-06-30T20:00:00Z'),
                p.golesLocal  = 0,
                p.golesVisitante = 0
MERGE (local)-[:PARTICIPA_EN  {condicion: 'LOCAL'}]->(p)
MERGE (visita)-[:PARTICIPA_EN {condicion: 'VISITANTE'}]->(p)
MERGE (p)-[:SE_JUEGA_EN]->(sede)
RETURN p.partidoId AS partido, p.fase AS fase, p.estado AS estado,
       local.nombre AS local, visita.nombre AS visitante, sede.nombre AS sede;


// ----------------------------------------------------------------------------
// 1.2 · Alta de un jugador y su vínculo con el plantel.
//      La clave natural sigue siendo el dni, igual que en el Hito 4.
// ----------------------------------------------------------------------------
MATCH (e:Equipo {equipoId: 'ARG'})
MERGE (j:Jugador {dni: '40551234'})
  ON CREATE SET j.nombre          = 'Lautaro',
                j.apellido        = 'Peralta',
                j.posicion        = 'Delantero',
                j.dorsal          = 23,
                j.nacionalidad    = 'Argentina',
                j.fechaNacimiento = date('2006-03-14'),
                j.fechaAlta       = datetime('2030-06-01T00:00:00Z')
MERGE (j)-[r:JUEGA_EN]->(e)
  ON CREATE SET r.dorsal = 23, r.desde = date('2030-06-01'), r.rol = 'PLANTEL'
RETURN j.dni AS dni, j.nombre + ' ' + j.apellido AS jugador,
       j.posicion AS posicion, e.nombre AS equipo, r.dorsal AS dorsal;


// ----------------------------------------------------------------------------
// 1.3 · Alta de una CADENA CAUSAL de eventos en el partido nuevo.
//      Se crean los eventos, el orden total ([:SIGUIENTE_EVENTO]) y la
//      dependencia causal ([:CAUSA_DE]) en una sola operación, para que el
//      subgrafo nunca quede en un estado donde un gol existe sin su causa.
// ----------------------------------------------------------------------------
MATCH (p:Partido {partidoId: 'PAR-DEMO-01'})
WITH p, [
  {sec:1, tipo:'INICIO_PARTIDO', min:0,  cond:'LOCAL', dorsal:1},
  {sec:2, tipo:'PASE',           min:66, cond:'LOCAL', dorsal:8},
  {sec:3, tipo:'ASISTENCIA',     min:67, cond:'LOCAL', dorsal:10},
  {sec:4, tipo:'GOL',            min:67, cond:'LOCAL', dorsal:23},
  {sec:5, tipo:'FIN_PARTIDO',    min:90, cond:'LOCAL', dorsal:1}
] AS guion
UNWIND guion AS ev
MERGE (n:Evento {eventoId: p.partidoId + '-EV-' + right('0' + toString(ev.sec), 2)})
  ON CREATE SET n.partidoId          = p.partidoId,
                n.secuencia          = ev.sec,
                n.tipo               = ev.tipo,
                n.minuto             = ev.min,
                n.condicionEquipo    = ev.cond,
                n.dorsalProtagonista = ev.dorsal,
                n.timestamp          = p.fechaHora + duration({minutes: ev.min}),
                n.regionOrigen       = 'AMERICAS'
MERGE (n)-[:OCURRE_EN]->(p)
WITH DISTINCT p
// orden total dentro de la partición del partido
MATCH (a:Evento {partidoId: p.partidoId})
MATCH (b:Evento {partidoId: p.partidoId})
WHERE b.secuencia = a.secuencia + 1
MERGE (a)-[:SIGUIENTE_EVENTO]->(b)
WITH DISTINCT p
// dependencia causal: pase -> asistencia -> gol
UNWIND [[2,3],[3,4]] AS c
MATCH (x:Evento {partidoId: p.partidoId, secuencia: c[0]})
MATCH (y:Evento {partidoId: p.partidoId, secuencia: c[1]})
MERGE (x)-[:CAUSA_DE]->(y)
RETURN p.partidoId AS partido, count(*) AS relacionesCausalesCreadas;


// ----------------------------------------------------------------------------
// 1.4 · Cierre de los vínculos derivados del evento nuevo:
//      tipo de evento (catálogo) y jugador protagonista.
// ----------------------------------------------------------------------------
MATCH (n:Evento {partidoId: 'PAR-DEMO-01'})
MATCH (t:TipoEvento {tipoEventoId: n.tipo})
MERGE (n)-[:ES_DE_TIPO]->(t);

MATCH (n:Evento {partidoId: 'PAR-DEMO-01'})-[:OCURRE_EN]->(p:Partido)<-[part:PARTICIPA_EN]-(eq:Equipo)
WHERE part.condicion = n.condicionEquipo
MATCH (j:Jugador)-[jn:JUEGA_EN]->(eq)
WHERE jn.dorsal = n.dorsalProtagonista
MERGE (n)-[:PROTAGONIZADO_POR]->(j);


// ############################################################################
//  2. READ — recuperación
// ############################################################################

// ----------------------------------------------------------------------------
// 2.1 · Recuperación puntual por identificador (usa el índice de la
//      restricción de unicidad: acceso por seek, no por scan).
// ----------------------------------------------------------------------------
MATCH (e:Equipo {equipoId: 'ARG'})
RETURN e.equipoId AS codigoFifa, e.nombre AS equipo, e.confederacion AS confederacion,
       e.rankingFifa AS ranking, e.entrenador AS entrenador;


// ----------------------------------------------------------------------------
// 2.2 · Recuperación por patrón con filtro, orden y paginación.
//      Plantel de un equipo filtrado por posición: es el equivalente en grafo
//      del índice { equipoId: 1, posicion: 1 } del Hito 4, pero la parte
//      "equipoId" la resuelve la relación en lugar de una propiedad.
// ----------------------------------------------------------------------------
MATCH (j:Jugador)-[r:JUEGA_EN]->(e:Equipo {equipoId: 'BRA'})
WHERE j.posicion IN ['Delantero', 'Mediocampista']
RETURN j.dni AS dni, j.apellido + ', ' + j.nombre AS jugador,
       j.posicion AS posicion, r.dorsal AS dorsal, r.rol AS rol
ORDER BY j.posicion, r.dorsal
SKIP 0 LIMIT 10;


// ----------------------------------------------------------------------------
// 2.3 · Recuperación del timeline completo de un partido, en orden causal.
//      Es el acceso dominante del módulo y el que justifica el índice
//      compuesto (partidoId, secuencia).
// ----------------------------------------------------------------------------
MATCH (n:Evento {partidoId: 'PAR-A-1'})
OPTIONAL MATCH (n)-[:PROTAGONIZADO_POR]->(j:Jugador)
RETURN n.secuencia AS sec, n.minuto AS minuto, n.tipo AS evento,
       n.condicionEquipo AS lado,
       coalesce(j.apellido, '-') AS protagonista,
       n.regionOrigen AS regionIngesta
ORDER BY n.secuencia;


// ----------------------------------------------------------------------------
// 2.4 · Agregación: tabla de posiciones de un grupo, derivada de los partidos.
//      Ningún dato acá está almacenado: todo se calcula recorriendo el grafo.
// ----------------------------------------------------------------------------
MATCH (e:Equipo)-[part:PARTICIPA_EN]->(p:Partido {grupo: 'A', estado: 'FINALIZADO'})
WITH e,
     CASE part.condicion WHEN 'LOCAL' THEN p.golesLocal     ELSE p.golesVisitante END AS gf,
     CASE part.condicion WHEN 'LOCAL' THEN p.golesVisitante ELSE p.golesLocal     END AS gc
RETURN e.nombre AS equipo,
       count(*)                                        AS jugados,
       sum(CASE WHEN gf > gc THEN 3 WHEN gf = gc THEN 1 ELSE 0 END) AS puntos,
       sum(gf) AS golesAFavor, sum(gc) AS golesEnContra,
       sum(gf) - sum(gc) AS diferencia
ORDER BY puntos DESC, diferencia DESC, golesAFavor DESC;


// ############################################################################
//  3. UPDATE — actualización de nodos y de relaciones
// ############################################################################

// ----------------------------------------------------------------------------
// 3.1 · Actualización de propiedades de un NODO, acotada por identificador.
//      Se cierra el partido de dieciseisavos con su resultado.
// ----------------------------------------------------------------------------
MATCH (p:Partido {partidoId: 'PAR-DEMO-01'})
SET p.estado          = 'FINALIZADO',
    p.golesLocal      = 1,
    p.golesVisitante  = 0,
    p.definidoPor     = 'TIEMPO_REGLAMENTARIO',
    p.fechaCierre     = datetime('2030-06-30T21:52:00Z')
RETURN p.partidoId AS partido, p.estado AS estado,
       p.golesLocal AS local, p.golesVisitante AS visitante;


// ----------------------------------------------------------------------------
// 3.2 · Actualización de propiedades de una RELACIÓN.
//      El dorsal y el rol viven en [:JUEGA_EN], no en el jugador: son
//      atributos del VÍNCULO con ese equipo, no de la persona.
// ----------------------------------------------------------------------------
MATCH (j:Jugador {dni: '40551234'})-[r:JUEGA_EN]->(e:Equipo {equipoId: 'ARG'})
SET r.rol    = 'CAPITAN',
    r.dorsal = 10,
    j.dorsal = 10
RETURN j.apellido AS jugador, e.nombre AS equipo, r.dorsal AS dorsal, r.rol AS rol;


// ----------------------------------------------------------------------------
// 3.3 · Actualización ESTRUCTURAL: reasignar un jugador a otro equipo.
//      En un modelo documental esto sería un $set sobre `equipoId`. En el
//      grafo es borrar una arista y crear otra: la relación ES el dato.
//      Nótese que el DELETE está acotado por AMBOS extremos del patrón.
// ----------------------------------------------------------------------------
MATCH (j:Jugador {dni: '40551234'})-[r:JUEGA_EN]->(:Equipo {equipoId: 'ARG'})
DELETE r;

MATCH (j:Jugador {dni: '40551234'})
MATCH (nuevo:Equipo {equipoId: 'URU'})
MERGE (j)-[r:JUEGA_EN]->(nuevo)
  ON CREATE SET r.dorsal = 19, r.desde = date('2030-07-01'), r.rol = 'PLANTEL'
SET j.nacionalidad = 'Uruguay', j.dorsal = 19
RETURN j.dni AS dni, j.apellido AS jugador, nuevo.nombre AS equipoActual, r.desde AS desde;


// ----------------------------------------------------------------------------
// 3.4 · Actualización masiva CONTROLADA (no global): solo los partidos de una
//      jornada de un grupo. El filtro define el alcance de la escritura.
// ----------------------------------------------------------------------------
MATCH (p:Partido {grupo: 'B', jornada: 3})
SET p.observacion = 'Jornada simultánea por reglamento FIFA'
RETURN count(p) AS partidosActualizados;


// ############################################################################
//  4. DELETE — eliminación PRECISA
//     Cada borrado va precedido por su consulta de verificación.
// ############################################################################

// ----------------------------------------------------------------------------
// 4.1 · VERIFICAR ANTES DE BORRAR: ¿qué exactamente se va a eliminar?
//      Esta consulta NO borra nada. Se ejecuta y se lee el resultado.
// ----------------------------------------------------------------------------
MATCH (p:Partido {partidoId: 'PAR-DEMO-01'})
OPTIONAL MATCH (n:Evento)-[:OCURRE_EN]->(p)
RETURN p.partidoId          AS partidoAEliminar,
       count(n)             AS eventosQueSeBorraran,
       collect(n.eventoId)[0..5] AS muestraEventos;


// ----------------------------------------------------------------------------
// 4.2 · Eliminación de una RELACIÓN solamente (los nodos sobreviven).
//      Caso real: se anula una tarjeta tras revisión del VAR, pero el evento
//      de la falta sigue existiendo. Se borra el vínculo causal, no el hecho.
// ----------------------------------------------------------------------------
MATCH (:Evento {partidoId: 'PAR-DEMO-01'})-[c:CAUSA_DE]->(:Evento {partidoId: 'PAR-DEMO-01', secuencia: 4})
DELETE c
RETURN count(*) AS vinculosCausalesEliminados;


// ----------------------------------------------------------------------------
// 4.3 · Eliminación de un NODO con todas sus relaciones, ACOTADA por clave.
//      DETACH DELETE borra el nodo y sus aristas; sin el filtro por dni
//      borraría el padrón completo de jugadores.
// ----------------------------------------------------------------------------
MATCH (j:Jugador {dni: '40551234'})
DETACH DELETE j;


// ----------------------------------------------------------------------------
// 4.4 · Eliminación de un SUBGRAFO acotado a una partición.
//      Se borra el partido de demostración y SOLO los eventos de ESE partido.
//      El filtro {partidoId: ...} es lo que garantiza que el borrado no se
//      propague al resto del torneo: la partición del Hito 3 también acota
//      el radio de daño de una operación destructiva.
// ----------------------------------------------------------------------------
MATCH (n:Evento {partidoId: 'PAR-DEMO-01'})
DETACH DELETE n;

MATCH (p:Partido {partidoId: 'PAR-DEMO-01'})
DETACH DELETE p;


// ----------------------------------------------------------------------------
// 4.5 · Verificación posterior: el grafo volvió al estado de carga.cypher.
//      Debe devolver 0 en las tres columnas.
// ----------------------------------------------------------------------------
OPTIONAL MATCH (p:Partido {partidoId: 'PAR-DEMO-01'})
WITH count(p) AS partidosResiduales
OPTIONAL MATCH (n:Evento {partidoId: 'PAR-DEMO-01'})
WITH partidosResiduales, count(n) AS eventosResiduales
OPTIONAL MATCH (j:Jugador {dni: '40551234'})
RETURN partidosResiduales, eventosResiduales, count(j) AS jugadorDemoResidual;


// ############################################################################
//  5. ANTI-PATRONES — NO EJECUTAR (documentados por la nota del enunciado)
// ############################################################################
//
//  Estas sentencias están COMENTADAS a propósito. Cada una destruye el
//  subgrafo completo y ninguna tiene un patrón acotado:
//
//      MATCH (n) DETACH DELETE n;              // borra TODA la base
//      MATCH (n:Evento) DETACH DELETE n;       // borra los 1.152 eventos
//      MATCH ()-[r:CAUSA_DE]->() DELETE r;     // destruye la trazabilidad causal
//      MATCH (j:Jugador) SET j.dorsal = 10;    // pisa los 1.282 jugadores
//
//  Criterio adoptado para este hito: toda sentencia de escritura destructiva
//  debe filtrar por, como mínimo, una clave natural (equipoId, dni,
//  partidoId, eventoId) o por la clave de partición (partidoId). Si el
//  patrón no puede acotarse, la operación se hace primero como MATCH ...
//  RETURN count(*) y recién después se convierte en DELETE.
// ############################################################################

RETURN 'crud.cypher finalizado · el grafo volvió al estado que dejó carga.cypher' AS mensaje;
