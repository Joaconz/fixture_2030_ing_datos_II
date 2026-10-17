# Diagnóstico de fallas (RF17, RF18, RNF10, RNF12, §5.3, §5.7)

Diagnosticar no es probar comandos al azar. Cada falla de esta página tiene **hipótesis → prueba ejecutada → resultado → siguiente paso**. Las fallas se provocaron de forma **controlada y reversible**: `docker stop/start`, `docker pause/unpause` o una segunda instancia de la API con una sola variable mal puesta. Nunca se borraron volúmenes ni datos.

Evidencia: [`corridas/20261017-001625_fallas-controladas/fallas_controladas.md`](evidencia/corridas/20261017-001625_fallas-controladas/fallas_controladas.md) (relato por escenario) y [`resultados_falla_controlada.md`](evidencia/corridas/20261017-001625_fallas-controladas/resultados_falla_controlada.md) (81 pruebas, 81 como se esperaba). Commit `e1de5d6`.

## 1. Cómo responde la API (RF18)

| Situación | HTTP · `code` | Ejemplo observado | Motivo en el log |
|---|---|---|---|
| Recurso inexistente | 404 · `TEAM_NOT_FOUND`, `MATCH_NOT_FOUND`, `SESSION_NOT_FOUND` | `/equipos/XXX` | — (la fuente respondió `ok`) |
| Ausencia válida | 200 con `items: []` / `puntos: []` | `/partidos/PAR-D16-01/eventos`, ventana 2031 | — |
| Error de validación | 400 · `VALIDATION_ERROR`, `INVALID_TIME_WINDOW` | `/equipos/arg`, ventana invertida | — (no se consulta la fuente) |
| Ruta inexistente | 404 · `ROUTE_NOT_FOUND` | `/partidos/PAR-A-1/detalle` (IRIS) | — |
| Dependencia no disponible | **503** · `DEPENDENCY_UNAVAILABLE` + `Retry-After: 5` | Redis detenido | `conexion`, `autenticacion`, `autorizacion`, `contexto`, `no_configurado`, `rechazo` |
| Dependencia que no responde a tiempo | **504** · `DEPENDENCY_TIMEOUT` + `Retry-After: 5` | InfluxDB en pausa | `timeout` |
| Error interno | 500 · `INTERNAL_ERROR` | (no se observó) | traza resumida, sin URIs |
| API no alcanzable | sin respuesta HTTP | `localhost:8002` | — |

La respuesta pública dice **qué** fuente falló (`details[campo=dependencia]`), pero no **por qué** cuando se trata de una credencial o de un contexto: eso queda en el log, con el `X-Request-Id` de la request. El chequeo de salud (`/health/dependencias`) sí muestra la categoría (`credencial rechazada`, `contexto inexistente`…), nunca el valor.

## 2. Tipos de falla de red (§5.3)

| Resultado | Hipótesis | Prueba | Observado | Siguiente paso |
|---|---|---|---|---|
| Conexión exitosa | hay listener | `prueba_tcp.py` a los cinco puertos | conecta en 0,2–0,5 ms | seguir a protocolo |
| Connection refused | el host responde pero nada escucha | Mongo en `27018`, IRIS `1972`/`52773`, Redis por la IP de la LAN | refused al instante (RST) | revisar proceso, puerto publicado e interfaz (`docker ps`) |
| Timeout | no hay respuesta: ruta, firewall o proceso colgado | `192.0.2.1:27017` (TEST-NET-1) | sin respuesta en 2 s (el límite) | probar desde el mismo entorno que la API y revisar la red |
| Host no resuelto | el nombre no existe en este entorno | `mongodb-inexistente.invalid`; `fixture2030_mongo` desde la red de Cassandra | `nodename nor servname provided` · `unresolved` | revisar el host y la red Compose (`localhost` vs nombre de servicio) |
| Puerto incorrecto | proceso vivo, prueba apuntando a otro listener | Mongo `27018` con Mongo vivo en `27017` | refused | comparar el puerto con el del `docker-compose.yml` y con el de la API (`prueba_config.py` lo compara) |
| `pause`: puerto abierto, proceso mudo | el socket lo sostiene Docker | TCP a `8181` con InfluxDB en pausa | **conecta** | por eso TCP no alcanza: el driver/HTTP da timeout → 504 |

Una conexión TCP exitosa **no** se presentó en ningún caso como prueba de autenticación, contexto o consulta válida. La matriz tiene una columna por capa justamente para eso.

## 3. Escenarios de falla controlada (§5.7)

### 3.1 Dependencia detenida — Redis (`docker stop`)

- **Hipótesis:** con Redis detenido, `/sesiones/{id}` debe responder 503 rápido, sin colgarse. `/partidos/{id}` debe seguir en 200, porque la caché es una optimización. La readiness debe quedar degradada pero lista (Redis no es esencial).
- **Condición inicial:** `fixture2030-redis` `running/healthy`; 2 claves persistentes y 3 533 con TTL; volumen `fixture2030_redis_data` creado el 26/09/2026.
- **Prueba y resultado:** `GET /sesiones/demo-ses-0000001-1` → **503 `DEPENDENCY_UNAVAILABLE` en 5,4 ms** (repetido: 1,6 ms), log `motivo=conexion`, `tipo=ConnectionError`. `GET /partidos/PAR-A-1` → 200 (la caché se saltea). `/health/dependencias` → 503 con `redis: DOWN «no responde»`. `/health/ready` → **200 `LISTA_DEGRADADA`**, `noDisponibles: [redis]`. `GET /equipos/ARG` → 200. TCP `6379` → connection refused.
- **Recuperación:** `docker start`, healthy en 6 s. La primera request posterior ya dio 200, **sin reiniciar la API** (RF20).
- **Datos:** 2 claves persistentes antes y después; el volumen tiene la misma fecha de creación. Las claves con TTL bajaron de 3 533 a 3 511 porque vencen solas (sesiones de 30 min del Hito 7), no porque se perdieran.

### 3.2 Dependencia detenida — MongoDB, una fuente esencial

- **Hipótesis:** Mongo es esencial (`READY_ESENCIALES=mongodb,neo4j`): la readiness tiene que pasar a 503.
- **Resultado:** `GET /equipos/ARG` → **503 en 1,91 s** (repetido: 1,74 s), `motivo=conexion`, `tipo=ServerSelectionTimeoutError` con `[Errno 61]`. `/health/ready` → **503 `NO_LISTA`**, `noDisponibles: [mongodb]`. `GET /partidos/PAR-A-1/eventos` (Neo4j) → 200. TCP `27017` → refused.
- **Por qué tarda ~1,8 s y no 2 ms como Redis:** pymongo reintenta la selección de servidor hasta `serverSelectionTimeoutMS`, que es el 80 % de `DEP_TIMEOUT_S` (1,6 s). El límite está acotado y no hay reintentos ilimitados (RNF12).
- **Recuperación:** la API volvió a responder 0,6 s después del `docker start`, sin reiniciarse. **Datos:** `jugadores=1472` antes y después; el volumen `fixture2030_mongo_data` está intacto.

### 3.3 Dependencia colgada — InfluxDB (`docker pause`)

- **Hipótesis:** el puerto sigue abierto pero nadie contesta. La API tiene que cortar en `DEP_TIMEOUT_S` (2 s) y responder **504**, no 503 ni una espera indefinida.
- **Resultado:** `GET /partidos/PAR-A-1/estadisticas…` → **504 `DEPENDENCY_TIMEOUT` en 2,008 s y 2,004 s**, `motivo=timeout`. TCP `8181` → **conecta** (ese es el punto: TCP no basta). `/health/dependencias` → 503, `influxdb: DOWN «timeout»` en 2,01 s. `/health/ready` → 200 `LISTA_DEGRADADA`.
- **Recuperación:** `docker unpause`; 200 inmediato sin reiniciar la API. **Datos:** 11 400 puntos de `PAR-A-1` antes y después.

### 3.4 Configuración incorrecta (instancia temporal de la API en `:8011`)

Una variable mal puesta por caso. La instancia principal y las bases no se tocan; la instancia temporal se termina al final de cada caso.

| Caso | Variable | Request de la fuente | Motivo en el log | `/health/dependencias` | Otra fuente en la misma instancia | Siguiente paso si pasara de verdad |
|---|---|---|---|---|---|---|
| credencial inválida | `NEO4J_PASSWORD` | 503 (50 ms; repetida 7 ms) | `autenticacion` (`AuthError`) | `DOWN «credencial rechazada»` | Mongo 200 | corregir la contraseña sin imprimirla (`prueba_config.py` informa sólo si está definida) |
| database inexistente | `NEO4J_DATABASE` | 503 | `contexto` (`DatabaseNotFound`) | `DOWN «contexto inexistente»` | 200 | `SHOW DATABASES`; revisar el nombre |
| keyspace inexistente | `CASSANDRA_KEYSPACE` | 503 | `contexto` (`InvalidRequest` al preparar) | `DOWN «contexto inexistente»` | 200 | `DESCRIBE KEYSPACES`; correr `esquema.cql` |
| **database inexistente** | `MONGO_DB` | **404 `TEAM_NOT_FOUND`** | — (Mongo respondió `ok`) | `DOWN «contexto inexistente»` | 200 | ver H11-1: sólo el chequeo de salud lo detecta |
| database inexistente | `INFLUX_DB` | 503 | `contexto` (404 `database not found`) | `DOWN «contexto inexistente»` | 200 | revisar la database del Hito 8 |
| token inválido | `INFLUX_TOKEN` | 503 | `autenticacion` (401) | `DOWN «credencial rechazada»` | 200 | regenerar con `autorizacion_local.sh` |
| token no configurado | `INFLUX_TOKEN_FILE` inexistente | 503 | `no_configurado` | **`NOT_CONFIGURED «sin configurar»`** | 200 | crear el archivo del token |
| puerto incorrecto | `REDIS_URL` → `:6390` | 503 en 36 ms (repetida 1,6 ms) | `conexion` | `DOWN «no responde»` | 200 | comparar con el puerto publicado |
| host no resuelto | `MONGO_URI` → `mongo-inexistente.invalid` | **504** la 1.ª (2,03 s), **503** la 2.ª (1,76 s) | `timeout`, después `conexion` | `DOWN «no responde»` | 200 | ver H11-4 |
| timeout demasiado bajo | `DEP_TIMEOUT_S=0.001` | 504 | `timeout` | `DOWN «timeout»` | **también 504** (el timeout es global) | `DEP_TIMEOUT_S` ≥ 1 s; medirlo con carga en el Hito 12 |

Todas las respuestas llegaron dentro del límite (`DEP_TIMEOUT_S + 1 s`). Ninguna request quedó bloqueada y no hubo reintentos ilimitados: los drivers reintentan sólo dentro de su timeout (pymongo en la selección, neo4j en `max_transaction_retry_time`) y la API no agrega reintentos (RNF12).

## 4. Cliente nativo vs. API (§5.5)

| Comparación | Dónde se vio | Lectura |
|---|---|---|
| nativo funciona / API funciona | corrida completa, las cinco fuentes | la cadena opera |
| nativo funciona / API falla | escenarios 3.4: Neo4j, Cassandra y Redis responden a sus CLI, pero la instancia mal configurada da 503 | problema de **configuración de la API**, no del producto: revisar `.env` y el log con el request-id |
| nativo falla / API falla | escenarios 3.1–3.3 (contenedor detenido o en pausa): TCP refused o timeout y la API da 503/504 | problema del **producto** o de la red |
| nativo funciona / API responde 404 | `MONGO_DB` mal escrito: `mongosh` lee `fixture2030` y la API responde `TEAM_NOT_FOUND` | la conectividad "funciona" pero el contexto es otro (H11-1) |

## 5. Hallazgos del hito

Cada hallazgo se encontró ejecutando las pruebas de este hito, no por revisión de código.

<a id="h11-1"></a>
**H11-1 — MongoDB no falla con una database mal escrita.** *Hipótesis:* con `MONGO_DB` mal escrito, la API debería fallar. *Prueba:* control `database inexistente` en `prueba_drivers.py` y caso `mongo-database`. *Resultado:* Mongo crea el contexto al vuelo y devuelve vacío: la API responde **404 `TEAM_NOT_FOUND` con 200 de la fuente**, es decir, una ausencia "válida" falsa. *Corrección aplicada:* el ping de Mongo en `/health/dependencias` ahora verifica que exista la colección `equipos` (`listCollections` filtrado, sin leer documentos) y marca `DOWN «contexto inexistente»`. *Pendiente (decisión de diseño, no se tocó):* las requests normales siguen sin verificar el contexto, porque costaría un `listCollections` por request. El chequeo de salud y la readiness son los que lo detectan.

**H11-2 — Database inexistente en Neo4j terminaba en 500.** *Resultado antes del cambio:* `ClientError: DatabaseNotFound` no estaba entre los errores de disponibilidad y caía en el handler de error inesperado. *Corrección:* el adaptador lo traduce a 503 con motivo `contexto`. Cualquier otro `ClientError` (Cypher inválido) sigue siendo 500, porque es un bug y no una dependencia.

**H11-3 — Timeout y caída eran indistinguibles.** Los dos daban 503 `DEPENDENCY_UNAVAILABLE` (Hito 10). *Corrección:* timeout → **504 `DEPENDENCY_TIMEOUT`**. Se actualizaron el contrato OpenAPI, el front (504 se muestra como "fuente no disponible"), Postman y las pruebas.

**H11-4 — El driver asíncrono de MongoDB informa un rechazo como "Connect call failed".** La primera versión del clasificador buscaba "refused" y clasificaba a Mongo detenido como `timeout` (504). *Corrección:* se reconocen `Errno 61/111` y "Connect call failed". Además, la selección de servidor de pymongo usa el 80 % de `DEP_TIMEOUT_S`, para que el error del driver llegue antes que el corte de la API. *Límite que queda:* con un host que no resuelve, la **primera** request después de arrancar la API suma el descubrimiento inicial de la topología y todavía corta por timeout (504). Las siguientes dan 503 `conexion`. Se acepta y se documenta.

**H11-5 — Neo4j bloquea el usuario tras varios intentos fallidos.** Después de 3 requests con la contraseña mala, Neo4j responde `Neo.ClientError.Security.AuthenticationRateLimit`, que **no** es un `AuthError`. El chequeo de salud lo mostraba `UNKNOWN`. *Corrección:* los `Security.*` se clasifican como `autenticacion`. *Implicancia operativa:* una API con una contraseña mala que reintente puede bloquear unos segundos al **mismo usuario** para otros clientes. Por eso los scripts esperan 6 s después de ese caso, y es otra razón para no reintentar ilimitadamente.

**H11-6 — El chequeo de salud del Hito 10 era optimista para InfluxDB.** Sólo llamaba a `/health`, que no exige token: con el token vencido o la database borrada, `/health/dependencias` decía `UP`. *Corrección:* el ping hace además `SELECT 1` con el token sobre la database configurada (costo: una consulta HTTP trivial, ver [`health_readiness.md`](health_readiness.md)).

**H11-7 — Clave ausente y clave vencida no se distinguen en Redis.** Es una propiedad del producto, no un bug. Ver [`capas_de_evaluacion.md`](capas_de_evaluacion.md) § Redis.

**Observaciones de higiene** (no cambian el estado de conectividad):
- La contraseña de Neo4j es la de desarrollo documentada en `fixture2030-neo4j/.env.example`, y el `.env` local tiene permisos `0644`. Es aceptable en un laboratorio. `prueba_config.py` lo marca WARN como observación y la redacción no la borra, porque es un valor público que además coincide con el nombre de la base de Mongo.
- MongoDB se publica en `0.0.0.0:27017` sin autenticación: desde la LAN es alcanzable (escenario "IP de la LAN"). Redis e InfluxDB, en cambio, se publican sólo en loopback.
