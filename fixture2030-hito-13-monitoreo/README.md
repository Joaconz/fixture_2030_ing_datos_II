# Hito 13 · Monitoreo con Prometheus + Grafana

Stack de observabilidad de la Clase 14: Prometheus recolecta (modelo *pull*), Grafana visualiza y los exporters traducen las métricas del host y de las bases a formato Prometheus.

```
fixture2030-hito-13-monitoreo/
├── docker-compose.yml                       # prometheus, grafana y exporters
├── prometheus.yml                           # targets que scrapea Prometheus
├── blackbox.yml                             # módulos de sonda (TCP / HTTP) del blackbox-exporter
└── grafana/
    ├── provisioning/
    │   ├── datasources/prometheus.yml       # datasource "Prometheus" (uid fijo)
    │   └── dashboards/fixture2030.yml       # carga los .json de grafana/dashboards
    └── dashboards/fixture2030-monitoreo.json
```

## Levantar

```bash
mkdir -p ~/docker/data/prometheus ~/docker/data/grafana
docker compose up -d
```

| Servicio | URL | Notas |
|---|---|---|
| Grafana | http://localhost:3000 | `admin` / `fixture2030` (desarrollo; se pisan con `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD` en un `.env`) |
| Prometheus | http://localhost:9090 | *Status → Targets* muestra el estado de cada scrape |
| node-exporter | http://localhost:9100/metrics | métricas del host |
| mongodb-exporter | http://localhost:9216/metrics | métricas de MongoDB |
| redis-exporter | http://localhost:9121/metrics | métricas de Redis |
| blackbox-exporter | http://localhost:9115 | sondas de disponibilidad de las cinco bases |

Grafana arranca con todo configurado por *provisioning*: el datasource Prometheus y el dashboard **Fixture 2030 — Monitoreo** (página de inicio, carpeta *Fixture 2030*). No hay que configurar nada desde la UI.

## Persistencia

Igual que Redis, Cassandra, InfluxDB e IRIS: **volúmenes nombrados** (`fixture2030_prometheus_data`, `fixture2030_grafana_data`) respaldados por `~/docker/data/prometheus` y `~/docker/data/grafana`. Las carpetas tienen que existir antes del primer `up`. `docker compose down` conserva los datos.

## Fuentes de métricas

| Job | Exporter | Qué mide |
|---|---|---|
| `prometheus` | el propio Prometheus | su TSDB y sus scrapes |
| `node-exporter` | `prom/node-exporter` | CPU, memoria, disco y red del host |
| `mongodb` | `percona/mongodb_exporter` | operaciones por tipo, conexiones (`mongodb_up`) |
| `redis` | `oliver006/redis_exporter` | comandos/s, hits y misses de la caché, memoria, clientes (`redis_up`) |
| `cassandra` | `jmx_prometheus_javaagent` dentro de la JVM de Cassandra (`host.docker.internal:7070`) | latencia p50/p99 y peticiones/s de lecturas y escrituras, timeouts / unavailables / fallas, disco por tabla, tareas pendientes |
| `salud-bases` | `prom/blackbox-exporter` | `probe_success` por base: TCP a MongoDB (27017), Redis (6379) y Cassandra (9042); HTTP a Neo4j (7474) e InfluxDB (`/health`, 8181) |

**Cómo llegan a las bases.** Cada módulo (Hitos 4 a 8) tiene su propio compose y su propia red, y se levanta por separado. Los exporters no se suman a esas redes: llegan por los puertos publicados en la notebook a través de `host.docker.internal`. Así este stack arranca aunque las bases estén apagadas (se ven como CAÍDA) y no hubo que tocar los compose de otros hitos. Está probado en Docker Desktop (macOS); en Linux, Redis e InfluxDB publican solo en `127.0.0.1` y no son alcanzables desde `host-gateway`.

**Cassandra necesita su override.** Cassandra publica métricas solo por JMX y la imagen oficial deja JMX escuchando dentro del contenedor. En lugar de abrir JMX remoto, el override [`fixture2030-cassandra/docker-compose.monitoreo.yml`](../fixture2030-cassandra/docker-compose.monitoreo.yml) carga el agente oficial de Prometheus en la JVM, que expone `/metrics` en el puerto 7070. Sin el override, Cassandra funciona igual que en el Hito 6 y el target `cassandra` queda DOWN (la sonda de `salud-bases` sigue funcionando):

```bash
cd ../fixture2030-cassandra
docker compose -f docker-compose.yml -f docker-compose.monitoreo.yml up -d
```

**Lo que no tiene métricas internas (solo disponibilidad):**
- **Neo4j:** el endpoint Prometheus (`server.metrics.prometheus.enabled`) es solo de Enterprise; usamos Community.
- **InfluxDB 3 Core:** tiene `/metrics` propio, pero exige el token de administración.

## Dashboard

- **Estado de salud:** `up` por target (OK / CAÍDO), cantidad de targets arriba y **estado de salud por base** (`probe_success`, OK / CAÍDA). Cada target nuevo de `prometheus.yml` aparece solo.
- **MongoDB:** operaciones por segundo por tipo y conexiones abiertas.
- **Cassandra:** latencia p50/p99 (umbral experimental de 100 ms marcado en rojo), peticiones por segundo, errores, disco por tabla y tareas pendientes.
- **Redis:** comandos por segundo, hit ratio de la caché, memoria y clientes conectados.
- **Host:** CPU, memoria, disco, red y carga (node-exporter).
- **Prometheus:** duración de cada scrape y muestras ingeridas por segundo.

## Agregar targets

Editar `prometheus.yml` y recargar sin reiniciar:

```bash
curl -X POST http://localhost:9090/-/reload
```

La API del Hito 10 todavía no expone `/metrics`; el job `fixture-api` (`host.docker.internal:8000`) queda comentado hasta que lo haga.
