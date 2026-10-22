# Capa API — rutas del Hito 10 (cadena completa)

- Fecha (UTC) de inicio: 2026-10-22T20:31:15Z
- Commit: `sin-git`
- Entorno: notebook-docker-desktop
- Origen de la prueba: notebook (host) · Darwin arm64 · python 3.9.6
- Timeouts: conexión 2 s · operación 3 s · API 8 s
- Secretos: ninguno se imprime; toda salida pasa por `registro.redactar` (RNF7/RNF8).

| Fecha (UTC) | Producto | Capa | Prueba | Objetivo / contexto | Resultado | ms | Detalle | Interpretación | No demuestra |
|---|---|---|---|---|---|---:|---|---|---|
| 2026-10-22T20:31:15Z | api | api | `GET /health` | `http://localhost:8000 · dependencia: ninguna (liveness)` | **OK** | 14.2 | HTTP 200 · exito · estado=OK · requestId=h11-20261022-203115-01 | el proceso de la API responde sin tocar fuentes. Observado: la cadena cliente–API–adaptador–producto funciona para este caso de uso | rendimiento o concurrencia (Hito 12) |
| 2026-10-22T20:31:17Z | api | api | `GET /health/ready` | `http://localhost:8000 · dependencia: mongodb, neo4j (esenciales)` | **WARN** | 2010.9 | HTTP 503 · salud_degradada · estado=NO_LISTA · noDisponibles=['mongodb', 'neo4j', 'cassandra', 'redis', 'influxdb'] · requestId=h11-20261022-203115-02 | readiness: las esenciales están UP. Observado: el chequeo de salud informa al menos una fuente que no está UP (503 con el detalle por fuente) | rendimiento o concurrencia (Hito 12) |
| 2026-10-22T20:31:17Z | api | api | `GET /health/dependencias` | `http://localhost:8000 · dependencia: las cinco (chequeo profundo, con caché)` | **WARN** | 5.9 | HTTP 503 · salud_degradada · estado=DEGRADADO · mongodb=DOWN, neo4j=DOWN, cassandra=DOWN, redis=DOWN, influxdb=DOWN, iris=NOT_CONFIGURED · desdeCache=True · requestId=h11-20261022-203115-03 | estado por dependencia. Observado: el chequeo de salud informa al menos una fuente que no está UP (503 con el detalle por fuente) | rendimiento o concurrencia (Hito 12) |
| 2026-10-22T20:31:17Z | iris | api | `GET /partidos/PAR-A-1/detalle` | `http://localhost:8000 · dependencia: iris (no integrado)` | **OK** | 4.6 | HTTP 404 · ruta_inexistente · code=ROUTE_NOT_FOUND · requestId=h11-20261022-203115-04 | la ruta de IRIS de la Clase 12 no existe en esta API: IRIS fuera de la arquitectura. Observado: la API no expone esa ruta (404 ROUTE_NOT_FOUND) | rendimiento o concurrencia (Hito 12) |
| 2026-10-22T20:31:17Z | api | api | `control: API no alcanzable (puerto sin listener)` | `http://localhost:8001/health` | **OK** | 3.3 | api_no_alcanzable · ConnectionRefusedError: [Errno 61] Connection refused | no hubo respuesta HTTP: la API no está escuchando en esa URL | nada sobre las fuentes: no se llegó a la API |

## Líneas de log asociadas (filtradas por X-Request-Id, campos sin datos sensibles)

| requestId | Log de acceso y de adaptadores |
|---|---|
| `h11-20261022-203115-01` | request 200 1.4ms |
| `h11-20261022-203115-02` | request 503 2006.9ms; redis.ping=no_disponible/conexion 16.9ms; influxdb.ping=no_disponible/conexion 22.5ms; cassandra.conectar=no_disponible/conexion 23.4ms; cassandra.ping=no_disponible/conexion 23.6ms; mongodb.ping=no_disponible/conexion 1780.2ms; neo4j.ping=timeout/timeout 2001.1ms |
| `h11-20261022-203115-03` | request 503 1.5ms |
| `h11-20261022-203115-04` | request 404 0.3ms |
