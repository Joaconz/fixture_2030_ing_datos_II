# Prueba de dependencia caída — cassandra

- Fecha (UTC): 2026-10-13T19:40:13Z
- Máquina: Darwin 25.6.0 arm64
- API: http://localhost:8000 · DEP_TIMEOUT_S = 2.0 s · límite aceptado = 3.0 s
- Contenedor: fixture2030-cassandra (sólo docker stop / docker start)

| Fase | Request | HTTP | Tiempo (s) | X-Cache | X-Request-Id | Cuerpo (recortado) |
|---|---|---:|---:|---|---|---|
| 1-arriba | `GET /partidos/PAR-A-1/comentarios?limit=5` | 200 | 0.012388 | - | caida-cassandra-1-arriba | {"partidoId":"PAR-A-1","items":[{"comentarioId":"PAR-A-1-C0004633","partidoId":"PAR-A-1","usuarioId":"USR-0000038","alias":"hincha_38","hinchada":"LOCAL","minut |
| 2-caida | `GET /partidos/PAR-A-1/comentarios?limit=5` | 503 | 0.006036 | - | caida-cassandra-2-caida | {"code":"DEPENDENCY_UNAVAILABLE","message":"La fuente 'cassandra' no está disponible. Reintentar más tarde.","requestId":"caida-cassandra-2-caida","details":[ |
| 2-caida-repite | `GET /partidos/PAR-A-1/comentarios?limit=5` | 503 | 0.001868 | - | caida-cassandra-2-caida-repite | {"code":"DEPENDENCY_UNAVAILABLE","message":"La fuente 'cassandra' no está disponible. Reintentar más tarde.","requestId":"caida-cassandra-2-caida-repite","det |
| 2-caida-salud | `GET /health/dependencias` | 503 | 0.029253 | - | caida-cassandra-2-caida-salud | {"estado":"DEGRADADO","dependencias":[{"nombre":"mongodb","estado":"UP","latenciaMs":2.0,"detalle":null},{"nombre":"neo4j","estado":"UP","latenciaMs":27.4,"deta |
| 3-recuperada | `GET /partidos/PAR-A-1/comentarios?limit=5` | 200 | 0.016467 | - | caida-cassandra-3-recuperada | {"partidoId":"PAR-A-1","items":[{"comentarioId":"PAR-A-1-C0004633","partidoId":"PAR-A-1","usuarioId":"USR-0000038","alias":"hincha_38","hinchada":"LOCAL","minut |

## Verificaciones

- OK: con la fuente arriba el endpoint no da 503 (dio 200)
- OK: con la fuente detenida el endpoint da 503 (dio 503)
- OK: el 503 usa el formato único con code DEPENDENCY_UNAVAILABLE
- OK: el 503 llega en menos de 3.0 s (0.006036 s y 0.001868 s)
- OK: /health/dependencias da 503 con la fuente DOWN (dio 503)
- OK: al volver la fuente la API se recupera sin reiniciarse (dio 200)

Resultado: todas las verificaciones OK
