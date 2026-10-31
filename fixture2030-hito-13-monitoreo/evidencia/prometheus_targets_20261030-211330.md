# Targets de Prometheus — 2026-10-31T00:13:30Z

Fuente: `GET http://localhost:9090/api/v1/targets` y `probe_success{job="salud-bases"}`. Commit: `074851c`.

## Targets (lo que Prometheus pudo leer)

| job | base / capa | instance | estado | último scrape | error |
|---|---|---|---|---|---|
| cassandra | cassandra | host.docker.internal:7070 | UP | 2026-10-31T00:13:26 |  |
| fixture-api | aplicacion | host.docker.internal:8000 | UP | 2026-10-31T00:13:23 |  |
| mongodb | mongodb | mongodb-exporter:9216 | UP | 2026-10-31T00:13:26 |  |
| node-exporter | - | node-exporter:9100 | UP | 2026-10-31T00:13:26 |  |
| prometheus | - | prometheus:9090 | UP | 2026-10-31T00:13:23 |  |
| redis | redis | redis-exporter:9121 | UP | 2026-10-31T00:13:23 |  |
| salud-bases | cassandra | host.docker.internal:9042 | UP | 2026-10-31T00:13:17 |  |
| salud-bases | influxdb | http://host.docker.internal:8181/health | UP | 2026-10-31T00:13:18 |  |
| salud-bases | mongodb | host.docker.internal:27017 | UP | 2026-10-31T00:13:22 |  |
| salud-bases | neo4j | http://host.docker.internal:7474 | UP | 2026-10-31T00:13:17 |  |
| salud-bases | redis | host.docker.internal:6379 | UP | 2026-10-31T00:13:15 |  |

## Disponibilidad por base (sonda del blackbox-exporter)

| base | probe_success |
|---|---|
| mongodb | 1 |
| redis | 1 |
| cassandra | 1 |
| neo4j | 1 |
| influxdb | 1 |

## Alertas activas

- alertname=ApiErroresAltos alertstate=pending severidad=critica 1
