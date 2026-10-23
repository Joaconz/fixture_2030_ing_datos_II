# Capa API — rutas del Hito 10 (cadena completa)

- Fecha (UTC) de inicio: 2026-10-17T00:35:46Z
- Commit: `ea51b8f`
- Entorno: notebook-docker-desktop
- Origen de la prueba: notebook (host) · Windows AMD64 · python 3.13.7
- Timeouts: conexión 2 s · operación 3 s · API 8 s
- Secretos: ninguno se imprime; toda salida pasa por `registro.redactar` (RNF7/RNF8).

| Fecha (UTC) | Producto | Capa | Prueba | Objetivo / contexto | Resultado | ms | Detalle | Interpretación | No demuestra |
|---|---|---|---|---|---|---:|---|---|---|
| 2026-10-17T00:35:48Z | api | api | `GET /health` | `http://localhost:8001 · dependencia: ninguna (liveness)` | **OK** | 1050.9 | HTTP 200 · exito · estado=OK · requestId=h11-20261017-003546-01 | el proceso de la API responde sin tocar fuentes. Observado: la cadena cliente–API–adaptador–producto funciona para este caso de uso | rendimiento o concurrencia (Hito 12) |
| 2026-10-17T00:35:49Z | api | api | `GET /health/ready` | `http://localhost:8001 · dependencia: mongodb, neo4j (esenciales)` | **OK** | 1060.0 | HTTP 200 · exito · estado=LISTA · noDisponibles=[] · requestId=h11-20261017-003546-02 | readiness: las esenciales están UP. Observado: la cadena cliente–API–adaptador–producto funciona para este caso de uso | rendimiento o concurrencia (Hito 12) |
| 2026-10-17T00:35:50Z | api | api | `GET /health/dependencias` | `http://localhost:8001 · dependencia: las cinco (chequeo profundo, con caché)` | **OK** | 1032.0 | HTTP 200 · exito · estado=OK · mongodb=UP, neo4j=UP, cassandra=UP, redis=UP, influxdb=UP, iris=NOT_CONFIGURED · desdeCache=True · requestId=h11-20261017-003546-03 | estado por dependencia. Observado: la cadena cliente–API–adaptador–producto funciona para este caso de uso | rendimiento o concurrencia (Hito 12) |
| 2026-10-17T00:35:51Z | redis | api | `GET /sesiones/demo-ses-0000001-1` | `http://localhost:8001 · dependencia: redis` | **OK** | 1025.6 | HTTP 200 · exito · estado=ACTIVA · requestId=h11-20261017-003546-04 | CU10 sesión de demo: 200 si está cargada, 404 si venció (TTL 30 min del Hito 7). Observado: la cadena cliente–API–adaptador–producto funciona para este caso de uso | rendimiento o concurrencia (Hito 12) |
| 2026-10-17T00:35:52Z | redis | api | `GET /sesiones/diag-no-existe-h11` | `http://localhost:8001 · dependencia: redis` | **OK** | 1058.3 | HTTP 404 · inexistente · code=SESSION_NOT_FOUND · requestId=h11-20261017-003546-05 | sesión inexistente → 404, no 503. Observado: la fuente respondió: el recurso no existe (404), la dependencia está disponible | rendimiento o concurrencia (Hito 12) |
| 2026-10-17T00:35:54Z | api | api | `control: API no alcanzable (puerto sin listener)` | `http://localhost:8002/health` | **OK** | 2052.1 | api_no_alcanzable · ConnectionRefusedError: [WinError 10061] No se puede establecer una conexión ya que el equipo de destino denegó expresamente dicha conexión | no hubo respuesta HTTP: la API no está escuchando en esa URL | nada sobre las fuentes: no se llegó a la API |

## Líneas de log asociadas (filtradas por X-Request-Id, campos sin datos sensibles)

| requestId | Log de acceso y de adaptadores |
|---|---|
| `h11-20261017-003546-01` | request 200 0.7ms |
| `h11-20261017-003546-02` | request 200 39.5ms; redis.ping=ok 6.4ms; cassandra.ping=ok 10.5ms; mongodb.ping=ok 12.9ms; neo4j.ping=ok 13.2ms; influxdb.ping=ok 34.3ms |
| `h11-20261017-003546-03` | request 200 1.6ms |
| `h11-20261017-003546-04` | request 200 4.0ms; redis.get_sesion=ok 2.4ms |
| `h11-20261017-003546-05` | request 404 2.4ms; redis.get_sesion=ok 1.3ms |
