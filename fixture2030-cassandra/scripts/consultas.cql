-- ============================================================================
--  Fixture 2030 — Hito 6 · Módulo de Comentarios (Cassandra)
--  ARCHIVO: scripts/consultas.cql
--  PROPÓSITO: consultas de lectura compatibles con las claves declaradas,
--             una por patrón de acceso (Q0..Q7 de docs/patrones_de_acceso.md).
--  CUBRE: RF9, RF10, RNF4, RNF6.
--
--  EJECUCIÓN (después de carga_muestra.cql; con la carga masiva los
--  resultados son más grandes pero las consultas son las mismas):
--      docker compose exec cassandra cqlsh -f /scripts/consultas.cql
--
--  NINGUNA consulta usa ALLOW FILTERING. Todas restringen la clave de
--  partición completa, así que cada una toca una partición (o un conjunto
--  acotado y conocido de particiones).
--
--  Partidos de la muestra:
--    PAR-A-1    audiencia NORMAL  -> buckets = 1 (solo bucket 0), inicio 13:00 UTC
--    PAR-D16-01 audiencia MAXIMA  -> buckets = 4 (0..3),          inicio 16:00 UTC
-- ============================================================================

USE fixture2030_comentarios;
CONSISTENCY ONE;   -- R=1 del Hito 3 para comentarios


-- ============================================================================
--  Q0 — Parámetros de partición del partido (la app lo lee y lo cachea)
-- ============================================================================
SELECT partido_id, audiencia, buckets, ventana_minutos, inicio
FROM config_particion_partido
WHERE partido_id IN ('PAR-A-1', 'PAR-D16-01');


-- ============================================================================
--  Q1 — ÚLTIMOS COMENTARIOS de un partido en vivo   (la consulta más frecuente)
--  Secuencia acotada por partido: ventana actual, más reciente primero.
-- ============================================================================

-- Q1.a Partido NORMAL (1 bucket): UNA partición, ya ordenada DESC en disco.
--      No hace falta ORDER BY: el clustering (creado_en DESC) es el orden.
SELECT creado_en, comentario_id, alias_usuario, minuto_partido, contenido
FROM comentarios_por_partido
WHERE partido_id = 'PAR-A-1'
  AND ventana    = '2030-06-09 14:20:00.000+0000'
  AND bucket     = 0
LIMIT 50;

-- Q1.b Partido de audiencia MÁXIMA (4 buckets): las 4 particiones de la ventana.
--      El coordinador mezcla los 4 resultados ordenados. Cassandra solo permite
--      ORDER BY + IN sobre la clave de partición con el paginado desactivado.
--      En la aplicación la forma recomendada es 4 lecturas en paralelo (una por
--      bucket, LIMIT 50 cada una) y mezclar en memoria: mismo costo, sin
--      concentrar el trabajo en un coordinador.
PAGING OFF;
SELECT creado_en, bucket, comentario_id, alias_usuario, minuto_partido, contenido
FROM comentarios_por_partido
WHERE partido_id = 'PAR-D16-01'
  AND ventana    = '2030-06-29 17:30:00.000+0000'
  AND bucket IN (0, 1, 2, 3)
ORDER BY creado_en DESC
LIMIT 50;
PAGING ON;

-- Q1.c Si la ventana actual trae menos de 50 (arranque de la ventana), la app
--      completa con la ventana anterior (ventana - 10 min). Nunca más de 2
--      ventanas por pedido.
SELECT creado_en, comentario_id, alias_usuario, contenido
FROM comentarios_por_partido
WHERE partido_id = 'PAR-A-1'
  AND ventana    = '2030-06-09 14:10:00.000+0000'
  AND bucket     = 0
LIMIT 50;


-- ============================================================================
--  Q2 — COMENTARIOS DE UN TRAMO del partido (ej: los 5 minutos tras un gol)
--  Rango sobre la PRIMERA columna de clustering, dentro de la partición.
-- ============================================================================
SELECT creado_en, comentario_id, minuto_partido, contenido
FROM comentarios_por_partido
WHERE partido_id = 'PAR-D16-01'
  AND ventana    = '2030-06-29 17:30:00.000+0000'
  AND bucket     = 1
  AND creado_en >= '2030-06-29 17:30:00.000+0000'
  AND creado_en <  '2030-06-29 17:35:00.000+0000';


-- ============================================================================
--  Q3 — PAGINACIÓN HACIA ATRÁS ("cargar anteriores")
--  Cursor = creado_en del último comentario que ya ve el usuario. Se pide lo
--  estrictamente anterior. No usa OFFSET (Cassandra no lo tiene, y sería
--  costoso): la posición la da la clave de clustering.
-- ============================================================================
SELECT creado_en, comentario_id, contenido
FROM comentarios_por_partido
WHERE partido_id = 'PAR-D16-01'
  AND ventana    = '2030-06-29 17:30:00.000+0000'
  AND bucket     = 1
  AND creado_en  < '2030-06-29 17:34:08.595+0000'
LIMIT 20;


-- ============================================================================
--  Q4 — COLA DE MODERACIÓN de un partido   (índice SAI, estructura secundaria)
--  El índice se resuelve DENTRO de la partición indicada: no hay fan-out ni
--  ALLOW FILTERING. El moderador recorre las ventanas del partido en orden.
-- ============================================================================
SELECT creado_en, comentario_id, usuario_id, contenido, estado_moderacion
FROM comentarios_por_partido
WHERE partido_id = 'PAR-A-1'
  AND ventana    = '2030-06-09 13:10:00.000+0000'
  AND bucket     = 0
  AND estado_moderacion = 'PENDIENTE';

SELECT creado_en, comentario_id, usuario_id, contenido, estado_moderacion
FROM comentarios_por_partido
WHERE partido_id = 'PAR-D16-01'
  AND ventana    = '2030-06-29 17:30:00.000+0000'
  AND bucket     = 2
  AND estado_moderacion = 'PENDIENTE';


-- ============================================================================
--  Q5 — HISTORIAL DE UN USUARIO   (tabla adicional, duplicación controlada)
--  Imposible de responder con la tabla principal sin recorrer todo el
--  keyspace: usuario_id no es parte de su clave primaria.
-- ============================================================================
SELECT creado_en, partido_id, minuto_partido, contenido, estado_moderacion
FROM comentarios_por_usuario
WHERE usuario_id = 'USR-0000038'
  AND mes        = '2030-06'
LIMIT 20;

-- Q5.b Desde el historial se llega a la fila original con el puntero
--      (partido_id, ventana, bucket) + clustering. Lectura de UNA fila.
SELECT comentario_id, creado_en, responde_a, estado_moderacion, contenido
FROM comentarios_por_partido
WHERE partido_id = 'PAR-D16-01'
  AND ventana    = '2030-06-29 17:20:00.000+0000'
  AND bucket     = 3
  AND creado_en  = '2030-06-29 17:29:22.285+0000'
  AND comentario_id = 'PAR-D16-01-C0203900';


-- ============================================================================
--  Q6 — MÉTRICAS DE INTERACCIÓN de un comentario (contadores)
--  Después de crud.cql el contador de la demo queda en 0 (se subió y se bajó).
-- ============================================================================
SELECT comentario_id, me_gusta, respuestas, reportes
FROM interacciones_por_comentario
WHERE comentario_id = 'PAR-A-1-DEMO-CRUD';


-- ============================================================================
--  Q7 — COMENTARIOS AGRUPADOS por partición   (RF9: "ordenados o agrupados")
--  GROUP BY sobre columnas de la clave primaria, en su orden. Sirve además de
--  EVIDENCIA de distribución: con la carga masiva, los 4 buckets de la ventana
--  pico de PAR-D16-01 deben quedar con ~16.000 filas cada uno.
-- ============================================================================
PAGING OFF;
SELECT partido_id, ventana, bucket, count(*) AS comentarios
FROM comentarios_por_partido
WHERE partido_id = 'PAR-D16-01'
  AND ventana    = '2030-06-29 17:30:00.000+0000'
  AND bucket IN (0, 1, 2, 3)
GROUP BY partido_id, ventana, bucket;

-- Q7.b Actividad del partido NORMAL, ventana por ventana (curva del partido)
SELECT partido_id, ventana, bucket, count(*) AS comentarios
FROM comentarios_por_partido
WHERE partido_id = 'PAR-A-1'
  AND ventana IN ('2030-06-09 12:40:00.000+0000', '2030-06-09 12:50:00.000+0000',
                  '2030-06-09 13:00:00.000+0000', '2030-06-09 13:10:00.000+0000',
                  '2030-06-09 13:20:00.000+0000', '2030-06-09 13:30:00.000+0000',
                  '2030-06-09 13:40:00.000+0000', '2030-06-09 13:50:00.000+0000',
                  '2030-06-09 14:00:00.000+0000', '2030-06-09 14:10:00.000+0000',
                  '2030-06-09 14:20:00.000+0000', '2030-06-09 14:30:00.000+0000',
                  '2030-06-09 14:40:00.000+0000', '2030-06-09 14:50:00.000+0000',
                  '2030-06-09 15:00:00.000+0000')
  AND bucket = 0
GROUP BY partido_id, ventana, bucket;
PAGING ON;


-- ============================================================================
--  EVIDENCIA DE ACCESO A UNA SOLA PARTICIÓN (TRACING)
--  En la traza de Q1.a debe aparecer una única lectura de partición
--  ("Executing single-partition query on comentarios_por_partido").
-- ============================================================================
TRACING ON;
SELECT creado_en, comentario_id, contenido
FROM comentarios_por_partido
WHERE partido_id = 'PAR-A-1' AND ventana = '2030-06-09 14:20:00.000+0000' AND bucket = 0
LIMIT 50;
TRACING OFF;


-- ============================================================================
--  ANTIPATRÓN DOCUMENTADO (NO EJECUTAR) — por qué existe comentarios_por_usuario
--  Sin la clave de partición, Cassandra rechaza la consulta salvo que se
--  agregue ALLOW FILTERING, que recorre TODAS las particiones de todos los
--  nodos. Con 1.050.000 comentarios es un full scan del clúster en cada pedido.
-- ============================================================================
-- SELECT * FROM comentarios_por_partido WHERE usuario_id = 'USR-0000038' ALLOW FILTERING;
