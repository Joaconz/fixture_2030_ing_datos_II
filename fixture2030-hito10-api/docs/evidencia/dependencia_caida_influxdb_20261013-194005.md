# Prueba de dependencia caída — influxdb

- Fecha (UTC): 2026-10-13T19:40:05Z
- Máquina: Darwin 25.6.0 arm64
- API: http://localhost:8000 · DEP_TIMEOUT_S = 2.0 s · límite aceptado = 3.0 s
- Contenedor: fixture2030-influxdb (sólo docker stop / docker start)

| Fase | Request | HTTP | Tiempo (s) | X-Cache | X-Request-Id | Cuerpo (recortado) |
|---|---|---:|---:|---|---|---|
| 1-arriba | `GET /partidos/PAR-A-1/estadisticas?desde=2030-06-09T13:00:00Z&hasta=2030-06-09T13:30:00Z&agregacion=1m` | 200 | 0.019326 | - | caida-influxdb-1-arriba | {"partidoId":"PAR-A-1","desde":"2030-06-09T13:00:00Z","hasta":"2030-06-09T13:30:00Z","agregacion":"1m","puntos":[{"time":"2030-06-09T13:00:00Z","equipoCodigo":" |
| 2-caida | `GET /partidos/PAR-A-1/estadisticas?desde=2030-06-09T13:00:00Z&hasta=2030-06-09T13:30:00Z&agregacion=1m` | 503 | 0.002828 | - | caida-influxdb-2-caida | {"code":"DEPENDENCY_UNAVAILABLE","message":"La fuente 'influxdb' no está disponible. Reintentar más tarde.","requestId":"caida-influxdb-2-caida","details":[{" |
| 2-caida-repite | `GET /partidos/PAR-A-1/estadisticas?desde=2030-06-09T13:00:00Z&hasta=2030-06-09T13:30:00Z&agregacion=1m` | 503 | 0.002075 | - | caida-influxdb-2-caida-repite | {"code":"DEPENDENCY_UNAVAILABLE","message":"La fuente 'influxdb' no está disponible. Reintentar más tarde.","requestId":"caida-influxdb-2-caida-repite","detai |
| 2-caida-salud | `GET /health/dependencias` | 503 | 0.043974 | - | caida-influxdb-2-caida-salud | {"estado":"DEGRADADO","dependencias":[{"nombre":"mongodb","estado":"UP","latenciaMs":2.5,"detalle":null},{"nombre":"neo4j","estado":"UP","latenciaMs":42.0,"deta |
| 3-recuperada | `GET /partidos/PAR-A-1/estadisticas?desde=2030-06-09T13:00:00Z&hasta=2030-06-09T13:30:00Z&agregacion=1m` | 200 | 0.013383 | - | caida-influxdb-3-recuperada | {"partidoId":"PAR-A-1","desde":"2030-06-09T13:00:00Z","hasta":"2030-06-09T13:30:00Z","agregacion":"1m","puntos":[{"time":"2030-06-09T13:00:00Z","equipoCodigo":" |

## Verificaciones

- OK: con la fuente arriba el endpoint no da 503 (dio 200)
- OK: con la fuente detenida el endpoint da 503 (dio 503)
- OK: el 503 usa el formato único con code DEPENDENCY_UNAVAILABLE
- OK: el 503 llega en menos de 3.0 s (0.002828 s y 0.002075 s)
- OK: /health/dependencias da 503 con la fuente DOWN (dio 503)
- OK: al volver la fuente la API se recupera sin reiniciarse (dio 200)

Resultado: todas las verificaciones OK
