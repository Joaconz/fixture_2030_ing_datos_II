# Alertas y umbrales (§5.4, RF9)

Las ocho reglas viven en [`prometheus/reglas-o-alertas.yml`](../prometheus/reglas-o-alertas.yml) y se validan con `promtool check rules`. Prometheus las evalúa cada 15 s. **No hay Alertmanager**: nadie recibe un mensaje; el estado se ve en http://localhost:9090/alerts y en el panel "Alertas activas" de Grafana. En un despliegue real, el paso siguiente sería enrutar `critica` a quien está de guardia y `advertencia` a un canal del equipo.

Cada alerta pasa por `pending` (la condición se cumple pero todavía no pasó el tiempo `for`) y después a `firing`.

## BaseNoResponde

| Campo | Valor |
|---|---|
| Métrica | `probe_success{job="salud-bases"}` (sonda TCP/HTTP del blackbox-exporter) |
| Condición | `== 0` |
| Duración mínima | 1 minuto |
| Severidad | crítica |
| Componente | la base indicada por la etiqueta `base` (MongoDB, Redis, Cassandra, Neo4j o InfluxDB) |
| Impacto en el Fixture | Las rutas de la API que dependen de esa base responden 503: sin comentarios (Cassandra), sin sesiones (Redis), sin partidos ni eventos (Neo4j), sin equipos (MongoDB) o sin estadísticas (InfluxDB). Las demás rutas siguen funcionando: la arquitectura aísla cada falla en su módulo. |
| Quién la atiende | quien opera la plataforma de datos |
| Acción | `docker ps` y `docker logs` del contenedor; `GET /health/dependencias` de la API para ver el motivo (`conexion`, `timeout`, `autenticacion`, `contexto`). |
| Por qué el umbral | 1 minuto = 4 sondas seguidas fallidas: descarta un reinicio rápido o una sonda perdida. **Verificado:** en la [prueba de falla](../evidencia/prueba_de_falla_redis_20261030-211553.md) la caída se vio a los 10 s y la alerta pasó a firing a los 72 s. |

## TargetSinScrape

| Campo | Valor |
|---|---|
| Métrica | `up` |
| Condición | `== 0` |
| Duración mínima | 2 minutos |
| Severidad | advertencia |
| Componente | el exporter o la API indicados por `job` |
| Impacto | No es una caída del Fixture: es **pérdida de visibilidad**. Los paneles de ese componente quedan vacíos y sus alertas dejan de poder evaluarse. |
| Quién la atiende | quien mantiene el monitoreo |
| Acción | Error del scrape en http://localhost:9090/targets y el procedimiento de [`metricas_y_consultas.md`](metricas_y_consultas.md) §"Investigar un target DOWN". |
| Por qué el umbral | 2 minutos (8 scrapes): más tolerante que `BaseNoResponde` porque perder un exporter es menos grave que perder una base. Experimental. |

## ApiErroresAltos

| Campo | Valor |
|---|---|
| Métrica | `fixture2030_http_requests_total` |
| Condición | 5xx sobre el total, ventana de 5 minutos, `> 1 %` |
| Duración mínima | 5 minutos |
| Severidad | crítica |
| Componente | API REST (y la base que la arrastra) |
| Impacto | Usuarios que reciben errores en vez de datos del partido. |
| Quién la atiende | quien opera la API; si Q6 apunta a una base, quien opera esa base |
| Acción | Panel "Llamadas por segundo a cada base, por resultado" (dashboard *3. Comparación entre bases*): qué `dependencia` pasa a `no_disponible` o `timeout`. |
| Por qué el umbral | El Hito 12 midió **0 errores** con 364 req/s, así que cualquier 5xx sostenido es una anomalía. 1 % deja margen para un error aislado. **Observado:** se activó (pending) con Neo4j rechazando credenciales e InfluxDB sin token (18,6 % de 5xx). |

## ApiLatenciaAlta

| Campo | Valor |
|---|---|
| Métrica | `fixture2030_http_request_duration_seconds` |
| Condición | p95 (ventana de 5 minutos) `> 150 ms` |
| Duración mínima | 5 minutos |
| Severidad | advertencia |
| Componente | API REST |
| Impacto | Comentarios y eventos en vivo que se perciben lentos **antes** de que aparezcan errores: es la alerta temprana. |
| Quién la atiende | quien opera la API |
| Acción | Comparar con "Latencia p95 de cada base" (Q5): si la base no subió, el cuello está en la API. |
| Por qué el umbral | El Hito 12 midió un p95 de **82,4 ms** bajo carga (20 usuarios, 364 req/s). 150 ms es ~1,8 veces eso: una prueba de carga normal no lo dispara, una degradación real sí. Basado en una medición, pero de un solo escenario: experimental. |

## CassandraEscriturasEncoladas

| Campo | Valor |
|---|---|
| Métrica | `cassandra_threadpool_pendingtasks{pool="MutationStage"}` |
| Condición | `> 100` |
| Duración mínima | 2 minutos |
| Severidad | advertencia |
| Componente | Cassandra (N6, comentarios) |
| Impacto | En un pico de comentarios (un gol en un partido de alto interés) las escrituras se encolan y el POST de comentario se vuelve lento; si sigue, llegan los timeouts. |
| Quién la atiende | quien opera Cassandra |
| Acción | Mirar compactaciones pendientes y la latencia de escritura (Q7). Con un solo nodo no hay a dónde repartir: la salida es agregar nodos (la estrategia de partición por partido + ventana + bucket lo permite) o limitar la carga. |
| Por qué el umbral | En las pruebas la cola estuvo siempre en 0 (`max_over_time` de 2 horas, 30/10/2026). 100 tareas sostenidas 2 minutos significa que el nodo no da abasto. **Experimental:** no se llegó a saturar Cassandra en el laboratorio. |

## Neo4jNoResponde

| Campo | Valor |
|---|---|
| Métrica | `neo4j_up` (exporter propio, [`metricas_neo4j_e_influxdb.md`](metricas_neo4j_e_influxdb.md)) |
| Condición | `== 0` |
| Duración mínima | 1 minuto |
| Severidad | crítica |
| Componente | Neo4j (N2 partidos, N3 eventos, N8 tipos de evento) |
| Impacto | Sin calendario ni línea de tiempo de eventos: las rutas de partidos y eventos de la API responden 503. |
| Quién la atiende | quien opera Neo4j |
| Acción | `docker logs fixture2030-neo4j-exporter` dice el motivo (conexión rechazada, credencial, base offline); después `docker ps` / `docker logs fixture2030-neo4j`. |
| Por qué el umbral | Mismo minuto que `BaseNoResponde`. La diferencia es qué mira: la sonda solo ve el puerto 7474 abierto; esta alerta exige que una consulta real corra, así que también salta con la credencial rechazada o la base offline. Con Neo4j apagado saltan las dos. **Verificado** (10/11/2026, stack aislado): firing a los 88 s del `docker stop`, resuelta 58 s después del `docker start` (ver la evidencia de métricas de Neo4j e InfluxDB). |

## Neo4jConsultaLenta

| Campo | Valor |
|---|---|
| Métrica | `neo4j_consulta_referencia_segundos{medida="servidor"}` (eventos de un partido, tiempo del motor) |
| Condición | `> 0.1` (100 ms) |
| Duración mínima | 5 minutos |
| Severidad | advertencia |
| Componente | Neo4j |
| Impacto | La línea de tiempo del partido se sirve lenta; con la API cargada acerca el p95 a `ApiLatenciaAlta`. |
| Quién la atiende | quien opera Neo4j |
| Acción | Heap y transacciones abiertas en el dashboard *4. Bases por dentro*; revisar que existan los índices de `estructura.cypher`. |
| Por qué el umbral | En el laboratorio la consulta tarda 6–66 ms en el motor con la base caliente. Justo después de un reinicio la primera vuelta tarda más (caché fría) y la alerta queda en pending unos segundos: el `for` de 5 minutos evita que eso dispare. **Experimental:** no se probó con carga. |

## InfluxDBEscriturasRechazadas

| Campo | Valor |
|---|---|
| Métrica | `influxdb3_write_lines_rejected_total` (`/metrics` de InfluxDB) |
| Condición | `increase(...[5m]) > 0` |
| Duración mínima | 1 minuto |
| Severidad | advertencia |
| Componente | InfluxDB 3 Core (N7 estadísticas en vivo) |
| Impacto | Esos puntos de estadísticas no se guardan: los agregados del partido quedan incompletos. La base sigue respondiendo, así que ninguna otra alerta lo ve. |
| Quién la atiende | quien opera la carga de estadísticas |
| Acción | Ver la respuesta del `POST /api/v3/write_lp` (conflicto de tipo de campo o línea mal formada) en el log del cargador o de la API. |
| Por qué el umbral | En operación normal el contador no se mueve: cualquier rechazo es un error del productor de datos. **Verificado** (10/11/2026): una línea con `tipo=5i` sobre un campo string devolvió HTTP 400 y la alerta pasó a firing. Se resuelve sola cuando el rechazo sale de la ventana de 5 minutos. |
