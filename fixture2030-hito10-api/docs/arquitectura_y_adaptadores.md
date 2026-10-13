# Arquitectura y adaptadores — Hito 10

**Ingeniería de Datos II · Fixture 2030** — Santiago Pazos, Valentina Frisoli, Joaquín Núñez

## 1. Capas (RF9 / RNF1 / §5.2)

```
Cliente HTTP (front web/, Swagger UI, Postman, curl)
   │
   ▼
app/routes/*.py         contrato HTTP: path/query/body/headers validados por Pydantic, códigos de estado
   │  (Depends)
   ▼
app/services/*.py       casos de uso: reglas, cursores, composición de fuentes, decisión de 404/409
   │  (puertos: app/services/ports.py)
   ▼
app/adapters/*.py       un adaptador por producto: conexión, contexto, consulta, mapeo, traducción de errores
   │
   ▼
driver nativo           pymongo · neo4j · cassandra-driver · redis.asyncio · httpx
   │
   ▼
MongoDB · Neo4j · Cassandra · Redis · InfluxDB 3 (contenedores de los Hitos 4–8)
```

| Capa | Conoce | No conoce |
|---|---|---|
| `routes/` | HTTP, schemas públicos, qué servicio llamar | Drivers, consultas, reglas de negocio |
| `services/` | Casos de uso, reglas (p. ej. reglas por tipo de evento), cursores, 404/409 | Drivers, CQL/Cypher/SQL, HTTP (salvo las excepciones de dominio) |
| `adapters/` | Driver, database/keyspace, consultas parametrizadas, mapeo a schemas | HTTP, rutas |
| `core/` | Errores, request-id, logs, inyección de dependencias | Casos de uso |

Una ruta típica tiene 2–3 líneas (validación declarativa + llamada al servicio). La única "pieza de transporte" en un servicio es la cabecera `X-Cache`, que el servicio de partidos informa como dato (`HIT/MISS/BYPASS`) y la ruta copia.

**Puertos.** `app/services/ports.py` define con `Protocol` lo que cada servicio espera de un adaptador. Los adaptadores reales y los falsos de `tests/unit/` implementan los mismos métodos; por eso los servicios se prueban sin Docker (`app.dependency_overrides`), y cambiar un driver no toca rutas ni servicios.

**Pieza común: `app/adapters/base.py::ejecutar`.** Toda operación de red de cualquier adaptador pasa por ahí:
- `asyncio.wait_for` con el timeout configurado (RNF8);
- excepciones de disponibilidad del driver → `DependencyUnavailableError` → **503** (nunca un 200 vacío, RNF9);
- las excepciones de dominio (`NotFoundError`, `ConflictError`) atraviesan sin cambio;
- una línea de log por operación con `dependencia`, `operacion`, `resultado` y `duracion_ms`, sin parámetros ni resultados (RNF10).

**Ciclo de vida.** `app/main.py::lifespan` crea los cinco adaptadores al arrancar y los cierra al apagar. `connect()` **no** abre conexiones: todas son perezosas, así que la API arranca aunque una fuente esté caída y esa fuente responde 503 hasta que vuelve (sin reiniciar la API; ver `evidencia/dependencia_caida_*.md`, fase "recuperada").

## 2. Adaptadores (§5.5–§5.9)

### MongoDB — `app/adapters/mongo.py`
- **Conexión:** `AsyncMongoClient(MONGO_URI)`, perezoso; `serverSelectionTimeoutMS`, `connectTimeoutMS` y `socketTimeoutMS` = `DEP_TIMEOUT_S`.
- **Contexto:** database `MONGO_DB` (`fixture2030`), colecciones `equipos` y `jugadores` del Hito 4.
- **Consultas:** `find_one({_id: codigo})` con proyección explícita; plantel con `find({equipoId, [posicion], dorsal: {$gt: cursor}})`, `hint` al índice `{equipoId: 1, posicion: 1}` del Hito 4, orden por dorsal y `limit`. Nunca se devuelve el documento completo (no se expone el `_id` interno de jugadores).
- **Mapeo:** `_id` → `codigo`, `equipoId` → `equipoCodigo`.
- **Errores:** `ServerSelectionTimeoutError`, `ConnectionFailure`, `NetworkTimeout`, `AutoReconnect` → 503.

### Neo4j — `app/adapters/neo4j.py`
- **Conexión:** `AsyncGraphDatabase.driver` con usuario/contraseña de entorno; `connection_timeout`, `connection_acquisition_timeout` y `max_transaction_retry_time` = `DEP_TIMEOUT_S`.
- **Contexto:** database `NEO4J_DATABASE`; sesiones de lectura (`execute_read`) para consultas y **transacciones de escritura explícitas** (`execute_write`) para el alta de eventos y el cierre.
- **Consultas:** todo Cypher es parametrizado (`$partidoId`, `$tipo`, `$despues`, `$limite`…); ningún valor del cliente se concatena, y el cliente no elige etiquetas, relaciones ni propiedades (§5.6). Los recorridos están acotados: un partido y sus vecinos inmediatos, o los eventos de una partición con `ORDER BY secuencia LIMIT`.
- **Inexistente vs. vacío:** `list_eventos` devuelve `None` si el `:Partido` no existe y `[]` si existe sin eventos → 404 vs. 200 vacío.
- **Escritura de eventos:** una transacción que (1) toma un bloqueo de escritura sobre el `:Partido` (`SET p._lockApi = true REMOVE p._lockApi`), lo que serializa altas y cierres concurrentes del mismo partido; (2) chequea, en este orden, partido inexistente → replay de la misma `Idempotency-Key` (o clave reusada con otro cuerpo) → `FINALIZADO` → ya hay `FIN_PARTIDO` → `INICIO`/`FIN` repetido → tipo presente en `:TipoEvento`; (3) crea el evento con `secuencia = max + 1`, `origen: 'API'`, la `huella` del cuerpo y las relaciones `OCURRE_EN`, `ES_DE_TIPO`, `SIGUIENTE_EVENTO` y, si se resuelve, `PROTAGONIZADO_POR`.
- **Cierre:** una transacción que exige `PROGRAMADO` y un `FIN_PARTIDO`, cuenta los `GOL` por `condicionEquipo` (misma derivación que el paso 12 de `carga.cypher`) y fija `estado`, `golesLocal`, `golesVisitante` y `cerradoEn`.
- **Errores:** `ServiceUnavailable`, `SessionExpired`, `AuthError`, `DatabaseUnavailable` → 503 (un `AuthError` no se expone como tal).

### Cassandra — `app/adapters/cassandra.py`
- **Conexión:** `Cluster` con `DCAwareRoundRobinPolicy(local_dc=CASSANDRA_DC)` y perfil `consistency_level=LOCAL_ONE` (R=1/W=1 del Hito 3, N6), `request_timeout = DEP_TIMEOUT_S`. Conexión perezosa: la primera operación conecta (`connect_timeout = DEP_TIMEOUT_S`) dentro de un `asyncio.shield`, así una request que agota su timeout no descarta una conexión en curso que reusará la siguiente.
- **Reactor:** el reactor por defecto del driver en el venv (libev) con `execute_async`, puenteado a `asyncio` con `call_soon_threadsafe`; sólo `connect`/`prepare`/`shutdown` van al threadpool. No se usa `AsyncioConnection` (experimental en 3.30).
- **Contexto:** keyspace `CASSANDRA_KEYSPACE` (`fixture2030_comentarios`). **Prepared statements** preparados una vez.
- **Consultas:** siempre con la clave de partición completa `(partido_id, ventana, bucket)`. "Estrictamente después de una posición" con clustering mixto (`creado_en DESC, comentario_id ASC`) se resuelve con dos rangos sobre la misma partición en paralelo (`creado_en = t AND comentario_id > id` y `creado_en < t`).
- **Escritura:** `BatchStatement(LOGGED)` con los `INSERT` en `comentarios_por_partido` y `comentarios_por_usuario`; columnas sin valor como `UNSET_VALUE` (no crean tombstones).
- **Errores:** `NoHostAvailable`, `OperationTimedOut`, `ReadTimeout`, `WriteTimeout`, `Unavailable`, `ConnectionException` → 503. El `wait_for` de una operación usa hasta 3 × `DEP_TIMEOUT_S` porque puede incluir la conexión inicial y dos rangos; con el nodo colgado se observó 503 a los 2,0 s (`evidencia/dependencia_lenta_pause_*.md`).

### Redis — `app/adapters/redis.py`
- **Conexión:** `redis.asyncio.Redis.from_url(REDIS_URL, socket_connect_timeout, socket_timeout, decode_responses=True)`; base lógica 0 del Hito 7.
- **Operaciones:** `HGETALL` + `TTL` en un pipeline sin transacción (lectura; un TTL `-2` = no existe); cierre con `WATCH f30:ses:{id}` → `HGET usuario_id` → `MULTI` `SREM f30:usr:{usuario}:sesiones {id}` + `DEL f30:ses:{id}` `EXEC`; un `WatchError` se reintenta una vez y, si vuelve a abortar, 503 (no se borra a ciegas). Caché: `GET`, `SET … EX`, `DEL`. **Sin Lua, `EVAL` ni `FCALL`** (PR #11).
- **Errores:** `ConnectionError`, `TimeoutError`, `BusyLoadingError` → 503.
- **No exponer de más:** el servicio filtra el hash (no sale `solicitudes`) y trata un hash incompleto (vence entre lectura y renovación, ver `sesiones.redis` §3.4 bis) como sesión inexistente.

### InfluxDB 3 Core — `app/adapters/influx.py`
- **Conexión:** `httpx.AsyncClient(base_url=INFLUX_URL, timeout=DEP_TIMEOUT_S)`; token leído de `INFLUX_TOKEN` o del archivo local que crea el Hito 8 (`fixture2030-influxdb/secrets/admin-token.json`, ignorado por git), enviado como `Authorization: Bearer` y nunca logueado.
- **Contexto:** database `INFLUX_DB` (`fixture2030_vivo`), tabla `estadisticas_equipo`.
- **Consultas:** `POST /api/v3/query_sql` con texto fijo y `params` (`$partido`, `$desde`, `$hasta`, `$equipo`). `LIMIT` se valida como entero (1–2001) antes de escribirse en la consulta, porque InfluxDB 3 sólo garantiza parámetros en el `WHERE`. El intervalo de `date_bin` sale de un diccionario cerrado (`1m` → `1 minute`, `5m` → `5 minutes`), nunca del cliente. Agregación: `last_value(posesion_pct ORDER BY time)` y `max()` de los acumulados (nunca `sum`, Hito 8).
- **Vacío vs. caído:** 200 con `[]` (o cuerpo vacío) → lista vacía; 401/403 (token inválido), 404 (base inexistente), 400 (tabla inexistente) y 5xx → 503 con mensaje genérico; sin token → 503 sin llamar a InfluxDB. `ping` = `GET /health` (no requiere token).

## 3. Integración entre fuentes

La única request que combina dos fuentes es `GET /partidos/{id}` (Neo4j + Redis), con cache-aside: es el patrón P5/P6 que diseñó el Hito 7 para el dato más leído del torneo. Las escrituras sobre el partido (alta de evento, cierre) invalidan la copia (`DEL`); si Redis no responde en ese momento la escritura **no** falla (ya está confirmada en Neo4j) y la copia vence sola en 60 s — riesgo de frescura documentado (pregunta guía 19). El resto de los endpoints consulta una sola fuente: no se cruza MongoDB con Neo4j por código de equipo (Hallazgo H1, ver [`coherencia_tpo.md`](./coherencia_tpo.md) §3).

## 4. Mapa de archivos

| Archivo | Responsabilidad |
|---|---|
| `app/main.py` | Arma la app: lifespan, middleware (request-id, CORS + Private Network Access), handlers, routers, OpenAPI |
| `app/config/settings.py` | Variables de entorno (pydantic-settings), secretos como `SecretStr` |
| `app/core/errors.py` | Excepciones de dominio y formato único de error |
| `app/core/request_id.py` | `X-Request-Id`, log de acceso, 500 seguro |
| `app/core/logging.py` | Logs JSON |
| `app/core/deps.py` | Adaptadores → servicios (inyección) |
| `app/services/ports.py` | Puertos de los adaptadores |
| `app/services/cursor_entero.py` | Cursor opaco de jugadores y eventos |
| `app/adapters/base.py` | Timeout, traducción a 503, log por dependencia |
