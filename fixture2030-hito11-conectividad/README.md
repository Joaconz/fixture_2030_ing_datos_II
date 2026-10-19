# Fixture 2030 — Hito 11 · Evaluación de la conectividad

**Ingeniería de Datos II · Clase 12** — Santiago Pazos, Valentina Frisoli, Joaquín Núñez

Procedimiento reproducible para comprobar, **capa por capa**, que la API integrada del Hito 10 puede localizar, alcanzar, autenticar y usar cada producto NoSQL del Fixture 2030. También describe qué hace la API cuando una dependencia está caída, colgada, mal configurada o sin datos.

```
configuración → resolución → TCP → protocolo → autenticación → autorización → contexto → operación mínima → endpoint de la API
```

Un contenedor encendido no significa una dependencia disponible. Por eso cada capa se prueba con el cliente o driver que le corresponde, y cada resultado deja escrito qué demuestra y qué todavía no.

## Resultado de la última evaluación

Corrida [`20261017-001129_completa`](docs/evidencia/corridas/20261017-001129_completa/matriz.md), commit `71a1625`, desde la notebook (el mismo origen que la API):

| Dependencia | Módulo (hito) | Estado | Observación |
|---|---|---|---|
| MongoDB 7.0.40 | Equipos y jugadores (4) | **DISPONIBLE** | Sin autenticación en el laboratorio (N/C). Una database mal escrita **no da error**: ver [diagnóstico](docs/diagnostico_de_fallas.md#h11-1) |
| Neo4j 2026.07.1 | Partidos, eventos, tipos (5 + reentrega H3) | **DISPONIBLE** | Observación: la contraseña es la de desarrollo del `.env.example` |
| Cassandra 5.0.9 | Comentarios (6) | **DISPONIBLE** | AllowAllAuthenticator (N/C) |
| Redis 8.10.2 | Sesiones y caché (7) | **DISPONIBLE** | Sin contraseña, sólo en 127.0.0.1 (N/C) |
| InfluxDB 3 Core 3.12.0 | Estadísticas en vivo (8) | **DISPONIBLE** | Se probaron token, permiso, database y una ventana acotada |
| InterSystems IRIS | Entidades complejas (9) | **NO_CONFIGURADO** | Fuera de la arquitectura vigente desde la reentrega del Hito 3. No se inventan resultados |

148 pruebas: 128 OK · 2 WARN (las dos son observaciones sobre la credencial de desarrollo de Neo4j) · 0 FAIL · 0 SKIP · 18 N/C. Las fallas controladas ([`20261017-001625_fallas-controladas`](docs/evidencia/corridas/20261017-001625_fallas-controladas/fallas_controladas.md), commit `e1de5d6`) dieron 81/81 resultados como se esperaba. **OK significa que esa prueba concreta funcionó en ese momento.** No es una garantía de rendimiento ni de disponibilidad permanente (RNF17). La carga masiva corresponde al Hito 12.

## Requisitos

- macOS, Linux o WSL con bash, `python3` ≥ 3.10 y `curl`.
- Docker Desktop (o Engine + Compose v2) con los cinco módulos levantados (ver [`../fixture2030-hito10-api/docs/conectividad_y_configuracion.md`](../fixture2030-hito10-api/docs/conectividad_y_configuracion.md) §5).
- La API del Hito 10 con su `.venv`: `bash ../fixture2030-hito10-api/scripts/iniciar_api.sh` lo crea. Las pruebas de capas 3 a 6 usan **ese** intérprete, porque así se prueban los mismos drivers que usa la API (pymongo, neo4j, cassandra-driver, redis, httpx).
- Clientes nativos opcionales: `mongosh`, `redis-cli`, `cypher-shell`, `cqlsh`, `influxdb3`. Si no están en la notebook se usa el que trae la imagen con `docker exec` y el registro lo marca como *origen: dentro del contenedor*. Si no hay ni cliente ni contenedor, el resultado es **SKIP**.

> **SKIP** significa que la prueba no se ejecutó por falta de herramienta o configuración. **No** significa "producto caído".
> **N/C** significa que la capa no aplica en este entorno (laboratorio sin autenticación) o que el producto no está configurado (IRIS).

## Variables

Se leen en este orden: [`config/configuracion-ejemplo.env`](config/configuracion-ejemplo.env) (versionado, sin secretos) < `config/configuracion.env` (local, ignorado por git) < variables de entorno.

| Grupo | Variables | Ejemplo |
|---|---|---|
| Entorno y límites | `ENTORNO`, `CONNECT_TIMEOUT`, `OPERACION_TIMEOUT`, `API_TIMEOUT` | `notebook-docker-desktop`, 2 s, 3 s, 8 s |
| API | `API_URL`, `API_DIR` | `http://localhost:8000`, `../fixture2030-hito10-api` |
| MongoDB | `MONGO_HOST`, `MONGO_PORT`, `MONGO_DB`, `MONGO_EQUIPO_DEMO` | `localhost`, `27017`, `fixture2030`, `ARG` |
| Neo4j | `NEO4J_HOST`, `NEO4J_BOLT_PORT`, `NEO4J_HTTP_PORT`, `NEO4J_DATABASE`, `NEO4J_USER`, `NEO4J_ENV_FILE` | `localhost`, `7687`, `7474`, `neo4j`, `neo4j`, `../fixture2030-neo4j/.env` |
| Cassandra | `CASSANDRA_HOST`, `CASSANDRA_PORT`, `CASSANDRA_KEYSPACE`, `CASSANDRA_TABLA`, `CASSANDRA_DC` | `127.0.0.1`, `9042`, `fixture2030_comentarios`, `comentarios_por_partido`, `datacenter1` |
| Redis | `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, `REDIS_SESION_DEMO` | `127.0.0.1`, `6379`, `0`, `demo-ses-0000001-1` |
| InfluxDB | `INFLUX_URL`, `INFLUX_DB`, `INFLUX_TABLA`, `INFLUX_TOKEN_FILE`, `INFLUX_DESDE`/`HASTA` | `http://127.0.0.1:8181`, `fixture2030_vivo`, `estadisticas_equipo`, `../fixture2030-influxdb/secrets/admin-token.json` |
| IRIS | `IRIS_HABILITADO`, `IRIS_HOST`, `IRIS_PORT`, `IRIS_PORTAL_URL`, `IRIS_NAMESPACE` | `0`, `127.0.0.1`, `1972`, `http://127.0.0.1:52773`, `USER` |

Los **secretos no van en ningún archivo de este hito**. La contraseña de Neo4j sale de `NEO4J_PASSWORD` (entorno) o del `.env` local del módulo Neo4j. El token de InfluxDB sale de `INFLUX_TOKEN` o del archivo local del Hito 8. Ningún script los imprime: `prueba_config.py` informa sólo si están definidos, cuántos caracteres tienen y si su archivo está fuera de git. Toda salida pasa por `registro.redactar()`, que borra los valores secretos, los tokens `apiv3_…`, las cabeceras `Authorization`, las URI con usuario y contraseña y la ruta del home (RNF7/RNF8). Las diferencias entre la notebook y un contenedor se explican en [`docs/topologia_y_entornos.md`](docs/topologia_y_entornos.md).

## Orden de ejecución

```bash
cd fixture2030-hito11-conectividad

# 0. Fuentes arriba y API corriendo (en otra terminal), con su log para correlacionar request-ids
bash ../fixture2030-hito10-api/scripts/iniciar_api.sh | tee docs/evidencia/crudo/api.log

# 1. Evaluación completa: config → TCP (+ escenarios de §5.3) → drivers y CLI → API → matriz
bash scripts/evaluar_conectividad.sh --escenarios --log docs/evidencia/crudo/api.log

# 2. Fallas controladas (stop/start de redis y mongodb, pause de influxdb, 10 configuraciones incorrectas)
bash scripts/evaluar_conectividad.sh --falla --producto redis --producto mongodb --log docs/evidencia/crudo/api.log
```

Cada ejecución crea `docs/evidencia/corridas/<fecha>_<modo>/` con un `.md` legible y un `.jsonl` por módulo, más `matriz.md`. Lo que queda en esa carpeta ya está redactado. Lo crudo (logs de la API) va a `docs/evidencia/crudo/`, que está ignorado por git.

### Modos (§5.8)

| Modo | Capa | Script | Qué pregunta responde |
|---|---|---|---|
| *(ninguno)* | todas menos fallas | `evaluar_conectividad.sh` | ¿Puede la API usar cada producto ahora? |
| `--config` | 0 | `prueba_config.py` | ¿Están los valores bien formados? ¿De dónde salen? ¿Los secretos existen sin mostrarse? ¿Coinciden con lo que carga la API? |
| `--tcp` (`--tcp-only`) | 1–2 | `prueba_tcp.py` | ¿Resuelve el host? ¿Hay un listener? ¿Es *refused*, *timeout* o *no resuelto*? |
| `--nativos` (`--native-only`) | 3–6 | `prueba_drivers.py` + `prueba_clientes_nativos.sh` | ¿Habla el protocolo? ¿Acepta la identidad? ¿Existe el contexto? ¿Funciona una lectura mínima? |
| `--api` (`--api-only`) | API | `prueba_api.py` | ¿Funciona la cadena cliente → API → adaptador → producto? ¿Se distingue vacío de inexistente, de validación y de caída? |
| `--falla` | §5.7 | `prueba_falla_controlada.py` | ¿Qué responde la API con una fuente detenida, colgada o mal configurada? ¿Se recupera sola? |
| `--matriz` | — | `generar_matriz.py` | Estado por dependencia de la corrida |

Opciones: `--producto X` (repetible; evaluación por producto, RNF13), `--escenarios`, `--api-url URL`, `--log ARCHIVO`, `--corrida NOMBRE`, `--limpiar` (borra **sólo** `docs/evidencia/crudo/`, nunca datos ni volúmenes). Con `ESTRICTO=1` el script sale con código 1 si hubo algún FAIL (para CI). Sin esa variable sale con 0, como el script de la Clase 12, para que siempre se vea el diagnóstico completo.

Cada módulo también se puede ejecutar solo, por ejemplo `../fixture2030-hito10-api/.venv/bin/python scripts/prueba_drivers.py --producto neo4j`.

## Estructura

```
fixture2030-hito11-conectividad/
├── README.md
├── .gitignore                     configuración local, secretos y salidas crudas fuera de git
├── config/
│   ├── configuracion-ejemplo.env  todas las variables, sin secretos
│   └── .gitignore                 configuracion.env y cualquier *.token/*.key
├── scripts/
│   ├── evaluar_conectividad.sh    punto de entrada (modos, filtros, resumen)
│   ├── registro.py                configuración, redacción y registro de evidencia (JSONL + Markdown)
│   ├── prueba_config.py           capa 0
│   ├── prueba_tcp.py              capas 1–2 (+ escenarios de §5.3)
│   ├── prueba_drivers.py          capas 3–6 con los drivers de la API
│   ├── prueba_clientes_nativos.sh capas 3–6 con mongosh / cypher-shell / cqlsh / redis-cli / influxdb3
│   ├── prueba_api.py              rutas del Hito 10
│   ├── prueba_falla_controlada.py stop/start, pause/unpause, configuración incorrecta
│   └── generar_matriz.py          matriz de la corrida
└── docs/
    ├── mapa_de_dependencias.md    producto · módulo · proceso · host · puerto · contexto · cliente · operación · endpoint
    ├── topologia_y_entornos.md    notebook vs contenedor, puertos publicados vs internos, redes Compose
    ├── capas_de_evaluacion.md     qué responde y qué no demuestra cada prueba, por producto
    ├── matriz_de_conectividad.md  matriz consolidada y significado de los estados
    ├── diagnostico_de_fallas.md   hipótesis → prueba → resultado → siguiente paso; hallazgos del hito
    ├── health_readiness.md        liveness, readiness, chequeo por dependencia, timeouts, frecuencia y costo
    ├── limitaciones_y_coherencia.md
    └── evidencia/                 corridas/ (redactadas) · capturas_redactadas/ · README.md
```

## Cambios en la API del Hito 10 (motivados por este hito)

Están en `../fixture2030-hito10-api/`, con pruebas (207 unitarias, 33 de integración, 151 aserciones de Newman y 651 casos de schemathesis en verde):

- **RF18:** un timeout de la fuente ahora responde **504 `DEPENDENCY_TIMEOUT`**. Antes era 503 con el mismo `code` que una caída. Una fuente caída, rechazada o mal configurada sigue siendo 503 `DEPENDENCY_UNAVAILABLE`.
- **RF17 / RNF11:** cada línea de log de un adaptador lleva `motivo`: `timeout`, `conexion`, `autenticacion`, `autorizacion`, `contexto`, `no_configurado` o `rechazo`. Una database inexistente en Neo4j antes terminaba en **500**. Ahora es 503 con motivo `contexto`.
- **§5.6:** `GET /health/ready` (readiness), un chequeo por dependencia que verifica el contexto y no sólo el ping, estados `UP`/`DOWN`/`NOT_CONFIGURED`/`UNKNOWN`, IRIS informado como `NOT_CONFIGURED` y una caché de `HEALTH_CACHE_S` con *single-flight*. Detalle en [`docs/health_readiness.md`](docs/health_readiness.md).

## Trazabilidad de requisitos

| Requisito | Dónde se cumple |
|---|---|
| RF1 dependencias | [`docs/mapa_de_dependencias.md`](docs/mapa_de_dependencias.md) |
| RF2 topología | [`docs/topologia_y_entornos.md`](docs/topologia_y_entornos.md) |
| RF3 configuración sin secretos | `prueba_config.py` · `resultados_config.md` |
| RF4 resolución · RF5 TCP | `prueba_tcp.py` · `resultados_tcp.md` |
| RF6 handshake · RF7 identidad y contexto · RF8 operación mínima | `prueba_drivers.py`, `prueba_clientes_nativos.sh` · `resultados_clientes.md` |
| RF9–RF14 por producto | [`docs/capas_de_evaluacion.md`](docs/capas_de_evaluacion.md) |
| RF15 rutas de la API · RF19 request-id, duración, log | `prueba_api.py` · `resultados_api.md` (tabla de log por request-id) |
| RF16 matriz | [`docs/matriz_de_conectividad.md`](docs/matriz_de_conectividad.md) · `matriz.md` de cada corrida |
| RF17 comportamiento ante fallas · RF18 respuestas distintas | [`docs/diagnostico_de_fallas.md`](docs/diagnostico_de_fallas.md) · cambios en la API |
| RF20 repetir tras recuperar · RF21 detención temporal | `fallas_controladas.md` (fase 3 de cada escenario) · [`docs/matriz_de_conectividad.md`](docs/matriz_de_conectividad.md) §3 |
| RF22 / RNF16 GitHub | este directorio, con historial de commits |
| RNF1 reproducibilidad | este README · configuración por archivo · verificado desde un clon limpio de la rama (sin secretos ni `.venv`): la capa 0 marca FAIL con el motivo (`NEO4J_PASSWORD` y token de InfluxDB «no definido»), las pruebas que dependen de esas credenciales quedan SKIP (los CLI de Neo4j e InfluxDB, con la variable que falta) y el driver de Cassandra queda SKIP indicando qué `.venv` usar; MongoDB y Redis, que no piden secretos, se evalúan igual |
| RNF2 capas · RNF4 clientes adecuados | una fila por capa y producto, con el cliente nativo o el driver (nunca HTTP genérico para Bolt, CQL ni RESP) |
| RNF3 origen | campo `origen` en cada fila · escenarios "dentro del contenedor" |
| RNF5 timeouts · RNF12 degradación | `CONNECT_TIMEOUT`, `OPERACION_TIMEOUT`, `API_TIMEOUT` · `DEP_TIMEOUT_S` de la API, sin reintentos ilimitados |
| RNF6 no destructivo | sólo lecturas, `ping`, `SELECT 1`, `docker stop/start`, `pause/unpause` |
| RNF7 / RNF8 secretos | `registro.redactar()` · `.gitignore` · `prueba_config.py` |
| RNF9 estados · RNF10 diagnóstico | `generar_matriz.py` · [`docs/diagnostico_de_fallas.md`](docs/diagnostico_de_fallas.md) |
| RNF13 independencia | `--producto`, un modo por capa, cada script también se ejecuta solo |
| RNF14 integridad del contexto | columna "objetivo / contexto" de cada fila |
| RNF15 legibilidad | un script por capa y una sección por modo |
| RNF17 honestidad · RNF18 trazabilidad | columnas "interpretación" y "no demuestra" · fecha, commit, entorno y origen en cada fila |

Limitaciones: [`docs/limitaciones_y_coherencia.md`](docs/limitaciones_y_coherencia.md).
