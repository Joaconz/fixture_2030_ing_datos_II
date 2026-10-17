# Fallas controladas y recuperación — relato por escenario (§5.7)

Tabla completa de pruebas: [`resultados_falla_controlada.md`](resultados_falla_controlada.md).

## Escenario: dependencia detenida (docker stop) — redis

**Condición inicial:** contenedor `fixture2030-redis` en estado `running/healthy`; API en http://localhost:8001 corriendo; persistentes=2 (con TTL: 3533, vencen solas); fixture2030_redis_data creado 2026-09-26T00:42:54Z.

**Cambio aplicado:** `docker stop fixture2030-redis` (reversible). Nada se borra.

**Prueba ejecutada:** `GET /sesiones/demo-ses-0000001-1` antes, durante y después; `/health/dependencias`, `/health/ready`, una ruta de otra fuente y TCP a 127.0.0.1:6379 durante la falla.

**Respuesta de la API:** ver tabla; `/health/ready` durante la falla: HTTP 200 (estado=LISTA_DEGRADADA · noDisponibles=['redis']).

**Transporte durante la falla:** TCP 127.0.0.1:6379 → connection refused (stop: no hay listener).

**Recuperación:** `docker start fixture2030-redis`; contenedor listo en 6 s; la API volvió a responder en 0.0 s más sin reiniciarse.

**Datos y volúmenes conservados:** antes `persistentes=2 (con TTL: 3533, vencen solas)` · después `persistentes=2 (con TTL: 3511, vencen solas)` · `fixture2030_redis_data creado 2026-09-26T00:42:54Z` → iguales.

**Duración total:** 21 s.

| Fase | Request | HTTP | Clasificación | ms | X-Request-Id | Respuesta (resumen) | Motivo en log | Aviso del adaptador |
|---|---|---:|---|---:|---|---|---|---|
| 1. fuente arriba | `GET /sesiones/demo-ses-0000001-1` | 200 | exito | 13.3 | `h11-falla-20261017-001625-01` | estado=ACTIVA | - | - |
| 1. fuente arriba | `GET /health/ready` | 200 | exito | 8.8 | `h11-falla-20261017-001625-02` | estado=LISTA · noDisponibles=[] | - | - |
| 2. falla | `GET /sesiones/demo-ses-0000001-1` | 503 | dependencia_no_disponible | 5.4 | `h11-falla-20261017-001625-03` | code=DEPENDENCY_UNAVAILABLE · dependencia=redis | conexion | dependencia no disponible |
| 2. falla (repite) | `GET /sesiones/demo-ses-0000001-1` | 503 | dependencia_no_disponible | 1.6 | `h11-falla-20261017-001625-04` | code=DEPENDENCY_UNAVAILABLE · dependencia=redis | conexion | dependencia no disponible |
| 2. falla | `GET /partidos/PAR-A-1` | 200 | exito | 10.1 | `h11-falla-20261017-001625-05` | estado=FINALIZADO · partidoId=PAR-A-1 | conexion | dependencia no disponible |
| 2. falla | `GET /health/dependencias` | 503 | salud_degradada | 20.5 | `h11-falla-20261017-001625-06` | estado=DEGRADADO · mongodb=UP, neo4j=UP, cassandra=UP, redis=DOWN, influxdb=UP, iris=NOT_CONFIGURED · desdeCache=False | conexion | dependencia no disponible |
| 2. falla | `GET /health/ready` | 200 | exito | 1.8 | `h11-falla-20261017-001625-07` | estado=LISTA_DEGRADADA · noDisponibles=['redis'] | - | - |
| 2. falla (otra fuente sigue) | `GET /equipos/ARG` | 200 | exito | 2.6 | `h11-falla-20261017-001625-08` | codigo=ARG | - | - |
| 3. recuperada (sin reiniciar la API) | `GET /sesiones/demo-ses-0000001-1` | 200 | exito | 2.2 | `h11-falla-20261017-001625-09` | estado=ACTIVA | - | - |
| 3. recuperada | `GET /health/dependencias` | 200 | exito | 12.6 | `h11-falla-20261017-001625-10` | estado=OK · mongodb=UP, neo4j=UP, cassandra=UP, redis=UP, influxdb=UP, iris=NOT_CONFIGURED · desdeCache=False | - | - |

## Escenario: dependencia detenida (docker stop) — mongodb

**Condición inicial:** contenedor `fixture2030_mongo` en estado `running`; API en http://localhost:8001 corriendo; jugadores=1472; fixture2030_mongo_data creado 2026-09-04T22:17:13Z.

**Cambio aplicado:** `docker stop fixture2030_mongo` (reversible). Nada se borra.

**Prueba ejecutada:** `GET /equipos/ARG` antes, durante y después; `/health/dependencias`, `/health/ready`, una ruta de otra fuente y TCP a 127.0.0.1:27017 durante la falla.

**Respuesta de la API:** ver tabla; `/health/ready` durante la falla: HTTP 503 (estado=NO_LISTA · noDisponibles=['mongodb']).

**Transporte durante la falla:** TCP 127.0.0.1:27017 → connection refused (stop: no hay listener).

**Recuperación:** `docker start fixture2030_mongo`; contenedor listo en 0 s; la API volvió a responder en 0.6 s más sin reiniciarse.

**Datos y volúmenes conservados:** antes `jugadores=1472` · después `jugadores=1472` · `fixture2030_mongo_data creado 2026-09-04T22:17:13Z` → iguales.

**Duración total:** 20 s.

| Fase | Request | HTTP | Clasificación | ms | X-Request-Id | Respuesta (resumen) | Motivo en log | Aviso del adaptador |
|---|---|---:|---|---:|---|---|---|---|
| 1. fuente arriba | `GET /equipos/ARG` | 200 | exito | 15.5 | `h11-falla-20261017-001647-01` | codigo=ARG | - | - |
| 1. fuente arriba | `GET /health/ready` | 200 | exito | 1.6 | `h11-falla-20261017-001647-02` | estado=LISTA · noDisponibles=[] | - | - |
| 2. falla | `GET /equipos/ARG` | 503 | dependencia_no_disponible | 1914.4 | `h11-falla-20261017-001647-03` | code=DEPENDENCY_UNAVAILABLE · dependencia=mongodb | conexion | dependencia no disponible |
| 2. falla (repite) | `GET /equipos/ARG` | 503 | dependencia_no_disponible | 1739.0 | `h11-falla-20261017-001647-04` | code=DEPENDENCY_UNAVAILABLE · dependencia=mongodb | conexion | dependencia no disponible |
| 2. falla | `GET /health/dependencias` | 503 | salud_degradada | 1748.9 | `h11-falla-20261017-001647-05` | estado=DEGRADADO · mongodb=DOWN, neo4j=UP, cassandra=UP, redis=UP, influxdb=UP, iris=NOT_CONFIGURED · desdeCache=False | conexion | dependencia no disponible |
| 2. falla | `GET /health/ready` | 503 | salud_degradada | 1.6 | `h11-falla-20261017-001647-06` | estado=NO_LISTA · noDisponibles=['mongodb'] | - | - |
| 2. falla (otra fuente sigue) | `GET /partidos/PAR-A-1/eventos?limit=5` | 200 | exito | 9.8 | `h11-falla-20261017-001647-07` | partidoId=PAR-A-1 · items=5 | - | - |
| 3. recuperada (sin reiniciar la API) | `GET /equipos/ARG` | 200 | exito | 2.9 | `h11-falla-20261017-001647-08` | codigo=ARG | - | - |
| 3. recuperada | `GET /health/dependencias` | 200 | exito | 12.4 | `h11-falla-20261017-001647-09` | estado=OK · mongodb=UP, neo4j=UP, cassandra=UP, redis=UP, influxdb=UP, iris=NOT_CONFIGURED · desdeCache=False | - | - |

## Escenario: dependencia colgada (docker pause) — influxdb

**Condición inicial:** contenedor `fixture2030-influxdb` en estado `running/healthy`; API en http://localhost:8001 corriendo; puntos PAR-A-1=11400; fixture2030_influxdb_data creado 2026-10-13T19:26:47Z.

**Cambio aplicado:** `docker pause fixture2030-influxdb` (reversible). Nada se borra.

**Prueba ejecutada:** `GET /partidos/PAR-A-1/estadisticas?desde=2030-06-09T13:00:00Z&hasta=2030-06-09T13:30:00Z` antes, durante y después; `/health/dependencias`, `/health/ready`, una ruta de otra fuente y TCP a 127.0.0.1:8181 durante la falla.

**Respuesta de la API:** ver tabla; `/health/ready` durante la falla: HTTP 200 (estado=LISTA_DEGRADADA · noDisponibles=['influxdb']).

**Transporte durante la falla:** TCP 127.0.0.1:8181 → conecta (pause: el puerto lo sigue sosteniendo Docker, pero el proceso no contesta).

**Recuperación:** `docker unpause fixture2030-influxdb`; contenedor listo en 6 s; la API volvió a responder en 0.0 s más sin reiniciarse.

**Datos y volúmenes conservados:** antes `puntos PAR-A-1=11400` · después `puntos PAR-A-1=11400` · `fixture2030_influxdb_data creado 2026-10-13T19:26:47Z` → iguales.

**Duración total:** 26 s.

| Fase | Request | HTTP | Clasificación | ms | X-Request-Id | Respuesta (resumen) | Motivo en log | Aviso del adaptador |
|---|---|---:|---|---:|---|---|---|---|
| 1. fuente arriba | `GET /partidos/PAR-A-1/estadisticas?desde=2030-06-09T13:00:00Z&hasta=2030-06-09T13:30:00Z` | 200 | exito | 18.7 | `h11-falla-20261017-001708-01` | partidoId=PAR-A-1 · cantidad=60 · truncado=False · puntos=60 | - | - |
| 1. fuente arriba | `GET /health/ready` | 200 | exito | 1.7 | `h11-falla-20261017-001708-02` | estado=LISTA · noDisponibles=[] | - | - |
| 2. falla | `GET /partidos/PAR-A-1/estadisticas?desde=2030-06-09T13:00:00Z&hasta=2030-06-09T13:30:00Z` | 504 | dependencia_timeout | 2008.0 | `h11-falla-20261017-001708-03` | code=DEPENDENCY_TIMEOUT · dependencia=influxdb | timeout | - |
| 2. falla (repite) | `GET /partidos/PAR-A-1/estadisticas?desde=2030-06-09T13:00:00Z&hasta=2030-06-09T13:30:00Z` | 504 | dependencia_timeout | 2004.2 | `h11-falla-20261017-001708-04` | code=DEPENDENCY_TIMEOUT · dependencia=influxdb | timeout | - |
| 2. falla | `GET /health/dependencias` | 503 | salud_degradada | 2010.1 | `h11-falla-20261017-001708-05` | estado=DEGRADADO · mongodb=UP, neo4j=UP, cassandra=UP, redis=UP, influxdb=DOWN, iris=NOT_CONFIGURED · desdeCache=False | timeout | - |
| 2. falla | `GET /health/ready` | 200 | exito | 1.6 | `h11-falla-20261017-001708-06` | estado=LISTA_DEGRADADA · noDisponibles=['influxdb'] | - | - |
| 2. falla (otra fuente sigue) | `GET /equipos/ARG` | 200 | exito | 2.9 | `h11-falla-20261017-001708-07` | codigo=ARG | - | - |
| 3. recuperada (sin reiniciar la API) | `GET /partidos/PAR-A-1/estadisticas?desde=2030-06-09T13:00:00Z&hasta=2030-06-09T13:30:00Z` | 200 | exito | 15.3 | `h11-falla-20261017-001708-08` | partidoId=PAR-A-1 · cantidad=60 · truncado=False · puntos=60 | - | - |
| 3. recuperada | `GET /health/dependencias` | 200 | exito | 12.6 | `h11-falla-20261017-001708-09` | estado=OK · mongodb=UP, neo4j=UP, cassandra=UP, redis=UP, influxdb=UP, iris=NOT_CONFIGURED · desdeCache=False | - | - |

## Escenario: configuración incorrecta — credencial inválida (Neo4j)

**Condición inicial:** instancia temporal de la API en http://127.0.0.1:8011 con la configuración normal salvo `NEO4J_PASSWORD`.

**Cambio aplicado:** `NEO4J_PASSWORD` = valor de diagnóstico (credencial inválida (Neo4j)); el valor no se muestra si es credencial. La instancia principal y las bases no se tocan.

**Respuesta de la API:** `GET /partidos/PAR-A-1/eventos?limit=5` → HTTP 503 dependencia_no_disponible en 50.1 ms (repetida: HTTP 503 dependencia_no_disponible en 7.0 ms); `/health/dependencias` → HTTP 503, neo4j: DOWN «credencial rechazada»; otra fuente → exito.

**Mensaje de log:** motivo `autenticacion`; aviso del adaptador: «dependencia no disponible».

**Recuperación:** se termina la instancia temporal (la configuración correcta nunca cambió).

**Datos y volúmenes conservados:** no aplica: sólo se leyó.

| Fase | Request | HTTP | Clasificación | ms | X-Request-Id | Respuesta (resumen) | Motivo en log | Aviso del adaptador |
|---|---|---:|---|---:|---|---|---|---|
| con la variable mal puesta | `GET /partidos/PAR-A-1/eventos?limit=5` | 503 | dependencia_no_disponible | 50.1 | `h11-falla-20261017-001736-01` | code=DEPENDENCY_UNAVAILABLE · dependencia=neo4j | autenticacion | dependencia no disponible |
| con la variable mal puesta (repite) | `GET /partidos/PAR-A-1/eventos?limit=5` | 503 | dependencia_no_disponible | 7.0 | `h11-falla-20261017-001736-02` | code=DEPENDENCY_UNAVAILABLE · dependencia=neo4j | autenticacion | dependencia no disponible |
| con la variable mal puesta | `GET /health/dependencias` | 503 | salud_degradada | 29.2 | `h11-falla-20261017-001736-03` | estado=DEGRADADO · mongodb=UP, neo4j=DOWN, cassandra=UP, redis=UP, influxdb=UP, iris=NOT_CONFIGURED · desdeCache=False | autenticacion | dependencia no disponible |
| otra fuente en la misma instancia | `GET /equipos/ARG` | 200 | exito | 3.0 | `h11-falla-20261017-001736-04` | codigo=ARG | - | - |

## Escenario: configuración incorrecta — database inexistente (Neo4j)

**Condición inicial:** instancia temporal de la API en http://127.0.0.1:8011 con la configuración normal salvo `NEO4J_DATABASE`.

**Cambio aplicado:** `NEO4J_DATABASE` = valor de diagnóstico (database inexistente (Neo4j)); el valor no se muestra si es credencial. La instancia principal y las bases no se tocan.

**Respuesta de la API:** `GET /partidos/PAR-A-1/eventos?limit=5` → HTTP 503 dependencia_no_disponible en 41.6 ms (repetida: HTTP 503 dependencia_no_disponible en 6.0 ms); `/health/dependencias` → HTTP 503, neo4j: DOWN «contexto inexistente»; otra fuente → exito.

**Mensaje de log:** motivo `contexto`; aviso del adaptador: «-».

**Recuperación:** se termina la instancia temporal (la configuración correcta nunca cambió).

**Datos y volúmenes conservados:** no aplica: sólo se leyó.

| Fase | Request | HTTP | Clasificación | ms | X-Request-Id | Respuesta (resumen) | Motivo en log | Aviso del adaptador |
|---|---|---:|---|---:|---|---|---|---|
| con la variable mal puesta | `GET /partidos/PAR-A-1/eventos?limit=5` | 503 | dependencia_no_disponible | 41.6 | `h11-falla-20261017-001745-01` | code=DEPENDENCY_UNAVAILABLE · dependencia=neo4j | contexto | - |
| con la variable mal puesta (repite) | `GET /partidos/PAR-A-1/eventos?limit=5` | 503 | dependencia_no_disponible | 6.0 | `h11-falla-20261017-001745-02` | code=DEPENDENCY_UNAVAILABLE · dependencia=neo4j | contexto | - |
| con la variable mal puesta | `GET /health/dependencias` | 503 | salud_degradada | 32.8 | `h11-falla-20261017-001745-03` | estado=DEGRADADO · mongodb=UP, neo4j=DOWN, cassandra=UP, redis=UP, influxdb=UP, iris=NOT_CONFIGURED · desdeCache=False | contexto | - |
| otra fuente en la misma instancia | `GET /equipos/ARG` | 200 | exito | 2.0 | `h11-falla-20261017-001745-04` | codigo=ARG | - | - |

## Escenario: configuración incorrecta — keyspace inexistente (Cassandra)

**Condición inicial:** instancia temporal de la API en http://127.0.0.1:8011 con la configuración normal salvo `CASSANDRA_KEYSPACE`.

**Cambio aplicado:** `CASSANDRA_KEYSPACE` = valor de diagnóstico (keyspace inexistente (Cassandra)); el valor no se muestra si es credencial. La instancia principal y las bases no se tocan.

**Respuesta de la API:** `GET /partidos/PAR-A-1/comentarios?limit=5` → HTTP 503 dependencia_no_disponible en 54.1 ms (repetida: HTTP 503 dependencia_no_disponible en 19.0 ms); `/health/dependencias` → HTTP 503, cassandra: DOWN «contexto inexistente»; otra fuente → exito.

**Mensaje de log:** motivo `contexto`; aviso del adaptador: «dependencia no disponible».

**Recuperación:** se termina la instancia temporal (la configuración correcta nunca cambió).

**Datos y volúmenes conservados:** no aplica: sólo se leyó.

| Fase | Request | HTTP | Clasificación | ms | X-Request-Id | Respuesta (resumen) | Motivo en log | Aviso del adaptador |
|---|---|---:|---|---:|---|---|---|---|
| con la variable mal puesta | `GET /partidos/PAR-A-1/comentarios?limit=5` | 503 | dependencia_no_disponible | 54.1 | `h11-falla-20261017-001747-01` | code=DEPENDENCY_UNAVAILABLE · dependencia=cassandra | contexto | dependencia no disponible |
| con la variable mal puesta (repite) | `GET /partidos/PAR-A-1/comentarios?limit=5` | 503 | dependencia_no_disponible | 19.0 | `h11-falla-20261017-001747-02` | code=DEPENDENCY_UNAVAILABLE · dependencia=cassandra | contexto | dependencia no disponible |
| con la variable mal puesta | `GET /health/dependencias` | 503 | salud_degradada | 27.2 | `h11-falla-20261017-001747-03` | estado=DEGRADADO · mongodb=UP, neo4j=UP, cassandra=DOWN, redis=UP, influxdb=UP, iris=NOT_CONFIGURED · desdeCache=False | contexto | dependencia no disponible |
| otra fuente en la misma instancia | `GET /equipos/ARG` | 200 | exito | 1.9 | `h11-falla-20261017-001747-04` | codigo=ARG | - | - |

## Escenario: configuración incorrecta — database inexistente (MongoDB)

**Condición inicial:** instancia temporal de la API en http://127.0.0.1:8011 con la configuración normal salvo `MONGO_DB`.

**Cambio aplicado:** `MONGO_DB` = valor de diagnóstico (database inexistente (MongoDB)); el valor no se muestra si es credencial. La instancia principal y las bases no se tocan.

**Respuesta de la API:** `GET /equipos/ARG` → HTTP 404 inexistente en 52.8 ms (repetida: HTTP 404 inexistente en 3.5 ms); `/health/dependencias` → HTTP 503, mongodb: DOWN «contexto inexistente»; otra fuente → exito.

**Mensaje de log:** motivo `-`; aviso del adaptador: «-».

**Recuperación:** se termina la instancia temporal (la configuración correcta nunca cambió).

**Datos y volúmenes conservados:** no aplica: sólo se leyó.

| Fase | Request | HTTP | Clasificación | ms | X-Request-Id | Respuesta (resumen) | Motivo en log | Aviso del adaptador |
|---|---|---:|---|---:|---|---|---|---|
| con la variable mal puesta | `GET /equipos/ARG` | 404 | inexistente | 52.8 | `h11-falla-20261017-001750-01` | code=TEAM_NOT_FOUND | - | - |
| con la variable mal puesta (repite) | `GET /equipos/ARG` | 404 | inexistente | 3.5 | `h11-falla-20261017-001750-02` | code=TEAM_NOT_FOUND | - | - |
| con la variable mal puesta | `GET /health/dependencias` | 503 | salud_degradada | 34.8 | `h11-falla-20261017-001750-03` | estado=DEGRADADO · mongodb=DOWN, neo4j=UP, cassandra=UP, redis=UP, influxdb=UP, iris=NOT_CONFIGURED · desdeCache=False | contexto | - |
| otra fuente en la misma instancia | `GET /partidos/PAR-A-1/comentarios?limit=5` | 200 | exito | 5.4 | `h11-falla-20261017-001750-04` | partidoId=PAR-A-1 · items=5 | - | - |

## Escenario: configuración incorrecta — database inexistente (InfluxDB)

**Condición inicial:** instancia temporal de la API en http://127.0.0.1:8011 con la configuración normal salvo `INFLUX_DB`.

**Cambio aplicado:** `INFLUX_DB` = valor de diagnóstico (database inexistente (InfluxDB)); el valor no se muestra si es credencial. La instancia principal y las bases no se tocan.

**Respuesta de la API:** `GET /partidos/PAR-A-1/estadisticas?desde=2030-06-09T13:00:00Z&hasta=2030-06-09T13:30:00Z` → HTTP 503 dependencia_no_disponible en 40.3 ms (repetida: HTTP 503 dependencia_no_disponible en 2.6 ms); `/health/dependencias` → HTTP 503, influxdb: DOWN «contexto inexistente»; otra fuente → exito.

**Mensaje de log:** motivo `contexto`; aviso del adaptador: «la database configurada no existe en InfluxDB».

**Recuperación:** se termina la instancia temporal (la configuración correcta nunca cambió).

**Datos y volúmenes conservados:** no aplica: sólo se leyó.

| Fase | Request | HTTP | Clasificación | ms | X-Request-Id | Respuesta (resumen) | Motivo en log | Aviso del adaptador |
|---|---|---:|---|---:|---|---|---|---|
| con la variable mal puesta | `GET /partidos/PAR-A-1/estadisticas?desde=2030-06-09T13:00:00Z&hasta=2030-06-09T13:30:00Z` | 503 | dependencia_no_disponible | 40.3 | `h11-falla-20261017-001753-01` | code=DEPENDENCY_UNAVAILABLE · dependencia=influxdb | contexto | la database configurada no existe en InfluxDB |
| con la variable mal puesta (repite) | `GET /partidos/PAR-A-1/estadisticas?desde=2030-06-09T13:00:00Z&hasta=2030-06-09T13:30:00Z` | 503 | dependencia_no_disponible | 2.6 | `h11-falla-20261017-001753-02` | code=DEPENDENCY_UNAVAILABLE · dependencia=influxdb | contexto | la database configurada no existe en InfluxDB |
| con la variable mal puesta | `GET /health/dependencias` | 503 | salud_degradada | 29.4 | `h11-falla-20261017-001753-03` | estado=DEGRADADO · mongodb=UP, neo4j=UP, cassandra=UP, redis=UP, influxdb=DOWN, iris=NOT_CONFIGURED · desdeCache=False | contexto | la database configurada no existe en InfluxDB |
| otra fuente en la misma instancia | `GET /equipos/ARG` | 200 | exito | 2.1 | `h11-falla-20261017-001753-04` | codigo=ARG | - | - |

## Escenario: configuración incorrecta — token inválido (InfluxDB)

**Condición inicial:** instancia temporal de la API en http://127.0.0.1:8011 con la configuración normal salvo `INFLUX_TOKEN`.

**Cambio aplicado:** `INFLUX_TOKEN` = valor de diagnóstico (token inválido (InfluxDB)); el valor no se muestra si es credencial. La instancia principal y las bases no se tocan.

**Respuesta de la API:** `GET /partidos/PAR-A-1/estadisticas?desde=2030-06-09T13:00:00Z&hasta=2030-06-09T13:30:00Z` → HTTP 503 dependencia_no_disponible en 39.8 ms (repetida: HTTP 503 dependencia_no_disponible en 3.3 ms); `/health/dependencias` → HTTP 503, influxdb: DOWN «credencial rechazada»; otra fuente → exito.

**Mensaje de log:** motivo `autenticacion`; aviso del adaptador: «token rechazado por InfluxDB».

**Recuperación:** se termina la instancia temporal (la configuración correcta nunca cambió).

**Datos y volúmenes conservados:** no aplica: sólo se leyó.

| Fase | Request | HTTP | Clasificación | ms | X-Request-Id | Respuesta (resumen) | Motivo en log | Aviso del adaptador |
|---|---|---:|---|---:|---|---|---|---|
| con la variable mal puesta | `GET /partidos/PAR-A-1/estadisticas?desde=2030-06-09T13:00:00Z&hasta=2030-06-09T13:30:00Z` | 503 | dependencia_no_disponible | 39.8 | `h11-falla-20261017-001756-01` | code=DEPENDENCY_UNAVAILABLE · dependencia=influxdb | autenticacion | token rechazado por InfluxDB |
| con la variable mal puesta (repite) | `GET /partidos/PAR-A-1/estadisticas?desde=2030-06-09T13:00:00Z&hasta=2030-06-09T13:30:00Z` | 503 | dependencia_no_disponible | 3.3 | `h11-falla-20261017-001756-02` | code=DEPENDENCY_UNAVAILABLE · dependencia=influxdb | autenticacion | token rechazado por InfluxDB |
| con la variable mal puesta | `GET /health/dependencias` | 503 | salud_degradada | 29.0 | `h11-falla-20261017-001756-03` | estado=DEGRADADO · mongodb=UP, neo4j=UP, cassandra=UP, redis=UP, influxdb=DOWN, iris=NOT_CONFIGURED · desdeCache=False | autenticacion | token rechazado por InfluxDB |
| otra fuente en la misma instancia | `GET /equipos/ARG` | 200 | exito | 2.0 | `h11-falla-20261017-001756-04` | codigo=ARG | - | - |

## Escenario: configuración incorrecta — token no configurado (InfluxDB)

**Condición inicial:** instancia temporal de la API en http://127.0.0.1:8011 con la configuración normal salvo `INFLUX_TOKEN`, `INFLUX_TOKEN_FILE`.

**Cambio aplicado:** `INFLUX_TOKEN`, `INFLUX_TOKEN_FILE` = valor de diagnóstico (token no configurado (InfluxDB)); el valor no se muestra si es credencial. La instancia principal y las bases no se tocan.

**Respuesta de la API:** `GET /partidos/PAR-A-1/estadisticas?desde=2030-06-09T13:00:00Z&hasta=2030-06-09T13:30:00Z` → HTTP 503 dependencia_no_disponible en 33.4 ms (repetida: HTTP 503 dependencia_no_disponible en 1.3 ms); `/health/dependencias` → HTTP 503, influxdb: NOT_CONFIGURED «sin configurar»; otra fuente → exito.

**Mensaje de log:** motivo `no_configurado`; aviso del adaptador: «-».

**Recuperación:** se termina la instancia temporal (la configuración correcta nunca cambió).

**Datos y volúmenes conservados:** no aplica: sólo se leyó.

| Fase | Request | HTTP | Clasificación | ms | X-Request-Id | Respuesta (resumen) | Motivo en log | Aviso del adaptador |
|---|---|---:|---|---:|---|---|---|---|
| con la variable mal puesta | `GET /partidos/PAR-A-1/estadisticas?desde=2030-06-09T13:00:00Z&hasta=2030-06-09T13:30:00Z` | 503 | dependencia_no_disponible | 33.4 | `h11-falla-20261017-001758-01` | code=DEPENDENCY_UNAVAILABLE · dependencia=influxdb | no_configurado | - |
| con la variable mal puesta (repite) | `GET /partidos/PAR-A-1/estadisticas?desde=2030-06-09T13:00:00Z&hasta=2030-06-09T13:30:00Z` | 503 | dependencia_no_disponible | 1.3 | `h11-falla-20261017-001758-02` | code=DEPENDENCY_UNAVAILABLE · dependencia=influxdb | no_configurado | - |
| con la variable mal puesta | `GET /health/dependencias` | 503 | salud_degradada | 30.5 | `h11-falla-20261017-001758-03` | estado=DEGRADADO · mongodb=UP, neo4j=UP, cassandra=UP, redis=UP, influxdb=NOT_CONFIGURED, iris=NOT_CONFIGURED · desdeCache=False | no_configurado | - |
| otra fuente en la misma instancia | `GET /equipos/ARG` | 200 | exito | 2.1 | `h11-falla-20261017-001758-04` | codigo=ARG | - | - |

## Escenario: configuración incorrecta — puerto incorrecto (Redis 6390)

**Condición inicial:** instancia temporal de la API en http://127.0.0.1:8011 con la configuración normal salvo `REDIS_URL`.

**Cambio aplicado:** `REDIS_URL` = valor de diagnóstico (puerto incorrecto (Redis 6390)); el valor no se muestra si es credencial. La instancia principal y las bases no se tocan.

**Respuesta de la API:** `GET /sesiones/demo-ses-0000001-1` → HTTP 503 dependencia_no_disponible en 35.7 ms (repetida: HTTP 503 dependencia_no_disponible en 1.6 ms); `/health/dependencias` → HTTP 503, redis: DOWN «no responde»; otra fuente → exito.

**Mensaje de log:** motivo `conexion`; aviso del adaptador: «dependencia no disponible».

**Recuperación:** se termina la instancia temporal (la configuración correcta nunca cambió).

**Datos y volúmenes conservados:** no aplica: sólo se leyó.

| Fase | Request | HTTP | Clasificación | ms | X-Request-Id | Respuesta (resumen) | Motivo en log | Aviso del adaptador |
|---|---|---:|---|---:|---|---|---|---|
| con la variable mal puesta | `GET /sesiones/demo-ses-0000001-1` | 503 | dependencia_no_disponible | 35.7 | `h11-falla-20261017-001801-01` | code=DEPENDENCY_UNAVAILABLE · dependencia=redis | conexion | dependencia no disponible |
| con la variable mal puesta (repite) | `GET /sesiones/demo-ses-0000001-1` | 503 | dependencia_no_disponible | 1.6 | `h11-falla-20261017-001801-02` | code=DEPENDENCY_UNAVAILABLE · dependencia=redis | conexion | dependencia no disponible |
| con la variable mal puesta | `GET /health/dependencias` | 503 | salud_degradada | 31.3 | `h11-falla-20261017-001801-03` | estado=DEGRADADO · mongodb=UP, neo4j=UP, cassandra=UP, redis=DOWN, influxdb=UP, iris=NOT_CONFIGURED · desdeCache=False | conexion | dependencia no disponible |
| otra fuente en la misma instancia | `GET /equipos/ARG` | 200 | exito | 2.1 | `h11-falla-20261017-001801-04` | codigo=ARG | - | - |

## Escenario: configuración incorrecta — host no resuelto (MongoDB)

**Condición inicial:** instancia temporal de la API en http://127.0.0.1:8011 con la configuración normal salvo `MONGO_URI`.

**Cambio aplicado:** `MONGO_URI` = valor de diagnóstico (host no resuelto (MongoDB)); el valor no se muestra si es credencial. La instancia principal y las bases no se tocan.

**Respuesta de la API:** `GET /equipos/ARG` → HTTP 504 dependencia_timeout en 2032.0 ms (repetida: HTTP 503 dependencia_no_disponible en 1759.2 ms); `/health/dependencias` → HTTP 503, mongodb: DOWN «no responde»; otra fuente → exito.

**Mensaje de log:** motivo `conexion`; aviso del adaptador: «dependencia no disponible».

**Recuperación:** se termina la instancia temporal (la configuración correcta nunca cambió).

**Datos y volúmenes conservados:** no aplica: sólo se leyó.

| Fase | Request | HTTP | Clasificación | ms | X-Request-Id | Respuesta (resumen) | Motivo en log | Aviso del adaptador |
|---|---|---:|---|---:|---|---|---|---|
| con la variable mal puesta | `GET /equipos/ARG` | 504 | dependencia_timeout | 2032.0 | `h11-falla-20261017-001804-01` | code=DEPENDENCY_TIMEOUT · dependencia=mongodb | timeout | - |
| con la variable mal puesta (repite) | `GET /equipos/ARG` | 503 | dependencia_no_disponible | 1759.2 | `h11-falla-20261017-001804-02` | code=DEPENDENCY_UNAVAILABLE · dependencia=mongodb | conexion | dependencia no disponible |
| con la variable mal puesta | `GET /health/dependencias` | 503 | salud_degradada | 1753.0 | `h11-falla-20261017-001804-03` | estado=DEGRADADO · mongodb=DOWN, neo4j=UP, cassandra=UP, redis=UP, influxdb=UP, iris=NOT_CONFIGURED · desdeCache=False | conexion | dependencia no disponible |
| otra fuente en la misma instancia | `GET /partidos/PAR-A-1/comentarios?limit=5` | 200 | exito | 10.6 | `h11-falla-20261017-001804-04` | partidoId=PAR-A-1 · items=5 | - | - |

## Escenario: configuración incorrecta — timeout demasiado bajo (DEP_TIMEOUT_S=0.001)

**Condición inicial:** instancia temporal de la API en http://127.0.0.1:8011 con la configuración normal salvo `DEP_TIMEOUT_S`.

**Cambio aplicado:** `DEP_TIMEOUT_S` = valor de diagnóstico (timeout demasiado bajo (DEP_TIMEOUT_S=0.001)); el valor no se muestra si es credencial. La instancia principal y las bases no se tocan.

**Respuesta de la API:** `GET /partidos/PAR-A-1/eventos?limit=5` → HTTP 504 dependencia_timeout en 45.8 ms (repetida: HTTP 504 dependencia_timeout en 2.4 ms); `/health/dependencias` → HTTP 503, neo4j: DOWN «timeout»; otra fuente → dependencia_timeout.

**Mensaje de log:** motivo `timeout`; aviso del adaptador: «-».

**Recuperación:** se termina la instancia temporal (la configuración correcta nunca cambió).

**Datos y volúmenes conservados:** no aplica: sólo se leyó.

| Fase | Request | HTTP | Clasificación | ms | X-Request-Id | Respuesta (resumen) | Motivo en log | Aviso del adaptador |
|---|---|---:|---|---:|---|---|---|---|
| con la variable mal puesta | `GET /partidos/PAR-A-1/eventos?limit=5` | 504 | dependencia_timeout | 45.8 | `h11-falla-20261017-001814-01` | code=DEPENDENCY_TIMEOUT · dependencia=neo4j | timeout | - |
| con la variable mal puesta (repite) | `GET /partidos/PAR-A-1/eventos?limit=5` | 504 | dependencia_timeout | 2.4 | `h11-falla-20261017-001814-02` | code=DEPENDENCY_TIMEOUT · dependencia=neo4j | timeout | - |
| con la variable mal puesta | `GET /health/dependencias` | 503 | salud_degradada | 10.9 | `h11-falla-20261017-001814-03` | estado=DEGRADADO · mongodb=DOWN, neo4j=DOWN, cassandra=DOWN, redis=DOWN, influxdb=DOWN, iris=NOT_CONFIGURED · desdeCache=False | timeout | - |
| otra fuente en la misma instancia | `GET /equipos/ARG` | 504 | dependencia_timeout | 1.5 | `h11-falla-20261017-001814-04` | code=DEPENDENCY_TIMEOUT · dependencia=mongodb | timeout | - |
