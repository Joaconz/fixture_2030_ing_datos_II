# Prueba de dependencia caída — redis

- Fecha (UTC): 2026-10-13T19:39:21Z
- Máquina: Darwin 25.6.0 arm64
- API: http://localhost:8000 · DEP_TIMEOUT_S = 2.0 s · límite aceptado = 3.0 s
- Contenedor: fixture2030-redis (sólo docker stop / docker start)

| Fase | Request | HTTP | Tiempo (s) | X-Cache | X-Request-Id | Cuerpo (recortado) |
|---|---|---:|---:|---|---|---|
| 1-arriba | `GET /sesiones/demo-ses-0000001-1` | 200 | 0.003864 | - | caida-redis-1-arriba | {"sesionId":"demo-ses-0000001-1","usuarioId":"USR-0000001","rol":"HINCHA","region":"EU","dispositivo":"ios","estado":"ACTIVA","creadaEn":"2030-06-29T15:58:53Z", |
| 1-arriba-detalle | `GET /partidos/PAR-A-1` | 200 | 0.002879 | HIT | caida-redis-1-arriba-detalle | {"partidoId":"PAR-A-1","fase":"GRUPOS","grupo":"A","jornada":1,"fechaHora":"2030-06-09T13:00:00Z","estado":"FINALIZADO","sede":{"sedeId":"URU-CEN","nombre":"Est |
| 2-caida | `GET /sesiones/demo-ses-0000001-1` | 503 | 0.003186 | - | caida-redis-2-caida | {"code":"DEPENDENCY_UNAVAILABLE","message":"La fuente 'redis' no está disponible. Reintentar más tarde.","requestId":"caida-redis-2-caida","details":[{"campo" |
| 2-caida-repite | `GET /sesiones/demo-ses-0000001-1` | 503 | 0.001787 | - | caida-redis-2-caida-repite | {"code":"DEPENDENCY_UNAVAILABLE","message":"La fuente 'redis' no está disponible. Reintentar más tarde.","requestId":"caida-redis-2-caida-repite","details":[{ |
| 2-caida-detalle | `GET /partidos/PAR-A-1` | 200 | 0.053496 | BYPASS | caida-redis-2-caida-detalle | {"partidoId":"PAR-A-1","fase":"GRUPOS","grupo":"A","jornada":1,"fechaHora":"2030-06-09T13:00:00Z","estado":"FINALIZADO","sede":{"sedeId":"URU-CEN","nombre":"Est |
| 2-caida-salud | `GET /health/dependencias` | 503 | 0.009266 | - | caida-redis-2-caida-salud | {"estado":"DEGRADADO","dependencias":[{"nombre":"mongodb","estado":"UP","latenciaMs":3.6,"detalle":null},{"nombre":"neo4j","estado":"UP","latenciaMs":7.0,"detal |
| 3-recuperada | `GET /sesiones/demo-ses-0000001-1` | 200 | 0.002335 | - | caida-redis-3-recuperada | {"sesionId":"demo-ses-0000001-1","usuarioId":"USR-0000001","rol":"HINCHA","region":"EU","dispositivo":"ios","estado":"ACTIVA","creadaEn":"2030-06-29T15:58:53Z", |

## Verificaciones

- OK: con la fuente arriba el endpoint no da 503 (dio 200)
- OK: con la fuente detenida el endpoint da 503 (dio 503)
- OK: el 503 usa el formato único con code DEPENDENCY_UNAVAILABLE
- OK: el 503 llega en menos de 3.0 s (0.003186 s y 0.001787 s)
- OK: /health/dependencias da 503 con la fuente DOWN (dio 503)
- OK: /partidos/PAR-A-1 sigue 200 con X-Cache: BYPASS (dio 200, BYPASS)
- OK: al volver la fuente la API se recupera sin reiniciarse (dio 200)

Resultado: todas las verificaciones OK
