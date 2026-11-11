// ============================================================================
//  Fixture 2030 — Hito 5 · Módulo de Grafos (Neo4j)
//  ARCHIVO: queries/consultas_grafo.cypher
//  PROPÓSITO: consultas de patrones multi-salto, análisis causal, camino,
//             conectividad y centralidad; consultas y análisis sobre las
//             relaciones del enunciado (PARTICIPA, ANOTA, ASISTE,
//             RECIBE_TARJETA, REEMPLAZA).
//  CUBRE: RF8 (dos o más saltos), RF9 (camino/conectividad/centralidad),
//         RNF5, RNF7.
//  CONSULTAS NUMERADAS (19): 1.1-1.3, 2.1-2.3, 3.1-3.3, 4.1-4.2, 5.1-5.2,
//         7.1-7.5; más el análisis de relaciones (8.1-8.3) y la auditoría
//         (6.1-6.9).
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
//             (b) al sumar las eliminatorias (dieciseisavos a final), la
//                 cantidad de alcanzables crece: las eliminatorias son
//                 literalmente las aristas que unen las componentes.
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

// (b) Fase de grupos + eliminatorias
MATCH (origen:Equipo {equipoId: 'ARG'})-[:PARTICIPA_EN*1..8]-(otro:Equipo)
WHERE otro <> origen
RETURN 'Grupos + eliminatorias' AS escenario,
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
//        Se mide en segundos: `duration.between(...).days` ignora los meses
//        (11/06 -> 11/07 da P1M, con days = 0) y marcaba falsos conflictos
//        entre grupos y eliminatorias.
// ----------------------------------------------------------------------------
MATCH (p1:Partido)-[:SE_JUEGA_EN]->(s:Sede)<-[:SE_JUEGA_EN]-(p2:Partido)
WHERE p1.partidoId < p2.partidoId
  AND abs(duration.inSeconds(p1.fechaHora, p2.fechaHora).seconds) < 86400
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

// 6.7 · Relaciones del enunciado vs. eventos de origen. Son proyecciones
//       (carga.cypher, paso 18): cada una debe tener su evento y cada evento
//       su proyección. Todas las columnas deben dar 0.
RETURN
  COUNT { MATCH (g:Evento {tipo: 'GOL'})-[:PROTAGONIZADO_POR]->(j:Jugador)
          WHERE NOT (j)-[:ANOTA {eventoId: g.eventoId}]->(:Partido {partidoId: g.partidoId}) }
      AS golesSinAnota,
  COUNT { MATCH (a:Evento {tipo: 'ASISTENCIA'})-[:CAUSA_DE]->(:Evento {tipo: 'GOL'})
          WHERE NOT ()-[:ASISTE {eventoId: a.eventoId}]->() }
      AS asistenciasSinAsiste,
  COUNT { MATCH (t:Evento) WHERE t.tipo IN ['TARJETA_AMARILLA', 'TARJETA_ROJA']
            AND NOT ()-[:RECIBE_TARJETA {eventoId: t.eventoId}]->() }
      AS tarjetasSinRecibeTarjeta,
  COUNT { MATCH (s:Evento {tipo: 'SUSTITUCION'}) WHERE s.dorsalSaliente IS NOT NULL
            AND NOT ()-[:REEMPLAZA {eventoId: s.eventoId}]->() }
      AS sustitucionesSinReemplaza,
  COUNT { MATCH ()-[r:ANOTA|ASISTE|RECIBE_TARJETA|REEMPLAZA]->()
          WHERE NOT EXISTS { MATCH (:Evento {eventoId: r.eventoId}) } }
      AS proyeccionesSinEvento,
  COUNT { MATCH (j:Jugador)-[:ANOTA|RECIBE_TARJETA]->(p:Partido)
          WHERE NOT (j)-[:PARTICIPA]->(p) }
      AS actuacionesSinParticipa;

// 6.8 · Cuadro eliminatorio: ningún partido jugado terminó empatado y quien
//       pasó de ronda es quien ganó por goles (marcador derivado, paso 17).
//       Las dos columnas deben dar 0.
MATCH (p:Partido)
WHERE p.fase IN ['DIECISEISAVOS', 'OCTAVOS', 'CUARTOS', 'SEMIFINAL']
MATCH (gan:Equipo)-[c:PARTICIPA_EN]->(p)
WHERE c.condicion = CASE WHEN p.golesLocal > p.golesVisitante THEN 'LOCAL' ELSE 'VISITANTE' END
WITH p, gan,
     {DIECISEISAVOS: 'OCTAVOS', OCTAVOS: 'CUARTOS', CUARTOS: 'SEMIFINAL', SEMIFINAL: 'FINAL'}[p.fase]
       AS faseSiguiente
RETURN
  sum(CASE WHEN p.golesLocal = p.golesVisitante THEN 1 ELSE 0 END) AS empatesEnEliminatoria,
  sum(CASE WHEN EXISTS { (gan)-[:PARTICIPA_EN]->(:Partido {fase: faseSiguiente}) }
           THEN 0 ELSE 1 END)                                   AS ganadoresQueNoAvanzaron;

// 6.9 · Resumen del subgrafo (evidencia final, RF11)
MATCH (n)
RETURN labels(n)[0] AS etiqueta, count(*) AS nodos
ORDER BY etiqueta;

MATCH ()-[r]->()
RETURN type(r) AS relacion, count(*) AS relaciones
ORDER BY relacion;

MATCH (p:Partido)
WITH p, COUNT { (:Evento)-[:OCURRE_EN]->(p) } AS eventos
RETURN p.fase AS fase, p.estado AS estado, count(p) AS partidos, sum(eventos) AS eventos
ORDER BY min(p.ordenGlobal);


// ############################################################################
//  BLOQUE 7 — CONSULTAS SOBRE LAS RELACIONES DEL ENUNCIADO
//  PARTICIPA, ANOTA, ASISTE, RECIBE_TARJETA y REEMPLAZA (carga.cypher, paso
//  18). Son la proyección del subgrafo de eventos: la misma pregunta se puede
//  responder desde los :Evento con un salto más; acá se responde directo.
// ############################################################################

// ----------------------------------------------------------------------------
//  7.1 · GOLEADORES CON SUS ASISTIDORES
//
//  OBJETIVO : tabla de goleadores del torneo y, para cada uno, quiénes le
//             dieron los pases de gol y cuántos.
//  RECORRIDO: 2 saltos por gol
//             (Jugador)-[:ANOTA]->(Partido)  y  (Jugador)-[:ASISTE]->(Jugador)
//             unidos por el evento de gol (ASISTE.golEventoId = ANOTA.eventoId)
//  APORTE   : la sociedad asistidor-goleador es una relación ENTRE dos
//             jugadores. En el módulo documental son dos contadores sueltos
//             (`estadisticas.goles`, `estadisticas.asistencias`) que no dicen
//             quién asistió a quién.
// ----------------------------------------------------------------------------
MATCH (goleador:Jugador)-[an:ANOTA]->(:Partido)
MATCH (goleador)-[:JUEGA_EN]->(e:Equipo)
OPTIONAL MATCH (asistidor:Jugador)-[:ASISTE {golEventoId: an.eventoId}]->(goleador)
WITH goleador, e, asistidor, count(an) AS goles
WITH goleador, e, sum(goles) AS goles,
     collect(CASE WHEN asistidor IS NULL THEN null
                  ELSE asistidor.apellido + ' #' + toString(asistidor.dorsal)
                       + ' (' + toString(goles) + ')' END) AS asistidores
RETURN goleador.apellido + ', ' + goleador.nombre AS goleador,
       e.nombre AS equipo,
       goles,
       asistidores
ORDER BY goles DESC, goleador
LIMIT 15;


// ----------------------------------------------------------------------------
//  7.2 · TARJETAS POR PARTIDO
//
//  OBJETIVO : disciplina de cada partido jugado: cuántas amarillas y rojas,
//             de qué equipo y a quién. Los partidos sin tarjetas también
//             aparecen (con 0), por eso el OPTIONAL MATCH.
//  RECORRIDO: (Partido)<-[:RECIBE_TARJETA]-(Jugador)-[:JUEGA_EN]->(Equipo)
//  APORTE   : el tipo de tarjeta vive en la relación, así que "rojas por
//             fase" es un filtro de arista y no un join con el catálogo.
// ----------------------------------------------------------------------------
MATCH (p:Partido {estado: 'FINALIZADO'})
OPTIONAL MATCH (p)<-[t:RECIBE_TARJETA]-(j:Jugador)-[:JUEGA_EN]->(e:Equipo)
WITH p, t, j, e ORDER BY t.minuto
WITH p,
     count(t) AS tarjetas,
     sum(CASE t.tipo WHEN 'AMARILLA' THEN 1 ELSE 0 END) AS amarillas,
     sum(CASE t.tipo WHEN 'ROJA'     THEN 1 ELSE 0 END) AS rojas,
     collect(e.equipoId + ' · ' + j.apellido + ' #' + toString(j.dorsal) + ' · '
             + t.tipo + ' ' + toString(t.minuto) + "'") AS detalle
RETURN p.partidoId AS partido, p.fase AS fase, tarjetas, amarillas, rojas, detalle
ORDER BY rojas DESC, p.ordenGlobal
LIMIT 20;

// Resumen por fase (todos los partidos jugados de la fase).
MATCH (p:Partido {estado: 'FINALIZADO'})
WITH p, COUNT { (p)<-[:RECIBE_TARJETA {tipo: 'AMARILLA'}]-() } AS am,
        COUNT { (p)<-[:RECIBE_TARJETA {tipo: 'ROJA'}]-() }     AS ro
RETURN p.fase AS fase, count(p) AS partidos, sum(am) AS amarillas, sum(ro) AS rojas,
       round(toFloat(sum(am) + sum(ro)) / count(p), 2) AS tarjetasPorPartido
ORDER BY min(p.ordenGlobal);


// ----------------------------------------------------------------------------
//  7.3 · CADENA DE REEMPLAZOS
//
//  OBJETIVO : encadenar sustituciones dentro de un plantel: A entró por B, y
//             B (en otro partido) había entrado por C. Muestra qué jugadores
//             rotan en el mismo puesto a lo largo del torneo.
//  RECORRIDO: camino de longitud VARIABLE (Jugador)-[:REEMPLAZA*2..4]->(Jugador),
//             maximal: nadie reemplaza al primero y el último no reemplaza a
//             nadie.
//  APORTE   : la cadena no existe en ningún documento ni en ningún evento por
//             separado; aparece al recorrer reemplazos de partidos distintos.
// ----------------------------------------------------------------------------
MATCH ruta = (primero:Jugador)-[:REEMPLAZA*2..4]->(ultimo:Jugador)
WHERE NOT EXISTS { ()-[:REEMPLAZA]->(primero) }
  AND NOT EXISTS { (ultimo)-[:REEMPLAZA]->() }
MATCH (primero)-[:JUEGA_EN]->(e:Equipo)
WITH e, ruta,
     [n IN nodes(ruta) | n.apellido + ' #' + toString(n.dorsal)] AS cadena
RETURN e.nombre AS equipo,
       cadena,
       length(ruta) AS eslabones,
       count(*) AS combinacionesDePartidos,
       collect(DISTINCT [r IN relationships(ruta) | r.partidoId + ' ' + toString(r.minuto) + "'"])[0]
         AS ejemplo
ORDER BY eslabones DESC, equipo;


// ----------------------------------------------------------------------------
//  7.4 · RECORRIDO DE LOS FINALISTAS POR EL CUADRO
//
//  OBJETIVO : el camino de cada finalista desde dieciseisavos hasta la final:
//             rival, resultado y quién convirtió en cada ronda.
//  RECORRIDO: (Partido FINAL)<-[:PARTICIPA_EN]-(Equipo)-[:PARTICIPA_EN]->
//             (Partido eliminatorio)<-[:PARTICIPA_EN]-(Rival), más
//             (Jugador)-[:ANOTA]->(Partido) filtrado por el plantel del equipo.
//  APORTE   : el cuadro es una cadena de partidos unidos por equipos; en el
//             grafo se lee como un recorrido, sin reconstruir llaves a mano.
// ----------------------------------------------------------------------------
MATCH (:Partido {fase: 'FINAL'})<-[:PARTICIPA_EN]-(e:Equipo)
MATCH (e)-[c:PARTICIPA_EN]->(p:Partido)<-[:PARTICIPA_EN]-(rival:Equipo)
WHERE rival <> e AND p.fase <> 'GRUPOS'
OPTIONAL MATCH (j:Jugador)-[an:ANOTA]->(p)
  WHERE (j)-[:JUEGA_EN]->(e)
WITH e, c, p, rival, an, j ORDER BY an.minuto
WITH e, p, rival,
     CASE c.condicion WHEN 'LOCAL' THEN p.golesLocal ELSE p.golesVisitante END AS propios,
     CASE c.condicion WHEN 'LOCAL' THEN p.golesVisitante ELSE p.golesLocal END AS ajenos,
     collect(j.apellido + ' ' + toString(an.minuto) + "'") AS goleadores
RETURN e.nombre AS finalista,
       p.fase AS ronda,
       p.partidoId AS partido,
       rival.nombre AS rival,
       CASE WHEN propios IS NULL THEN 'por jugar'
            ELSE toString(propios) + '-' + toString(ajenos) END AS resultado,
       goleadores
ORDER BY finalista, p.ordenGlobal;


// ----------------------------------------------------------------------------
//  7.5 · FICHA DE ACTUACIÓN POR JUGADOR CON LAS CINCO RELACIONES
//
//  OBJETIVO : en una sola consulta, partidos jugados, goles, asistencias,
//             tarjetas y cambios (entró / salió) de cada jugador, y su aporte
//             de gol por partido.
//  RECORRIDO: 1 salto por cada una de las 5 relaciones desde el :Jugador
//             (subconsultas COUNT, sin producto cartesiano entre ellas).
//  APORTE   : las cinco preguntas salen del mismo nodo con un salto cada una;
//             desde los eventos serían cinco filtros por tipo con dos saltos.
// ----------------------------------------------------------------------------
MATCH (j:Jugador)-[:JUEGA_EN]->(e:Equipo)
WITH j, e,
     COUNT { (j)-[:PARTICIPA]->(:Partido) }        AS partidos,
     COUNT { (j)-[:ANOTA]->(:Partido) }            AS goles,
     COUNT { (j)-[:ASISTE]->(:Jugador) }           AS asistencias,
     COUNT { (j)-[:RECIBE_TARJETA]->(:Partido) }   AS tarjetas,
     COUNT { (j)-[:REEMPLAZA]->(:Jugador) }        AS entroDesdeElBanco,
     COUNT { (:Jugador)-[:REEMPLAZA]->(j) }        AS salioReemplazado
WHERE partidos > 0
RETURN j.apellido + ', ' + j.nombre AS jugador, e.nombre AS equipo, j.posicion AS posicion,
       partidos, goles, asistencias, tarjetas, entroDesdeElBanco, salioReemplazado,
       round(toFloat(goles + asistencias) / partidos, 2) AS aporteDeGolPorPartido
ORDER BY goles + asistencias DESC, partidos DESC, jugador
LIMIT 20;


// ############################################################################
//  BLOQUE 8 — ANÁLISIS DE LAS RELACIONES DEL ENUNCIADO
//  Conteos por tipo, grados y patrones. La lectura de los resultados está en
//  docs/decisiones.md §7.3.
// ############################################################################

// ----------------------------------------------------------------------------
//  8.1 · CONTEO Y GRADO POR TIPO DE RELACIÓN
//        Para cada tipo: aristas, nodos origen y destino distintos, y grado de
//        salida medio y máximo de los nodos origen.
// ----------------------------------------------------------------------------
UNWIND ['PARTICIPA', 'ANOTA', 'ASISTE', 'RECIBE_TARJETA', 'REEMPLAZA'] AS tipo
CALL (tipo) {
  MATCH (a)-[r]->(b) WHERE type(r) = tipo
  RETURN count(r) AS relaciones, count(DISTINCT a) AS origenes, count(DISTINCT b) AS destinos,
         labels(a)[0] + ' -> ' + labels(b)[0] AS direccion
}
CALL (tipo) {
  MATCH (a)-[r]->() WHERE type(r) = tipo
  WITH a, count(r) AS grado
  RETURN round(avg(grado), 2) AS gradoSalidaMedio, max(grado) AS gradoSalidaMax
}
RETURN tipo, direccion, relaciones, origenes, destinos, gradoSalidaMedio, gradoSalidaMax;


// ----------------------------------------------------------------------------
//  8.2 · DISTRIBUCIÓN DE GRADO DE PARTICIPA
//        ¿Cuántos jugadores actuaron en 1, 2, 3, ... partidos? Y del otro
//        lado: cuántos jugadores actúan por partido según la fase.
// ----------------------------------------------------------------------------
MATCH (j:Jugador)
WITH j, COUNT { (j)-[:PARTICIPA]->() } AS partidos
RETURN partidos AS partidosJugados, count(j) AS jugadores
ORDER BY partidosJugados;

MATCH (p:Partido {estado: 'FINALIZADO'})
WITH p, COUNT { (p)<-[:PARTICIPA]-() } AS jugadores
RETURN p.fase AS fase, min(jugadores) AS minimo, max(jugadores) AS maximo,
       round(avg(jugadores), 2) AS promedio
ORDER BY min(p.ordenGlobal);


// ----------------------------------------------------------------------------
//  8.3 · PATRONES ENTRE RELACIONES
//        Combinaciones que solo se ven cruzando dos o más tipos de relación.
// ----------------------------------------------------------------------------
// (a) Sociedades: pares asistidor -> goleador que se repiten.
MATCH (a:Jugador)-[s:ASISTE]->(g:Jugador)
WITH a, g, count(s) AS goles
RETURN goles AS golesDeLaSociedad, count(*) AS sociedades
ORDER BY golesDeLaSociedad DESC;

// (b) Patrones de actuación en un mismo partido.
CALL () {
  MATCH (j:Jugador)-[r:REEMPLAZA]->(), (j)-[:ANOTA]->(:Partido {partidoId: r.partidoId})
  WITH count(*) AS casos
  RETURN 'Entró desde el banco y convirtió' AS patron, casos
  UNION ALL
  MATCH (j:Jugador)-[:ANOTA]->(p:Partido)<-[:RECIBE_TARJETA]-(j)
  WITH count(*) AS casos
  RETURN 'Convirtió y fue amonestado o expulsado' AS patron, casos
  UNION ALL
  MATCH (j:Jugador)-[:ASISTE]->(:Jugador)-[:ASISTE]->(j)
  WITH count(*) AS casos
  RETURN 'Asistencia recíproca (A asiste a B y B a A)' AS patron, casos
  UNION ALL
  MATCH (j:Jugador)-[:RECIBE_TARJETA {tipo: 'ROJA'}]->(p:Partido)
  MATCH (j)-[:JUEGA_EN]->(:Equipo)-[c:PARTICIPA_EN]->(p)
  WHERE (c.condicion = 'LOCAL' AND p.golesLocal < p.golesVisitante)
     OR (c.condicion = 'VISITANTE' AND p.golesVisitante < p.golesLocal)
  WITH count(*) AS casos
  RETURN 'Expulsado en un partido que su equipo perdió' AS patron, casos
}
RETURN patron, casos;
