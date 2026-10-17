# Capas de evaluación por producto (RNF2, §5.2, §5.4, RF9–RF14)

La evaluación va de menor a mayor costo y **no salta capas**: si una capa falla, `prueba_drivers.py` registra las siguientes como SKIP ("no se ejecuta porque falló la capa X") en lugar de probar algo que no puede salir bien.

| Capa | Pregunta | Herramienta | Qué todavía NO demuestra |
|---|---|---|---|
| 0 configuración | ¿Los valores existen, están bien formados y coinciden con los de la API? | `prueba_config.py` | que el servidor exista |
| 1 resolución | ¿El nombre se convierte en una dirección **desde el origen de la API**? | `getaddrinfo` | que haya un proceso escuchando |
| 2 TCP | ¿Hay un listener en host:puerto? ¿O el resultado es *refused*, *timeout* o *no resuelto*? | `socket.create_connection` con `CONNECT_TIMEOUT` | protocolo, identidad, contexto ni consulta |
| 3 protocolo | ¿El servidor habla el protocolo del producto? | handshake del driver o del cliente nativo | que la credencial sirva |
| 4 autenticación | ¿El servidor acepta la identidad configurada? | `verify_authentication`, token, `ACL WHOAMI` | que tenga permiso sobre el contexto |
| 5 autorización | ¿La identidad puede leer el contexto? | rol/permiso del producto | que el contexto exista |
| 5' contexto | ¿Existen la database, el keyspace, la tabla o la clave que usa la API? | catálogo del producto (`listDatabases`, `system_schema`, `SHOW DATABASES`, `information_schema`) | que haya datos |
| 6 operación | ¿Funciona una lectura mínima, acotada y no destructiva? | consulta con `LIMIT` y proyección | rendimiento, concurrencia ni carga masiva (Hito 12) |
| API | ¿Funciona la cadena cliente → API → adaptador → producto? | `prueba_api.py` | que **todas** las rutas estén sanas, ni que soporte volumen |

Cada capa tiene **controles negativos**: se provoca a propósito la falla que esa capa debería detectar y se verifica que se observe y se clasifique bien. Un control da OK cuando la falla aparece como se esperaba. Los controles no cambian el estado de la dependencia en la matriz: se cuentan aparte.

Las tablas de abajo resumen la corrida [`20261017-001129_completa`](evidencia/corridas/20261017-001129_completa/resultados_clientes.md).

## MongoDB (RF9)

| Capa | Prueba | Resultado | Lectura |
|---|---|---|---|
| TCP | `localhost:27017` | conecta (0,4 ms) | listener publicado |
| protocolo | `hello` con pymongo · `mongosh ping` | MongoDB 7.0.40, maxWireVersion 21, primario | habla el wire protocol |
| autenticación / autorización | `connectionStatus` | 0 usuarios autenticados → **N/C** | el laboratorio corre sin `--auth` (Hito 4). Con autenticación, un `OperationFailure` 18 o 13 → la API responde 503 con motivo `autenticacion` o `autorizacion` |
| contexto | `listDatabases` contiene `fixture2030`; `listCollections` = `equipos`, `jugadores` | OK | la base y las colecciones de la API existen |
| contexto (control) | database `fixture2030_inexistente` | **sin error, lista vacía** | **Mongo no rechaza una database mal escrita: crea el contexto al vuelo.** Ver H11-1 en [`diagnostico_de_fallas.md`](diagnostico_de_fallas.md) |
| operación | `equipos.findOne({_id:"ARG"}, {_id,nombre})` · `jugadores.countDocuments({equipoId:"ARG"}, limit 50)` | ARG Argentina · 23 jugadores | CU1 y CU2 legibles |
| operación (control) | `findOne({_id:"XXX"})` | `None` sin error | ausencia válida → la API responde 404, no 503 |
| API | `GET /equipos/ARG` 200 · `/equipos/XXX` 404 `TEAM_NOT_FOUND` · `/equipos/arg` 400 | OK | cliente nativo y API coinciden |

## Neo4j (RF10)

| Capa | Prueba | Resultado | Lectura |
|---|---|---|---|
| TCP | `7687` (Bolt) y `7474` (HTTP) | conectan | son dos caminos distintos: que 7474 responda no dice nada de 7687 |
| protocolo HTTP | `GET http://localhost:7474/` | 200, Neo4j 2026.07.1 community, anuncia `bolt://localhost:7687` | el **portal** responde. No es el camino de la API |
| protocolo Bolt | `verify_connectivity` | Bolt 6.1 | el driver de la API negocia Bolt |
| autenticación | `verify_authentication` | aceptada | la credencial de la API es válida |
| autenticación (control) | contraseña inválida, un solo intento | `verify_authentication=False` + `AuthError` | una credencial mala es un error de **identidad**, no de red |
| autorización | `SHOW CURRENT USER` | usuario `neo4j`, sin roles (Community no tiene RBAC fino) | la identidad consulta su perfil |
| contexto | `SHOW DATABASES` | `neo4j` online | la database de la API existe |
| contexto (control) | sesión sobre `fixture2030inexistente` | `Neo.ClientError.Database.DatabaseNotFound` | Neo4j **sí** rechaza un contexto inexistente. Antes del Hito 11 la API lo convertía en 500; ahora es 503 con motivo `contexto` |
| operación | Cypher parametrizado (`$id`), timeout del lado servidor, `LIMIT 1` | `PAR-A-1`: 10 eventos · `PAR-D16-01`: 0 eventos · `PAR-X-99`: sin fila | distingue **partido con datos**, **resultado vacío válido** y **partido inexistente**. El error de conexión se prueba en las fallas controladas |
| CLI | `cypher-shell --param` (desde el contenedor) | `"PAR-A-1", 10` | mismo resultado con el cliente nativo |
| API | `/partidos/PAR-A-1/eventos` 200 · `/partidos/PAR-D16-01/eventos` 200 `items: []` · `/partidos/PAR-X-99/eventos` 404 | OK | |

## Cassandra (RF11)

| Capa | Prueba | Resultado | Lectura |
|---|---|---|---|
| TCP | `127.0.0.1:9042` | conecta | |
| protocolo | `Cluster.connect` + `system.local` | Cassandra 5.0.9, protocolo v5, DC `datacenter1`, cluster `Fixture2030-Lab` | el DC local coincide con `CASSANDRA_DC` (si no, el driver de la API no tendría a quién enviar) |
| autenticación / autorización | sesión sin credenciales | aceptada → **N/C** (AllowAllAuthenticator/Authorizer, Hito 6) | con PasswordAuthenticator fallaría con `AuthenticationFailed` dentro de `NoHostAvailable` |
| contexto | keyspace en `system_schema.keyspaces` (NetworkTopologyStrategy) · columnas de `comentarios_por_partido` | partition key `(partido_id, ventana, bucket)`, clustering `(creado_en, comentario_id)` | se conoce el patrón de partición que usa la API |
| contexto (controles) | `USE fixture2030_comentarios_inexistente` · tabla inexistente · `SELEC 1` | `InvalidRequest` · `InvalidRequest` · `SyntaxException` | keyspace o tabla mal = **contexto**. Sintaxis mal = **consulta inválida**, con respuesta inmediata. Un **timeout de conexión** tardaría `CONNECT_TIMEOUT` y daría `NoHostAvailable`/`OperationTimedOut` |
| operación | `config_particion_partido` de `PAR-A-1` + `SELECT … WHERE partición completa LIMIT 5` | 1 bucket, ventana de 10 min; 1 comentario en la primera partición, con 1 consulta | lectura acotada sin escaneo de tabla |
| CLI | `cqlsh -e "USE …; SELECT … LIMIT 1"` (desde el contenedor) | 1 fila | |
| API | `/partidos/PAR-A-1/comentarios?limit=5` 200 · `/partidos/PAR-X-99/comentarios` 404 | OK | |

## Redis (RF12)

| Capa | Prueba | Resultado | Lectura |
|---|---|---|---|
| TCP | `127.0.0.1:6379` | conecta | |
| protocolo | `PING` (redis-py y `redis-cli` en la notebook) · `INFO server` | `PONG` · Redis 8.10.2 standalone | respuesta básica del servidor |
| autenticación / autorización | `ACL WHOAMI` | `default`, sin contraseña → **N/C** | con `requirepass`, un cliente sin AUTH recibiría `NOAUTH` (identidad) y la API respondería 503 con motivo `autenticacion`. Con ACL, `NOPERM` → motivo `autorizacion` |
| contexto | `INFO keyspace` db0 | 3 887 claves (3 885 con TTL) al momento de la corrida | la base lógica que usa la API |
| operación | `EXISTS` + `TYPE` + `HLEN` + `TTL` de `f30:ses:demo-ses-0000001-1` (**no** se leen los valores: es un dato personal) | presente, hash de 10 campos, vence en 1 492 s | existencia y expiración |
| operación (controles) | clave inexistente · `127.0.0.1:6380` | `EXISTS 0`, `TTL -2` · `ConnectionError` | **clave ausente ≠ Redis no disponible**: la API responde 404 en el primer caso y 503 en el segundo |
| API | `/sesiones/demo-ses-0000001-1` 200 (o 404 si venció) · `/sesiones/diag-no-existe-h11` 404 | OK | |

**Ausente vs. vencida.** Redis borra la clave al vencer: una clave que **nunca existió** y una que **expiró** dan las dos `EXISTS 0` y `TTL -2`. Sólo se pueden separar con información externa: la clave pertenece a la carga de muestra del Hito 7 (TTL de 30 min) y `INFO stats` muestra `expired_keys` creciendo. `prueba_drivers.py` informa ambas cosas y no lo presenta como una certeza. Se observó en una corrida exploratoria previa (con las sesiones de demo ya vencidas, `expired_keys = 4200`), y la repetición de [`matriz_de_conectividad.md`](matriz_de_conectividad.md) §3 lo vuelve a mostrar.

## InfluxDB 3 Core (RF13)

| Capa | Prueba | Resultado | Lectura |
|---|---|---|---|
| TCP | `127.0.0.1:8181` | conecta | |
| protocolo | `GET /health` (sin token) · `GET /ping` | 200 · InfluxDB 3 Core 3.12.0 | el **servicio** responde; no prueba ni token ni database |
| autenticación (controles) | `SELECT 1` sin token · con token inválido | 401 · 401 | `/health` accesible ≠ consulta autorizada |
| autenticación | `SELECT 1` con el token (archivo local, valor no mostrado) | 200 | la identidad de la API es válida |
| autorización | el mismo token consulta `fixture2030_vivo` | OK | token de administración local del Hito 8. En producción se usaría un token de sólo lectura por database |
| contexto | `information_schema.tables` contiene `estadisticas_equipo` | OK | |
| contexto (control) | `SELECT 1` sobre `fixture2030_vivo_inexistente` | 404 `database not found` | **servicio accesible, contexto inválido** |
| operación | `date_bin(5 min)` + `count(*)` sobre `[2030-06-09T13:00Z, 13:30Z)`, `LIMIT 12` | 6 tramos, 3 600 puntos | consulta temporal **acotada** en rango y agregación |
| operación (control) | misma consulta en `2031-01-01T00:00Z` + 30 min | 200, `puntos: 0` | **ausencia de puntos** = 200 vacío |
| CLI | `influxdb3 query SELECT 1` con el token por variable de entorno (desde el contenedor) | 1 fila | |
| API | ventana con `agregacion=1m` 200 (60 puntos) · ventana 2031 200 `puntos: []` · ventana invertida 400 `INVALID_TIME_WINDOW` | OK | |

## IRIS (RF14)

IRIS **no forma parte de la arquitectura vigente** desde la reentrega del Hito 3, aprobada por el profesor el 13/10/2026. La API del Hito 10 no tiene adaptador para IRIS, y el profesor aceptó no implementar el RF8 del Hito 10. Por la restricción "Productos" del enunciado se declara **NO_CONFIGURADO** y no se inventan resultados:

| Capa | Qué se hizo | Resultado |
|---|---|---|
| configuración | `IRIS_HABILITADO=0` | N/C |
| TCP | sondeo de `127.0.0.1:1972` (Superserver) y `127.0.0.1:52773` (portal) | **connection refused**: no hay listener, coherente con el contenedor sin levantar |
| protocolo, identidad, namespace, operación | no se ejecutan | N/C ("no evaluado: fuera de la arquitectura") |
| API | `GET /partidos/PAR-A-1/detalle` (la ruta de IRIS del script de la Clase 12) | 404 `ROUTE_NOT_FOUND`: la ruta no existe en esta API |
| `/health/dependencias` | la API informa `iris: NOT_CONFIGURED`, `enArquitectura: false` | no degrada el estado global |

Si IRIS volviera, `IRIS_HABILITADO=1` activa: portal HTTP (`/csp/sys/UtilHome.csp`), Superserver por TCP y, con la terminal del contenedor (`iris session IRIS -U USER`), el namespace activo y `%Dictionary.CompiledClass.%ExistsId("Fixture.Partido")`. Así se distinguirían "portal accesible", "Superserver inaccesible", "namespace incorrecto" y "objeto inexistente". **Ese camino no se ejecutó en este hito** (ver limitaciones).
