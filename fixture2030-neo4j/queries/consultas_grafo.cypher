// ============================================================================
//  Fixture 2030 — Hito 5 · Módulo de Grafos (Neo4j)
//  ARCHIVO: queries/consultas_grafo.cypher
//  PROPÓSITO: consultas de patrones multi-salto, análisis causal, camino,
//             conectividad y centralidad.
//  CUBRE: RF8 (dos o más saltos), RF9 (camino/conectividad/centralidad),
//         RNF5, RNF7.
//
//  EJECUCIÓN:
//      docker compose exec neo4j cypher-shell -u neo4j -p fixture2030 \
//          -f /queries/consultas_grafo.cypher
//
//  Cada bloque declara: OBJETIVO, RECORRIDO (cuántos saltos y por dónde) y
//  QUÉ APORTA que no se obtiene desde una colección documental aislada.
// ============================================================================


// ############################################################################
//  BLOQUE 1 — CONSULTAS DE PATRÓN DE DOS O MÁS SALTOS  (RF8)
// ############################################################################

// ----------------------------------------------------------------------------
//  1.1 · AGENDA DE UN JUGADOR: ¿en qué estadios y en qué fechas juega?
//
//  OBJETIVO : itinerario individual de un futbolista durante la fase de grupos.
//  RECORRIDO: 3 saltos
//             (Jugador)-[:JUEGA_EN]->(Equipo)-[:PARTICIPA_EN]->(Partido)
//                      -[:SE_JUEGA_EN]->(Sede)
//  APORTE   : en el módulo documental esta pregunta exige tres consultas
//             encadenadas por la aplicación (jugador -> equipoId -> partidos
//             -> sedes). Acá es un solo patrón, y el motor resuelve el camino.
// ----------------------------------------------------------------------------
MATCH (j:Jugador)-[:JUEGA_EN]->(e:Equipo)-[part:PARTICIPA_EN]->(p:Partido)-[:SE_JUEGA_EN]->(s:Sede)
WHERE j.dni = '30000137'
RETURN j.apellido + ', ' + j.nombre AS jugador,
       e.nombre                     AS equipo,
       p.partidoId                  AS partido,
       p.jornada                    AS jornada,
       part.condicion               AS condicion,
       s.nombre + ' (' + s.ciudad + ')' AS sede,
       s.region                     AS regionSede,
       p.fechaHora                  AS fecha
ORDER BY p.fechaHora;


// ----------------------------------------------------------------------------
//  1.2 · RIVALES DE MIS RIVALES: conexión de segundo grado en el fixture.
//
//  OBJETIVO : detectar qué equipos comparten rival con Argentina sin
//             enfrentarla directamente. Es la pregunta que usa el área de
//             scouting para priorizar qué partidos mirar.
//  RECORRIDO: 4 saltos de relación (2 saltos de "rivalidad")
//             (Equipo)-[:PARTICIPA_EN]->(Partido)<-[:PARTICIPA_EN]-(Equipo)
//                     -[:PARTICIPA_EN]->(Partido)<-[:PARTICIPA_EN]-(Equipo)
//  APORTE   : un modelo documental necesitaría dos rondas de $lookup y una
//             deduplicación en la aplicación. Acá el filtro de "no directo"
//             se expresa con NOT (patrón), que es una operación nativa.
// ----------------------------------------------------------------------------
MATCH (origen:Equipo {equipoId: 'ARG'})-[:PARTICIPA_EN]->(p1:Partido)<-[:PARTICIPA_EN]-(rival:Equipo)
MATCH (rival)-[:PARTICIPA_EN]->(p2:Partido)<-[:PARTICIPA_EN]-(segundoGrado:Equipo)
WHERE segundoGrado <> origen
  AND NOT (origen)-[:PARTICIPA_EN]->(:Partido)<-[:PARTICIPA_EN]-(segundoGrado)
RETURN segundoGrado.nombre        AS equipoSegundoGrado,
       segundoGrado.confederacion AS confederacion,
       collect(DISTINCT rival.nombre) AS rivalesEnComun,
       count(DISTINCT p2)         AS partidosDeContacto
ORDER BY partidosDeContacto DESC, equipoSegundoGrado;


// ----------------------------------------------------------------------------
//  1.3 · SEDES POR CONFEDERACIÓN: dónde juega cada confederación.
//
//  OBJETIVO : distribución geográfica del torneo, insumo para logística y
//             para la asignación de réplicas por región del Hito 3.
//  RECORRIDO: 3 saltos (Equipo)->(Partido)->(Sede) + agrupación por región.
// ----------------------------------------------------------------------------
MATCH (e:Equipo)-[:PARTICIPA_EN]->(p:Partido)-[:SE_JUEGA_EN]->(s:Sede)
RETURN e.confederacion AS confederacion,
       s.region        AS regionDeReplica,
       count(DISTINCT p) AS partidos,
       count(DISTINCT s) AS sedesDistintas
ORDER BY confederacion, partidos DESC;


// ############################################################################
//  BLOQUE 2 — ANÁLISIS RELACIONAL SOBRE LA CONSISTENCIA CAUSAL  (Hito 3)
// ############################################################################

// ----------------------------------------------------------------------------
//  2.1 · LA CADENA QUE LLEVÓ AL GOL  ← consulta central del hito
//
//  OBJETIVO : reconstruir, para cada gol de un partido, la secuencia completa
//             de eventos que lo causaron, y quién ejecutó cada eslabón.
//  RECORRIDO: camino de longitud VARIABLE sobre [:CAUSA_DE*1..5], más un
//             salto a [:PROTAGONIZADO_POR] por cada nodo del camino.
//  POR QUÉ IMPORTA (Hito 3):
//             El Hito 3 definió Eventos en vivo como AP con CONSISTENCIA
//             CAUSAL: no se garantiza orden global, pero sí que una asistencia
//             nunca aparezca antes que su gol. Esa garantía no es un
//             comentario en un documento: acá es una ARISTA que se puede
//             recorrer y verificar. Reconstruir la jugada es exactamente
//             recorrer la relación de causalidad hacia atrás.
//  APORTE   : imposible de responder desde una colección de eventos sueltos
//             sin reimplementar el recorrido en la aplicación.
// ----------------------------------------------------------------------------
MATCH ruta = (inicio:Evento)-[:CAUSA_DE*1..5]->(gol:Evento {tipo: 'GOL'})
WHERE gol.partidoId = 'PAR-A-2'
  AND NOT ()-[:CAUSA_DE]->(inicio)          // solo cadenas desde su origen real
RETURN gol.eventoId  AS gol,
       gol.minuto    AS minutoDelGol,
       length(ruta)  AS eslabonesDeLaCadena,
       [n IN nodes(ruta) |
          n.tipo + ' (min ' + toString(n.minuto) + ' · #' +
          toString(n.dorsalProtagonista) + ' ' +
          coalesce([(n)-[:PROTAGONIZADO_POR]->(x:Jugador) | x.apellido][0], '?') + ')'
       ] AS secuenciaCausal
ORDER BY minutoDelGol;


// ----------------------------------------------------------------------------
//  2.2 · VALIDACIÓN DEL INVARIANTE CAUSAL DEL HITO 3
//
//  OBJETIVO : verificar que NINGÚN evento precede a su causa y que ninguna
//             cadena causal cruza la frontera de partición (el partido).
//  RESULTADO ESPERADO: 0 en las dos columnas.
//  APORTE   : convierte una afirmación de diseño del Hito 3 en una asersión
//             ejecutable sobre los datos reales. Es la prueba de que el
//             modelo respeta la consistencia causal, no solo la declara.
// ----------------------------------------------------------------------------
MATCH (causa:Evento)-[:CAUSA_DE]->(efecto:Evento)
RETURN
  sum(CASE WHEN causa.secuencia >= efecto.secuencia THEN 1 ELSE 0 END)
      AS violacionesDeOrdenCausal,
  sum(CASE WHEN causa.partidoId <> efecto.partidoId THEN 1 ELSE 0 END)
      AS cadenasQueCruzanParticion;


// ----------------------------------------------------------------------------
//  2.3 · ESTADÍSTICAS DERIVADAS DEL GRAFO (contraste con el Hito 4)
//
//  OBJETIVO : goleadores y asistidores del torneo.
//  RECORRIDO: 2 saltos (Evento)-[:PROTAGONIZADO_POR]->(Jugador)-[:JUEGA_EN]->(Equipo)
//  APORTE   : en el Hito 4, `jugadores.estadisticas.goles` es un contador
//             DENORMALIZADO que hay que mantener sincronizado en cada
//             escritura. Acá el mismo número se DERIVA del subgrafo de
//             eventos, así que no puede desincronizarse: si el gol existe,
//             el contador lo refleja; si se anula el evento, el contador baja
//             solo. Es la razón concreta por la que N3 conviene como grafo.
// ----------------------------------------------------------------------------
MATCH (n:Evento)-[:PROTAGONIZADO_POR]->(j:Jugador)-[:JUEGA_EN]->(e:Equipo)
WHERE n.tipo IN ['GOL', 'ASISTENCIA']
RETURN j.apellido + ', ' + j.nombre AS jugador,
       e.nombre AS equipo,
       j.posicion AS posicion,
       sum(CASE WHEN n.tipo = 'GOL'        THEN 1 ELSE 0 END) AS goles,
       sum(CASE WHEN n.tipo = 'ASISTENCIA' THEN 1 ELSE 0 END) AS asistencias
ORDER BY goles DESC, asistencias DESC, jugador
LIMIT 15;


// ############################################################################
//  BLOQUE 3 — CAMINO Y CONECTIVIDAD  (RF9)
// ############################################################################

// ----------------------------------------------------------------------------
//  3.1 · CAMINO MÁS CORTO ENTRE DOS EQUIPOS EN LA RED DE RIVALIDADES
//
//  OBJETIVO : ¿cuál es la cadena más corta de enfrentamientos que conecta a
//             dos selecciones? ("Argentina jugó contra X, que jugó contra Y").
//  ALGORITMO: shortestPath sobre [:PARTICIPA_EN] recorrida sin dirección.
//  INTERPRETACIÓN EN EL FIXTURE 2030: mide el "grado de separación deportiva".
//             Sirve para comparar fortalezas de forma indirecta cuando dos
//             equipos todavía no se enfrentaron.
// ----------------------------------------------------------------------------
MATCH (a:Equipo {equipoId: 'ARG'})          // Grupo A
MATCH (b:Equipo {equipoId: 'URU'})          // Grupo B
MATCH ruta = shortestPath( (a)-[:PARTICIPA_EN*..10]-(b) )
RETURN a.nombre AS desde,
       b.nombre AS hasta,
       length(ruta) / 2 AS gradosDeSeparacion,
       [x IN nodes(ruta) | coalesce(x.nombre, x.partidoId)] AS camino;


// ----------------------------------------------------------------------------
//  3.2 · ANÁLISIS DE CONECTIVIDAD: ¿es el fixture un grafo conexo?
//
//  OBJETIVO : medir cuántos equipos son alcanzables desde uno dado, primero
//             usando SOLO partidos de grupos y después con la eliminatoria.
//  HALLAZGO : (a) con solo la fase de grupos se alcanzan 3 equipos — los del
//                 propio grupo. La fase de grupos NO es un grafo conexo: son
//                 16 COMPONENTES AISLADAS de 4 equipos cada una.
//             (b) al sumar los dieciseisavos, la cantidad de alcanzables
//                 crece: las eliminatorias son literalmente las aristas que
//                 unen las componentes.
//  POR QUÉ IMPORTA: esa estructura no es un detalle deportivo, es la
//             justificación empírica de la partición POR PARTIDO del Hito 3.
//             Los recorridos frecuentes (plantel, timeline, jugada del gol)
//             no cruzan la frontera del partido, así que particionar por
//             partido no obliga a coordinar particiones en ninguna consulta
//             caliente. Esto es visible en el grafo y NO lo es en una
//             colección de documentos.
// ----------------------------------------------------------------------------
// (a) Solo fase de grupos
MATCH ruta = (origen:Equipo {equipoId: 'ARG'})-[:PARTICIPA_EN*1..8]-(otro:Equipo)
WHERE otro <> origen
  AND all(x IN nodes(ruta) WHERE NOT x:Partido OR x.fase = 'GRUPOS')
RETURN 'Solo fase de grupos' AS escenario,
       count(DISTINCT otro)  AS equiposAlcanzables,
       collect(DISTINCT otro.nombre) AS alcanzados;

// (b) Fase de grupos + dieciseisavos
MATCH (origen:Equipo {equipoId: 'ARG'})-[:PARTICIPA_EN*1..8]-(otro:Equipo)
WHERE otro <> origen
RETURN 'Grupos + dieciseisavos' AS escenario,
       count(DISTINCT otro)     AS equiposAlcanzables;


// ----------------------------------------------------------------------------
//  3.3 · TAMAÑO DE CADA COMPONENTE (verificación del hallazgo anterior)
//        Cada grupo debe dar exactamente 4 equipos y 6 partidos.
// ----------------------------------------------------------------------------
MATCH (g:Grupo)<-[:PERTENECE_A]-(e:Equipo)
WITH g, count(e) AS equipos
MATCH (p:Partido)-[:CORRESPONDE_A]->(g)
RETURN g.grupoId AS grupo, equipos, count(p) AS partidos
ORDER BY grupo;


// ############################################################################
//  BLOQUE 4 — CENTRALIDAD  (RF9)
// ############################################################################

// ----------------------------------------------------------------------------
//  4.1 · CENTRALIDAD DE GRADO EN LA RED DE CAUSALIDAD
//
//  OBJETIVO : identificar a los jugadores más determinantes, entendiendo
//             "determinante" no como "el que hizo el gol" sino como
//             "el que aparece en más cadenas causales que terminan en gol".
//  ALGORITMO: centralidad de grado calculada en Cypher puro sobre
//             [:CAUSA_DE*1..4], sin depender de la versión de GDS.
//  INTERPRETACIÓN: un mediocampista que nunca convierte pero inicia muchas
//             jugadas de gol tiene centralidad alta y goles cero. Ese perfil
//             es INVISIBLE en la tabla de goleadores del módulo documental y
//             solo aparece si el dato se recorre como relaciones.
// ----------------------------------------------------------------------------
MATCH (n:Evento)-[:PROTAGONIZADO_POR]->(j:Jugador)-[:JUEGA_EN]->(e:Equipo)
MATCH (n)-[:CAUSA_DE*1..4]->(gol:Evento {tipo: 'GOL'})
WITH j, e,
     count(DISTINCT gol) AS golesEnLosQueIntervino,
     count(DISTINCT n)   AS eventosCausalesPropios
RETURN j.apellido + ', ' + j.nombre AS jugador,
       e.nombre   AS equipo,
       j.posicion AS posicion,
       golesEnLosQueIntervino,
       eventosCausalesPropios,
       golesEnLosQueIntervino * 1.0 / eventosCausalesPropios AS impactoPorIntervencion
ORDER BY golesEnLosQueIntervino DESC, jugador
LIMIT 20;


// ----------------------------------------------------------------------------
//  4.2 · CENTRALIDAD DE SEDES: qué estadios concentran el torneo.
//        Insumo directo para el dimensionamiento por región del Hito 3.
// ----------------------------------------------------------------------------
MATCH (s:Sede)<-[:SE_JUEGA_EN]-(p:Partido)<-[:PARTICIPA_EN]-(e:Equipo)
RETURN s.nombre AS sede, s.ciudad AS ciudad, s.region AS regionDeReplica,
       count(DISTINCT p) AS partidos,
       count(DISTINCT e) AS equiposDistintos,
       count(DISTINCT e.confederacion) AS confederacionesDistintas
ORDER BY partidos DESC, equiposDistintos DESC;


// ----------------------------------------------------------------------------
//  4.3 · [OPCIONAL] Lo mismo con Graph Data Science.
//        El plugin GDS está habilitado en el docker-compose. La SINTAXIS DE
//        PROYECCIÓN CAMBIA ENTRE VERSIONES MAYORES DE GDS y la imagen es
//        `latest`, así que este bloque queda comentado: la respuesta oficial
//        del hito es la de Cypher puro (4.1/4.2), que no depende de eso.
//        Si el entorno lo admite, descomentar y registrar la versión con:
//            RETURN gds.version();
//
//  // Proyección de la red de rivalidades (GDS 2.4+, sintaxis de agregación)
//  MATCH (a:Equipo)-[:PARTICIPA_EN]->(:Partido)<-[:PARTICIPA_EN]-(b:Equipo)
//  WHERE a <> b
//  RETURN gds.graph.project('rivalidades2030', a, b) AS g;
//
//  // Centralidad de grado sobre esa proyección
//  CALL gds.degree.stream('rivalidades2030')
//  YIELD nodeId, score
//  RETURN gds.util.asNode(nodeId).nombre AS equipo, score AS grado
//  ORDER BY grado DESC LIMIT 10;
//
//  // Limpieza de la proyección en memoria
//  CALL gds.graph.drop('rivalidades2030') YIELD graphName RETURN graphName;
// ----------------------------------------------------------------------------


// ############################################################################
//  BLOQUE 5 — CONSULTAS DE PROGRAMACIÓN DEL FIXTURE
// ############################################################################

// ----------------------------------------------------------------------------
//  5.1 · Cruces de una jornada con sus dos equipos y su sede, en una sola
//        consulta. Los dos equipos se distinguen por la propiedad de la
//        RELACIÓN, no por dos campos distintos del nodo partido.
// ----------------------------------------------------------------------------
MATCH (loc:Equipo)-[:PARTICIPA_EN {condicion: 'LOCAL'}]->(p:Partido {jornada: 1})
MATCH (vis:Equipo)-[:PARTICIPA_EN {condicion: 'VISITANTE'}]->(p)
MATCH (p)-[:SE_JUEGA_EN]->(s:Sede)
RETURN p.grupo AS grupo,
       loc.nombre + ' ' + toString(p.golesLocal) + ' - ' +
       toString(p.golesVisitante) + ' ' + vis.nombre AS resultado,
       s.nombre AS sede, s.region AS region, p.fechaHora AS fecha
ORDER BY p.fechaHora, grupo;


// ----------------------------------------------------------------------------
//  5.2 · Detección de conflictos de programación: dos partidos en la misma
//        sede con menos de 24 horas de diferencia.
// ----------------------------------------------------------------------------
MATCH (p1:Partido)-[:SE_JUEGA_EN]->(s:Sede)<-[:SE_JUEGA_EN]-(p2:Partido)
WHERE p1.partidoId < p2.partidoId
  AND duration.between(p1.fechaHora, p2.fechaHora).days < 1
  AND duration.between(p1.fechaHora, p2.fechaHora).days > -1
RETURN s.nombre AS sede, p1.partidoId AS partidoA, p1.fechaHora AS fechaA,
       p2.partidoId AS partidoB, p2.fechaHora AS fechaB
ORDER BY sede, fechaA;


// ############################################################################
//  BLOQUE 6 — AUDITORÍA DE INTEGRIDAD DEL SUBGRAFO  (RNF7 / RF11)
//  Sustituye, en Community Edition, a las restricciones de existencia que solo
//  ofrece Enterprise. Todos los valores esperados son 0.
// ############################################################################

// 6.1 · Eventos sin partido (huérfanos respecto de su partición)
MATCH (n:Evento)
WHERE NOT (n)-[:OCURRE_EN]->(:Partido)
RETURN count(n) AS eventosHuerfanos;

// 6.2 · Eventos cuyo tipo no existe en el catálogo N8
MATCH (n:Evento)
WHERE NOT (n)-[:ES_DE_TIPO]->(:TipoEvento)
RETURN count(n) AS eventosConTipoDesconocido;

// 6.3 · Jugadores sin equipo (equivalente al chequeo de relaciones huérfanas
//       del Hito 4: "el 100% de los jugadores queda vinculado a un equipo")
MATCH (j:Jugador)
WHERE NOT (j)-[:JUEGA_EN]->(:Equipo)
RETURN count(j) AS jugadoresSinEquipo;

// 6.4 · Partidos que no tienen exactamente un local y un visitante
MATCH (p:Partido)
OPTIONAL MATCH (:Equipo)-[l:PARTICIPA_EN {condicion: 'LOCAL'}]->(p)
OPTIONAL MATCH (:Equipo)-[v:PARTICIPA_EN {condicion: 'VISITANTE'}]->(p)
WITH p, count(DISTINCT l) AS locales, count(DISTINCT v) AS visitantes
WHERE locales <> 1 OR visitantes <> 1
RETURN count(p) AS partidosMalFormados;

// 6.5 · Cadenas de orden total rotas (huecos en [:SIGUIENTE_EVENTO])
MATCH (n:Evento)
WHERE NOT (n)-[:SIGUIENTE_EVENTO]->()          // debería ser solo el FIN_PARTIDO
  AND n.tipo <> 'FIN_PARTIDO'
RETURN count(n) AS eventosSinSucesorIndebido;

// 6.6 · Marcador almacenado vs. goles contados en el grafo
MATCH (p:Partido {estado: 'FINALIZADO'})
OPTIONAL MATCH (gl:Evento)-[:OCURRE_EN]->(p)
  WHERE gl.tipo = 'GOL' AND gl.condicionEquipo = 'LOCAL'
WITH p, count(gl) AS golesLocalReales
OPTIONAL MATCH (gv:Evento)-[:OCURRE_EN]->(p)
  WHERE gv.tipo = 'GOL' AND gv.condicionEquipo = 'VISITANTE'
WITH p, golesLocalReales, count(gv) AS golesVisitanteReales
WHERE p.golesLocal <> golesLocalReales OR p.golesVisitante <> golesVisitanteReales
RETURN count(p) AS partidosConMarcadorInconsistente;

// 6.7 · Resumen del subgrafo (evidencia final, RF11)
MATCH (n)
RETURN labels(n)[0] AS etiqueta, count(*) AS nodos
ORDER BY etiqueta;

MATCH ()-[r]->()
RETURN type(r) AS relacion, count(*) AS relaciones
ORDER BY relacion;
