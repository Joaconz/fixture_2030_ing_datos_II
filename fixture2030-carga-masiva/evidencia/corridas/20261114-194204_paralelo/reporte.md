# Carga masiva integrada — modo paralelo

- Ejecutado: 2026-11-14T19:42:07+00:00 (UTC) · commit `62d5a41`
- Comando: `python fixture2030-carga-masiva/scripts/orquestador.py --modo paralelo`
- VM de Docker: 10 CPUs, 7.75 GiB · 33 contenedores ajenos a la prueba ocupaban hasta 4.565 MiB
- Parámetros de los cargadores: Cassandra concurrencia 128 · InfluxDB lote 50.000, hilos 8
- Memoria al empezar: VM 7.934 MiB, 33 contenedores ajenos con 4.595 MiB, RAM libre del host None MiB · presupuesto para la prueba: 2.571 MiB
- Orden: mongodb → neo4j → cassandra → influxdb → redis
- Desde volúmenes vacíos: sí (limpieza al inicio de la corrida)
- Insumos de InfluxDB: generados en esta corrida (26,3 s, fuera del tiempo de carga)

## Tiempos por base

| Base | Arranque (s) | Preparación (s) | **Carga (s)** | Carga desde → hasta (s) | Volumen | Throughput de la carga | Verificación (s) | Apagado (s) | Estado |
|---|---:|---:|---:|---|---:|---:|---:|---:|---|
| mongodb | 6,4 | 12,0 | 1,5 | 18,4 → 19,9 | 1.728 documentos | 1.187,7 documentos/s | 1,2 | 3,3 | ok |
| redis | 5,9 | 0,0 | 3,6 | 5,9 → 9,5 | 100.000 usuarios | 27.878,1 usuarios/s | 23,8 | 1,7 | ok |
| neo4j | 15,4 | 2,0 | 7,5 | 41,8 → 49,3 | 13.736 nodos+relaciones | 1.842,9 nodos+relaciones/s | 0,6 | 3,3 | ok |
| influxdb | 22,5 | 4,5 | 46,3 | 80,3 → 126,5 | 10.094.400 puntos | 218.245,3 puntos/s | 3,5 | 0,4 | ok |
| cassandra | 58,8 | 5,2 | 188,1 | 194,5 → 382,6 | 1.050.000 comentarios | 5.581,1 comentarios/s | 13,4 | 6,6 | ok |

| Total | Valor |
|---|---|
| **Reloj: arranque de la primera → fin de la última carga** | **382,6 s** |
| Reloj total (incluye verificación, distribución y apagado) | 402,7 s |
| Suma de las fases de carga | 247,0 s |
| Suma de arranque + preparación + carga de todas las bases | 379,7 s |
| Registros cargados (de distinta naturaleza) | 11.259.864 |
| Registros por segundo de reloj | 29.429,9 |
| Última carga en terminar | cassandra |
| Carga más larga | cassandra (188,1 s) |

- **mongodb**: 64 equipos + 1664 jugadores (load/seed.js, bulkWrite con upsert)
- **redis**: carga_muestra.sh + carga_volumen.sh 100000: conteo usuarios=100000 sesiones=100000 perfiles=100000 (11 comandos por usuario, redis-cli --pipe)
- **neo4j**: 3,089 nodos + 10,647 relaciones (queries/carga.cypher, MERGE)
- **influxdb**: 10,094,400 puntos en fixture2030_vivo (scripts/carga_lotes.py --perfil completo, lote 50000, hilos 8) · 221,934.5 puntos/s (medida por carga_lotes.py)
- **cassandra**: 1,050,000 comentarios = 2,100,000 filas en 2 tablas (scripts/carga_masiva.py, concurrencia 128) · 12,124 escrituras/s (medida por carga_masiva.py)

### Admisión (cuándo arrancó cada base)

| Base | Admitida en (s) | Reservado al admitirla (MiB) | Bases en curso | RAM libre del host (MiB) |
|---|---:|---:|---:|---:|
| mongodb | 0,0 | 1.152 | 1 | None |
| redis | 0,0 | 1.664 | 2 | None |
| neo4j | 24,3 | 2.560 | 2 | None |
| influxdb | 53,2 | 2.560 | 1 | None |
| cassandra | 130,4 | 2.816 | 1 | None |

## Recursos (docker stats durante todas las fases)

188 muestras. Pico de RAM de los contenedores de la prueba: **2.359 MiB**; pico de RAM de toda la VM (prueba + ajenos): **5.910 MiB** de 7.936 MiB; pico de CPU de la prueba: **518,7 %** (100 % = 1 CPU, 10 CPUs = 1000 %). RAM libre mínima del host: **None MiB**.

| Contenedor | Muestras | CPU prom. (%) | CPU máx. (%) | RAM máx. (MiB) |
|---|---:|---:|---:|---:|
| f30cm-cassandra | 126 | 151,5 | 343,7 | 1.955 |
| f30cm-cassandra-cargador | 97 | 97,7 | 116,0 | 441 |
| f30cm-influxdb | 28 | 76,3 | 474,9 | 1.514 |
| f30cm-influxdb-cargador | 21 | 13,6 | 33,6 | 128 |
| f30cm-mongodb | 9 | 36,6 | 167,5 | 521 |
| f30cm-mongodb-cargador | 3 | 37,0 | 99,6 | 37 |
| f30cm-neo4j | 13 | 221,3 | 453,0 | 1.371 |
| f30cm-redis | 15 | 60,1 | 133,1 | 141 |

## Validación de integridad

25 de 26 chequeos OK · fallidos: ninguno · informativos: ['Cruce · equipos MongoDB sin equipoId igual en Neo4j (H1, se mide)']

| Chequeo | Esperado | Obtenido | Resultado |
|---|---:|---:|---|
| MongoDB · equipos | 64 | 64 | OK |
| MongoDB · jugadores | 1.664 | 1.664 | OK |
| MongoDB · dni duplicados | 0 | 0 | OK |
| MongoDB · (equipo, dorsal) duplicados | 0 | 0 | OK |
| MongoDB · jugadores sin equipo | 0 | 0 | OK |
| Neo4j · partidos | 127 | 127 | OK |
| Neo4j · eventos | 1.572 | 1.572 | OK |
| Neo4j · partidoId duplicados | 0 | 0 | OK |
| Neo4j · eventoId duplicados | 0 | 0 | OK |
| Neo4j · equipoId / dni duplicados | 0 | 0 | OK |
| Neo4j · eventos sin partido | 0 | 0 | OK |
| Neo4j · relaciones del enunciado presentes | las 5 | las 5 | OK |
| Cassandra · comentarios (comentarios_por_partido) | 1.050.000 | 1.050.000 | OK |
| Cassandra · comentarios (comentarios_por_usuario) | 1.050.000 | 1.050.000 | OK |
| Cassandra · comentario_id duplicados | 0 | 0 | OK |
| Cassandra · comentarios en una sola de las dos vistas | 0 | 0 | OK |
| InfluxDB · puntos | 10.094.400 | 10.094.400 | OK |
| InfluxDB · estadisticas_equipo = manifiesto | 1.276.800 | 1.276.800 | OK |
| InfluxDB · audiencia_partido = manifiesto | 7.795.200 | 7.795.200 | OK |
| InfluxDB · operacion_plataforma = manifiesto | 1.022.400 | 1.022.400 | OK |
| Redis · usuarios del volumen (índice de sesiones, TTL 12 h) | 100.000 | 100.000 | OK |
| Redis · usuarios con != 1 sesión (duplicados) | 0 | 0 | OK |
| Cruce · partido_id de cassandra que no existen en Neo4j | 0 | 0 | OK |
| Cruce · partido_id de redis que no existen en Neo4j | 0 | 0 | OK |
| Cruce · partido_id de influxdb que no existen en Neo4j | 0 | 0 | OK |
| Cruce · equipos MongoDB sin equipoId igual en Neo4j (H1, se mide) | medido | 12 | H1 |

### Referencias cruzadas

- `partido_id` de **cassandra**: 112 distintos; inexistentes en Neo4j: 0 ; partidos de Neo4j sin datos en esta base: 15
- `partido_id` de **redis**: 112 distintos; inexistentes en Neo4j: 0 ; partidos de Neo4j sin datos en esta base: 15
- `partido_id` de **influxdb**: 112 distintos; inexistentes en Neo4j: 0 ; partidos de Neo4j sin datos en esta base: 15

**Equipos MongoDB ↔ Neo4j (hallazgo H1, medido y sin corregir)**: 64 en MongoDB, 64 en Neo4j, **52 con el mismo código** y **12 que no coinciden** de cada lado.

- Mismo nombre, distinto código (5): Chile CHL/CHI, Paraguay PRY/PAR, Arabia Saudita SAU/KSA, Uruguay URY/URU, Sudáfrica ZAF/RSA
- Solo en MongoDB, sin par por nombre (7): CHN China, HAI Haití, IND India, NCL Nueva Caledonia, PNG Papúa Nueva Guinea, SLV El Salvador, TRI Trinidad y Tobago
- Solo en Neo4j, sin par por nombre (7): COD RD Congo, GRE Grecia, MLI Malí, NOR Noruega, ROU Rumania, UAE Emiratos Árabes Unidos, WAL Gales

## Distribución de los datos

Interpretación: `docs/distribucion_y_escalabilidad.md`. Datos completos en `reporte.json` → `distribucion`.

### MongoDB

- Jugadores por equipo: 64 equipos, mín 26, máx 26, prom 26.0
- Por confederación: UEFA 520 (20 eq.), AFC 260 (10 eq.), CONMEBOL 260 (10 eq.), CONCACAF 260 (10 eq.), CAF 260 (10 eq.), OFC 104 (4 eq.)
- Por posición: Mediocampista 437, Delantero 419, Arquero 418, Defensor 390
- `equipos`: 64 docs, 14.467 B de datos (226 B/doc), 4.096 B en disco, 2 índices (8.192 B)
- `jugadores`: 1.664 docs, 368.241 B de datos (221 B/doc), 4.096 B en disco, 4 índices (16.384 B)

### Neo4j

- Nodos por etiqueta: Evento 1.572, Jugador 1.282, Partido 127, Equipo 64, Grupo 16, Sede 16, TipoEvento 12
- Relaciones por tipo: OCURRE_EN 1.572, ES_DE_TIPO 1.572, PROTAGONIZADO_POR 1.572, SIGUIENTE_EVENTO 1.446, JUEGA_EN 1.282, PARTICIPA 1.248, CAUSA_DE 702, PARTICIPA_EN 254, ANOTA 220, ASISTE 220, RECIBE_TARJETA 136, REEMPLAZA 136, SE_JUEGA_EN 127, CORRESPONDE_A 96, PERTENECE_A 64

| Etiqueta | Grado mín | p50 | p99 | máx | prom |
|---|---:|---:|---:|---:|---:|
| Evento | 4 | 6 | 7 | 7 | 5.7 |
| Jugador | 1 | 1 | 21 | 29 | 4.0 |
| Partido | 3 | 30 | 37 | 37 | 28.8 |
| Equipo | 22 | 25 | 31 | 31 | 25.0 |
| Grupo | 10 | 10 | 10 | 10 | 10.0 |
| Sede | 7 | 7 | 11 | 11 | 7.9 |
| TipoEvento | 0 | 126 | 294 | 294 | 131.0 |

- Más conectados: TipoEvento PASE (294), TipoEvento GOL (220), TipoEvento ASISTENCIA (220), TipoEvento FALTA (136), TipoEvento SUSTITUCION (136)
- Eventos por fase: GRUPOS 96 partidos / 1152 eventos, DIECISEISAVOS 16 partidos / 220 eventos, OCTAVOS 8 partidos / 116 eventos, CUARTOS 4 partidos / 52 eventos, SEMIFINAL 2 partidos / 32 eventos, FINAL 1 partidos / 0 eventos

### Cassandra

- `comentarios_por_partido`: SSTable count: 2 · Space used (live): 74075025 · Space used (total): 74075025 · Number of partitions (estimate): 1725 · Memtable data size: 0 · Local write count: 1050000 · Compacted partition minimum bytes: 5723 · Compacted partition maximum bytes: 2346799 · Compacted partition mean bytes: 84334
- `comentarios_por_usuario`: SSTable count: 2 · Space used (live): 61334365 · Space used (total): 61334365 · Number of partitions (estimate): 356876 · Memtable data size: 0 · Local write count: 1050000 · Compacted partition minimum bytes: 104 · Compacted partition maximum bytes: 20501 · Compacted partition mean bytes: 359
- `config_particion_partido`: SSTable count: 1 · Space used (live): 9031 · Space used (total): 9031 · Number of partitions (estimate): 112 · Memtable data size: 0 · Local write count: 112 · Compacted partition minimum bytes: 61 · Compacted partition maximum bytes: 86 · Compacted partition mean bytes: 73
- Filas por partición (recorrido completo) `comentarios_por_partido`: 1725 particiones · {'min': 49, 'p50': 258, 'p90': 1052, 'p99': 5883, 'max': 16161}
- `comentarios_por_usuario`: 360052 particiones · {'min': 1, 'p50': 2, 'p90': 6, 'p99': 11, 'max': 192}
- Particiones más grandes: PAR-D16-01 2030-06-29T17:30:00 bucket 0 = 16.161; PAR-D16-01 2030-06-29T17:30:00 bucket 1 = 16.160; PAR-D16-01 2030-06-29T17:30:00 bucket 2 = 16.160; PAR-D16-01 2030-06-29T17:30:00 bucket 3 = 16.159; PAR-D16-01 2030-06-29T17:20:00 bucket 2 = 9.993
- Comentarios por partido: {'n': 112, 'min': 4687, 'p50': 4688, 'p90': 20000, 'max': 300000, 'prom': 9375, 'max_sobre_prom': 32.0}
- Más comentados: PAR-D16-01 300.000, PAR-D16-02 20.000, PAR-D16-03 20.000, PAR-D16-04 20.000, PAR-D16-05 20.000

```
fixture2030_comentarios/comentarios_por_partido histograms
Percentile      Read Latency     Write Latency          SSTables    Partition Size        Cell Count
                    (micros)          (micros)                             (bytes)                  
50%                     0.00             20.00              0.00             35425              2299
75%                     0.00             42.00              0.00             88148              5722
95%                     0.00           1109.00              0.00            315852             20501
98%                     0.00           1916.00              0.00            454826             29521
99%                     0.00           2299.00              0.00            785939             51012
Min                     0.00              0.00              0.00              5723               373
Max                     0.00         182785.00              0.00           2346799            152321
```

### Redis

- Por tipo (`--memkeys`): list 0 claves / 0 B, hash 202.176 claves / 38.692.870 B, stream 0 claves / 0 B, string 0 claves / 0 B, set 102.001 claves / 8.586.705 B, zset 2 claves / 1.606 B
- Por prefijo: `f30:ses` 102.173, `f30:usr:…:sesiones` 102.000, `f30:cache:usuario:…:perfil` 100.000, `f30:voto` 2, `f30:rank` 1
- Memoria: used_memory=63969600, used_memory_human=61.01M, used_memory_peak_human=66.49M, used_memory_dataset=39497408, maxmemory_human=256.00M, maxmemory_policy=volatile-lru, mem_fragmentation_ratio=1.43, db0=keys=304176,expires=304174,avg_ttl=15075968,subexpiry=0, expired_keys=27, evicted_keys=0
- Bytes por clave (MEMORY USAGE): sesion (HASH) 262, indice de sesiones (SET) 84, perfil en cache (HASH) 121

### InfluxDB

- Series por tabla: estadisticas_equipo 224, audiencia_partido 896, operacion_plataforma 5
- Puntos por partido en `estadisticas_equipo`: n 112, min 11.400, p50 11.400, p90 11.400, max 11.400, prom 11.400, max_sobre_prom 1,0 · mayores: PAR-A-2 11.400, PAR-E-2 11.400, PAR-E-1 11.400
- Puntos por partido en `audiencia_partido`: n 112, min 69.600, p50 69.600, p90 69.600, max 69.600, prom 69.600, max_sobre_prom 1,0 · mayores: PAR-I-1 69.600, PAR-A-1 69.600, PAR-M-2 69.600
- Partidos por audiencia: NORMAL 96, MAXIMA 1, ALTA 15
- Disco: {'tamano': '603M', 'archivos_parquet': '1000', 'archivos_wal': '47'}

