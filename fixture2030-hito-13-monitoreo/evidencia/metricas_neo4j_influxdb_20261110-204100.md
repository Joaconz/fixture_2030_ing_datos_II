# Métricas internas de Neo4j e InfluxDB — verificación del 10/11/2026

**Fecha:** 10/11/2026, 20:31–21:06 UTC (17:31–18:06 hora local). **Código:** commit `4219cde` (rama `claude/monitoreo-exporters-neo4j-influx-d756fa`). **Docker Desktop 28.3.3** en Windows 11 (VM de 8 GB, 12 CPU).

Qué se verifica: los targets nuevos (`neo4j`, `influxdb`) en UP, que las métricas tienen valores, que las 8 reglas se evalúan, que las dos alertas nuevas que se pueden provocar disparan, y que el dashboard *Fixture 2030 — Neo4j e InfluxDB* carga con datos. Doc: [`../docs/metricas_neo4j_e_influxdb.md`](../docs/metricas_neo4j_e_influxdb.md).

## Cómo se armó la prueba

En la misma notebook otra sesión tenía levantado el mismo stack, así que todo corrió **aislado**: proyectos de compose propios, nombres de contenedor `h13exp-*`, volúmenes `h13exp_*` y puertos propios. Se usaron los compose del repo **sin modificarlos**, con un override por fuera del repo que solo cambia nombres, puertos y volúmenes:

```bash
# Neo4j (Hito 5) en 17474/17687 y carga del subgrafo
(cd fixture2030-neo4j && NEO4J_HTTP_PORT=17474 NEO4J_BOLT_PORT=17687 docker compose -p h13exp-neo4j -f docker-compose.yml -f <override> up -d)
docker exec h13exp-neo4j cypher-shell -u neo4j -p <dev> -f /queries/estructura.cypher
docker exec h13exp-neo4j cypher-shell -u neo4j -p <dev> -f /queries/carga.cypher
# InfluxDB 3 Core (Hito 8) en 18181, datos nuevos, y su token como en un clon nuevo
(cd fixture2030-influxdb && INFLUX_PORT=18181 docker compose -p h13exp-influxdb -f docker-compose.yml -f <override> up -d)
(cd fixture2030-influxdb && COMPOSE_PROJECT_NAME=h13exp-influxdb sh scripts/autorizacion_local.sh)   # -> secrets/admin-token.json
bash fixture2030-hito-13-monitoreo/scripts/preparar_token_influxdb.sh                              # -> secrets/prometheus-token
# Monitoreo (Prometheus 29090, Grafana 23000, exporter de Neo4j 29474)
(cd fixture2030-hito-13-monitoreo && docker compose -p h13exp -f docker-compose.yml -f <override> up -d)
```

Únicas diferencias con el uso normal: Prometheus montó una copia de `prometheus.yml` con `7474→17474` y `8181→18181` (el resto idéntico) y el exporter apuntó a `http://host.docker.internal:17474`. Tráfico de InfluxDB generado con un bucle (20 líneas de line protocol + 1 consulta SQL cada 2 s, base `prueba_monitoreo`). La API, Mongo, Redis y Cassandra eran los de la otra sesión: solo se leyeron.

**Diferencias entre lo probado y el commit:** (1) el plazo de 8 s del exporter se agregó **después** de la prueba con Prometheus (ver §6) y se probó corriendo el exporter directamente contra el Neo4j de prueba; (2) los colores de los paneles *stat* y la línea de umbral del dashboard se ajustaron durante la prueba (Grafana recargó el archivo solo).

## 1. Targets — `PROM_URL=http://localhost:29090 bash scripts/verificar_targets.sh` (20:41:38 UTC)

| job | base / capa | instance | estado | último scrape | error |
|---|---|---|---|---|---|
| cassandra | cassandra | host.docker.internal:7070 | DOWN | 2026-11-10T20:41:25 | `connection refused`: la Cassandra de la otra sesión no tiene el agente JMX (no es de este cambio) |
| fixture-api | aplicacion | host.docker.internal:8000 | UP | 2026-11-10T20:41:26 |  |
| **influxdb** | influxdb | host.docker.internal:18181 | **UP** | 2026-11-10T20:41:25 |  |
| mongodb | mongodb | mongodb-exporter:9216 | UP | 2026-11-10T20:41:29 |  |
| **neo4j** | neo4j | neo4j-exporter:9474 | **UP** | 2026-11-10T20:41:35 |  |
| node-exporter | - | node-exporter:9100 | UP | 2026-11-10T20:41:25 |  |
| prometheus | - | prometheus:9090 | UP | 2026-11-10T20:41:24 |  |
| redis | redis | redis-exporter:9121 | UP | 2026-11-10T20:41:25 |  |
| salud-bases | cassandra | host.docker.internal:9042 | UP | 2026-11-10T20:41:35 |  |
| salud-bases | influxdb | http://host.docker.internal:18181/health | UP | 2026-11-10T20:41:38 |  |
| salud-bases | mongodb | host.docker.internal:27017 | UP | 2026-11-10T20:41:29 |  |
| salud-bases | neo4j | http://host.docker.internal:17474 | UP | 2026-11-10T20:41:26 |  |
| salud-bases | redis | host.docker.internal:6379 | UP | 2026-11-10T20:41:23 |  |

13 targets: los 11 de antes más `neo4j` e `influxdb`, los dos nuevos en UP. El script imprimió `Commit: f8b2140` porque el cambio todavía no estaba commiteado; el código probado es el de `4219cde` salvo lo dicho arriba. Antes, a mano: `curl http://127.0.0.1:18181/metrics` sin token → **401**; con el token → 200.

## 2. Valores de las métricas nuevas (consultas a `/api/v1/query`, 20:46 UTC)

| Consulta | Series → valor |
|---|---|
| `neo4j_up` | - → 1 |
| `neo4j_consulta_referencia_segundos` | medida=servidor → 0.006<br>medida=ida_y_vuelta → 0.018136 |
| `neo4j_nodos` | etiqueta=Equipo → 64<br>etiqueta=Jugador → 1282<br>etiqueta=Partido → 112<br>etiqueta=Sede → 16<br>etiqueta=Evento → 1152<br>etiqueta=Grupo → 16<br>etiqueta=TipoEvento → 12 |
| `neo4j_relaciones` | tipo=PARTICIPA_EN → 224<br>tipo=PERTENECE_A → 64<br>tipo=JUEGA_EN → 1282<br>tipo=SE_JUEGA_EN → 112<br>tipo=CORRESPONDE_A → 96<br>tipo=OCURRE_EN → 1152<br>tipo=ES_DE_TIPO → 1152<br>tipo=PROTAGONIZADO_POR → 1152<br>tipo=SIGUIENTE_EVENTO → 1056<br>tipo=CAUSA_DE → 512 |
| `neo4j_base_online` | db=neo4j → 1<br>db=system → 1 |
| `neo4j_transacciones_abiertas` | - → 0 |
| `neo4j_heap_bytes` | tipo=usado → 354655984<br>tipo=maximo → 1073741824 |
| `neo4j_info` | edicion=community version=2026.09.0 → 1 |
| `neo4j_exporter_duracion_segundos` | - → 0.174985 |
| `up{job="influxdb"}` | - → 1 |
| `influxdb3_write_lines_total` | - → 1282 |
| `influxdb3_write_lines_rejected_total` | - → 1 |
| `rate(influxdb3_write_lines_total[1m])` | - → 6.6674074897210795 |
| `sum by (method_path, status) (rate(http_requests_total{job="influxdb", method_path!="GET /metrics"}[1m])) > 0` | method_path=GET /health status=ok → 0.2666962995888432<br>method_path=POST /api/v3/write_lp status=ok → 0.333370374486054<br>method_path=POST /api/v3/query_sql status=ok → 0.333370374486054 |
| `histogram_quantile(0.95, sum by (le, method_path) (rate(http_request_duration_seconds_bucket{job="influxdb", method_path=~".*(write&#124;query).*"}[5m])))` | method_path=GET /api/v3/query_sql → NaN<br>method_path=POST /api/v3/write_lp → 0.9814224055604216<br>method_path=POST /api/v3/query_sql → 0.03749999999999995 |
| `histogram_quantile(0.95, sum by (le) (rate(influxdb_iox_query_log_end2end_duration_seconds_bucket{job="influxdb"}[5m])))` | - → 0.15600403794161158 |
| `jemalloc_memstats_bytes{job="influxdb", stat=~"allocated&#124;resident&#124;active"}` | stat=active → 21471232<br>stat=resident → 41652224 |

Lectura: el grafo cargado del Hito 5 (2654 nodos, 6802 relaciones), la consulta de referencia en 6 ms en el motor (18 ms ida y vuelta), Neo4j 2026.09.0 community. InfluxDB recibiendo ~6,7 líneas/s, con 1 línea rechazada (la de la prueba de §4). El p95 de `write_lp` cerca de 1 s es el comportamiento normal de InfluxDB 3: confirma la escritura después del flush del WAL, que por defecto es cada 1 s (`--wal-flush-interval`). `GET /api/v3/query_sql` da `NaN` porque no recibió requests (la consulta fue por POST).

## 3. Reglas evaluadas (`GET /api/v1/rules`, 20:46 UTC)

| Grupo | Regla | health | estado | última evaluación (UTC) |
|---|---|---|---|---|
| fixture2030-api | ApiErroresAltos | ok | inactive | 2026-11-10T20:46:27 |
| fixture2030-api | ApiLatenciaAlta | ok | inactive | 2026-11-10T20:46:27 |
| fixture2030-cassandra | CassandraEscriturasEncoladas | ok | inactive | 2026-11-10T20:46:34 |
| fixture2030-disponibilidad | BaseNoResponde | ok | inactive | 2026-11-10T20:46:32 |
| fixture2030-disponibilidad | TargetSinScrape | ok | firing | 2026-11-10T20:46:32 |
| fixture2030-influxdb | InfluxDBEscriturasRechazadas | ok | firing | 2026-11-10T20:46:32 |
| fixture2030-neo4j | Neo4jNoResponde | ok | inactive | 2026-11-10T20:46:34 |
| fixture2030-neo4j | Neo4jConsultaLenta | ok | inactive | 2026-11-10T20:46:34 |

Las 8 reglas con `health = ok` (se evalúan sin error). `TargetSinScrape` en firing es por la Cassandra sin agente de la otra sesión; `InfluxDBEscriturasRechazadas` por la prueba de §4.

## 4. Alertas forzadas — línea rechazada en InfluxDB y `docker stop` de Neo4j

Comando: un script de prueba (fuera del repo) que manda una línea con conflicto de tipo a InfluxDB, hace `docker stop h13exp-neo4j` (el Neo4j **de la prueba**, no el de la otra sesión), consulta `ALERTS` cada 5 s hasta ver las dos alertas en firing, hace `docker start` y espera la resolución.

| hora | evento |
|---|---|
| 20:42:47 | antes: neo4j_up = (vacío), rechazadas = (vacío) |
| 20:43:25 | POST write_lp con `tipo=5i` (el campo es string): {"error":"partial write of line protocol occurred","data":[{"error_message":"invalid column type for column 'tipo', expected iox::column_type::field::string, got iox::column_type::field::integer","line_number":1,"original_line":"evento,partido=P9 ti"}]} HTTP 400 |
| 20:43:37 | `docker stop h13exp-neo4j` |
| 20:43:37 | Prometheus ve neo4j_up = 0 |
| 20:44:49 | **InfluxDBEscriturasRechazadas firing**: alertname=InfluxDBEscriturasRechazadas alertstate=firing base=influxdb instance=host.docker.internal:18181 job=influxdb severidad=advertencia => 1 |
| 20:45:05 | **Neo4jNoResponde firing**: alertname=Neo4jNoResponde alertstate=firing base=neo4j instance=neo4j-exporter:9474 job=neo4j severidad=critica => 1 |
| 20:45:05 | ALERTS con todo en firing: alertname=TargetSinScrape alertstate=firing base=cassandra instance=host.docker.internal:7070 job=cassandra severidad=advertencia => 1 ; alertname=InfluxDBEscriturasRechazadas alertstate=firing base=influxdb instance=host.docker.internal:18181 job=influxdb severidad=advertencia => 1 ; alertname=BaseNoResponde alertstate=firing base=neo4j instance=http://host.docker.internal:17474 job=salud-bases severidad=critica => 1 ; alertname=Neo4jNoResponde alertstate=firing base=neo4j instance=neo4j-exporter:9474 job=neo4j severidad=critica => 1 |
| 20:45:06 | logs del exporter: [neo4j-exporter] consulta de referencia: <urlopen error [Errno 111] Connection refused> |
| 20:45:07 | `docker start h13exp-neo4j` |
| 20:45:44 | neo4j_up = 1 otra vez |
| 20:46:05 | Neo4jNoResponde resuelta (ya no está en ALERTS) |
| 20:46:05 | ALERTS al final: alertname=Neo4jConsultaLenta alertstate=pending base=neo4j instance=neo4j-exporter:9474 job=neo4j medida=servidor severidad=advertencia => 1 ; alertname=TargetSinScrape alertstate=firing base=cassandra instance=host.docker.internal:7070 job=cassandra severidad=advertencia => 1 ; alertname=InfluxDBEscriturasRechazadas alertstate=firing base=influxdb instance=host.docker.internal:18181 job=influxdb severidad=advertencia => 1 ; alertname=TargetSinScrape alertstate=firing capa=aplicacion instance=host.docker.internal:8000 job=fixture-api severidad=advertencia => 1 |

Lectura:

- **`InfluxDBEscriturasRechazadas`**: InfluxDB respondió **HTTP 400** (`invalid column type for column 'tipo'`) y la alerta pasó a **firing 84 s** después (ventana de 5 min + `for` de 1 min + scrape y evaluación cada 15 s).
- **`Neo4jNoResponde`**: **firing a los 88 s** del `docker stop` (`for` de 1 min). Junto con ella saltó `BaseNoResponde{base="neo4j"}` (sonda). El log del exporter da el motivo: `Connection refused`. Con `docker start`, `neo4j_up` volvió a 1 a los 37 s (lo que tarda Neo4j en arrancar) y la alerta se resolvió a los 58 s.
- **`Neo4jConsultaLenta`** quedó en *pending* justo después del reinicio (primera consulta con la caché fría, ~2 s) y a las 20:46:34 ya estaba *inactive*: el `for` de 5 min evita el falso positivo. No se forzó en firing.
- La primera fila dice `(vacío)` porque a las 20:42–20:43 la VM de Docker se trabó (ver §6): Prometheus no tenía muestras frescas.

## 5. Dashboard — Grafana (`GET /api/dashboards/uid/fixture2030-neo4j-influxdb` y `POST /api/ds/query` por panel, 20:47 UTC)

Dashboard: **Fixture 2030 — Neo4j e InfluxDB** (uid `fixture2030-neo4j-influxdb`), carpeta *Fixture 2030*, provisionado: True, archivo `fixture2030-neo4j-influxdb.json`

| Panel | Consultas | Series | Puntos con valor (últimos 15 min) |
|---|---|---|---|
| Neo4j: estado | 2 | 2 | 32 |
| Tamaño del grafo | 2 | 2 | 24 |
| Versión | 1 | 1 | 12 |
| Alertas de Neo4j e InfluxDB | 1 | 1 | 1 |
| Latencia de la consulta de referencia | 1 | 2 | 24 |
| Transacciones abiertas | 1 | 1 | 12 |
| Heap de la JVM | 1 | 2 | 24 |
| Nodos por etiqueta | 1 | 7 | 84 |
| Relaciones por tipo | 1 | 10 | 120 |
| Duración de la recolección del exporter | 2 | 2 | 45 |
| InfluxDB: métricas internas | 1 | 1 | 25 |
| Tiempo encendido | 1 | 1 | 21 |
| Líneas escritas (total) | 2 | 2 | 42 |
| Memoria del proceso | 1 | 1 | 21 |
| Líneas por segundo (escritura) | 2 | 2 | 42 |
| Requests HTTP por segundo, por endpoint y resultado | 1 | 4 | 53 |
| Latencia p95 de escritura y consulta | 1 | 3 | 29 |
| Consultas: p95 de punta a punta en el motor | 1 | 1 | 15 |
| Bytes escritos por segundo | 1 | 1 | 21 |
| Memoria (jemalloc) | 1 | 3 | 63 |

Los 20 paneles (más las 2 filas) devuelven series con valores a través del datasource de Grafana. La tabla de alertas tenía en ese momento la alerta de InfluxDB. Capturas (21:01 UTC, rango de 20 min; los huecos son la caída de Neo4j de §4 y las trabas de la VM de §6):

- [`dashboards/neo4j_influxdb_fila_neo4j.jpg`](dashboards/neo4j_influxdb_fila_neo4j.jpg): fila Neo4j (estado OK, 2654 nodos / 6802 relaciones, 2026.09.0 community, latencia con la línea de umbral, heap, conteos por etiqueta y tipo).
- [`dashboards/neo4j_influxdb_fila_influxdb.jpg`](dashboards/neo4j_influxdb_fila_influxdb.jpg): fila InfluxDB (`/metrics` OK, 29,7 min encendido, 3002 líneas aceptadas y 2 rechazadas).

## 6. Lo que no salió limpio

- **La VM de Docker se saturó** (8 GB compartidos con el stack de la otra sesión, réplicas de MongoDB y otros proyectos). Entre 20:42:20 y 20:43:20 Prometheus no pudo scrapear **ningún** target, ni a sí mismo (`up{job="prometheus"} = 0`); a las 20:53 y a las 21:03 el motor de Docker devolvió `500 Internal Server Error` y Grafana/Prometheus tardaban más de 30 s. Por eso las capturas son de la vista de la pantalla y no del dashboard entero.
- **Scrape de Neo4j cortado.** En la última corrida (`verificar_targets.sh`, 21:03:17 UTC), con Neo4j tardando más de 5 s por consulta, el target `neo4j` quedó DOWN con `context deadline exceeded`: el exporter hacía sus 7 consultas con 5 s de timeout cada una y se pasaba de los 10 s del scrape. Corregido en el commit con un **plazo total de 8 s** (las consultas que no entran se saltean y el exporter responde igual). Verificado corriendo el exporter contra el Neo4j de prueba: con Neo4j saturado respondió `neo4j_up 0` en 5,9 s; con un host inalcanzable, en 5,1 s; con Neo4j sano, `neo4j_up 1` y todas las métricas en 0,7 s; con el plazo forzado a 0,8 s, `neo4j_up 1`, conteos y las demás salteadas con `sin tiempo dentro del plazo del scrape`. **No** se repitió el scrape desde Prometheus con el plazo nuevo (el motor de Docker no respondía).

Tabla de esa última corrida (21:03:17 UTC):

| job | base / capa | instance | estado | último scrape | error |
|---|---|---|---|---|---|
| cassandra | cassandra | host.docker.internal:7070 | DOWN | 2026-11-10T21:03:08 | Get "http://host.docker.internal:7070/metrics": dial tcp 192.168.65.254:7070: connect: con |
| fixture-api | aplicacion | host.docker.internal:8000 | UP | 2026-11-10T21:03:09 |  |
| influxdb | influxdb | host.docker.internal:18181 | UP | 2026-11-10T21:03:08 |  |
| mongodb | mongodb | mongodb-exporter:9216 | UP | 2026-11-10T21:02:58 |  |
| neo4j | neo4j | neo4j-exporter:9474 | DOWN | 2026-11-10T21:03:04 | Get "http://neo4j-exporter:9474/metrics": context deadline exceeded |
| node-exporter | - | node-exporter:9100 | UP | 2026-11-10T21:03:09 |  |
| prometheus | - | prometheus:9090 | UP | 2026-11-10T21:03:08 |  |
| redis | redis | redis-exporter:9121 | UP | 2026-11-10T21:03:08 |  |
| salud-bases | cassandra | host.docker.internal:9042 | UP | 2026-11-10T21:03:03 |  |
| salud-bases | influxdb | http://host.docker.internal:18181/health | UP | 2026-11-10T21:03:06 |  |
| salud-bases | mongodb | host.docker.internal:27017 | UP | 2026-11-10T21:03:13 |  |
| salud-bases | neo4j | http://host.docker.internal:17474 | UP | 2026-11-10T21:03:10 |  |
| salud-bases | redis | host.docker.internal:6379 | UP | 2026-11-10T21:03:07 |  |

## 7. Limpieza

`docker compose down` de los tres proyectos de prueba (`h13exp`, `h13exp-neo4j`, `h13exp-influxdb`) y `docker volume rm` de los seis volúmenes `h13exp_*`. Se borraron también el `admin-token.json` y el `prometheus-token` de la instancia de prueba. No se tocaron contenedores ni volúmenes `fixture2030-*` / `f30-*` de otras sesiones.
