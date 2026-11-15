# Carga masiva integrada — modo paralelo

- Ejecutado: 2026-11-11T20:36:43+00:00 (UTC) · commit `fc08ebb`
- Comando: `python fixture2030-carga-masiva/scripts/orquestador.py --modo paralelo`
- VM de Docker: 12 CPUs, 7.68 GiB · 18 contenedores ajenos a la prueba ocupaban hasta 4.401 MiB
- Parámetros de los cargadores: Cassandra concurrencia 128 · InfluxDB lote 50.000, hilos 8
- Memoria al empezar: VM 7.869 MiB, 17 contenedores ajenos con 3.966 MiB, RAM libre del host 1.383 MiB · presupuesto para la prueba: 3.135 MiB
- Orden: mongodb → neo4j → cassandra → influxdb → redis
- Desde volúmenes vacíos: sí (limpieza al inicio de la corrida)

> **Corrida cortada por el vigía de memoria:** RAM disponible del host 45 MiB (< 250)
- Insumos de InfluxDB: reutilizados (deterministas)

## Tiempos por base

| Base | Arranque (s) | Preparación (s) | **Carga (s)** | Carga desde → hasta (s) | Volumen | Throughput de la carga | Verificación (s) | Apagado (s) | Estado |
|---|---:|---:|---:|---|---:|---:|---:|---:|---|
| mongodb | 12,8 | 6,5 | 3,2 | 19,3 → 22,5 | 1.728 documentos | 542,6 documentos/s | 2,8 | 12,8 | ok |
| redis | 8,9 | 0,0 | 15,9 | 8,9 → 24,9 | 100.000 usuarios | 6.270,5 usuarios/s | 65,3 | 16,3 | ok |
| neo4j | 83,2 | 8,5 | 25,4 | 129,8 → 155,2 | 13.736 nodos+relaciones | 540,1 nodos+relaciones/s | 2,6 | 13,3 | ok |
| cassandra | 94,5 | 20,6 | 491,7 | 286,2 → 778,0 | –  | – /s | – | – | falló en carga |
| influxdb | – | – | – | – → – | –  | – /s | – | – | no arrancó (vigía) |

| Total | Valor |
|---|---|
| **Reloj: arranque de la primera → fin de la última carga** | **778,0 s** |
| Reloj total (incluye verificación, distribución y apagado) | 782,0 s |
| Suma de las fases de carga | 536,2 s |
| Suma de arranque + preparación + carga de todas las bases | 771,2 s |
| Registros cargados (de distinta naturaleza) | 115.464 |
| Registros por segundo de reloj | 148,4 |
| Última carga en terminar | cassandra |
| Carga más larga | cassandra (491,7 s) |

- **mongodb**: 64 equipos + 1664 jugadores (load/seed.js, bulkWrite con upsert)
- **redis**: carga_muestra.sh + carga_volumen.sh 100000: conteo usuarios=100000 sesiones=100000 perfiles=100000 (11 comandos por usuario, redis-cli --pipe)
- **neo4j**: 3,089 nodos + 10,647 relaciones (queries/carga.cypher, MERGE)
- **cassandra**: 
  - error: `carga: ErrorPaso: docker exec f30cm-cassandra-cargador python scripts/carga_masiva.py --salida /app/evidencia/20261111-203638_paralelo… salió con 137 (491.7 s):
`
- **influxdb**: 

### Admisión (cuándo arrancó cada base)

| Base | Admitida en (s) | Reservado al admitirla (MiB) | Bases en curso | RAM libre del host (MiB) |
|---|---:|---:|---:|---:|
| mongodb | 0,0 | 1.152 | 1 | 1.593 |
| redis | 0,0 | 1.664 | 2 | 1.593 |
| neo4j | 38,1 | 2.560 | 2 | 1.091 |
| cassandra | 171,1 | 2.816 | 1 | 857 |

## Recursos (docker stats durante todas las fases)

243 muestras. Pico de RAM de los contenedores de la prueba: **1.886 MiB**; pico de RAM de toda la VM (prueba + ajenos): **6.011 MiB** de 7.864 MiB; pico de CPU de la prueba: **466,3 %** (100 % = 1 CPU, 12 CPUs = 1200 %). RAM libre mínima del host: **45 MiB**.

| Contenedor | Muestras | CPU prom. (%) | CPU máx. (%) | RAM máx. (MiB) |
|---|---:|---:|---:|---:|
| f30cm-cassandra | 193 | 149,5 | 359,1 | 1.765 |
| f30cm-cassandra-cargador | 157 | 101,0 | 122,0 | 137 |
| f30cm-mongodb | 7 | 55,2 | 140,6 | 469 |
| f30cm-mongodb-cargador | 6 | 50,9 | 143,6 | 50 |
| f30cm-neo4j | 37 | 194,9 | 400,4 | 1.493 |
| f30cm-redis | 29 | 55,9 | 134,1 | 89 |

## Validación de integridad

15 de 16 chequeos OK · fallidos: ninguno · informativos: ['Cruce · equipos MongoDB sin equipoId igual en Neo4j (H1, se mide)']

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
| Redis · usuarios del volumen (índice de sesiones, TTL 12 h) | 100.000 | 100.000 | OK |
| Redis · usuarios con != 1 sesión (duplicados) | 0 | 0 | OK |
| Cruce · partido_id de redis que no existen en Neo4j | 0 | 0 | OK |
| Cruce · equipos MongoDB sin equipoId igual en Neo4j (H1, se mide) | medido | 12 | H1 |

### Referencias cruzadas

- `partido_id` de **redis**: 112 distintos; inexistentes en Neo4j: 0 ; partidos de Neo4j sin datos en esta base: 15

**Equipos MongoDB ↔ Neo4j (hallazgo H1, medido y sin corregir)**: 64 en MongoDB, 64 en Neo4j, **52 con el mismo código** y **12 que no coinciden** de cada lado.

- Mismo nombre, distinto código (5): Chile CHL/CHI, Paraguay PRY/PAR, Arabia Saudita SAU/KSA, Uruguay URY/URU, Sudáfrica ZAF/RSA
- Solo en MongoDB, sin par por nombre (7): CHN China, HAI Haití, IND India, NCL Nueva Caledonia, PNG Papúa Nueva Guinea, SLV El Salvador, TRI Trinidad y Tobago
- Solo en Neo4j, sin par por nombre (7): COD RD Congo, GRE Grecia, MLI Malí, NOR Noruega, ROU Rumania, UAE Emiratos Árabes Unidos, WAL Gales

## Distribución de los datos

Interpretación: `docs/distribucion_y_escalabilidad.md`. Datos completos en `reporte.json` → `distribucion`.

### MongoDB

- Jugadores por equipo: 64 equipos, mín 26, máx 26, prom 26.0
- Por confederación: UEFA 520 (20 eq.), AFC 260 (10 eq.), CAF 260 (10 eq.), CONCACAF 260 (10 eq.), CONMEBOL 260 (10 eq.), OFC 104 (4 eq.)
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

### Redis

- Por tipo (`--memkeys`): list 0 claves / 0 B, hash 202.129 claves / 38.680.818 B, stream 0 claves / 0 B, string 0 claves / 0 B, set 102.001 claves / 8.586.705 B, zset 2 claves / 1.606 B
- Por prefijo: `f30:ses` 102.119, `f30:usr:…:sesiones` 102.000, `f30:cache:usuario:…:perfil` 100.000, `f30:voto` 2, `f30:rank` 1
- Memoria: used_memory=63935048, used_memory_human=60.97M, used_memory_peak_human=66.45M, used_memory_dataset=39498056, maxmemory_human=256.00M, maxmemory_policy=volatile-lru, mem_fragmentation_ratio=1.47, db0=keys=304122,expires=304120,avg_ttl=14591419,subexpiry=0, expired_keys=81, evicted_keys=0
- Bytes por clave (MEMORY USAGE): sesion (HASH) 262, indice de sesiones (SET) 84, perfil en cache (HASH) 121

