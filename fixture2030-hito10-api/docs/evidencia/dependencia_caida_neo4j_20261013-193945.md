# Prueba de dependencia caída — neo4j

- Fecha (UTC): 2026-10-13T19:39:45Z
- Máquina: Darwin 25.6.0 arm64
- API: http://localhost:8000 · DEP_TIMEOUT_S = 2.0 s · límite aceptado = 3.0 s
- Contenedor: fixture2030-neo4j (sólo docker stop / docker start)

| Fase | Request | HTTP | Tiempo (s) | X-Cache | X-Request-Id | Cuerpo (recortado) |
|---|---|---:|---:|---|---|---|
| 1-arriba | `GET /partidos/PAR-A-1/eventos?limit=5` | 200 | 0.032263 | - | caida-neo4j-1-arriba | {"partidoId":"PAR-A-1","items":[{"eventoId":"PAR-A-1-EV-01","partidoId":"PAR-A-1","secuencia":1,"tipo":"INICIO_PARTIDO","minuto":0,"condicionEquipo":"LOCAL","do |
| 2-caida | `GET /partidos/PAR-A-1/eventos?limit=5` | 503 | 2.014264 | - | caida-neo4j-2-caida | {"code":"DEPENDENCY_UNAVAILABLE","message":"La fuente 'neo4j' no respondió dentro del tiempo límite. Reintentar más tarde.","requestId":"caida-neo4j-2-caida" |
| 2-caida-repite | `GET /partidos/PAR-A-1/eventos?limit=5` | 503 | 2.004821 | - | caida-neo4j-2-caida-repite | {"code":"DEPENDENCY_UNAVAILABLE","message":"La fuente 'neo4j' no respondió dentro del tiempo límite. Reintentar más tarde.","requestId":"caida-neo4j-2-caida- |
| 2-caida-salud | `GET /health/dependencias` | 503 | 2.006349 | - | caida-neo4j-2-caida-salud | {"estado":"DEGRADADO","dependencias":[{"nombre":"mongodb","estado":"UP","latenciaMs":2.2,"detalle":null},{"nombre":"neo4j","estado":"DOWN","latenciaMs":2003.3," |
| 3-recuperada | `GET /partidos/PAR-A-1/eventos?limit=5` | 200 | 0.014599 | - | caida-neo4j-3-recuperada | {"partidoId":"PAR-A-1","items":[{"eventoId":"PAR-A-1-EV-01","partidoId":"PAR-A-1","secuencia":1,"tipo":"INICIO_PARTIDO","minuto":0,"condicionEquipo":"LOCAL","do |

## Verificaciones

- OK: con la fuente arriba el endpoint no da 503 (dio 200)
- OK: con la fuente detenida el endpoint da 503 (dio 503)
- OK: el 503 usa el formato único con code DEPENDENCY_UNAVAILABLE
- OK: el 503 llega en menos de 3.0 s (2.014264 s y 2.004821 s)
- OK: /health/dependencias da 503 con la fuente DOWN (dio 503)
- OK: al volver la fuente la API se recupera sin reiniciarse (dio 200)

Resultado: todas las verificaciones OK
