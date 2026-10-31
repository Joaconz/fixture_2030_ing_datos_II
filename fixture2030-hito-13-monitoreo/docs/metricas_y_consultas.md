# Métricas y consultas PromQL (§5.2, RF8)

## 1. Configuración de Prometheus

| Aspecto | Valor | Dónde |
|---|---|---|
| Intervalo de scraping | 15 s para todos los jobs (`scrape_interval`) | [`prometheus.yml`](../prometheus.yml) |
| Intervalo de evaluación de reglas | 15 s (`evaluation_interval`) | idem |
| Retención | 15 días (`--storage.tsdb.retention.time=15d`, explícita) | [`docker-compose.yml`](../docker-compose.yml) |
| Persistencia | volumen nombrado `fixture2030_prometheus_data` → `~/docker/data/prometheus` | idem |
| Reglas | [`prometheus/reglas-o-alertas.yml`](../prometheus/reglas-o-alertas.yml) (5 alertas) | idem |
| Recarga sin reiniciar | `curl -X POST http://localhost:9090/-/reload` (`--web.enable-lifecycle`) | idem |

Targets, exporters y etiquetas: ver la tabla "Relación job → componente" en [`inventario_de_componentes.md`](inventario_de_componentes.md).

### Validar que un target está UP

1. `bash scripts/verificar_targets.sh` (sale con código 1 si hay alguno DOWN; `--guardar` deja la tabla en `evidencia/`).
2. O en la UI: http://localhost:9090/targets.
3. O la consulta `up` en http://localhost:9090/graph: 1 por target leído en el último scrape.

### Investigar un target DOWN

| Paso | Qué mirar | Qué indica |
|---|---|---|
| 1 | Columna **error** de `/targets` (o de `verificar_targets.sh`) | `connection refused` = nada escucha en ese puerto; `context deadline exceeded` = responde lento; `no such host` = nombre mal escrito |
| 2 | `docker ps -a --filter name=fixture2030` | ¿El contenedor está corriendo? ¿Se reinicia en bucle? |
| 3 | `docker logs <contenedor> --tail 50` | Error de arranque, credenciales, memoria |
| 4 | `curl http://localhost:<puerto>/metrics` desde la notebook | Si responde acá pero no desde Prometheus, el problema es la red (`host.docker.internal`) |
| 5 | Para la API: `curl localhost:8000/health/dependencias` | Qué base ve caída la API y por qué motivo (`conexion`, `timeout`, `autenticacion`, `contexto`) |
| 6 | Para `cassandra`: ¿se levantó con el override? `docker inspect fixture2030-cassandra` y buscar `JVM_EXTRA_OPTS` | Sin el agente no hay puerto 7070 |

## 2. Consultas PromQL del sistema (RF8)

Las consultas que usan el dashboard y las alertas. "Período" es la ventana del `rate()` o del percentil; el rango del gráfico lo elige el usuario en Grafana (por defecto, últimos 30 minutos).

| # | Consulta | Qué mide | Unidad | Período | Tipo (RNF3) |
|---|---|---|---|---|---|
| Q1 | `max by (base) (probe_success{job="salud-bases"})` | Si cada base acepta conexiones (TCP) o responde su endpoint de salud (HTTP) | 0 / 1 | instantáneo (último scrape, 15 s) | Sonda |
| Q2 | `sum by (status) (rate(fixture2030_http_requests_total[1m]))` | Requests por segundo que atiende la API, separadas por status HTTP | req/s | 1 minuto | Directo |
| Q3 | `histogram_quantile(0.95, sum by (le, ruta) (rate(fixture2030_http_request_duration_seconds_bucket[5m])))` | Tiempo bajo el cual responde el 95 % de las requests de cada ruta, medido en la API (incluye la espera a las bases) | segundos | 5 minutos | Directo |
| Q4 | `100 * sum(rate(fixture2030_http_requests_total{status=~"5.."}[5m])) / clamp_min(sum(rate(fixture2030_http_requests_total[5m])), 1e-9)` | Porcentaje de respuestas 5xx sobre el total | % | 5 minutos | Directo |
| Q5 | `histogram_quantile(0.95, sum by (le, dependencia) (rate(fixture2030_dependencia_duration_seconds_bucket[5m])))` | p95 del tiempo de cada llamada de la API a cada base: **compara bases entre sí** (RF7) | segundos | 5 minutos | Inferido (medido en el adaptador, no en la base) |
| Q6 | `sum by (dependencia, resultado) (rate(fixture2030_dependencia_duration_seconds_count[1m]))` | Llamadas por segundo a cada base, por resultado (`ok`, `no_disponible`, `timeout`, `dominio:*`) | llamadas/s | 1 minuto | Directo |
| Q7 | `cassandra_clientrequest_latency_seconds{operacion=~"Read\|Write",quantile="0.99"}` | p99 de lecturas y escrituras vistas por el coordinador de Cassandra (sin red ni API) | segundos | la calcula Cassandra con un reservorio que da más peso a lo reciente (no es un `rate` de Prometheus): reacciona en minutos, no al instante | Exporter |
| Q8 | `rate(cassandra_clientrequest_total{operacion=~"Read\|Write"}[1m])` | Peticiones por segundo que recibe Cassandra | req/s | 1 minuto | Exporter |
| Q9 | `cassandra_threadpool_pendingtasks{pool="MutationStage"}` | Escrituras esperando en cola dentro de Cassandra | tareas | instantáneo | Exporter |
| Q10 | `rate(redis_keyspace_hits_total[1m]) / clamp_min(rate(redis_keyspace_hits_total[1m]) + rate(redis_keyspace_misses_total[1m]), 1e-9)` | Proporción de lecturas de Redis que encontraron la clave | 0–1 | 1 minuto | Exporter |
| Q11 | `sum by (type) (rate(mongodb_op_counters_total[1m]))` | Operaciones por segundo en MongoDB, por tipo | ops/s | 1 minuto | Exporter |

### Cómo se leen juntas: ¿API o base? (§6.5)

- **Q3 sube y Q5 no:** el tiempo extra está en la API (CPU del proceso, serialización, validación). La base responde igual de rápido.
- **Q3 y Q5 suben juntas para una `dependencia`:** el cuello está en esa base. Para Cassandra se confirma con Q7 (latencia interna) y Q9 (cola de escrituras).
- **Q5 alta pero Q7 baja (Cassandra):** el motor responde rápido y el tiempo se pierde entre el nodo y el código que espera la respuesta: red, pool de conexiones o **la propia API saturada** (la respuesta llega, pero el *event loop* de Python está ocupado y tarda en atenderla). Para separarlos, mirar la CPU del proceso de la API: es lo que pasó en la [carga observada](../evidencia/carga_observada_20261030-212441.md) (Cassandra p99 1,1 ms por dentro, 17 / 44 ms p50 / p95 desde la API, API al 97 % de CPU).
- **Q4 sube:** Q6 dice qué base pasó a `no_disponible` o `timeout`; Q1 confirma si la base está caída o solo lenta.

## 3. Valores observados en el laboratorio

Mediciones de esta notebook (Apple Silicon, Docker Desktop), no de producción (RNF8). **Prometheus y k6 no dan el mismo p95:** Prometheus lo estima interpolando dentro del bucket del histograma (entre 50 y 100 ms acá), k6 lo calcula con cada request. Para comparar entre sí, usar siempre la misma fuente.

| Observación | Valor | Fuente |
|---|---|---|
| Lecturas de Cassandra con carga de solo lectura (`cqlsh -f`, 3.000 SELECT por ronda) | ~400 req/s; p99 de lectura 4,8 ms en frío → ~0,3 ms en caliente; 0 errores | Q7/Q8 en Grafana durante la prueba, 30/10/2026 |
| p95 de cada base vista desde la API, ~250 req/s de GET mixtos | ≤ 5 ms para Cassandra, MongoDB y Redis (bucket más bajo del histograma) | Q5, 30/10/2026 |
| Detección de una base caída | 10 s desde `docker stop` hasta `probe_success = 0`; alerta en firing a los 72 s | [`evidencia/prueba_de_falla_redis_20261030-211553.md`](../evidencia/prueba_de_falla_redis_20261030-211553.md) |
| **Carga de lectura observada** (k6, 20 usuarios, solo GET de comentarios del partido caliente, 90 s) | 399 req/s, 0 errores. API p50 / p95 = 42 / 91 ms (Prometheus) y 45 / 71 ms (k6). Cassandra desde la API 17 / 44 ms; Cassandra por dentro p99 1,1 ms. CPU de la API 97 % (máx 100 %), Cassandra 90 % de un núcleo. 5 llamadas a Cassandra por GET | [`evidencia/carga_observada_20261030-212441.md`](../evidencia/carga_observada_20261030-212441.md) |
| Latencia de la API bajo carga (Hito 12) | p95 82,4 ms, p99 100,6 ms, 364 req/s, 0 errores (k6, 20 usuarios) | [`../../fixture2030-hito12-carga/docs/linea_base.md`](../../fixture2030-hito12-carga/docs/linea_base.md) — medido con k6, **no** con Prometheus |
