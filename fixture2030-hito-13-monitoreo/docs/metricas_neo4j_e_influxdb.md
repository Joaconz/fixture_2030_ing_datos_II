# Métricas internas de Neo4j e InfluxDB (§5.2, RF2)

Hasta este cambio, de Neo4j y de InfluxDB solo había **sonda** (el puerto o `/health` responde) y la **latencia vista desde la API**. Ahora las dos tienen métricas internas en Prometheus, alertas propias y un dashboard aparte: *Fixture 2030 — Neo4j e InfluxDB* ([`grafana/dashboards/fixture2030-neo4j-influxdb.json`](../grafana/dashboards/fixture2030-neo4j-influxdb.json)).

| Base | Job de Prometheus | De dónde salen las métricas | Credencial |
|---|---|---|---|
| Neo4j (Hito 5) | `neo4j` → `neo4j-exporter:9474` | Exporter propio [`neo4j-exporter/neo4j_exporter.py`](../neo4j-exporter/neo4j_exporter.py) que consulta Neo4j por la Query API HTTP | contraseña de desarrollo de Neo4j (`NEO4J_PASSWORD`, por defecto la de `fixture2030-neo4j`) |
| InfluxDB 3 Core (Hito 8) | `influxdb` → `host.docker.internal:8181/metrics` | El `/metrics` que trae InfluxDB | token de administración, leído de un archivo que no está en el repo |

## 1. InfluxDB: `/metrics` con el token, sin commitearlo

InfluxDB 3 Core expone `/metrics` en formato Prometheus, pero **exige el token de administración** (sin token responde 401; el compose del Hito 8 solo libera `/health` y `/ping`). Core no tiene tokens de solo lectura: el único que hay es el de administración.

Cómo se resolvió sin guardar el secreto en el repo:

1. El token ya existe en la notebook: `fixture2030-influxdb/secrets/admin-token.json`, creado por `sh fixture2030-influxdb/scripts/inicializacion.sh` e **ignorado por git** (`secrets/*`).
2. Prometheus lee el archivo de credenciales **tal cual** (no entiende JSON), así que [`scripts/preparar_token_influxdb.sh`](../scripts/preparar_token_influxdb.sh) copia solo el token a `fixture2030-influxdb/secrets/prometheus-token` (también ignorado por git; el token nunca se imprime). Lo llama `iniciar_monitoreo.sh` en cada arranque.
3. El compose monta la **carpeta** `../fixture2030-influxdb/secrets` en `/etc/prometheus/influxdb-secrets` (solo lectura) y el job usa:

   ```yaml
   authorization:
     type: Bearer
     credentials_file: /etc/prometheus/influxdb-secrets/prometheus-token
   ```

   Se monta la carpeta y no el archivo: si el archivo falta, Docker no inventa un directorio en su lugar, Prometheus arranca igual y el target `influxdb` queda DOWN con el error del archivo faltante. Prometheus relee el archivo en cada scrape: si el token cambia, alcanza con volver a correr el script.

**En un clon nuevo** (desde la raíz del repositorio, con InfluxDB arriba):

```bash
sh fixture2030-influxdb/scripts/inicializacion.sh                      # crea admin-token.json (se muestra UNA sola vez, queda en secrets/)
bash fixture2030-hito-13-monitoreo/scripts/preparar_token_influxdb.sh  # prometheus-token para el job influxdb
```

Si InfluxDB ya tenía un token de administración que se perdió, el servidor no crea otro: ver [`../../fixture2030-influxdb/secrets/README.md`](../../fixture2030-influxdb/secrets/README.md).

**Permisos:** `prometheus-token` queda en 644 y no en 600 porque Prometheus corre como `nobody` dentro del contenedor y en Linux no podría leer un archivo 600 del usuario de la notebook. Es un token de laboratorio que solo sirve para la instancia local.

### Métricas de InfluxDB que se usan

| Métrica | Qué es | Dónde se usa |
|---|---|---|
| `influxdb3_write_lines_total`, `influxdb3_write_lines_rejected_total` | Líneas de line protocol aceptadas y rechazadas (contadores; aparecen tras la primera escritura) | Paneles de escritura, alerta `InfluxDBEscriturasRechazadas` |
| `influxdb3_write_bytes_total` | Bytes de line protocol recibidos | Panel "Bytes escritos por segundo" |
| `http_requests_total{method_path, status}` | Requests por endpoint y resultado (`ok`, `client_error`, `server_error`, `aborted`) | Panel de requests |
| `http_request_duration_seconds` (histograma) | Duración de cada request HTTP por endpoint | p95 de `write_lp` y `query_sql` (la que usa la API). `write_lp` ronda **1 s a propósito**: InfluxDB confirma la escritura recién después del flush del WAL (`--wal-flush-interval`, 1 s por defecto) |
| `influxdb_iox_query_log_end2end_duration_seconds` (histograma) | Duración de cada consulta dentro del motor, de punta a punta | p95 de consultas |
| `jemalloc_memstats_bytes{stat}` | Memoria del proceso según el asignador jemalloc (`alloc`, `active`, `resident`, …) | Paneles de memoria |
| `process_start_time_seconds` | Arranque del proceso | "Tiempo encendido" (detecta reinicios) |

## 2. Neo4j: exporter propio

**Por qué un exporter propio.** El endpoint de Prometheus de Neo4j (`server.metrics.prometheus.*`) es solo de Enterprise; el módulo usa Community (`neo4j:latest`, probado con 2026.09.0 community). Las alternativas que se descartaron:

- **Exporters de terceros**: no hay uno conocido y mantenido para Neo4j Community con imagen versionada; los que existen dependen justamente del endpoint de Enterprise.
- **JMX con el agente de Prometheus** (lo que se hizo con Cassandra): en 2026.09 Community los MBeans `org.neo4j:*` ya no existen (se verificó con `CALL dbms.queryJmx('org.neo4j:*')`, que devuelve 0 filas); solo quedan los de la JVM. Además obligaría a tocar el compose de Neo4j.
- **Driver Bolt de Python** (`neo4j` + `prometheus_client`): habría que construir una imagen o instalar paquetes al arrancar.

Lo más simple que funciona: un script corto, **solo biblioteca estándar**, montado en `python:3.12-slim` (la misma imagen que usan las herramientas del Hito 8). En cada scrape hace unas pocas consultas de lectura por la **Query API HTTP** (`POST /db/<base>/query/v2`, la que reemplaza a la vieja API transaccional) y responde en formato de texto de Prometheus. No escribe en el grafo, no se construye ninguna imagen y no se toca el compose de Neo4j.

### Métricas

| Métrica | Origen | Qué indica |
|---|---|---|
| `neo4j_up` | la consulta de referencia corrió (1) o falló (0) | Neo4j **ejecuta consultas**, no solo acepta conexiones. Es más que la sonda: detecta credencial rechazada o base offline con el puerto abierto |
| `neo4j_consulta_referencia_segundos{medida}` | consulta de referencia: los eventos de un partido, la lectura principal de la API | `servidor` = tiempo del motor (`resultConsumedAfter` de la Query API); `ida_y_vuelta` = medido por el exporter, incluye HTTP |
| `neo4j_nodos{etiqueta}`, `neo4j_relaciones{tipo}` | `db.labels()` / `db.relationshipTypes()` + `count` por cada una (usa el *count store*, no recorre el grafo) | Tamaño del grafo; crece con los eventos de los partidos |
| `neo4j_base_online{db}` | `SHOW DATABASES` (base `system`) | Estado de cada base de Neo4j |
| `neo4j_transacciones_abiertas` | `SHOW TRANSACTIONS`, menos la del exporter | Transacciones abiertas en el momento del scrape |
| `neo4j_heap_bytes{tipo}` | `dbms.queryJmx('java.lang:type=Memory')` | Heap usado y máximo de la JVM |
| `neo4j_info{version, edicion}` | `dbms.components()` | Versión probada |
| `neo4j_exporter_duracion_segundos` | reloj del exporter | Cuánto tarda en recolectar (≈ 0,2–1 s con el host tranquilo) |

Si la consulta de referencia falla, el exporter responde igual (`neo4j_up 0`) y escribe el motivo en su log: `docker logs fixture2030-neo4j-exporter`.

**Plazo por scrape:** Prometheus corta el scrape a los 10 s. El exporter se da 8 s en total (5 s como máximo por consulta): si Neo4j está lento, las consultas que no entran se saltean (queda en el log `sin tiempo dentro del plazo del scrape`) y responde igual. Se agregó después de ver, con la VM de Docker saturada, un scrape cortado por `context deadline exceeded` (ver la evidencia).

**Qué no da Community y no se pudo obtener:** contador de transacciones confirmadas (`lastCommittedTxn` de `SHOW DATABASES` viene `NULL` en Community), page cache, checkpoints y métricas de Bolt. Por eso no hay "transacciones por segundo": solo las abiertas en cada instante.

## 3. Alertas nuevas

En [`prometheus/reglas-o-alertas.yml`](../prometheus/reglas-o-alertas.yml), mismo formato que las demás (`severidad`, `resumen`, `impacto`, `accion`). Detalle en [`alertas_y_umbral.md`](alertas_y_umbral.md).

| Alerta | Condición | `for` | Severidad | Por qué |
|---|---|---|---|---|
| `Neo4jNoResponde` | `neo4j_up == 0` | 1 min | crítica | Igual que `BaseNoResponde` (4 scrapes), pero mira si Neo4j **ejecuta consultas**: también salta con el puerto abierto y la credencial o la base mal |
| `Neo4jConsultaLenta` | `neo4j_consulta_referencia_segundos{medida="servidor"} > 0.1` | 5 min | advertencia | En el laboratorio la consulta tarda 6–66 ms en el motor con la base caliente. 100 ms sostenidos 5 min es una degradación real, y con la API ya cargada acerca a `ApiLatenciaAlta` (150 ms). Experimental |
| `InfluxDBEscriturasRechazadas` | `increase(influxdb3_write_lines_rejected_total[5m]) > 0` | 1 min | advertencia | Una línea rechazada es una estadística que no se guardó (conflicto de tipo o línea mal formada); en operación normal el valor es 0 |

La caída de InfluxDB ya la cubren `BaseNoResponde` (sonda `/health`) y `TargetSinScrape` (si `/metrics` deja de responder o falta el token).

## 4. PromQL del dashboard nuevo

| Panel | Consulta |
|---|---|
| Neo4j: estado | `max(neo4j_up)`, `max(neo4j_base_online{db="neo4j"})` |
| Latencia de la consulta de referencia | `neo4j_consulta_referencia_segundos` |
| Tamaño del grafo | `sum(neo4j_nodos)`, `sum(neo4j_relaciones)` |
| Heap de la JVM | `neo4j_heap_bytes` |
| InfluxDB: métricas internas | `up{job="influxdb"}` |
| Líneas por segundo | `rate(influxdb3_write_lines_total{job="influxdb"}[1m])` y `..._rejected_total` |
| Requests por endpoint | `sum by (method_path, status) (rate(http_requests_total{job="influxdb", method_path!="GET /metrics"}[1m])) > 0` |
| Latencia p95 de escritura y consulta | `histogram_quantile(0.95, sum by (le, method_path) (rate(http_request_duration_seconds_bucket{job="influxdb", method_path=~".*(write\|query).*"}[5m])))` |
| p95 de consultas en el motor | `histogram_quantile(0.95, sum by (le) (rate(influxdb_iox_query_log_end2end_duration_seconds_bucket{job="influxdb"}[5m])))` |
| Alertas de Neo4j e InfluxDB | `ALERTS{alertname=~"Neo4j.*\|InfluxDB.*"} or ALERTS{base=~"neo4j\|influxdb"} or ALERTS{job=~"neo4j\|influxdb"}` |

## 5. Verificación

Evidencia en [`../evidencia/metricas_neo4j_influxdb_20261110-204100.md`](../evidencia/metricas_neo4j_influxdb_20261110-204100.md): targets nuevos UP, valores de las métricas, alertas forzadas (`docker stop` de Neo4j y una línea rechazada en InfluxDB) y el dashboard cargado con datos, en un stack aislado (proyecto de compose y puertos propios).
