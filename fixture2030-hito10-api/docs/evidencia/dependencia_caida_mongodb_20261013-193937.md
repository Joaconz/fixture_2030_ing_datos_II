# Prueba de dependencia caída — mongodb

- Fecha (UTC): 2026-10-13T19:39:37Z
- Máquina: Darwin 25.6.0 arm64
- API: http://localhost:8000 · DEP_TIMEOUT_S = 2.0 s · límite aceptado = 3.0 s
- Contenedor: fixture2030_mongo (sólo docker stop / docker start)

| Fase | Request | HTTP | Tiempo (s) | X-Cache | X-Request-Id | Cuerpo (recortado) |
|---|---|---:|---:|---|---|---|
| 1-arriba | `GET /equipos/ARG` | 200 | 0.004406 | - | caida-mongodb-1-arriba | {"codigo":"ARG","nombre":"Argentina","confederacion":"CONMEBOL","rankingFifa":1,"grupo":"A","entrenador":"Lionel Scaloni","sede":"Madrid","colores":{"principal" |
| 2-caida | `GET /equipos/ARG` | 503 | 2.005229 | - | caida-mongodb-2-caida | {"code":"DEPENDENCY_UNAVAILABLE","message":"La fuente 'mongodb' no respondió dentro del tiempo límite. Reintentar más tarde.","requestId":"caida-mongodb-2-ca |
| 2-caida-repite | `GET /equipos/ARG` | 503 | 2.006272 | - | caida-mongodb-2-caida-repite | {"code":"DEPENDENCY_UNAVAILABLE","message":"La fuente 'mongodb' no respondió dentro del tiempo límite. Reintentar más tarde.","requestId":"caida-mongodb-2-ca |
| 2-caida-salud | `GET /health/dependencias` | 503 | 2.005889 | - | caida-mongodb-2-caida-salud | {"estado":"DEGRADADO","dependencias":[{"nombre":"mongodb","estado":"DOWN","latenciaMs":2002.7,"detalle":"timeout"},{"nombre":"neo4j","estado":"UP","latenciaMs": |
| 3-recuperada | `GET /equipos/ARG` | 200 | 0.004350 | - | caida-mongodb-3-recuperada | {"codigo":"ARG","nombre":"Argentina","confederacion":"CONMEBOL","rankingFifa":1,"grupo":"A","entrenador":"Lionel Scaloni","sede":"Madrid","colores":{"principal" |

## Verificaciones

- OK: con la fuente arriba el endpoint no da 503 (dio 200)
- OK: con la fuente detenida el endpoint da 503 (dio 503)
- OK: el 503 usa el formato único con code DEPENDENCY_UNAVAILABLE
- OK: el 503 llega en menos de 3.0 s (2.005229 s y 2.006272 s)
- OK: /health/dependencias da 503 con la fuente DOWN (dio 503)
- OK: al volver la fuente la API se recupera sin reiniciarse (dio 200)

Resultado: todas las verificaciones OK
