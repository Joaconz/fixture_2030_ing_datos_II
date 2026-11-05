# Inventario de componentes monitoreados (§5.1)

Qué hay en la plataforma, cómo se observa cada pieza y qué no se puede afirmar. Regla de la consigna: **una base cuenta como monitoreada solo si hay métrica, exporter o sonda que lo respalde**; la columna "mecanismo" dice cuál.

Tipos de mecanismo (RNF3):
- **Directo:** el propio componente expone `/metrics` (la API, Prometheus).
- **Exporter:** un proceso aparte traduce las métricas del producto a formato Prometheus.
- **Sonda:** el blackbox-exporter solo prueba que el puerto o el endpoint responde; no ve nada de adentro.
- **Inferido:** se deduce de otra métrica (por ejemplo, latencia de una base vista desde la API).

| Componente | Modelo de datos | Función en el Fixture | Puerto / endpoint | Mecanismo | Métricas seleccionadas | Riesgo que se observa | Limitaciones |
|---|---|---|---|---|---|---|---|
| **API REST** (Hito 10) | — (integra las 5 fuentes) | Único punto de entrada: equipos, partidos, eventos, comentarios, sesiones, estadísticas | `:8000/metrics` (job `fixture-api`) | Directo (`prometheus-client`, [`app/core/metricas.py`](../../fixture2030-hito10-api/app/core/metricas.py)) | `fixture2030_http_requests_total` (req por ruta y status), `fixture2030_http_request_duration_seconds` (latencia), `fixture2030_dependencia_duration_seconds` (tiempo de cada llamada a cada base, por resultado) | Latencia que percibe el usuario; 5xx por una base caída; distinguir si el cuello está en la API o en la base | Un solo proceso uvicorn en la notebook. Los histogramas tienen buckets desde 5 ms: debajo de eso no hay resolución |
| **MongoDB** (Hito 4) | Documental | N1 equipos y jugadores | `:27017` · exporter `:9216` (job `mongodb`) · sonda TCP | Exporter (`percona/mongodb_exporter`) + sonda | `mongodb_up`, `mongodb_op_counters_total` por tipo, `mongodb_connections{state="current"}` | Caída del catálogo de equipos; saturación de conexiones | Sin métricas por colección en el dashboard; nodo único (sin replica set) |
| **Neo4j** (Hito 5) | Grafo | N2 partidos, N3 eventos, N8 tipos de evento | `:7474` / `:7687` · sonda HTTP a `:7474` | Sonda + inferido (latencia desde la API) | `probe_success{base="neo4j"}`, `fixture2030_dependencia_duration_seconds{dependencia="neo4j"}` | Caída del calendario y de los eventos en vivo; cierre de partido (CP) imposible | **Sin métricas internas:** el endpoint Prometheus de Neo4j es solo de Enterprise y usamos Community |
| **Cassandra** (Hito 6) | Columnar (wide-column) | N6 comentarios por partido | `:9042` · agente JMX `:7070` (job `cassandra`) · sonda TCP | Exporter dentro de la JVM (`jmx_prometheus_javaagent`, override [`docker-compose.monitoreo.yml`](../../fixture2030-cassandra/docker-compose.monitoreo.yml)) + sonda | `cassandra_clientrequest_latency_seconds` p50/p99, `cassandra_clientrequest_total`, `cassandra_clientrequest_errores_total` (timeouts, unavailables, fallas), `cassandra_table_livediskspaceused`, `cassandra_threadpool_pendingtasks` | Pico de comentarios en un gol: escrituras encoladas, timeouts | Requiere levantar Cassandra con el override; nodo único (RF=1): "unavailable" equivale a nodo caído, no a pérdida de quórum |
| **Redis** (Hito 7) | Clave-valor | N5 sesiones (TTL) y caché del detalle de partido | `:6379` · exporter `:9121` (job `redis`) · sonda TCP | Exporter (`oliver006/redis_exporter`) + sonda | `redis_up`, `redis_commands_processed_total`, hits/misses de keyspace (hit ratio), `redis_memory_used_bytes`, `redis_connected_clients` | Caída de sesiones (usuarios deslogueados); caché que no acierta | El hit ratio mezcla la caché de partidos con las lecturas de sesiones |
| **InfluxDB 3 Core** (Hito 8) | Series temporales | N7 estadísticas en vivo | `:8181` · sonda HTTP a `/health` | Sonda + inferido (desde la API) | `probe_success{base="influxdb"}`, `fixture2030_dependencia_duration_seconds{dependencia="influxdb"}` | Estadísticas en vivo no disponibles | **Sin métricas internas:** `/metrics` de InfluxDB exige el token de administración y no se configuró en Prometheus para no guardar un secreto en el repo |
| **IRIS** (Hito 9) | Objetos | — (fuera de la arquitectura vigente desde la reentrega del Hito 3) | — | **No monitoreado** | — | — | Entrega histórica; no forma parte del sistema que se defiende ([`ESTADO-CANONICO`](../../docs/ESTADO-CANONICO-NECESIDADES.md) N2/N8) |
| **Host / VM de Docker** | — | Recursos compartidos por todas las piezas | node-exporter `:9100` | Exporter | CPU, memoria, disco, red, carga | Saturación del laboratorio que contamina las mediciones | En Docker Desktop mide la **VM de Docker**, no la notebook |
| **Prometheus** | TSDB | Recolección y alertas | `:9090` | Directo | `up`, `scrape_duration_seconds`, muestras ingeridas | Un target que deja de leerse | Retención 15 días; sin Alertmanager (las alertas se ven en `/alerts` y en Grafana) |
| **Grafana** | — | Visualización | `:3000` | — (no se monitorea a sí mismo) | — | — | Credenciales de desarrollo (`admin` / `fixture2030`), solo para el laboratorio |

## Relación job → componente

| Job de Prometheus | Componente observado | Etiquetas propias |
|---|---|---|
| `prometheus` | Prometheus | — |
| `node-exporter` | VM de Docker | — |
| `fixture-api` | API REST | `capa="aplicacion"` |
| `mongodb` | MongoDB | `base="mongodb"` |
| `redis` | Redis | `base="redis"` |
| `cassandra` | Cassandra | `base="cassandra"` |
| `salud-bases` | Las 5 bases (una serie por base) | `base`, `instance` = dirección sondeada |

`up{job=...}` dice si Prometheus pudo **leer el exporter**; `probe_success{base=...}` dice si la **base** responde. No son lo mismo: con Redis apagado, `up{job="redis"}` sigue en 1 (el exporter responde) y `redis_up` / `probe_success{base="redis"}` pasan a 0.
