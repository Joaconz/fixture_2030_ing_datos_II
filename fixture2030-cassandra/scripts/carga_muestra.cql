-- ============================================================================
--  Fixture 2030 — Hito 6 · Módulo de Comentarios (Cassandra)
--  ARCHIVO: scripts/carga_muestra.cql   (GENERADO por scripts/generar_muestra.py)
--  PROPÓSITO: carga PEQUEÑA para validar esquema, CRUD y consultas en desarrollo.
--
--  EJECUCIÓN (después de esquema.cql):
--      docker compose exec cassandra cqlsh -f /scripts/carga_muestra.cql
--
--  IDEMPOTENCIA (RNF7): en Cassandra INSERT es un UPSERT sobre la clave primaria.
--  Todas las claves son deterministas, así que reejecutar este archivo deja
--  exactamente las mismas filas. No se cargan contadores acá a propósito:
--  un UPDATE ... SET c = c + 1 NO es idempotente (ver decisiones §6).
--  Las columnas sin valor se OMITEN del INSERT (escribir null crea tombstones).
--
--  CONTENIDO: 112 filas de configuración + 80 comentarios
--  (PAR-A-1, PAR-D16-01), duplicados de forma controlada en
--  comentarios_por_partido y comentarios_por_usuario.
-- ============================================================================

USE fixture2030_comentarios;

-- ----------------------------------------------------------------------------
--  1) Configuración de partición de los 112 partidos del Hito 5
--     buckets se fija ANTES del partido según la audiencia esperada.
-- ----------------------------------------------------------------------------
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-A-1', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-09 13:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-A-2', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-09 13:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-A-3', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-14 13:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-A-4', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-14 13:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-A-5', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-19 13:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-A-6', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-19 13:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-B-1', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-10 13:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-B-2', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-10 13:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-B-3', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-15 13:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-B-4', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-15 13:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-B-5', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-20 13:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-B-6', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-20 13:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-C-1', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-11 13:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-C-2', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-11 13:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-C-3', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-16 13:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-C-4', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-16 13:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-C-5', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-21 13:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-C-6', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-21 13:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-D-1', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-12 13:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-D-2', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-12 13:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-D-3', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-17 13:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-D-4', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-17 13:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-D-5', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-22 13:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-D-6', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-22 13:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-E-1', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-09 16:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-E-2', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-09 16:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-E-3', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-14 16:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-E-4', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-14 16:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-E-5', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-19 16:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-E-6', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-19 16:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-F-1', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-10 16:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-F-2', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-10 16:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-F-3', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-15 16:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-F-4', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-15 16:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-F-5', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-20 16:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-F-6', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-20 16:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-G-1', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-11 16:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-G-2', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-11 16:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-G-3', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-16 16:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-G-4', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-16 16:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-G-5', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-21 16:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-G-6', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-21 16:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-H-1', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-12 16:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-H-2', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-12 16:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-H-3', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-17 16:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-H-4', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-17 16:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-H-5', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-22 16:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-H-6', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-22 16:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-I-1', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-09 19:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-I-2', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-09 19:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-I-3', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-14 19:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-I-4', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-14 19:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-I-5', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-19 19:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-I-6', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-19 19:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-J-1', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-10 19:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-J-2', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-10 19:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-J-3', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-15 19:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-J-4', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-15 19:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-J-5', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-20 19:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-J-6', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-20 19:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-K-1', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-11 19:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-K-2', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-11 19:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-K-3', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-16 19:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-K-4', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-16 19:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-K-5', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-21 19:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-K-6', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-21 19:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-L-1', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-12 19:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-L-2', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-12 19:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-L-3', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-17 19:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-L-4', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-17 19:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-L-5', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-22 19:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-L-6', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-22 19:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-M-1', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-09 22:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-M-2', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-09 22:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-M-3', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-14 22:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-M-4', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-14 22:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-M-5', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-19 22:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-M-6', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-19 22:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-N-1', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-10 22:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-N-2', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-10 22:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-N-3', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-15 22:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-N-4', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-15 22:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-N-5', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-20 22:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-N-6', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-20 22:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-O-1', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-11 22:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-O-2', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-11 22:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-O-3', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-16 22:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-O-4', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-16 22:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-O-5', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-21 22:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-O-6', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-21 22:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-P-1', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-12 22:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-P-2', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-12 22:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-P-3', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-17 22:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-P-4', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-17 22:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-P-5', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-22 22:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-P-6', 'GRUPOS', 'NORMAL', 1, 10, '2030-06-22 22:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-D16-01', 'DIECISEISAVOS', 'MAXIMA', 4, 10, '2030-06-29 16:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-D16-02', 'DIECISEISAVOS', 'ALTA', 1, 10, '2030-06-29 19:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-D16-03', 'DIECISEISAVOS', 'ALTA', 1, 10, '2030-06-29 22:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-D16-04', 'DIECISEISAVOS', 'ALTA', 1, 10, '2030-06-30 01:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-D16-05', 'DIECISEISAVOS', 'ALTA', 1, 10, '2030-06-30 16:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-D16-06', 'DIECISEISAVOS', 'ALTA', 1, 10, '2030-06-30 19:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-D16-07', 'DIECISEISAVOS', 'ALTA', 1, 10, '2030-06-30 22:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-D16-08', 'DIECISEISAVOS', 'ALTA', 1, 10, '2030-07-01 01:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-D16-09', 'DIECISEISAVOS', 'ALTA', 1, 10, '2030-07-01 16:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-D16-10', 'DIECISEISAVOS', 'ALTA', 1, 10, '2030-07-01 19:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-D16-11', 'DIECISEISAVOS', 'ALTA', 1, 10, '2030-07-01 22:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-D16-12', 'DIECISEISAVOS', 'ALTA', 1, 10, '2030-07-02 01:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-D16-13', 'DIECISEISAVOS', 'ALTA', 1, 10, '2030-07-02 16:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-D16-14', 'DIECISEISAVOS', 'ALTA', 1, 10, '2030-07-02 19:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-D16-15', 'DIECISEISAVOS', 'ALTA', 1, 10, '2030-07-02 22:00:00.000+0000');
INSERT INTO config_particion_partido (partido_id, fase, audiencia, buckets, ventana_minutos, inicio) VALUES ('PAR-D16-16', 'DIECISEISAVOS', 'ALTA', 1, 10, '2030-07-03 01:00:00.000+0000');

-- ----------------------------------------------------------------------------
--  2) Comentarios: escritura DUAL controlada (vista por partido + vista por usuario)
--     Cada par va en un LOGGED BATCH para que las dos vistas no queden
--     desalineadas si falla una de las escrituras (ver decisiones §5).
-- ----------------------------------------------------------------------------
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-A-1', '2030-06-09 13:00:00.000+0000', 0, '2030-06-09 13:00:27.639+0000', 'PAR-A-1-C0000200', 'USR-0143024', 'hincha_143024', 'VISITANTE', 0, 'Faltan 5 minutos, aguanten', 'pt', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0143024', '2030-06', '2030-06-09 13:00:27.639+0000', 'PAR-A-1-C0000200', 'PAR-A-1', '2030-06-09 13:00:00.000+0000', 0, 0, 'Faltan 5 minutos, aguanten', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-A-1', '2030-06-09 13:10:00.000+0000', 0, '2030-06-09 13:10:46.858+0000', 'PAR-A-1-C0000400', 'USR-0007501', 'hincha_7501', 'VISITANTE', 10, 'Joga bonito, que time', 'es', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0007501', '2030-06', '2030-06-09 13:10:46.858+0000', 'PAR-A-1-C0000400', 'PAR-A-1', '2030-06-09 13:10:00.000+0000', 0, 10, 'Joga bonito, que time', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-A-1', '2030-06-09 13:10:00.000+0000', 0, '2030-06-09 13:19:34.218+0000', 'PAR-A-1-C0000600', 'USR-0237501', 'hincha_237501', 'VISITANTE', 19, 'Qué atajada del arquero!!', 'en', 'PENDIENTE', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0237501', '2030-06', '2030-06-09 13:19:34.218+0000', 'PAR-A-1-C0000600', 'PAR-A-1', '2030-06-09 13:10:00.000+0000', 0, 19, 'Qué atajada del arquero!!', 'PENDIENTE');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-A-1', '2030-06-09 13:20:00.000+0000', 0, '2030-06-09 13:24:24.198+0000', 'PAR-A-1-C0000800', 'USR-0047826', 'hincha_47826', 'LOCAL', 24, 'Ese pase fue de otro planeta', 'es', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0047826', '2030-06', '2030-06-09 13:24:24.198+0000', 'PAR-A-1-C0000800', 'PAR-A-1', '2030-06-09 13:20:00.000+0000', 0, 24, 'Ese pase fue de otro planeta', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-A-1', '2030-06-09 13:20:00.000+0000', 0, '2030-06-09 13:26:10.737+0000', 'PAR-A-1-C0001000', 'USR-0079448', 'hincha_79448', 'LOCAL', 26, 'Nos vemos en la próxima ronda', 'es', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0079448', '2030-06', '2030-06-09 13:26:10.737+0000', 'PAR-A-1-C0001000', 'PAR-A-1', '2030-06-09 13:20:00.000+0000', 0, 26, 'Nos vemos en la próxima ronda', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-A-1', '2030-06-09 13:30:00.000+0000', 0, '2030-06-09 13:30:25.268+0000', 'PAR-A-1-C0001200', 'USR-0240536', 'hincha_240536', 'LOCAL', 30, 'Allez les bleus', 'ar', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0240536', '2030-06', '2030-06-09 13:30:25.268+0000', 'PAR-A-1-C0001200', 'PAR-A-1', '2030-06-09 13:30:00.000+0000', 0, 30, 'Allez les bleus', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-A-1', '2030-06-09 13:30:00.000+0000', 0, '2030-06-09 13:37:38.579+0000', 'PAR-A-1-C0001400', 'USR-0025702', 'hincha_25702', 'LOCAL', 37, 'What a save!', 'es', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0025702', '2030-06', '2030-06-09 13:37:38.579+0000', 'PAR-A-1-C0001400', 'PAR-A-1', '2030-06-09 13:30:00.000+0000', 0, 37, 'What a save!', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-A-1', '2030-06-09 13:30:00.000+0000', 0, '2030-06-09 13:38:14.806+0000', 'PAR-A-1-C0001600', 'USR-0011164', 'hincha_11164', 'VISITANTE', 38, 'Con esta hinchada no se puede perder', 'es', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0011164', '2030-06', '2030-06-09 13:38:14.806+0000', 'PAR-A-1-C0001600', 'PAR-A-1', '2030-06-09 13:30:00.000+0000', 0, 38, 'Con esta hinchada no se puede perder', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-A-1', '2030-06-09 13:40:00.000+0000', 0, '2030-06-09 13:41:27.225+0000', 'PAR-A-1-C0001800', 'USR-0107492', 'hincha_107492', 'VISITANTE', 41, 'El VAR está mirando, esperemos', 'es', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0107492', '2030-06', '2030-06-09 13:41:27.225+0000', 'PAR-A-1-C0001800', 'PAR-A-1', '2030-06-09 13:40:00.000+0000', 0, 41, 'El VAR está mirando, esperemos', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-A-1', '2030-06-09 13:40:00.000+0000', 0, '2030-06-09 13:44:25.964+0000', 'PAR-A-1-C0002000', 'USR-0142118', 'hincha_142118', 'NEUTRAL', 44, 'Primer tiempo aburrido, a ver el segundo', 'es', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0142118', '2030-06', '2030-06-09 13:44:25.964+0000', 'PAR-A-1-C0002000', 'PAR-A-1', '2030-06-09 13:40:00.000+0000', 0, 44, 'Primer tiempo aburrido, a ver el segundo', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-A-1', '2030-06-09 13:40:00.000+0000', 0, '2030-06-09 13:47:24.596+0000', 'PAR-A-1-C0002200', 'USR-0170129', 'hincha_170129', 'LOCAL', 47, 'Con esta hinchada no se puede perder', 'fr', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0170129', '2030-06', '2030-06-09 13:47:24.596+0000', 'PAR-A-1-C0002200', 'PAR-A-1', '2030-06-09 13:40:00.000+0000', 0, 47, 'Con esta hinchada no se puede perder', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-A-1', '2030-06-09 13:50:00.000+0000', 0, '2030-06-09 13:52:07.059+0000', 'PAR-A-1-C0002400', 'USR-0006981', 'hincha_6981', 'NEUTRAL', 52, 'Tiki taka puro', 'es', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0006981', '2030-06', '2030-06-09 13:52:07.059+0000', 'PAR-A-1-C0002400', 'PAR-A-1', '2030-06-09 13:50:00.000+0000', 0, 52, 'Tiki taka puro', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-A-1', '2030-06-09 13:50:00.000+0000', 0, '2030-06-09 13:54:49.204+0000', 'PAR-A-1-C0002600', 'USR-0169191', 'hincha_169191', 'LOCAL', 54, 'Esa defensa está dormida', 'pt', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0169191', '2030-06', '2030-06-09 13:54:49.204+0000', 'PAR-A-1-C0002600', 'PAR-A-1', '2030-06-09 13:50:00.000+0000', 0, 54, 'Esa defensa está dormida', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-A-1', '2030-06-09 14:00:00.000+0000', 0, '2030-06-09 14:04:45.627+0000', 'PAR-A-1-C0002800', 'USR-0025996', 'hincha_25996', 'VISITANTE', 64, 'Partidazo, se viene la remontada', 'ar', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0025996', '2030-06', '2030-06-09 14:04:45.627+0000', 'PAR-A-1-C0002800', 'PAR-A-1', '2030-06-09 14:00:00.000+0000', 0, 64, 'Partidazo, se viene la remontada', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-A-1', '2030-06-09 14:10:00.000+0000', 0, '2030-06-09 14:12:56.900+0000', 'PAR-A-1-C0003000', 'USR-0175028', 'hincha_175028', 'LOCAL', 72, 'Allez les bleus', 'en', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0175028', '2030-06', '2030-06-09 14:12:56.900+0000', 'PAR-A-1-C0003000', 'PAR-A-1', '2030-06-09 14:10:00.000+0000', 0, 72, 'Allez les bleus', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-A-1', '2030-06-09 14:20:00.000+0000', 0, '2030-06-09 14:21:39.105+0000', 'PAR-A-1-C0003200', 'USR-0210732', 'hincha_210732', 'LOCAL', 81, 'Increíble lo de este partido', 'en', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0210732', '2030-06', '2030-06-09 14:21:39.105+0000', 'PAR-A-1-C0003200', 'PAR-A-1', '2030-06-09 14:20:00.000+0000', 0, 81, 'Increíble lo de este partido', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-A-1', '2030-06-09 14:20:00.000+0000', 0, '2030-06-09 14:26:19.125+0000', 'PAR-A-1-C0003400', 'USR-0027864', 'hincha_27864', 'LOCAL', 86, 'Vamos selección! Hoy se gana', 'pt', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0027864', '2030-06', '2030-06-09 14:26:19.125+0000', 'PAR-A-1-C0003400', 'PAR-A-1', '2030-06-09 14:20:00.000+0000', 0, 86, 'Vamos selección! Hoy se gana', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-A-1', '2030-06-09 14:20:00.000+0000', 0, '2030-06-09 14:29:17.991+0000', 'PAR-A-1-C0003600', 'USR-0016464', 'hincha_16464', 'NEUTRAL', 89, 'El VAR está mirando, esperemos', 'es', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0016464', '2030-06', '2030-06-09 14:29:17.991+0000', 'PAR-A-1-C0003600', 'PAR-A-1', '2030-06-09 14:20:00.000+0000', 0, 89, 'El VAR está mirando, esperemos', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-A-1', '2030-06-09 14:30:00.000+0000', 0, '2030-06-09 14:33:59.420+0000', 'PAR-A-1-C0003800', 'USR-0211735', 'hincha_211735', 'VISITANTE', 93, 'Esa defensa está dormida', 'es', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0211735', '2030-06', '2030-06-09 14:33:59.420+0000', 'PAR-A-1-C0003800', 'PAR-A-1', '2030-06-09 14:30:00.000+0000', 0, 93, 'Esa defensa está dormida', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-A-1', '2030-06-09 14:30:00.000+0000', 0, '2030-06-09 14:36:09.260+0000', 'PAR-A-1-C0004000', 'USR-0165059', 'hincha_165059', 'LOCAL', 96, 'What a save!', 'en', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0165059', '2030-06', '2030-06-09 14:36:09.260+0000', 'PAR-A-1-C0004000', 'PAR-A-1', '2030-06-09 14:30:00.000+0000', 0, 96, 'What a save!', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-A-1', '2030-06-09 14:30:00.000+0000', 0, '2030-06-09 14:39:54.109+0000', 'PAR-A-1-C0004200', 'USR-0220271', 'hincha_220271', 'LOCAL', 99, 'What a save!', 'es', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0220271', '2030-06', '2030-06-09 14:39:54.109+0000', 'PAR-A-1-C0004200', 'PAR-A-1', '2030-06-09 14:30:00.000+0000', 0, 99, 'What a save!', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, responde_a, editado) VALUES ('PAR-A-1', '2030-06-09 14:40:00.000+0000', 0, '2030-06-09 14:47:54.646+0000', 'PAR-A-1-C0004400', 'USR-0042100', 'hincha_42100', 'LOCAL', 107, 'Con esta hinchada no se puede perder', 'pt', 'PUBLICADO', 'PAR-A-1-C0004202', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0042100', '2030-06', '2030-06-09 14:47:54.646+0000', 'PAR-A-1-C0004400', 'PAR-A-1', '2030-06-09 14:40:00.000+0000', 0, 107, 'Con esta hinchada no se puede perder', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-A-1', '2030-06-09 14:50:00.000+0000', 0, '2030-06-09 14:58:00.943+0000', 'PAR-A-1-C0004600', 'USR-0027732', 'hincha_27732', 'LOCAL', 118, 'Tarjeta roja, se va a las duchas', 'pt', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0027732', '2030-06', '2030-06-09 14:58:00.943+0000', 'PAR-A-1-C0004600', 'PAR-A-1', '2030-06-09 14:50:00.000+0000', 0, 118, 'Tarjeta roja, se va a las duchas', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-A-1', '2030-06-09 15:00:00.000+0000', 0, '2030-06-09 15:00:48.744+0000', 'PAR-A-1-C0004633', 'USR-0000038', 'hincha_38', 'LOCAL', 120, 'Allez les bleus', 'es', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0000038', '2030-06', '2030-06-09 15:00:48.744+0000', 'PAR-A-1-C0004633', 'PAR-A-1', '2030-06-09 15:00:00.000+0000', 0, 120, 'Allez les bleus', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 15:50:00.000+0000', 2, '2030-06-29 15:55:15.073+0000', 'PAR-D16-01-C0008000', 'USR-0076893', 'hincha_76893', 'LOCAL', 0, 'Increíble lo de este partido', 'pt', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0076893', '2030-06', '2030-06-29 15:55:15.073+0000', 'PAR-D16-01-C0008000', 'PAR-D16-01', '2030-06-29 15:50:00.000+0000', 2, 0, 'Increíble lo de este partido', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 16:00:00.000+0000', 3, '2030-06-29 16:01:48.201+0000', 'PAR-D16-01-C0013428', 'USR-0000038', 'hincha_38', 'VISITANTE', 1, 'Qué atajada del arquero!!', 'en', 'PENDIENTE', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0000038', '2030-06', '2030-06-29 16:01:48.201+0000', 'PAR-D16-01-C0013428', 'PAR-D16-01', '2030-06-29 16:00:00.000+0000', 3, 1, 'Qué atajada del arquero!!', 'PENDIENTE');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 16:00:00.000+0000', 1, '2030-06-29 16:03:52.344+0000', 'PAR-D16-01-C0016000', 'USR-0206564', 'hincha_206564', 'VISITANTE', 3, 'Esa defensa está dormida', 'es', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0206564', '2030-06', '2030-06-29 16:03:52.344+0000', 'PAR-D16-01-C0016000', 'PAR-D16-01', '2030-06-29 16:00:00.000+0000', 1, 3, 'Esa defensa está dormida', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 16:00:00.000+0000', 2, '2030-06-29 16:09:21.907+0000', 'PAR-D16-01-C0024000', 'USR-0003783', 'hincha_3783', 'NEUTRAL', 9, 'Ese pase fue de otro planeta', 'es', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0003783', '2030-06', '2030-06-29 16:09:21.907+0000', 'PAR-D16-01-C0024000', 'PAR-D16-01', '2030-06-29 16:00:00.000+0000', 2, 9, 'Ese pase fue de otro planeta', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 16:10:00.000+0000', 2, '2030-06-29 16:15:30.333+0000', 'PAR-D16-01-C0032000', 'USR-0011805', 'hincha_11805', 'LOCAL', 15, 'Allez les bleus', 'pt', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0011805', '2030-06', '2030-06-29 16:15:30.333+0000', 'PAR-D16-01-C0032000', 'PAR-D16-01', '2030-06-29 16:10:00.000+0000', 2, 15, 'Allez les bleus', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 16:20:00.000+0000', 1, '2030-06-29 16:21:48.220+0000', 'PAR-D16-01-C0040000', 'USR-0019559', 'hincha_19559', 'LOCAL', 21, 'What a save!', 'fr', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0019559', '2030-06', '2030-06-29 16:21:48.220+0000', 'PAR-D16-01-C0040000', 'PAR-D16-01', '2030-06-29 16:20:00.000+0000', 1, 21, 'What a save!', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 16:20:00.000+0000', 2, '2030-06-29 16:27:04.501+0000', 'PAR-D16-01-C0048000', 'USR-0046954', 'hincha_46954', 'LOCAL', 27, 'Ese pase fue de otro planeta', 'es', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0046954', '2030-06', '2030-06-29 16:27:04.501+0000', 'PAR-D16-01-C0048000', 'PAR-D16-01', '2030-06-29 16:20:00.000+0000', 2, 27, 'Ese pase fue de otro planeta', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 16:30:00.000+0000', 1, '2030-06-29 16:31:13.039+0000', 'PAR-D16-01-C0056000', 'USR-0202142', 'hincha_202142', 'LOCAL', 31, 'Partidazo, se viene la remontada', 'en', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0202142', '2030-06', '2030-06-29 16:31:13.039+0000', 'PAR-D16-01-C0056000', 'PAR-D16-01', '2030-06-29 16:30:00.000+0000', 1, 31, 'Partidazo, se viene la remontada', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, responde_a, editado) VALUES ('PAR-D16-01', '2030-06-29 16:30:00.000+0000', 3, '2030-06-29 16:31:07.012+0000', 'PAR-D16-01-C0061180', 'USR-0000038', 'hincha_38', 'VISITANTE', 31, 'Increíble lo de este partido', 'es', 'PUBLICADO', 'PAR-D16-01-C0061088', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0000038', '2030-06', '2030-06-29 16:31:07.012+0000', 'PAR-D16-01-C0061180', 'PAR-D16-01', '2030-06-29 16:30:00.000+0000', 3, 31, 'Increíble lo de este partido', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 16:30:00.000+0000', 3, '2030-06-29 16:32:45.775+0000', 'PAR-D16-01-C0062108', 'USR-0000038', 'hincha_38', 'LOCAL', 32, 'Ese pase fue de otro planeta', 'es', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0000038', '2030-06', '2030-06-29 16:32:45.775+0000', 'PAR-D16-01-C0062108', 'PAR-D16-01', '2030-06-29 16:30:00.000+0000', 3, 32, 'Ese pase fue de otro planeta', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 16:30:00.000+0000', 2, '2030-06-29 16:32:14.425+0000', 'PAR-D16-01-C0064000', 'USR-0046475', 'hincha_46475', 'LOCAL', 32, 'Joga bonito, que time', 'en', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0046475', '2030-06', '2030-06-29 16:32:14.425+0000', 'PAR-D16-01-C0064000', 'PAR-D16-01', '2030-06-29 16:30:00.000+0000', 2, 32, 'Joga bonito, que time', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 16:30:00.000+0000', 2, '2030-06-29 16:33:16.190+0000', 'PAR-D16-01-C0072000', 'USR-0032147', 'hincha_32147', 'LOCAL', 33, 'Allez les bleus', 'es', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0032147', '2030-06', '2030-06-29 16:33:16.190+0000', 'PAR-D16-01-C0072000', 'PAR-D16-01', '2030-06-29 16:30:00.000+0000', 2, 33, 'Allez les bleus', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 16:30:00.000+0000', 2, '2030-06-29 16:34:57.327+0000', 'PAR-D16-01-C0074837', 'USR-0000038', 'hincha_38', 'LOCAL', 34, 'Partidazo, se viene la remontada', 'en', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0000038', '2030-06', '2030-06-29 16:34:57.327+0000', 'PAR-D16-01-C0074837', 'PAR-D16-01', '2030-06-29 16:30:00.000+0000', 2, 34, 'Partidazo, se viene la remontada', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 16:30:00.000+0000', 0, '2030-06-29 16:36:51.482+0000', 'PAR-D16-01-C0080000', 'USR-0169134', 'hincha_169134', 'VISITANTE', 36, 'Nos vemos en la próxima ronda', 'es', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0169134', '2030-06', '2030-06-29 16:36:51.482+0000', 'PAR-D16-01-C0080000', 'PAR-D16-01', '2030-06-29 16:30:00.000+0000', 0, 36, 'Nos vemos en la próxima ronda', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, responde_a, editado) VALUES ('PAR-D16-01', '2030-06-29 16:40:00.000+0000', 3, '2030-06-29 16:42:48.328+0000', 'PAR-D16-01-C0088000', 'USR-0079184', 'hincha_79184', 'LOCAL', 42, 'Árbitro, era penal clarísimo', 'ar', 'PUBLICADO', 'PAR-D16-01-C0087884', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0079184', '2030-06', '2030-06-29 16:42:48.328+0000', 'PAR-D16-01-C0088000', 'PAR-D16-01', '2030-06-29 16:40:00.000+0000', 3, 42, 'Árbitro, era penal clarísimo', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 16:40:00.000+0000', 0, '2030-06-29 16:48:25.498+0000', 'PAR-D16-01-C0096000', 'USR-0178566', 'hincha_178566', 'VISITANTE', 48, 'Se nos escapa el partido', 'es', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0178566', '2030-06', '2030-06-29 16:48:25.498+0000', 'PAR-D16-01-C0096000', 'PAR-D16-01', '2030-06-29 16:40:00.000+0000', 0, 48, 'Se nos escapa el partido', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 16:40:00.000+0000', 3, '2030-06-29 16:49:06.476+0000', 'PAR-D16-01-C0104000', 'USR-0127546', 'hincha_127546', 'VISITANTE', 49, 'Cambio ya, el 9 no la toca', 'en', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0127546', '2030-06', '2030-06-29 16:49:06.476+0000', 'PAR-D16-01-C0104000', 'PAR-D16-01', '2030-06-29 16:40:00.000+0000', 3, 49, 'Cambio ya, el 9 no la toca', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 16:50:00.000+0000', 3, '2030-06-29 16:50:16.263+0000', 'PAR-D16-01-C0112000', 'USR-0059074', 'hincha_59074', 'LOCAL', 50, 'El VAR está mirando, esperemos', 'ar', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0059074', '2030-06', '2030-06-29 16:50:16.263+0000', 'PAR-D16-01-C0112000', 'PAR-D16-01', '2030-06-29 16:50:00.000+0000', 3, 50, 'El VAR está mirando, esperemos', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 16:50:00.000+0000', 0, '2030-06-29 16:59:06.373+0000', 'PAR-D16-01-C0120000', 'USR-0000890', 'hincha_890', 'VISITANTE', 59, 'Nos vemos en la próxima ronda', 'ar', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0000890', '2030-06', '2030-06-29 16:59:06.373+0000', 'PAR-D16-01-C0120000', 'PAR-D16-01', '2030-06-29 16:50:00.000+0000', 0, 59, 'Nos vemos en la próxima ronda', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 17:00:00.000+0000', 1, '2030-06-29 17:01:23.424+0000', 'PAR-D16-01-C0122510', 'USR-0000038', 'hincha_38', 'VISITANTE', 61, 'Árbitro, era penal clarísimo', 'en', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0000038', '2030-06', '2030-06-29 17:01:23.424+0000', 'PAR-D16-01-C0122510', 'PAR-D16-01', '2030-06-29 17:00:00.000+0000', 1, 61, 'Árbitro, era penal clarísimo', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 17:00:00.000+0000', 3, '2030-06-29 17:03:00.418+0000', 'PAR-D16-01-C0128000', 'USR-0122957', 'hincha_122957', 'VISITANTE', 63, 'Árbitro, era penal clarísimo', 'en', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0122957', '2030-06', '2030-06-29 17:03:00.418+0000', 'PAR-D16-01-C0128000', 'PAR-D16-01', '2030-06-29 17:00:00.000+0000', 3, 63, 'Árbitro, era penal clarísimo', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 17:00:00.000+0000', 2, '2030-06-29 17:04:05.307+0000', 'PAR-D16-01-C0134302', 'USR-0000038', 'hincha_38', 'VISITANTE', 64, 'Allez les bleus', 'es', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0000038', '2030-06', '2030-06-29 17:04:05.307+0000', 'PAR-D16-01-C0134302', 'PAR-D16-01', '2030-06-29 17:00:00.000+0000', 2, 64, 'Allez les bleus', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 17:00:00.000+0000', 0, '2030-06-29 17:04:05.929+0000', 'PAR-D16-01-C0136000', 'USR-0057866', 'hincha_57866', 'LOCAL', 64, 'Con esta hinchada no se puede perder', 'es', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0057866', '2030-06', '2030-06-29 17:04:05.929+0000', 'PAR-D16-01-C0136000', 'PAR-D16-01', '2030-06-29 17:00:00.000+0000', 0, 64, 'Con esta hinchada no se puede perder', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 17:00:00.000+0000', 3, '2030-06-29 17:04:54.939+0000', 'PAR-D16-01-C0140072', 'USR-0000038', 'hincha_38', 'LOCAL', 64, 'Se nos escapa el partido', 'fr', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0000038', '2030-06', '2030-06-29 17:04:54.939+0000', 'PAR-D16-01-C0140072', 'PAR-D16-01', '2030-06-29 17:00:00.000+0000', 3, 64, 'Se nos escapa el partido', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 17:00:00.000+0000', 3, '2030-06-29 17:05:27.516+0000', 'PAR-D16-01-C0144000', 'USR-0050749', 'hincha_50749', 'NEUTRAL', 65, 'Qué golazo, no lo puedo creer', 'es', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0050749', '2030-06', '2030-06-29 17:05:27.516+0000', 'PAR-D16-01-C0144000', 'PAR-D16-01', '2030-06-29 17:00:00.000+0000', 3, 65, 'Qué golazo, no lo puedo creer', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, responde_a, editado) VALUES ('PAR-D16-01', '2030-06-29 17:00:00.000+0000', 3, '2030-06-29 17:09:01.802+0000', 'PAR-D16-01-C0152000', 'USR-0125122', 'hincha_125122', 'LOCAL', 69, 'Allez les bleus', 'en', 'PUBLICADO', 'PAR-D16-01-C0151996', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0125122', '2030-06', '2030-06-29 17:09:01.802+0000', 'PAR-D16-01-C0152000', 'PAR-D16-01', '2030-06-29 17:00:00.000+0000', 3, 69, 'Allez les bleus', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 17:10:00.000+0000', 0, '2030-06-29 17:15:21.669+0000', 'PAR-D16-01-C0160000', 'USR-0200894', 'hincha_200894', 'VISITANTE', 75, 'Esa defensa está dormida', 'en', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0200894', '2030-06', '2030-06-29 17:15:21.669+0000', 'PAR-D16-01-C0160000', 'PAR-D16-01', '2030-06-29 17:10:00.000+0000', 0, 75, 'Esa defensa está dormida', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 17:20:00.000+0000', 3, '2030-06-29 17:21:22.685+0000', 'PAR-D16-01-C0168000', 'USR-0127974', 'hincha_127974', 'VISITANTE', 81, 'Primer tiempo aburrido, a ver el segundo', 'es', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0127974', '2030-06', '2030-06-29 17:21:22.685+0000', 'PAR-D16-01-C0168000', 'PAR-D16-01', '2030-06-29 17:20:00.000+0000', 3, 81, 'Primer tiempo aburrido, a ver el segundo', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 17:20:00.000+0000', 0, '2030-06-29 17:24:29.498+0000', 'PAR-D16-01-C0172154', 'USR-0000038', 'hincha_38', 'VISITANTE', 84, 'What a save!', 'pt', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0000038', '2030-06', '2030-06-29 17:24:29.498+0000', 'PAR-D16-01-C0172154', 'PAR-D16-01', '2030-06-29 17:20:00.000+0000', 0, 84, 'What a save!', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 17:20:00.000+0000', 0, '2030-06-29 17:25:51.871+0000', 'PAR-D16-01-C0176000', 'USR-0069266', 'hincha_69266', 'VISITANTE', 85, 'Qué golazo, no lo puedo creer', 'fr', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0069266', '2030-06', '2030-06-29 17:25:51.871+0000', 'PAR-D16-01-C0176000', 'PAR-D16-01', '2030-06-29 17:20:00.000+0000', 0, 85, 'Qué golazo, no lo puedo creer', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, motivo_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 17:20:00.000+0000', 2, '2030-06-29 17:27:48.950+0000', 'PAR-D16-01-C0184000', 'USR-0067858', 'hincha_67858', 'VISITANTE', 87, 'Ese pase fue de otro planeta', 'es', 'OCULTO', 'LENGUAJE_OFENSIVO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0067858', '2030-06', '2030-06-29 17:27:48.950+0000', 'PAR-D16-01-C0184000', 'PAR-D16-01', '2030-06-29 17:20:00.000+0000', 2, 87, 'Ese pase fue de otro planeta', 'OCULTO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 17:20:00.000+0000', 1, '2030-06-29 17:28:37.058+0000', 'PAR-D16-01-C0184956', 'USR-0000038', 'hincha_38', 'LOCAL', 88, 'El VAR está mirando, esperemos', 'pt', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0000038', '2030-06', '2030-06-29 17:28:37.058+0000', 'PAR-D16-01-C0184956', 'PAR-D16-01', '2030-06-29 17:20:00.000+0000', 1, 88, 'El VAR está mirando, esperemos', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 17:20:00.000+0000', 2, '2030-06-29 17:28:31.812+0000', 'PAR-D16-01-C0192000', 'USR-0026526', 'hincha_26526', 'VISITANTE', 88, 'Partidazo, se viene la remontada', 'fr', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0026526', '2030-06', '2030-06-29 17:28:31.812+0000', 'PAR-D16-01-C0192000', 'PAR-D16-01', '2030-06-29 17:20:00.000+0000', 2, 88, 'Partidazo, se viene la remontada', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 17:20:00.000+0000', 0, '2030-06-29 17:28:58.186+0000', 'PAR-D16-01-C0192436', 'USR-0000038', 'hincha_38', 'LOCAL', 88, 'Faltan 5 minutos, aguanten', 'pt', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0000038', '2030-06', '2030-06-29 17:28:58.186+0000', 'PAR-D16-01-C0192436', 'PAR-D16-01', '2030-06-29 17:20:00.000+0000', 0, 88, 'Faltan 5 minutos, aguanten', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 17:20:00.000+0000', 1, '2030-06-29 17:28:26.509+0000', 'PAR-D16-01-C0193506', 'USR-0000038', 'hincha_38', 'LOCAL', 88, 'Con esta hinchada no se puede perder', 'es', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0000038', '2030-06', '2030-06-29 17:28:26.509+0000', 'PAR-D16-01-C0193506', 'PAR-D16-01', '2030-06-29 17:20:00.000+0000', 1, 88, 'Con esta hinchada no se puede perder', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 17:20:00.000+0000', 2, '2030-06-29 17:29:19.168+0000', 'PAR-D16-01-C0200000', 'USR-0075261', 'hincha_75261', 'LOCAL', 89, 'Joga bonito, que time', 'en', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0075261', '2030-06', '2030-06-29 17:29:19.168+0000', 'PAR-D16-01-C0200000', 'PAR-D16-01', '2030-06-29 17:20:00.000+0000', 2, 89, 'Joga bonito, que time', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, responde_a, editado) VALUES ('PAR-D16-01', '2030-06-29 17:20:00.000+0000', 3, '2030-06-29 17:29:22.285+0000', 'PAR-D16-01-C0203900', 'USR-0000038', 'hincha_38', 'LOCAL', 89, 'Qué golazo, no lo puedo creer', 'es', 'PUBLICADO', 'PAR-D16-01-C0203705', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0000038', '2030-06', '2030-06-29 17:29:22.285+0000', 'PAR-D16-01-C0203900', 'PAR-D16-01', '2030-06-29 17:20:00.000+0000', 3, 89, 'Qué golazo, no lo puedo creer', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, motivo_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 17:30:00.000+0000', 1, '2030-06-29 17:30:42.648+0000', 'PAR-D16-01-C0208000', 'USR-0063918', 'hincha_63918', 'LOCAL', 90, 'Vamos equipo! Hoy se gana', 'en', 'OCULTO', 'LENGUAJE_OFENSIVO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0063918', '2030-06', '2030-06-29 17:30:42.648+0000', 'PAR-D16-01-C0208000', 'PAR-D16-01', '2030-06-29 17:30:00.000+0000', 1, 90, 'Vamos equipo! Hoy se gana', 'OCULTO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 17:30:00.000+0000', 3, '2030-06-29 17:30:35.684+0000', 'PAR-D16-01-C0213781', 'USR-0000038', 'hincha_38', 'VISITANTE', 90, 'Faltan 5 minutos, aguanten', 'es', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0000038', '2030-06', '2030-06-29 17:30:35.684+0000', 'PAR-D16-01-C0213781', 'PAR-D16-01', '2030-06-29 17:30:00.000+0000', 3, 90, 'Faltan 5 minutos, aguanten', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 17:30:00.000+0000', 2, '2030-06-29 17:30:45.577+0000', 'PAR-D16-01-C0216000', 'USR-0058863', 'hincha_58863', 'LOCAL', 90, 'Joga bonito, que time', 'es', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0058863', '2030-06', '2030-06-29 17:30:45.577+0000', 'PAR-D16-01-C0216000', 'PAR-D16-01', '2030-06-29 17:30:00.000+0000', 2, 90, 'Joga bonito, que time', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 17:30:00.000+0000', 1, '2030-06-29 17:31:43.967+0000', 'PAR-D16-01-C0224000', 'USR-0094298', 'hincha_94298', 'VISITANTE', 91, 'Se nos escapa el partido', 'en', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0094298', '2030-06', '2030-06-29 17:31:43.967+0000', 'PAR-D16-01-C0224000', 'PAR-D16-01', '2030-06-29 17:30:00.000+0000', 1, 91, 'Se nos escapa el partido', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 17:30:00.000+0000', 1, '2030-06-29 17:31:11.743+0000', 'PAR-D16-01-C0232000', 'USR-0138153', 'hincha_138153', 'NEUTRAL', 91, 'Árbitro, era penal clarísimo', 'pt', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0138153', '2030-06', '2030-06-29 17:31:11.743+0000', 'PAR-D16-01-C0232000', 'PAR-D16-01', '2030-06-29 17:30:00.000+0000', 1, 91, 'Árbitro, era penal clarísimo', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 17:30:00.000+0000', 2, '2030-06-29 17:32:20.722+0000', 'PAR-D16-01-C0240000', 'USR-0205418', 'hincha_205418', 'VISITANTE', 92, 'Cambio ya, el 9 no la toca', 'pt', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0205418', '2030-06', '2030-06-29 17:32:20.722+0000', 'PAR-D16-01-C0240000', 'PAR-D16-01', '2030-06-29 17:30:00.000+0000', 2, 92, 'Cambio ya, el 9 no la toca', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 17:30:00.000+0000', 2, '2030-06-29 17:33:06.636+0000', 'PAR-D16-01-C0241943', 'USR-0000038', 'hincha_38', 'LOCAL', 93, 'Allez les bleus', 'es', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0000038', '2030-06', '2030-06-29 17:33:06.636+0000', 'PAR-D16-01-C0241943', 'PAR-D16-01', '2030-06-29 17:30:00.000+0000', 2, 93, 'Allez les bleus', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, responde_a, editado) VALUES ('PAR-D16-01', '2030-06-29 17:30:00.000+0000', 1, '2030-06-29 17:34:08.595+0000', 'PAR-D16-01-C0248000', 'USR-0010273', 'hincha_10273', 'LOCAL', 94, 'Árbitro, era penal clarísimo', 'ar', 'PUBLICADO', 'PAR-D16-01-C0247973', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0010273', '2030-06', '2030-06-29 17:34:08.595+0000', 'PAR-D16-01-C0248000', 'PAR-D16-01', '2030-06-29 17:30:00.000+0000', 1, 94, 'Árbitro, era penal clarísimo', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 17:30:00.000+0000', 3, '2030-06-29 17:35:07.526+0000', 'PAR-D16-01-C0253699', 'USR-0000038', 'hincha_38', 'NEUTRAL', 95, 'Qué golazo, no lo puedo creer', 'es', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0000038', '2030-06', '2030-06-29 17:35:07.526+0000', 'PAR-D16-01-C0253699', 'PAR-D16-01', '2030-06-29 17:30:00.000+0000', 3, 95, 'Qué golazo, no lo puedo creer', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 17:30:00.000+0000', 2, '2030-06-29 17:36:38.477+0000', 'PAR-D16-01-C0256000', 'USR-0045237', 'hincha_45237', 'LOCAL', 96, 'Increíble lo de este partido', 'es', 'PENDIENTE', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0045237', '2030-06', '2030-06-29 17:36:38.477+0000', 'PAR-D16-01-C0256000', 'PAR-D16-01', '2030-06-29 17:30:00.000+0000', 2, 96, 'Increíble lo de este partido', 'PENDIENTE');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 17:30:00.000+0000', 1, '2030-06-29 17:38:14.616+0000', 'PAR-D16-01-C0264000', 'USR-0246113', 'hincha_246113', 'VISITANTE', 98, 'Partidazo, se viene la remontada', 'es', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0246113', '2030-06', '2030-06-29 17:38:14.616+0000', 'PAR-D16-01-C0264000', 'PAR-D16-01', '2030-06-29 17:30:00.000+0000', 1, 98, 'Partidazo, se viene la remontada', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 17:30:00.000+0000', 0, '2030-06-29 17:38:48.617+0000', 'PAR-D16-01-C0264452', 'USR-0000038', 'hincha_38', 'VISITANTE', 98, 'Qué atajada del arquero!!', 'es', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0000038', '2030-06', '2030-06-29 17:38:48.617+0000', 'PAR-D16-01-C0264452', 'PAR-D16-01', '2030-06-29 17:30:00.000+0000', 0, 98, 'Qué atajada del arquero!!', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 17:40:00.000+0000', 1, '2030-06-29 17:40:42.571+0000', 'PAR-D16-01-C0272000', 'USR-0044113', 'hincha_44113', 'VISITANTE', 100, 'Vamos campeón! Hoy se gana', 'pt', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0044113', '2030-06', '2030-06-29 17:40:42.571+0000', 'PAR-D16-01-C0272000', 'PAR-D16-01', '2030-06-29 17:40:00.000+0000', 1, 100, 'Vamos campeón! Hoy se gana', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 17:40:00.000+0000', 3, '2030-06-29 17:46:22.281+0000', 'PAR-D16-01-C0280000', 'USR-0122835', 'hincha_122835', 'LOCAL', 106, 'Qué atajada del arquero!!', 'pt', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0122835', '2030-06', '2030-06-29 17:46:22.281+0000', 'PAR-D16-01-C0280000', 'PAR-D16-01', '2030-06-29 17:40:00.000+0000', 3, 106, 'Qué atajada del arquero!!', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 17:50:00.000+0000', 0, '2030-06-29 17:53:35.301+0000', 'PAR-D16-01-C0288000', 'USR-0076474', 'hincha_76474', 'NEUTRAL', 113, 'Árbitro, era penal clarísimo', 'fr', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0076474', '2030-06', '2030-06-29 17:53:35.301+0000', 'PAR-D16-01-C0288000', 'PAR-D16-01', '2030-06-29 17:50:00.000+0000', 0, 113, 'Árbitro, era penal clarísimo', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, responde_a, editado) VALUES ('PAR-D16-01', '2030-06-29 17:50:00.000+0000', 1, '2030-06-29 17:56:39.686+0000', 'PAR-D16-01-C0291231', 'USR-0000038', 'hincha_38', 'NEUTRAL', 116, 'El VAR está mirando, esperemos', 'en', 'PUBLICADO', 'PAR-D16-01-C0291168', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0000038', '2030-06', '2030-06-29 17:56:39.686+0000', 'PAR-D16-01-C0291231', 'PAR-D16-01', '2030-06-29 17:50:00.000+0000', 1, 116, 'El VAR está mirando, esperemos', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 17:50:00.000+0000', 2, '2030-06-29 17:57:11.610+0000', 'PAR-D16-01-C0292519', 'USR-0000038', 'hincha_38', 'LOCAL', 117, 'Ese pase fue de otro planeta', 'en', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0000038', '2030-06', '2030-06-29 17:57:11.610+0000', 'PAR-D16-01-C0292519', 'PAR-D16-01', '2030-06-29 17:50:00.000+0000', 2, 117, 'Ese pase fue de otro planeta', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 18:00:00.000+0000', 3, '2030-06-29 18:01:23.912+0000', 'PAR-D16-01-C0296000', 'USR-0027852', 'hincha_27852', 'VISITANTE', 121, 'Vamos campeón! Hoy se gana', 'en', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0027852', '2030-06', '2030-06-29 18:01:23.912+0000', 'PAR-D16-01-C0296000', 'PAR-D16-01', '2030-06-29 18:00:00.000+0000', 3, 121, 'Vamos campeón! Hoy se gana', 'PUBLICADO');
APPLY BATCH;
BEGIN BATCH
  INSERT INTO comentarios_por_partido (partido_id, ventana, bucket, creado_en, comentario_id, usuario_id, alias_usuario, hinchada, minuto_partido, contenido, idioma, estado_moderacion, editado) VALUES ('PAR-D16-01', '2030-06-29 18:00:00.000+0000', 1, '2030-06-29 18:04:45.946+0000', 'PAR-D16-01-C0299344', 'USR-0000038', 'hincha_38', 'LOCAL', 124, 'Increíble lo de este partido', 'es', 'PUBLICADO', false);
  INSERT INTO comentarios_por_usuario (usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket, minuto_partido, contenido, estado_moderacion) VALUES ('USR-0000038', '2030-06', '2030-06-29 18:04:45.946+0000', 'PAR-D16-01-C0299344', 'PAR-D16-01', '2030-06-29 18:00:00.000+0000', 1, 124, 'Increíble lo de este partido', 'PUBLICADO');
APPLY BATCH;

-- ----------------------------------------------------------------------------
--  3) Verificación: correr este archivo dos veces debe dar los mismos conteos.
-- ----------------------------------------------------------------------------
SELECT count(*) AS config_partidos FROM config_particion_partido;
SELECT count(*) AS comentarios_par_a_1 FROM comentarios_por_partido WHERE partido_id = 'PAR-A-1' AND ventana IN ('2030-06-09 13:00:00.000+0000', '2030-06-09 13:10:00.000+0000', '2030-06-09 13:20:00.000+0000', '2030-06-09 13:30:00.000+0000', '2030-06-09 13:40:00.000+0000', '2030-06-09 13:50:00.000+0000', '2030-06-09 14:00:00.000+0000', '2030-06-09 14:10:00.000+0000', '2030-06-09 14:20:00.000+0000', '2030-06-09 14:30:00.000+0000', '2030-06-09 14:40:00.000+0000', '2030-06-09 14:50:00.000+0000', '2030-06-09 15:00:00.000+0000') AND bucket = 0;
SELECT count(*) AS historial_demo FROM comentarios_por_usuario WHERE usuario_id = 'USR-0000038' AND mes = '2030-06';
