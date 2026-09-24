-- ============================================================================
--  Fixture 2030 — Hito 6 · Módulo de Comentarios (Cassandra)
--  ARCHIVO: scripts/esquema.cql
--  PROPÓSITO: keyspace, tablas y estructuras de acceso secundarias.
--  CUBRE: RF2, RF4, RF5, RF6, RF7, RF10, RNF4, RNF6, RNF7.
--
--  EJECUCIÓN:
--      docker compose exec cassandra cqlsh -f /scripts/esquema.cql
--
--  IDEMPOTENCIA (RNF7): todas las sentencias usan IF NOT EXISTS. Reejecutar
--  este archivo no borra datos ni falla.
--
--  REGLA DE DISEÑO (RNF4): cada tabla existe porque hay una consulta concreta
--  que la necesita. El número de consulta (Q1..Q7) remite a
--  docs/patrones_de_acceso.md.
-- ============================================================================


-- ============================================================================
--  1) KEYSPACE  (RF2)
--  --------------------------------------------------------------------------
--  NetworkTopologyStrategy aun en el laboratorio de UN nodo: es la estrategia
--  de producción que definió el Hito 3 (réplica por región). Acá el factor es 1
--  porque hay un solo nodo; en producción sería {'americas': 3, 'europa': 3,
--  'africa': 3} y la escritura de comentarios usaría W=ONE (N=3, R=1, W=1).
--  El nombre 'datacenter1' es el DC por defecto del contenedor.
--  SimpleStrategy se descartó: sirve para un solo DC y no se puede migrar a
--  multi-región sin redefinir el keyspace.
-- ============================================================================
CREATE KEYSPACE IF NOT EXISTS fixture2030_comentarios
  WITH replication = {'class': 'NetworkTopologyStrategy', 'datacenter1': 1}
  AND durable_writes = true;

USE fixture2030_comentarios;


-- ============================================================================
--  2) CONFIGURACIÓN DE PARTICIÓN POR PARTIDO
--  --------------------------------------------------------------------------
--  Consulta que la justifica: Q0 "¿en cuántos buckets está repartido este
--  partido?". La aplicación la lee UNA vez antes de escribir o leer un partido
--  (y la cachea). Es una tabla chica: 112 filas, una partición por partido.
--  Regla operativa: `buckets` se fija ANTES del partido y SOLO PUEDE CRECER
--  (ver decisiones_de_particionamiento.md §4).
-- ============================================================================
CREATE TABLE IF NOT EXISTS config_particion_partido (
    partido_id       text,        -- = Partido.partidoId del Hito 5 (Neo4j)
    fase             text,        -- GRUPOS | DIECISEISAVOS
    audiencia        text,        -- NORMAL | ALTA | MAXIMA (estimación previa)
    buckets          int,         -- sub-particiones por ventana (1, 2, 4, 8...)
    ventana_minutos  int,         -- ancho de la ventana temporal (10)
    inicio           timestamp,   -- inicio programado del partido (UTC)
    PRIMARY KEY (partido_id)
) WITH comment = 'Q0 - parametros de particion de cada partido (fijados antes del partido)';


-- ============================================================================
--  3) TABLA PRINCIPAL: comentarios por partido  (RF4, RF5, RF6, RF7)
--  --------------------------------------------------------------------------
--  Consultas que la justifican:
--    Q1 últimos N comentarios de un partido (lo más frecuente, en vivo)
--    Q2 comentarios de un partido dentro de un rango de tiempo
--    Q3 paginación hacia atrás ("cargar anteriores")
--    Q4 cola de moderación de un partido (vía índice SAI, sección 5)
--
--  CLAVE PRIMARIA:  ((partido_id, ventana, bucket), creado_en, comentario_id)
--
--  · Clave de partición (partido_id, ventana, bucket)
--      partido_id -> localidad: todo lo que se lee junto es del mismo partido.
--      ventana    -> tramo de 10 minutos. Acota la partición en el TIEMPO:
--                    ninguna partición crece durante todo el partido.
--      bucket     -> 0..buckets-1 = crc32(comentario_id) % buckets. Acota la
--                    partición en CARGA: en un partido de audiencia máxima la
--                    ventana del minuto 90 se reparte entre varios nodos.
--      Es la "partición compuesta partido + ventana temporal" del Hito 3,
--      con el bucket agregado como respuesta medida al hotspot (§3 del doc).
--
--  · Columnas de clustering (creado_en DESC, comentario_id ASC)
--      creado_en DESC -> la partición ya está ordenada de más nuevo a más
--                        viejo: Q1 es leer las primeras N filas, sin ordenar.
--      comentario_id  -> desempate. Dos comentarios en el mismo milisegundo
--                        no se pisan (sin él, el segundo sobrescribiría al
--                        primero: en Cassandra INSERT es UPSERT).
-- ============================================================================
CREATE TABLE IF NOT EXISTS comentarios_por_partido (
    -- clave de partición
    partido_id          text,
    ventana             timestamp,   -- piso de creado_en a múltiplo de 10 min
    bucket              int,
    -- clustering
    creado_en           timestamp,   -- instante de creación (UTC, ms)
    comentario_id       text,        -- '{partido_id}-C{secuencia}' (determinista)
    -- autor (RF6)
    usuario_id          text,        -- = identificador del padrón de Usuarios (N4)
    alias_usuario       text,        -- duplicado a propósito: se muestra sin ir a N4
    -- contexto deportivo (RF6)
    hinchada            text,        -- LOCAL | VISITANTE | NEUTRAL
    minuto_partido      int,         -- minuto de juego al que refiere el comentario
    responde_a          text,        -- comentario_id al que responde (hilo), o null
    -- contenido (RF6)
    contenido           text,
    idioma              text,        -- es | pt | en | fr | ar
    editado             boolean,
    -- moderación (RF6)
    estado_moderacion   text,        -- PUBLICADO | PENDIENTE | OCULTO | ELIMINADO
    motivo_moderacion   text,
    moderado_por        text,
    moderado_en         timestamp,
    PRIMARY KEY ((partido_id, ventana, bucket), creado_en, comentario_id)
) WITH CLUSTERING ORDER BY (creado_en DESC, comentario_id ASC)
  AND comment = 'Q1 Q2 Q3 Q4 - comentarios de un partido por ventana de 10 min y bucket, del mas reciente al mas antiguo';
-- Sin default_time_to_live: los comentarios se conservan como histórico
-- (N9 del Hito 2). La moderación hace BORRADO LÓGICO (estado = ELIMINADO) para
-- no generar tombstones en la tabla más leída. Ver decisiones §6.


-- ============================================================================
--  4) TABLA DE ACCESO SECUNDARIA: historial por usuario  (RF10)
--  --------------------------------------------------------------------------
--  Consulta que la justifica:
--    Q5 "últimos comentarios de un usuario" (perfil, moderación de un autor).
--
--  Por qué NO se resuelve con la tabla principal: usuario_id no es parte de la
--  clave primaria de comentarios_por_partido. Responder Q5 allí exigiría
--  recorrer TODAS las particiones de TODOS los partidos (ALLOW FILTERING sobre
--  1.050.000 filas). Un índice secundario sobre usuario_id tampoco sirve: sin
--  la clave de partición en la consulta, el índice igual consulta todos los
--  nodos del clúster.
--
--  Solución: DUPLICACIÓN CONTROLADA. Cada comentario se escribe en las dos
--  tablas, en el mismo LOGGED BATCH. Se copian solo las columnas que el
--  historial muestra, más (partido_id, ventana, bucket) como PUNTERO a la fila
--  original, para poder moderarla sin buscarla.
--
--  CLAVE: ((usuario_id, mes), creado_en, comentario_id)
--    mes = 'AAAA-MM'. Acota la partición de un usuario muy activo; durante el
--    torneo (junio-julio 2030) un usuario tiene como máximo 2 particiones.
-- ============================================================================
CREATE TABLE IF NOT EXISTS comentarios_por_usuario (
    usuario_id          text,
    mes                 text,        -- 'AAAA-MM'
    creado_en           timestamp,
    comentario_id       text,
    -- puntero a la fila original en comentarios_por_partido
    partido_id          text,
    ventana             timestamp,
    bucket              int,
    -- columnas que muestra el historial
    minuto_partido      int,
    contenido           text,
    estado_moderacion   text,
    PRIMARY KEY ((usuario_id, mes), creado_en, comentario_id)
) WITH CLUSTERING ORDER BY (creado_en DESC, comentario_id ASC)
  AND comment = 'Q5 - historial de comentarios de un usuario por mes (vista duplicada)';


-- ============================================================================
--  5) ÍNDICE SECUNDARIO SAI sobre estado de moderación  (RF10)
--  --------------------------------------------------------------------------
--  Consulta que lo justifica:
--    Q4 "comentarios PENDIENTES de moderación de un partido, ventana por ventana".
--
--  Por qué índice y NO otra tabla: la consulta SIEMPRE trae la clave de
--  partición completa. El índice SAI (Storage-Attached Index, Cassandra 5+)
--  se resuelve entonces DENTRO de una sola partición, sin fan-out a otros
--  nodos, y sin ALLOW FILTERING. Una tabla "por estado" obligaría a borrar e
--  insertar la fila cada vez que cambia el estado (el estado sería parte de la
--  clave), generando un tombstone por cada acción de moderación.
--
--  Lo que NO se hace con este índice: buscar pendientes de TODO el torneo sin
--  partición. Esa consulta haría fan-out a todo el clúster; si el producto la
--  necesitara, correspondería una tabla propia (ver decisiones §7).
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_comentarios_estado
    ON comentarios_por_partido (estado_moderacion)
    USING 'sai';


-- ============================================================================
--  6) MÉTRICAS DE INTERACCIÓN  (RF6)
--  --------------------------------------------------------------------------
--  Consulta que la justifica:
--    Q6 "me gusta / respuestas / reportes de un comentario".
--
--  Tabla aparte porque en Cassandra una tabla con columnas `counter` solo
--  puede tener contadores fuera de la clave primaria. Partición = un
--  comentario: los "me gusta" de un gol se reparten entre miles de
--  particiones distintas, no se concentran en la del partido.
--
--  Los contadores NO son idempotentes (reaplicar +1 suma otra vez) y no
--  admiten TTL. Por eso no se cargan en la carga de muestra ni en la masiva:
--  solo se ejercitan en crud.cql, con +1 y luego -1 para dejar el estado igual.
-- ============================================================================
CREATE TABLE IF NOT EXISTS interacciones_por_comentario (
    comentario_id   text,
    me_gusta        counter,
    respuestas      counter,
    reportes        counter,
    PRIMARY KEY (comentario_id)
) WITH comment = 'Q6 - contadores de interaccion por comentario';


-- ============================================================================
--  7) VERIFICACIÓN DEL ESQUEMA
-- ============================================================================
DESCRIBE KEYSPACE fixture2030_comentarios;
