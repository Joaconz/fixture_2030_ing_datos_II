// ============================================================================
//  Fixture 2030 — Hito 5 · Módulo de Grafos (Neo4j)
//  ARCHIVO: queries/estructura.cypher
//  PROPÓSITO: restricciones de unicidad e índices del subgrafo.
//  REQUISITOS CUBIERTOS: RF10 (integridad e índices), RNF4 (idempotencia),
//                        RNF6 (coherencia de identificadores con el Hito 4).
//
//  EJECUCIÓN:
//      docker compose exec neo4j cypher-shell -u neo4j -p fixture2030 \
//          -f /queries/estructura.cypher
//
//  IMPORTANTE: este archivo SIEMPRE se ejecuta ANTES de carga.cypher.
//  Las restricciones de unicidad son las que hacen que el MERGE de la carga
//  sea seguro y eficiente (sin ellas, un MERGE concurrente puede duplicar).
//  Todas las sentencias usan IF NOT EXISTS: correr el archivo N veces no
//  produce error ni objetos duplicados.
// ============================================================================


// ----------------------------------------------------------------------------
// 1. RESTRICCIONES DE UNICIDAD — identidad de cada entidad
// ----------------------------------------------------------------------------
// Contrato de identificadores compartido con el módulo documental (Hito 4):
//   Equipo   -> equipoId    'EQ-001'  .. 'EQ-064'      (= _id en MongoDB)
//   Jugador  -> jugadorId   'JUG-0001'.. 'JUG-1152'    (= _id en MongoDB)
// Los IDs propios de este hito siguen la misma convención de prefijo:
//   Partido  -> partidoId   'PAR-GA-1'
//   Sede     -> sedeId      'SED-01'
//   Evento   -> eventoId    'PAR-GA-1-EV-05'  (prefijado por partido: la clave
//                                              de partición del Hito 3)
//   Grupo    -> grupoId     'A' .. 'P'
//   TipoEvento -> tipoEventoId 'TE-01'  (catálogo N8 del Hito 2/3)

CREATE CONSTRAINT equipo_id_unico IF NOT EXISTS
FOR (e:Equipo) REQUIRE e.equipoId IS UNIQUE;

CREATE CONSTRAINT jugador_id_unico IF NOT EXISTS
FOR (j:Jugador) REQUIRE j.jugadorId IS UNIQUE;

CREATE CONSTRAINT partido_id_unico IF NOT EXISTS
FOR (p:Partido) REQUIRE p.partidoId IS UNIQUE;

CREATE CONSTRAINT sede_id_unico IF NOT EXISTS
FOR (s:Sede) REQUIRE s.sedeId IS UNIQUE;

CREATE CONSTRAINT evento_id_unico IF NOT EXISTS
FOR (ev:Evento) REQUIRE ev.eventoId IS UNIQUE;

CREATE CONSTRAINT grupo_id_unico IF NOT EXISTS
FOR (g:Grupo) REQUIRE g.grupoId IS UNIQUE;

CREATE CONSTRAINT tipoevento_id_unico IF NOT EXISTS
FOR (t:TipoEvento) REQUIRE t.tipoEventoId IS UNIQUE;

// El código del tipo de evento ('GOL', 'ASISTENCIA', ...) también es una clave
// natural: se usa como punto de entrada al catálogo desde cada Evento.
CREATE CONSTRAINT tipoevento_codigo_unico IF NOT EXISTS
FOR (t:TipoEvento) REQUIRE t.codigo IS UNIQUE;


// ----------------------------------------------------------------------------
// 2. RESTRICCIONES DE EXISTENCIA (SOLO NEO4J ENTERPRISE)
// ----------------------------------------------------------------------------
// Se dejan documentadas pero COMENTADAS: la imagen `neo4j:latest` que usa la
// materia es Community Edition y estas sentencias fallarían. En Community, la
// obligatoriedad de estas propiedades la garantiza el script de carga (todas
// se asignan en el ON CREATE SET) y se verifica con la consulta de integridad
// incluida al final de consultas_grafo.cypher.
//
// CREATE CONSTRAINT evento_partido_obligatorio IF NOT EXISTS
// FOR (ev:Evento) REQUIRE ev.partidoId IS NOT NULL;
//
// CREATE CONSTRAINT evento_secuencia_obligatoria IF NOT EXISTS
// FOR (ev:Evento) REQUIRE ev.secuencia IS NOT NULL;


// ----------------------------------------------------------------------------
// 3. ÍNDICES DE APOYO A LOS PATRONES DE CONSULTA MÁS FRECUENTES
// ----------------------------------------------------------------------------
// Nota: cada restricción de unicidad ya crea su propio índice de respaldo.
// Por eso NO se indexan de nuevo equipoId, jugadorId, partidoId, etc.
// Lo que sigue son índices para los filtros que NO son por identificador.

// (a) Índice COMPUESTO sobre la clave de partición del Hito 3.
//     Es el índice más importante del módulo: el acceso dominante durante el
//     torneo es "traeme los eventos del partido X en orden". Al indexar
//     (partidoId, secuencia) juntos, la recuperación del timeline de un
//     partido queda acotada a una porción del grafo y ya viene ordenada.
CREATE INDEX evento_particion_partido IF NOT EXISTS
FOR (ev:Evento) ON (ev.partidoId, ev.secuencia);

// (b) Filtro por tipo de evento (goles, tarjetas, asistencias del torneo).
CREATE INDEX evento_tipo IF NOT EXISTS
FOR (ev:Evento) ON (ev.tipo);

// (c) Programación del fixture: "¿qué se juega hoy?" y "¿qué falta de octavos?"
CREATE INDEX partido_fecha IF NOT EXISTS
FOR (p:Partido) ON (p.fechaHora);

CREATE INDEX partido_fase IF NOT EXISTS
FOR (p:Partido) ON (p.fase);

CREATE INDEX partido_estado IF NOT EXISTS
FOR (p:Partido) ON (p.estado);

// (d) Navegación del plantel y de la geografía del torneo.
CREATE INDEX jugador_posicion IF NOT EXISTS
FOR (j:Jugador) ON (j.posicion);

CREATE INDEX equipo_confederacion IF NOT EXISTS
FOR (e:Equipo) ON (e.confederacion);

CREATE INDEX sede_pais IF NOT EXISTS
FOR (s:Sede) ON (s.pais);

// (e) Índice de RELACIÓN: la condición local/visitante se filtra en casi todas
//     las consultas de fixture, y es una propiedad de la relación, no del nodo.
CREATE INDEX participa_condicion IF NOT EXISTS
FOR ()-[r:PARTICIPA_EN]-() ON (r.condicion);

// (f) Búsqueda por nombre de equipo/jugador desde el Browser (texto exacto).
CREATE INDEX equipo_nombre IF NOT EXISTS
FOR (e:Equipo) ON (e.nombre);

CREATE INDEX jugador_nombre IF NOT EXISTS
FOR (j:Jugador) ON (j.nombre);


// ----------------------------------------------------------------------------
// 4. VERIFICACIÓN (evidencia para docs/evidencia/) — RF11
// ----------------------------------------------------------------------------
SHOW CONSTRAINTS YIELD name, type, labelsOrTypes, properties
RETURN name, type, labelsOrTypes, properties
ORDER BY name;

SHOW INDEXES YIELD name, type, entityType, labelsOrTypes, properties
RETURN name, type, entityType, labelsOrTypes, properties
ORDER BY name;
