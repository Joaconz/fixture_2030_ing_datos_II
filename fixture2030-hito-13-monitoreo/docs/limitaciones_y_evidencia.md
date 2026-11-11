# Limitaciones y evidencia (RNF2, RNF3, RNF8)

## 1. Índice de evidencia

Cada archivo dice con qué script y qué commit se generó.

| Evidencia | Qué demuestra | Cómo se generó |
|---|---|---|
| [`evidencia/prometheus_targets_20261030-211330.md`](../evidencia/prometheus_targets_20261030-211330.md) | 11 targets UP, las 5 bases respondiendo, alerta `ApiErroresAltos` en pending (RF2, RF3) | `scripts/verificar_targets.sh --guardar`, commit `074851c` |
| [`evidencia/prueba_de_falla_redis_20261030-211553.md`](../evidencia/prueba_de_falla_redis_20261030-211553.md) | Caída controlada de Redis: detección a los 10 s, alerta a los 72 s, API 503 en sesiones mientras MongoDB sigue respondiendo, recuperación a los 13 s del `docker start` (RF10) | `scripts/ejecutar_prueba_controlada.sh redis`, commit `074851c` |
| [`evidencia/dashboards/falla_redis_durante.jpg`](../evidencia/dashboards/falla_redis_durante.jpg) | Dashboard durante esa caída: Redis CAÍDA, las otras 4 bases OK. Es el dashboard único de entonces; esa fila hoy está en *1. Resumen y SLAs* | captura de Grafana, 30/10/2026 21:15 (hora local; 00:15 UTC del 31/10) |
| [`evidencia/dashboards/falla_redis_despues.jpg`](../evidencia/dashboards/falla_redis_despues.jpg) | Dashboard único de entonces, después de la recuperación | captura de Grafana, 30/10/2026 21:17 (hora local) |
| [`evidencia/carga_observada_20261030-212441.md`](../evidencia/carga_observada_20261030-212441.md) | Con carga de lectura (399 req/s), Cassandra responde en ~1 ms por dentro mientras la API, al 97 % de CPU, tarda 42–91 ms: el cuello es la API (confirma la hipótesis H2 del Hito 12) (RF11, RF12) | `scripts/ejecutar_carga_observada.sh`, commit `6cc5ef7` |
| [`evidencia/metricas_neo4j_influxdb_20261110-204100.md`](../evidencia/metricas_neo4j_influxdb_20261110-204100.md) y capturas [`dashboards/neo4j_influxdb_fila_neo4j.jpg`](../evidencia/dashboards/neo4j_influxdb_fila_neo4j.jpg), [`dashboards/neo4j_influxdb_fila_influxdb.jpg`](../evidencia/dashboards/neo4j_influxdb_fila_influxdb.jpg) | Targets `neo4j` e `influxdb` UP con valores; las 8 reglas evaluándose; `Neo4jNoResponde` en firing a los 88 s de un `docker stop` y resuelta 58 s después del `start`; `InfluxDBEscriturasRechazadas` en firing a los 84 s de una línea rechazada; los 20 paneles del dashboard nuevo con datos. Stack aislado, con la VM de Docker saturada en parte de la prueba (RF2, RF9) | `verificar_targets.sh`, API de Prometheus y de Grafana, `docker stop`/`start`; commit `4219cde`
| [`evidencia/dashboards/1_resumen_y_slas.png`](../evidencia/dashboards/1_resumen_y_slas.png) … [`5_infraestructura.png`](../evidencia/dashboards/5_infraestructura.png) | Los cinco dashboards provisionados y con datos bajo tráfico de lectura mixto; qué paneles quedaron vacíos y por qué: [`evidencia/dashboards/README.md`](../evidencia/dashboards/README.md) | `/render` de Grafana, 10/11/2026, con tráfico de lectura de 10 minutos | |
| Tests de `/metrics` | Las métricas de la API cuentan por plantilla de ruta, registran 503 y la llamada a cada base; `/metrics` no entra al contrato OpenAPI (RF4, RNF5) | [`../../fixture2030-hito10-api/tests/unit/test_metricas.py`](../../fixture2030-hito10-api/tests/unit/test_metricas.py) (217 tests pasan) |

**Lectura del informe de falla:** antes y después de la caída la API responde **404 `SESSION_NOT_FOUND`** a `/sesiones/demo-ses-0000001-1`. Es correcto: esa sesión no existe (las sesiones vencen por TTL y la API no tiene un POST para crearlas). El 404 prueba que **Redis respondió** "no está"; el **503 `DEPENDENCY_UNAVAILABLE`** del medio prueba que Redis **no respondió**. La ruta de control `/equipos/ARG` (MongoDB) siguió en 200 durante toda la caída: la falla quedó aislada en su módulo.

## 2. Qué se midió, qué viene de un exporter y qué se infiere (RNF3)

| Afirmación | Tipo |
|---|---|
| Latencia, volumen y errores de la API | **Medido directamente** por la API (`/metrics`) |
| Tiempo de cada llamada de la API a cada base | **Medido** en el adaptador; es la latencia de la base **más** red y driver, no la del motor |
| Disponibilidad de las 5 bases | **Sonda**: el puerto o el endpoint responde. No garantiza que las consultas funcionen (eso lo dice la API) |
| Métricas internas de MongoDB, Redis y Cassandra | **Exporter** |
| Métricas internas de InfluxDB | **Directo**: su propio `/metrics`, leído con el token de administración desde un archivo fuera del repo |
| Métricas internas de Neo4j | **Exporter propio**: consultas de lectura por la Query API (estado, latencia de una consulta de referencia, tamaño del grafo, transacciones abiertas, heap). No son las métricas del motor de Enterprise (ver §3) |
| "El cuello está en la API y no en la base" | **Inferido** al comparar Q3 con Q5 ([`metricas_y_consultas.md`](metricas_y_consultas.md)) |
| Escalabilidad horizontal, réplicas, N/R/W, comportamiento ante caída de una región | **Diseño** (Hito 3), **no medido**: todo corre en un nodo por base |

## 3. Limitaciones del laboratorio

1. **Un nodo por base.** No hay réplicas, quórum ni regiones. Las decisiones de distribución del Hito 3 (N=3, R/W en Cassandra, réplica por región) son de diseño; lo que se mide acá es un nodo.
2. **Métricas de Neo4j e InfluxDB con límites.** Neo4j Community no trae el endpoint de Prometheus (es de Enterprise): un exporter propio consulta la base en cada scrape, así que solo hay lo que Community deja consultar; no hay transacciones confirmadas por segundo (`lastCommittedTxn` viene `NULL`), page cache ni métricas de Bolt, y las transacciones abiertas son una foto cada 15 s. InfluxDB 3 Core expone `/metrics`, pero con el **token de administración** (Core no tiene tokens de solo lectura): Prometheus lo lee de `fixture2030-influxdb/secrets/prometheus-token`, ignorado por git, que hay que generar en cada notebook con `scripts/preparar_token_influxdb.sh`; sin él, el target `influxdb` queda DOWN. Detalle: [`metricas_neo4j_e_influxdb.md`](metricas_neo4j_e_influxdb.md).
3. **Credenciales locales que no están en el repo (RNF6).** La API toma la contraseña de Neo4j de `fixture2030-neo4j/.env` y el token de InfluxDB de `fixture2030-influxdb/secrets/admin-token.json`, los dos ignorados por git. En una copia nueva del repo **no existen**: Neo4j responde `credencial rechazada` e InfluxDB `sin configurar`, y sus rutas dan 503. Así se vio en este laboratorio el 30/10/2026 (por eso `ApiErroresAltos` aparece en pending en la evidencia). Antes de la defensa hay que crearlos (ver README §"Preparar la demo"). Verificado para Neo4j: con `cp .env.example .env` pasó a UP. El token de InfluxDB queda en `secrets/` (se muestra una sola vez); el monitoreo lo copia a `secrets/prometheus-token` para leer `/metrics`.
4. **Docker Desktop.** Los exporters llegan a las bases por `host.docker.internal`. En Linux, Redis e InfluxDB publican solo en `127.0.0.1` y no son alcanzables así. node-exporter mide la VM de Docker, no la notebook.
5. **Resolución de los histogramas de la API:** el bucket más bajo es 5 ms (si una base responde en 0,3 ms, el p95 se ve como ≤ 5 ms) y los percentiles se interpolan dentro de cada bucket: el p95 de Prometheus no coincide con el de k6 (91 contra 71 ms en la carga observada).
10. **La latencia de una base vista desde la API incluye la espera del *event loop*.** Con la API saturada, `fixture2030_dependencia_duration_seconds` sube aunque la base esté rápida. Por eso se compara siempre con la métrica interna (Cassandra) y con la CPU de la API.
6. **Cassandra necesita el override.** Sin `docker-compose.monitoreo.yml` no hay métricas internas (la sonda sigue funcionando). El script de carga del Hito 12 levanta Cassandra con el compose normal **solo si no está corriendo**; su paso `docker compose run cargador` podría recrear el contenedor sin el agente (no verificado).
7. **Sin Alertmanager.** Las alertas se evalúan y se ven, pero no se notifica a nadie.
8. **Prueba de falla completa sobre una sola base (Redis).** El script soporta MongoDB, Cassandra y Neo4j; no se ejecutó con ellas. De Neo4j sí se forzó la alerta `Neo4jNoResponde` con un `docker stop`, en un stack aislado y sin la API (ver la evidencia de métricas de Neo4j e InfluxDB).
9. **IRIS no se monitorea:** no forma parte de la arquitectura vigente.

## 4. Datos que no se pudieron obtener

- Carga **de escritura** observada con Prometheus: la carga observada fue solo de lectura para no escribir en Cassandra (RNF5). La de escritura existe en el Hito 12, medida con k6 y sin este monitoreo.
- Comportamiento de Cassandra saturado (la cola de escrituras nunca pasó de 0).
- Cualquier dato de réplicas o multirregión.
