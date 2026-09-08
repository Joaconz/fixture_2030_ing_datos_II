// ============================================================================
//  Fixture 2030 — Hito 5 · Módulo de Grafos (Neo4j)
//  ARCHIVO: queries/estructura.cypher
//  PROPÓSITO: restricciones de unicidad e índices del subgrafo.
//  CUBRE: RF10 (integridad e índices), RNF4 (idempotencia), RNF6 (coherencia).
//
//  EJECUCIÓN:
//      docker compose exec neo4j cypher-shell -u neo4j -p fixture2030 \
//          -f /queries/estructura.cypher
//
//  Este archivo se ejecuta SIEMPRE antes de carga.cypher: las restricciones de
//  unicidad son las que hacen que el MERGE de la carga sea seguro y barato
//  (sin el índice de respaldo, cada MERGE degrada a un recorrido de etiqueta).
//  Todo usa IF NOT EXISTS: correrlo N veces no falla ni duplica objetos.
// ============================================================================


// ----------------------------------------------------------------------------
// 1. CONTRATO DE IDENTIFICADORES CON EL HITO 4  (RF5 / RNF6)
// ----------------------------------------------------------------------------
// El Hito 4 decidió CLAVE NATURAL en lugar de ObjectId autogenerado, para que
// la carga fuera idempotente por upsert. Este hito respeta exactamente esa
// decisión y reutiliza las mismas claves, no unas nuevas:
//
//   MongoDB (Hito 4)                    Neo4j (Hito 5)
//   ---------------------------------   ---------------------------------
//   equipos._id      "ARG"          ->  (:Equipo  {equipoId: "ARG"})
//   jugadores.dni    "35123456"     ->  (:Jugador {dni:      "35123456"})
//   jugadores.equipoId "ARG"        ->  (:Jugador)-[:JUEGA_EN]->(:Equipo)
//
// El `dni` es la clave natural del jugador en Mongo (índice único, sección 4
// del Hito 4); el `_id: ObjectId()` es interno del motor documental y por eso
// NO se replica acá: replicarlo ataría el grafo a un detalle de implementación
// de la otra base, justo lo que la restricción de "no integrar por código"
// pide evitar.
//
// Identificadores propios de este hito (misma filosofía de clave natural):
//   (:Partido    {partidoId:    "PAR-A-1"})          fase + grupo + jornada
//   (:Sede       {sedeId:       "URU-CEN"})          país + estadio
//   (:Grupo      {grupoId:      "A"})                coincide con equipos.grupo
//   (:TipoEvento {tipoEventoId: "GOL"})              catálogo N8 del Hito 2/3
//   (:Evento     {eventoId:     "PAR-A-1-EV-05"})    PREFIJADO POR PARTIDO
//
// El eventoId lleva el partidoId adelante a propósito: la clave de partición
// definida en el Hito 3 para Eventos en vivo es el partido, y así el
// identificador es autodescriptivo respecto de su partición.


// ----------------------------------------------------------------------------
// 2. RESTRICCIONES DE UNICIDAD
// ----------------------------------------------------------------------------

CREATE CONSTRAINT equipo_id_unico IF NOT EXISTS
FOR (e:Equipo) REQUIRE e.equipoId IS UNIQUE;

CREATE CONSTRAINT jugador_dni_unico IF NOT EXISTS
FOR (j:Jugador) REQUIRE j.dni IS UNIQUE;

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


// ----------------------------------------------------------------------------
// 3. RESTRICCIONES DE EXISTENCIA — SOLO NEO4J ENTERPRISE
// ----------------------------------------------------------------------------
// El equivalente en grafo de los validadores $jsonSchema con validationLevel
// strict del Hito 4 son las restricciones de existencia y de tipo. La imagen
// `neo4j:latest` de la materia es COMMUNITY EDITION y no las soporta, así que
// quedan documentadas pero comentadas. En Community, la obligatoriedad la
// garantiza el ON CREATE SET de carga.cypher y se AUDITA con las consultas de
// integridad del bloque 6 de consultas_grafo.cypher.
//
// CREATE CONSTRAINT evento_partido_obligatorio IF NOT EXISTS
// FOR (ev:Evento) REQUIRE ev.partidoId IS NOT NULL;
//
// CREATE CONSTRAINT evento_secuencia_obligatoria IF NOT EXISTS
// FOR (ev:Evento) REQUIRE ev.secuencia IS NOT NULL;
//
// CREATE CONSTRAINT jugador_posicion_obligatoria IF NOT EXISTS
// FOR (j:Jugador) REQUIRE j.posicion IS NOT NULL;


// ----------------------------------------------------------------------------
// 4. ÍNDICES DE APOYO A LOS RECORRIDOS FRECUENTES
// ----------------------------------------------------------------------------
// Criterio heredado del Hito 4 (sección 4): NO se indexa ningún campo sin una
// consulta concreta que lo justifique, porque cada índice cuesta escritura y
// almacenamiento. Cada restricción de unicidad ya crea su índice de respaldo,
// así que acá NO se re-indexan equipoId, dni, partidoId, eventoId, etc.

// (a) ÍNDICE COMPUESTO SOBRE LA CLAVE DE PARTICIÓN DEL HITO 3.
//     Es el índice central del módulo. El acceso dominante durante el torneo
//     es "el timeline del partido X, en orden". Indexar (partidoId, secuencia)
//     juntos acota la lectura a una sola partición lógica y la devuelve ya
//     ordenada, sin sort en memoria.
CREATE INDEX evento_particion_partido IF NOT EXISTS
FOR (ev:Evento) ON (ev.partidoId, ev.secuencia);

// (b) Analítica transversal del torneo: goles, tarjetas, asistencias.
CREATE INDEX evento_tipo IF NOT EXISTS
FOR (ev:Evento) ON (ev.tipo);

// (c) Programación del fixture: "¿qué se juega hoy?", "¿qué falta de octavos?"
CREATE INDEX partido_fecha IF NOT EXISTS
FOR (p:Partido) ON (p.fechaHora);

CREATE INDEX partido_fase_estado IF NOT EXISTS
FOR (p:Partido) ON (p.fase, p.estado);

// (d) Equivalente en grafo del índice { equipoId: 1, posicion: 1 } del Hito 4.
//     En el grafo la parte `equipoId` la resuelve la relación JUEGA_EN (no
//     hace falta indexarla), así que el índice solo cubre la parte que sigue
//     siendo un filtro de propiedad: la posición.
CREATE INDEX jugador_posicion IF NOT EXISTS
FOR (j:Jugador) ON (j.posicion);

// (e) Equivalente del índice { apellido: 1, nombre: 1 } del Hito 4:
//     orden y paginación alfabética del listado general de jugadores.
CREATE INDEX jugador_apellido_nombre IF NOT EXISTS
FOR (j:Jugador) ON (j.apellido, j.nombre);

// (f) Cortes por confederación y por país/región anfitriona.
CREATE INDEX equipo_confederacion IF NOT EXISTS
FOR (e:Equipo) ON (e.confederacion);

CREATE INDEX sede_region IF NOT EXISTS
FOR (s:Sede) ON (s.region);

// (g) ÍNDICE DE RELACIÓN. La condición local/visitante se filtra en casi todas
//     las consultas de fixture y vive en la relación, no en el nodo.
CREATE INDEX participa_condicion IF NOT EXISTS
FOR ()-[r:PARTICIPA_EN]-() ON (r.condicion);


// ----------------------------------------------------------------------------
// 5. VERIFICACIÓN — evidencia para docs/evidencia/ (RF11)
// ----------------------------------------------------------------------------
SHOW CONSTRAINTS YIELD name, type, labelsOrTypes, properties
RETURN name, type, labelsOrTypes, properties
ORDER BY name;

SHOW INDEXES YIELD name, type, entityType, labelsOrTypes, properties
RETURN name, type, entityType, labelsOrTypes, properties
ORDER BY name;
