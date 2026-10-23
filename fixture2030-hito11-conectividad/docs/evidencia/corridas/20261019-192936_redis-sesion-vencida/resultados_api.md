# Capa API — rutas del Hito 10 (cadena completa)

- Fecha (UTC) de inicio: 2026-10-19T19:30:07Z
- Commit: `ea51b8f+cambios-locales`
- Entorno: notebook-docker-desktop
- Origen de la prueba: notebook (host) · Windows AMD64 · python 3.13.7
- Timeouts: conexión 2 s · operación 3 s · API 8 s
- Secretos: ninguno se imprime; toda salida pasa por `registro.redactar` (RNF7/RNF8).

| Fecha (UTC) | Producto | Capa | Prueba | Objetivo / contexto | Resultado | ms | Detalle | Interpretación | No demuestra |
|---|---|---|---|---|---|---:|---|---|---|
| 2026-10-19T19:30:08Z | api | api | `GET /health` | `http://localhost:8001 · dependencia: ninguna (liveness)` | **OK** | 1244.1 | HTTP 200 · exito · estado=OK · requestId=h11-20261019-193007-01 | el proceso de la API responde sin tocar fuentes. Observado: la cadena cliente–API–adaptador–producto funciona para este caso de uso | rendimiento o concurrencia (Hito 12) |
| 2026-10-19T19:30:10Z | api | api | `GET /health/ready` | `http://localhost:8001 · dependencia: mongodb, neo4j (esenciales)` | **OK** | 1268.0 | HTTP 200 · exito · estado=LISTA · noDisponibles=[] · requestId=h11-20261019-193007-02 | readiness: las esenciales están UP. Observado: la cadena cliente–API–adaptador–producto funciona para este caso de uso | rendimiento o concurrencia (Hito 12) |
| 2026-10-19T19:30:11Z | api | api | `GET /health/dependencias` | `http://localhost:8001 · dependencia: las cinco (chequeo profundo, con caché)` | **OK** | 1041.5 | HTTP 200 · exito · estado=OK · mongodb=UP, neo4j=UP, cassandra=UP, redis=UP, influxdb=UP, iris=NOT_CONFIGURED · desdeCache=True · requestId=h11-20261019-193007-03 | estado por dependencia. Observado: la cadena cliente–API–adaptador–producto funciona para este caso de uso | rendimiento o concurrencia (Hito 12) |
| 2026-10-19T19:30:12Z | redis | api | `GET /sesiones/demo-ses-0000001-1` | `http://localhost:8001 · dependencia: redis` | **OK** | 1040.4 | HTTP 404 · inexistente · code=SESSION_NOT_FOUND · requestId=h11-20261019-193007-04 | CU10 sesión de demo: 200 si está cargada, 404 si venció (TTL 30 min del Hito 7). Observado: la fuente respondió: el recurso no existe (404), la dependencia está disponible | rendimiento o concurrencia (Hito 12) |
| 2026-10-19T19:30:13Z | redis | api | `GET /sesiones/diag-no-existe-h11` | `http://localhost:8001 · dependencia: redis` | **OK** | 1022.4 | HTTP 404 · inexistente · code=SESSION_NOT_FOUND · requestId=h11-20261019-193007-05 | sesión inexistente → 404, no 503. Observado: la fuente respondió: el recurso no existe (404), la dependencia está disponible | rendimiento o concurrencia (Hito 12) |
| 2026-10-19T19:30:16Z | api | api | `control: API no alcanzable (puerto sin listener)` | `http://localhost:8002/health` | **OK** | 2033.3 | api_no_alcanzable · ConnectionRefusedError: [WinError 10061] No se puede establecer una conexión ya que el equipo de destino denegó expresamente dicha conexión | no hubo respuesta HTTP: la API no está escuchando en esa URL | nada sobre las fuentes: no se llegó a la API |

## Líneas de log asociadas (filtradas por X-Request-Id, campos sin datos sensibles)

| requestId | Log de acceso y de adaptadores |
|---|---|
| `h11-20261019-193007-01` | request 200 0.8ms |
| `h11-20261019-193007-02` | request 200 251.2ms; redis.ping=ok 48.8ms; cassandra.ping=ok 100.3ms; mongodb.ping=ok 139.1ms; neo4j.ping=ok 168.5ms; influxdb.ping=ok 213.5ms |
| `h11-20261019-193007-03` | request 200 21.4ms |
| `h11-20261019-193007-04` | request 404 20.5ms; redis.get_sesion=ok 4.4ms |
| `h11-20261019-193007-05` | request 404 3.0ms; redis.get_sesion=ok 1.5ms |
