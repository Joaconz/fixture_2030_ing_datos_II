# Alertas y umbrales (§5.4, RF9)

Las cinco reglas viven en [`prometheus/reglas-o-alertas.yml`](../prometheus/reglas-o-alertas.yml) y se validan con `promtool check rules`. Prometheus las evalúa cada 15 s. **No hay Alertmanager**: nadie recibe un mensaje; el estado se ve en http://localhost:9090/alerts y en el panel "Alertas activas" de Grafana. En un despliegue real, el paso siguiente sería enrutar `critica` a quien está de guardia y `advertencia` a un canal del equipo.

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
| Acción | Panel "Llamadas por segundo a cada base, por resultado": qué `dependencia` pasa a `no_disponible` o `timeout`. |
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
