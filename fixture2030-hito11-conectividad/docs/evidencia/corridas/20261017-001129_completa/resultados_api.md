# Capa API — rutas del Hito 10 (cadena completa)

- Fecha (UTC) de inicio: 2026-10-17T00:11:45Z
- Commit: `71a1625`
- Entorno: notebook-docker-desktop
- Origen de la prueba: notebook (host) · Darwin arm64 · python 3.14.5
- Timeouts: conexión 2 s · operación 3 s · API 8 s
- Secretos: ninguno se imprime; toda salida pasa por `registro.redactar` (RNF7/RNF8).

| Fecha (UTC) | Producto | Capa | Prueba | Objetivo / contexto | Resultado | ms | Detalle | Interpretación | No demuestra |
|---|---|---|---|---|---|---:|---|---|---|
| 2026-10-17T00:11:45Z | api | api | `GET /health` | `http://localhost:8001 · dependencia: ninguna (liveness)` | **OK** | 19.5 | HTTP 200 · exito · estado=OK · requestId=h11-20261017-001145-01 | el proceso de la API responde sin tocar fuentes. Observado: la cadena cliente–API–adaptador–producto funciona para este caso de uso | rendimiento o concurrencia (Hito 12) |
| 2026-10-17T00:11:45Z | api | api | `GET /health/ready` | `http://localhost:8001 · dependencia: mongodb, neo4j (esenciales)` | **OK** | 49.2 | HTTP 200 · exito · estado=LISTA · noDisponibles=[] · requestId=h11-20261017-001145-02 | readiness: las esenciales están UP. Observado: la cadena cliente–API–adaptador–producto funciona para este caso de uso | rendimiento o concurrencia (Hito 12) |
| 2026-10-17T00:11:45Z | api | api | `GET /health/dependencias` | `http://localhost:8001 · dependencia: las cinco (chequeo profundo, con caché)` | **OK** | 1.7 | HTTP 200 · exito · estado=OK · mongodb=UP, neo4j=UP, cassandra=UP, redis=UP, influxdb=UP, iris=NOT_CONFIGURED · desdeCache=True · requestId=h11-20261017-001145-03 | estado por dependencia. Observado: la cadena cliente–API–adaptador–producto funciona para este caso de uso | rendimiento o concurrencia (Hito 12) |
| 2026-10-17T00:11:45Z | mongodb | api | `GET /equipos/ARG` | `http://localhost:8001 · dependencia: mongodb` | **OK** | 2.9 | HTTP 200 · exito · codigo=ARG · requestId=h11-20261017-001145-04 | CU1 ficha de equipo. Observado: la cadena cliente–API–adaptador–producto funciona para este caso de uso | rendimiento o concurrencia (Hito 12) |
| 2026-10-17T00:11:45Z | mongodb | api | `GET /equipos/ARG/jugadores?limit=5` | `http://localhost:8001 · dependencia: mongodb` | **OK** | 3.4 | HTTP 200 · exito · items=5 · requestId=h11-20261017-001145-05 | CU2 plantel paginado. Observado: la cadena cliente–API–adaptador–producto funciona para este caso de uso | rendimiento o concurrencia (Hito 12) |
| 2026-10-17T00:11:45Z | mongodb | api | `GET /equipos/XXX` | `http://localhost:8001 · dependencia: mongodb` | **OK** | 2.2 | HTTP 404 · inexistente · code=TEAM_NOT_FOUND · requestId=h11-20261017-001145-06 | equipo inexistente → 404, no 503. Observado: la fuente respondió: el recurso no existe (404), la dependencia está disponible | rendimiento o concurrencia (Hito 12) |
| 2026-10-17T00:11:45Z | mongodb | api | `GET /equipos/arg` | `http://localhost:8001 · dependencia: ninguna (se valida antes)` | **OK** | 1.2 | HTTP 400 · validacion · code=VALIDATION_ERROR · requestId=h11-20261017-001145-07 | entrada inválida → 400 sin tocar la fuente. Observado: la API rechazó la entrada (400) antes de consultar la fuente | rendimiento o concurrencia (Hito 12) |
| 2026-10-17T00:11:45Z | neo4j | api | `GET /partidos/PAR-A-1` | `http://localhost:8001 · dependencia: neo4j (+ caché redis)` | **OK** | 14.9 | HTTP 200 · exito · estado=FINALIZADO · partidoId=PAR-A-1 · X-Cache=MISS · requestId=h11-20261017-001145-08 | CU4 detalle de partido (X-Cache). Observado: la cadena cliente–API–adaptador–producto funciona para este caso de uso | rendimiento o concurrencia (Hito 12) |
| 2026-10-17T00:11:45Z | neo4j | api | `GET /partidos/PAR-A-1/eventos?limit=5` | `http://localhost:8001 · dependencia: neo4j` | **OK** | 8.9 | HTTP 200 · exito · partidoId=PAR-A-1 · items=5 · requestId=h11-20261017-001145-09 | CU5 timeline. Observado: la cadena cliente–API–adaptador–producto funciona para este caso de uso | rendimiento o concurrencia (Hito 12) |
| 2026-10-17T00:11:45Z | neo4j | api | `GET /partidos/PAR-D16-01/eventos` | `http://localhost:8001 · dependencia: neo4j` | **OK** | 7.2 | HTTP 200 · vacio_valido · partidoId=PAR-D16-01 · items=0 · requestId=h11-20261017-001145-10 | partido sin eventos → 200 items: []. Observado: la fuente respondió y no hay datos: ausencia válida (200), no timeout | rendimiento o concurrencia (Hito 12) |
| 2026-10-17T00:11:45Z | neo4j | api | `GET /partidos/PAR-X-99/eventos` | `http://localhost:8001 · dependencia: neo4j` | **OK** | 4.4 | HTTP 404 · inexistente · code=MATCH_NOT_FOUND · requestId=h11-20261017-001145-11 | partido inexistente → 404 MATCH_NOT_FOUND. Observado: la fuente respondió: el recurso no existe (404), la dependencia está disponible | rendimiento o concurrencia (Hito 12) |
| 2026-10-17T00:11:45Z | cassandra | api | `GET /partidos/PAR-A-1/comentarios?limit=5` | `http://localhost:8001 · dependencia: cassandra` | **OK** | 8.5 | HTTP 200 · exito · partidoId=PAR-A-1 · items=5 · requestId=h11-20261017-001145-12 | CU7 comentarios por partición. Observado: la cadena cliente–API–adaptador–producto funciona para este caso de uso | rendimiento o concurrencia (Hito 12) |
| 2026-10-17T00:11:45Z | cassandra | api | `GET /partidos/PAR-X-99/comentarios?limit=5` | `http://localhost:8001 · dependencia: cassandra` | **OK** | 2.6 | HTTP 404 · inexistente · code=MATCH_NOT_FOUND · requestId=h11-20261017-001145-13 | sin config de partición → 404. Observado: la fuente respondió: el recurso no existe (404), la dependencia está disponible | rendimiento o concurrencia (Hito 12) |
| 2026-10-17T00:11:45Z | redis | api | `GET /sesiones/demo-ses-0000001-1` | `http://localhost:8001 · dependencia: redis` | **OK** | 2.3 | HTTP 200 · exito · estado=ACTIVA · requestId=h11-20261017-001145-14 | CU10 sesión de demo: 200 si está cargada, 404 si venció (TTL 30 min del Hito 7). Observado: la cadena cliente–API–adaptador–producto funciona para este caso de uso | rendimiento o concurrencia (Hito 12) |
| 2026-10-17T00:11:45Z | redis | api | `GET /sesiones/diag-no-existe-h11` | `http://localhost:8001 · dependencia: redis` | **OK** | 2.0 | HTTP 404 · inexistente · code=SESSION_NOT_FOUND · requestId=h11-20261017-001145-15 | sesión inexistente → 404, no 503. Observado: la fuente respondió: el recurso no existe (404), la dependencia está disponible | rendimiento o concurrencia (Hito 12) |
| 2026-10-17T00:11:45Z | influxdb | api | `GET /partidos/PAR-A-1/estadisticas?desde=2030-06-09T13:00:00Z&hasta=2030-06-09T13:30:00Z&agregacion=1m` | `http://localhost:8001 · dependencia: influxdb` | **OK** | 9.9 | HTTP 200 · exito · partidoId=PAR-A-1 · cantidad=60 · truncado=False · puntos=60 · requestId=h11-20261017-001145-16 | CU12 ventana agregada por minuto. Observado: la cadena cliente–API–adaptador–producto funciona para este caso de uso | rendimiento o concurrencia (Hito 12) |
| 2026-10-17T00:11:46Z | influxdb | api | `GET /partidos/PAR-A-1/estadisticas?desde=2031-01-01T00:00:00Z&hasta=2031-01-01T00:30:00Z` | `http://localhost:8001 · dependencia: influxdb` | **OK** | 7.0 | HTTP 200 · vacio_valido · partidoId=PAR-A-1 · cantidad=0 · truncado=False · puntos=0 · requestId=h11-20261017-001145-17 | ventana sin puntos → 200 puntos: []. Observado: la fuente respondió y no hay datos: ausencia válida (200), no timeout | rendimiento o concurrencia (Hito 12) |
| 2026-10-17T00:11:46Z | influxdb | api | `GET /partidos/PAR-A-1/estadisticas?desde=2030-06-09T13:30:00Z&hasta=2030-06-09T13:00:00Z` | `http://localhost:8001 · dependencia: ninguna (se valida antes)` | **OK** | 1.3 | HTTP 400 · validacion · code=INVALID_TIME_WINDOW · requestId=h11-20261017-001145-18 | ventana invertida → 400 INVALID_TIME_WINDOW. Observado: la API rechazó la entrada (400) antes de consultar la fuente | rendimiento o concurrencia (Hito 12) |
| 2026-10-17T00:11:46Z | iris | api | `GET /partidos/PAR-A-1/detalle` | `http://localhost:8001 · dependencia: iris (no integrado)` | **OK** | 1.0 | HTTP 404 · ruta_inexistente · code=ROUTE_NOT_FOUND · requestId=h11-20261017-001145-19 | la ruta de IRIS de la Clase 12 no existe en esta API: IRIS fuera de la arquitectura. Observado: la API no expone esa ruta (404 ROUTE_NOT_FOUND) | rendimiento o concurrencia (Hito 12) |
| 2026-10-17T00:11:46Z | api | api | `control: API no alcanzable (puerto sin listener)` | `http://localhost:8002/health` | **OK** | 0.4 | api_no_alcanzable · ConnectionRefusedError: [Errno 61] Connection refused | no hubo respuesta HTTP: la API no está escuchando en esa URL | nada sobre las fuentes: no se llegó a la API |

## Líneas de log asociadas (filtradas por X-Request-Id, campos sin datos sensibles)

| requestId | Log de acceso y de adaptadores |
|---|---|
| `h11-20261017-001145-01` | request 200 11.0ms |
| `h11-20261017-001145-02` | request 200 48.3ms; redis.ping=ok 6.9ms; influxdb.ping=ok 7.9ms; neo4j.ping=ok 10.9ms; mongodb.ping=ok 11.3ms; cassandra.conectar=ok 25.6ms; cassandra.ping=ok 26.7ms |
| `h11-20261017-001145-03` | request 200 0.8ms |
| `h11-20261017-001145-04` | request 200 2.0ms; mongodb.get_equipo=ok 1.0ms |
| `h11-20261017-001145-05` | request 200 2.5ms; mongodb.list_jugadores=ok 1.7ms |
| `h11-20261017-001145-06` | request 404 1.3ms; mongodb.get_equipo=ok 0.8ms |
| `h11-20261017-001145-07` | request 400 0.5ms |
| `h11-20261017-001145-08` | request 200 13.8ms; redis.cache_get_partido=ok 0.7ms; neo4j.get_partido=ok 11.4ms; redis.cache_set_partido=ok 0.5ms |
| `h11-20261017-001145-09` | request 200 8.0ms; neo4j.list_eventos=ok 7.3ms |
| `h11-20261017-001145-10` | request 200 6.4ms; neo4j.list_eventos=ok 5.8ms |
| `h11-20261017-001145-11` | request 404 3.5ms; neo4j.list_eventos=ok 2.8ms |
| `h11-20261017-001145-12` | request 200 7.6ms; cassandra.get_config=ok 1.8ms; cassandra.leer_particion=ok 1.2ms; cassandra.leer_particion=ok 1.1ms; cassandra.leer_particion=ok 1.0ms; cassandra.leer_particion=ok 1.1ms |
| `h11-20261017-001145-13` | request 404 1.7ms; cassandra.get_config=ok 1.2ms |
| `h11-20261017-001145-14` | request 200 1.5ms; redis.get_sesion=ok 0.8ms |
| `h11-20261017-001145-15` | request 404 1.0ms; redis.get_sesion=ok 0.6ms |
| `h11-20261017-001145-16` | request 200 9.1ms; influxdb.query_sql:1m=ok 7.9ms |
| `h11-20261017-001145-17` | request 200 6.0ms; influxdb.query_sql:1m=ok 5.4ms |
| `h11-20261017-001145-18` | request 400 0.4ms |
| `h11-20261017-001145-19` | request 404 0.2ms |
