# Mapa de dependencias (RF1, §5.1)

**Hito 11 · Fixture 2030** — estado al 17/10/2026, commit `71a1625`.

Todas las conexiones las abre **un único proceso**: la API del Hito 10 (`uvicorn app.main:app`), que corre en la notebook y no en un contenedor. Por eso, para la API, los hosts son `localhost`/`127.0.0.1` y los puertos son los **publicados** por Docker. Los clientes de este hito corren desde ese mismo origen (ver [`topologia_y_entornos.md`](topologia_y_entornos.md)).

La asignación de módulos a productos sale del estado canónico del repositorio ([`../../docs/ESTADO-CANONICO-NECESIDADES.md`](../../docs/ESTADO-CANONICO-NECESIDADES.md)). Desde la reentrega del Hito 3 (13/10/2026), N2 Partidos y N8 Tipos de evento viven en Neo4j e IRIS queda fuera de la arquitectura.

## 1. Tabla de dependencias

| Producto | Módulo del Fixture (hito) | Host desde la API | Puerto · protocolo | Contexto | Autenticación (sin valor) | Cliente / driver de la API | Operación mínima del hito | Endpoint relacionado | Esperado | Observado |
|---|---|---|---|---|---|---|---|---|---|---|
| **MongoDB 7** | N1 Equipos y jugadores (Hito 4) | `localhost` | `27017` · MongoDB wire | db `fixture2030`, colecciones `equipos`, `jugadores` | ninguna (laboratorio sin `--auth`) | `pymongo` `AsyncMongoClient` | `hello`; `listCollections` filtrado; `equipos.findOne({_id:"ARG"})` con proyección | `GET /equipos/{codigo}`, `/jugadores` | UP | **DISPONIBLE** |
| **Neo4j 2026.07** | N2 Partidos, N3 Eventos, N8 Tipos (Hito 5 + reentrega H3) | `localhost` | `7687` · Bolt (API) · `7474` · HTTP (Browser, no lo usa la API) | database `neo4j` | usuario `neo4j` + contraseña (`NEO4J_PASSWORD` o `.env` local del módulo) | `neo4j` `AsyncGraphDatabase` | `verify_connectivity`, `verify_authentication`, `SHOW DATABASES`, Cypher parametrizado `MATCH (p:Partido {partidoId:$id}) … LIMIT 1` | `GET /partidos/{id}`, `/eventos` | UP | **DISPONIBLE** |
| **Cassandra 5** | N5 Comentarios (Hito 6) | `127.0.0.1` | `9042` · CQL native v5 | keyspace `fixture2030_comentarios`, DC `datacenter1`, tabla `comentarios_por_partido` (PK `partido_id, ventana, bucket`) | ninguna (AllowAllAuthenticator) | `cassandra-driver` (`LOCAL_ONE`, DC-aware) | `system.local`; `system_schema`; `SELECT … WHERE partición completa LIMIT 5` | `GET /partidos/{id}/comentarios` | UP | **DISPONIBLE** |
| **Redis 8** | N6 Sesiones y caché (Hito 7) | `127.0.0.1` | `6379` · RESP (sólo loopback) | base lógica `0`, claves `f30:ses:{id}` y `f30:cache:partido:{id}` | ninguna (sin `requirepass`; sólo 127.0.0.1) | `redis-py` asyncio | `PING`; `INFO keyspace`; `EXISTS`/`TYPE`/`HLEN`/`TTL` de la sesión de demo (sin leer valores) | `GET /sesiones/{id}`; caché de `GET /partidos/{id}` | UP | **DISPONIBLE** |
| **InfluxDB 3 Core** | N7 Estadísticas en vivo (Hito 8) | `127.0.0.1` | `8181` · HTTP (sólo loopback) | database `fixture2030_vivo`, tabla `estadisticas_equipo` | token Bearer (`INFLUX_TOKEN` o archivo local `secrets/admin-token.json`) | `httpx` → `/api/v3/query_sql` | `/health` (sin token); `SELECT 1` con token; `information_schema.tables`; `date_bin` 5 min en una ventana de 30 min | `GET /partidos/{id}/estadisticas` | UP | **DISPONIBLE** |
| **InterSystems IRIS** | (Hito 9: Partido/Jugador/Evento como objetos) | `127.0.0.1` | `1972` · Superserver · `52773` · HTTP portal | namespace `USER`, clase `Fixture.Partido` | usuario IRIS | **ninguno: la API no tiene adaptador** | sólo el sondeo TCP, que confirma que no hay listener | ninguno (`/partidos/{id}/detalle` de la Clase 12 no existe: 404 `ROUTE_NOT_FOUND`) | NOT_CONFIGURED | **NO_CONFIGURADO** |

La columna **Observado** sale de la matriz de la corrida [`20261017-001129_completa`](evidencia/corridas/20261017-001129_completa/matriz.md). No se completó suponiendo disponibilidad: cada valor sale de una prueba ejecutada.

## 2. Qué endpoint toca qué dependencia

| Endpoint (GET, usado en el hito) | Dependencias | Ausencia válida | Error de dependencia |
|---|---|---|---|
| `/health` | ninguna (liveness) | — | — |
| `/health/ready` | resultado cacheado del chequeo profundo | — | 503 `NO_LISTA` si mongodb o neo4j no están UP |
| `/health/dependencias` | las cinco (ping + contexto) | — | 503 con el detalle por fuente |
| `/equipos/{codigo}` · `/jugadores` | MongoDB | 404 `TEAM_NOT_FOUND` | 503 / 504 |
| `/partidos/{id}` | Neo4j + Redis (caché, optativa) | 404 `MATCH_NOT_FOUND` | 503 / 504 de Neo4j. Si Redis cae, el detalle sigue 200 con `X-Cache: BYPASS` |
| `/partidos/{id}/eventos` | Neo4j | 200 `items: []` (sin eventos) · 404 (sin partido) | 503 / 504 |
| `/partidos/{id}/comentarios` | Cassandra | 200 `items: []` · 404 (sin config de partición) | 503 / 504 |
| `/sesiones/{id}` | Redis | 404 `SESSION_NOT_FOUND` (ausente **o vencida**: Redis no las distingue) | 503 / 504 |
| `/partidos/{id}/estadisticas` | InfluxDB | 200 `puntos: []` | 503 / 504 |

Las escrituras (`POST` eventos y comentarios, `PATCH` estado, `DELETE` sesión) no se usan para probar conectividad, porque cambiarían el dominio (RNF6). Su comportamiento se probó en el Hito 10 (idempotencia, 503 con la fuente caída).

## 3. Contenedores, redes y volúmenes

| Producto | Contenedor | Red Compose | Publicación en la notebook | Volumen nombrado (no se toca) |
|---|---|---|---|---|
| MongoDB | `fixture2030_mongo` | `fixture2030-hito4-mongodb_default` | `0.0.0.0:27017→27017` | `fixture2030_mongo_data` |
| Neo4j | `fixture2030-neo4j` | `fixture2030-net` | `0.0.0.0:7474→7474`, `0.0.0.0:7687→7687` | `fixture2030_neo4j_data`, `_logs`, `_plugins` |
| Cassandra | `fixture2030-cassandra` | `fixture2030-cassandra-net` | `0.0.0.0:9042→9042` | `fixture2030_cassandra_data` |
| Redis | `fixture2030-redis` | `fixture2030-redis_default` | `127.0.0.1:6379→6379` | `fixture2030_redis_data` |
| InfluxDB | `fixture2030-influxdb` | `fixture2030-influxdb-net` | `127.0.0.1:8181→8181` | `fixture2030_influxdb_data` |
| IRIS | `fixture2030-iris` (no levantado) | default del módulo | `127.0.0.1:1972`, `127.0.0.1:52773` | `fixture2030_iris_durable` |

En este laboratorio el puerto interno y el publicado coinciden. Lo que cambia entre la notebook y un contenedor es el **host** (ver [`topologia_y_entornos.md`](topologia_y_entornos.md) §2).
