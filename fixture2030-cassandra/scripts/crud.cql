-- ============================================================================
--  Fixture 2030 — Hito 6 · Módulo de Comentarios (Cassandra)
--  ARCHIVO: scripts/crud.cql
--  PROPÓSITO: operaciones de creación, lectura, actualización y eliminación
--             sobre el modelo del grupo.   CUBRE: RF8, RNF6.
--
--  EJECUCIÓN (después de esquema.cql y carga_muestra.cql):
--      docker compose exec cassandra cqlsh -f /scripts/crud.cql
--
--  ARCHIVO REPETIBLE: crea su propio comentario de demostración al principio
--  y lo elimina al final. Los contadores se suben y se vuelven a bajar. Al
--  terminar, el keyspace queda como lo dejó carga_muestra.cql (el bloque 7
--  debe devolver 0 filas).
--
--  Comentario de demostración:
--    partido  PAR-A-1   (audiencia NORMAL -> buckets = 1 -> bucket 0)
--    creado   2030-06-09 14:31:05.000 UTC  -> ventana 14:30 UTC
--    id       PAR-A-1-DEMO-CRUD
-- ============================================================================

USE fixture2030_comentarios;

-- W=1 / R=1 del Hito 3 para comentarios (N=3, R=1, W=1 en producción).
-- En el laboratorio de un nodo ONE y QUORUM coinciden; se deja explícito.
CONSISTENCY ONE;


-- ============================================================================
--  1) CREATE — escritura dual controlada en un LOGGED BATCH
--  El batch "logged" garantiza que, si una de las dos escrituras se aplica,
--  la otra también termina aplicándose (se registra en el batchlog antes de
--  ejecutarse). NO es para acelerar: es para que la vista por partido y la
--  vista por usuario no queden desalineadas.
-- ============================================================================
BEGIN BATCH
  INSERT INTO comentarios_por_partido
    (partido_id, ventana, bucket, creado_en, comentario_id,
     usuario_id, alias_usuario, hinchada, minuto_partido,
     contenido, idioma, editado, estado_moderacion)
  VALUES
    ('PAR-A-1', '2030-06-09 14:30:00.000+0000', 0, '2030-06-09 14:31:05.000+0000', 'PAR-A-1-DEMO-CRUD',
     'USR-DEMO-CRUD', 'hincha_demo', 'LOCAL', 91,
     'Comentario de prueba del CRUD', 'es', false, 'PUBLICADO');
  -- responde_a no se incluye: no es respuesta. Escribir null crearía un tombstone.
  INSERT INTO comentarios_por_usuario
    (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket,
     minuto_partido, contenido, estado_moderacion)
  VALUES
    ('USR-DEMO-CRUD', '2030-06', '2030-06-09 14:31:05.000+0000', 'PAR-A-1-DEMO-CRUD',
     'PAR-A-1', '2030-06-09 14:30:00.000+0000', 0,
     91, 'Comentario de prueba del CRUD', 'PUBLICADO');
APPLY BATCH;


-- ============================================================================
--  2) READ — lectura por clave primaria completa (una fila, una partición)
-- ============================================================================
-- 2.1 La fila en la vista por partido
SELECT comentario_id, creado_en, usuario_id, contenido, estado_moderacion, editado
FROM comentarios_por_partido
WHERE partido_id = 'PAR-A-1' AND ventana = '2030-06-09 14:30:00.000+0000' AND bucket = 0
  AND creado_en = '2030-06-09 14:31:05.000+0000' AND comentario_id = 'PAR-A-1-DEMO-CRUD';

-- 2.2 La misma fila en la vista por usuario (el puntero lleva a la original)
SELECT comentario_id, partido_id, ventana, bucket, contenido
FROM comentarios_por_usuario
WHERE usuario_id = 'USR-DEMO-CRUD' AND mes = '2030-06';


-- ============================================================================
--  3) UPDATE delimitado por la clave de la fila — edición del autor
--  En Cassandra UPDATE es un UPSERT: si la clave no existe, CREA la fila.
--  Por eso siempre se especifica la clave primaria COMPLETA y la edición
--  va en batch a las dos vistas.
-- ============================================================================
BEGIN BATCH
  UPDATE comentarios_por_partido
     SET contenido = 'Comentario de prueba del CRUD (editado)', editado = true
   WHERE partido_id = 'PAR-A-1' AND ventana = '2030-06-09 14:30:00.000+0000' AND bucket = 0
     AND creado_en = '2030-06-09 14:31:05.000+0000' AND comentario_id = 'PAR-A-1-DEMO-CRUD';
  UPDATE comentarios_por_usuario
     SET contenido = 'Comentario de prueba del CRUD (editado)'
   WHERE usuario_id = 'USR-DEMO-CRUD' AND mes = '2030-06'
     AND creado_en = '2030-06-09 14:31:05.000+0000' AND comentario_id = 'PAR-A-1-DEMO-CRUD';
APPLY BATCH;


-- ============================================================================
--  4) UPDATE de MODERACIÓN — con IF EXISTS (transacción liviana, LWT)
--  Riesgo que evita: que un moderador "oculte" un comentario que el autor ya
--  borró. Sin IF EXISTS, el UPDATE (upsert) resucitaría una fila fantasma con
--  solo las columnas de moderación. IF EXISTS usa Paxos y es ~4 veces más caro
--  que una escritura normal: se acepta porque la moderación es de baja
--  frecuencia. NO se usa en la escritura de comentarios (la operación caliente).
--  Una LWT no puede ir en un batch multi-partición: la vista por usuario se
--  actualiza después, solo si la primera devolvió [applied] = True.
-- ============================================================================
UPDATE comentarios_por_partido
   SET estado_moderacion = 'OCULTO', motivo_moderacion = 'SPAM',
       moderado_por = 'MOD-001', moderado_en = '2030-06-09 14:35:00.000+0000'
 WHERE partido_id = 'PAR-A-1' AND ventana = '2030-06-09 14:30:00.000+0000' AND bucket = 0
   AND creado_en = '2030-06-09 14:31:05.000+0000' AND comentario_id = 'PAR-A-1-DEMO-CRUD'
IF EXISTS;

UPDATE comentarios_por_usuario
   SET estado_moderacion = 'OCULTO'
 WHERE usuario_id = 'USR-DEMO-CRUD' AND mes = '2030-06'
   AND creado_en = '2030-06-09 14:31:05.000+0000' AND comentario_id = 'PAR-A-1-DEMO-CRUD';

-- 4.1 Contraprueba: moderar un comentario que NO existe no crea nada
UPDATE comentarios_por_partido
   SET estado_moderacion = 'OCULTO'
 WHERE partido_id = 'PAR-A-1' AND ventana = '2030-06-09 14:30:00.000+0000' AND bucket = 0
   AND creado_en = '2030-06-09 14:31:06.000+0000' AND comentario_id = 'NO-EXISTE'
IF EXISTS;
-- Esperado: [applied] = False


-- ============================================================================
--  5) UPDATE de MÉTRICAS — contadores (+1 y luego -1 para dejar el estado igual)
-- ============================================================================
UPDATE interacciones_por_comentario
   SET me_gusta = me_gusta + 1, respuestas = respuestas + 1, reportes = reportes + 1
 WHERE comentario_id = 'PAR-A-1-DEMO-CRUD';

SELECT comentario_id, me_gusta, respuestas, reportes
FROM interacciones_por_comentario WHERE comentario_id = 'PAR-A-1-DEMO-CRUD';
-- Esperado: 1, 1, 1 (en cada corrida de este archivo, porque el bloque siguiente revierte)

UPDATE interacciones_por_comentario
   SET me_gusta = me_gusta - 1, respuestas = respuestas - 1, reportes = reportes - 1
 WHERE comentario_id = 'PAR-A-1-DEMO-CRUD';
-- No se hace DELETE del contador: en Cassandra, volver a incrementar un
-- contador borrado tiene comportamiento indefinido. Se deja en 0.


-- ============================================================================
--  6) BORRADO LÓGICO — la eliminación NORMAL del módulo
--  El autor "borra" su comentario: se marca ELIMINADO y se vacía el texto en
--  las dos vistas. Escribir null en una celda genera un tombstone de CELDA
--  (chico); borrar la fila entera genera un tombstone de FILA, que el resto de
--  las lecturas de la ventana debe saltear hasta la compactación.
-- ============================================================================
BEGIN BATCH
  UPDATE comentarios_por_partido
     SET estado_moderacion = 'ELIMINADO', contenido = null
   WHERE partido_id = 'PAR-A-1' AND ventana = '2030-06-09 14:30:00.000+0000' AND bucket = 0
     AND creado_en = '2030-06-09 14:31:05.000+0000' AND comentario_id = 'PAR-A-1-DEMO-CRUD';
  UPDATE comentarios_por_usuario
     SET estado_moderacion = 'ELIMINADO', contenido = null
   WHERE usuario_id = 'USR-DEMO-CRUD' AND mes = '2030-06'
     AND creado_en = '2030-06-09 14:31:05.000+0000' AND comentario_id = 'PAR-A-1-DEMO-CRUD';
APPLY BATCH;

SELECT comentario_id, estado_moderacion, contenido
FROM comentarios_por_partido
WHERE partido_id = 'PAR-A-1' AND ventana = '2030-06-09 14:30:00.000+0000' AND bucket = 0
  AND creado_en = '2030-06-09 14:31:05.000+0000' AND comentario_id = 'PAR-A-1-DEMO-CRUD';


-- ============================================================================
--  7) DELETE CONTROLADO — eliminación física por clave primaria completa
--  Uso previsto: pedido de baja de datos personales o limpieza de una prueba.
--  Nunca se borra una partición entera ni por rango en la operación normal.
-- ============================================================================
BEGIN BATCH
  DELETE FROM comentarios_por_partido
   WHERE partido_id = 'PAR-A-1' AND ventana = '2030-06-09 14:30:00.000+0000' AND bucket = 0
     AND creado_en = '2030-06-09 14:31:05.000+0000' AND comentario_id = 'PAR-A-1-DEMO-CRUD';
  DELETE FROM comentarios_por_usuario
   WHERE usuario_id = 'USR-DEMO-CRUD' AND mes = '2030-06'
     AND creado_en = '2030-06-09 14:31:05.000+0000' AND comentario_id = 'PAR-A-1-DEMO-CRUD';
APPLY BATCH;

-- 7.1 Verificación: las dos consultas deben devolver 0
SELECT count(*) AS queda_en_partido
FROM comentarios_por_partido
WHERE partido_id = 'PAR-A-1' AND ventana = '2030-06-09 14:30:00.000+0000' AND bucket = 0
  AND creado_en = '2030-06-09 14:31:05.000+0000' AND comentario_id = 'PAR-A-1-DEMO-CRUD';

SELECT count(*) AS queda_en_usuario
FROM comentarios_por_usuario
WHERE usuario_id = 'USR-DEMO-CRUD' AND mes = '2030-06';
