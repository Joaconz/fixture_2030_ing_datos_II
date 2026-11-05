# Prueba de falla controlada — redis

Ejecutada con `scripts/ejecutar_prueba_controlada.sh redis` · commit `074851c` · contenedor `fixture2030-redis` (laboratorio). Falla inducida con `docker stop`; recuperación con `docker start`. No se borró ningún volumen.

## Línea de tiempo

| momento | hora (UTC) | desde la falla |
|---|---|---|
| inicio (tráfico de lectura a `/sesiones/demo-ses-0000001-1` y `/equipos/ARG`) | 2026-10-31T00:13:36Z | - |
| `docker stop fixture2030-redis` | 2026-10-31T00:14:06Z | 0 s |
| Prometheus ve `probe_success{base="redis"} = 0` | 2026-10-31T00:14:16Z | 10 s |
| alerta `BaseNoResponde` en firing (for: 1m) | 2026-10-31T00:15:18Z | 72 s |
| `docker start fixture2030-redis` | 2026-10-31T00:15:18Z | 72 s |
| Prometheus ve `probe_success = 1` | 2026-10-31T00:15:31Z | 85 s |
| alerta resuelta | 2026-10-31T00:15:33Z | - |

## Respuesta de la API en `/sesiones/demo-ses-0000001-1`

| antes | durante | después |
|---|---|---|
| HTTP 404 · code=SESSION_NOT_FOUND | HTTP 503 · code=DEPENDENCY_UNAVAILABLE | HTTP 404 · code=SESSION_NOT_FOUND |

## Series de Prometheus en el intervalo (paso 15 s)

### Disponibilidad — `probe_success{base="redis"}` (1 = responde)

| hora (UTC) | base=redis |
|---|---|
| 00:13:36 | 1 |
| 00:13:51 | 1 |
| 00:14:06 | 1 |
| 00:14:21 | 0 |
| 00:14:36 | 0 |
| 00:14:51 | 0 |
| 00:15:06 | 0 |
| 00:15:21 | 0 |
| 00:15:36 | 1 |
| 00:15:51 | 1 |

### Llamadas de la API a redis por resultado — `sum by (resultado) (rate(fixture2030_dependencia_duration_seconds_count{dependencia="redis"}[1m]))` (llamadas/s)

| hora (UTC) | resultado=no_disponible | resultado=ok |
|---|---|---|
| 00:13:36 |  | 0 |
| 00:13:51 |  | 0.222 |
| 00:14:06 |  | 1.64 |
| 00:14:21 |  | 2.84 |
| 00:14:36 | 2.08 | 2.62 |
| 00:14:51 | 3.15 | 1.2 |
| 00:15:06 | 4.21 | 0 |
| 00:15:21 | 4.24 | 0 |
| 00:15:36 | 3.76 | 0.467 |
| 00:15:51 | 2.33 | 1.87 |

### Respuestas de la API por status — `sum by (status) (rate(fixture2030_http_requests_total[1m]))` (req/s)

| hora (UTC) | status=200 | status=400 | status=404 | status=503 |
|---|---|---|---|---|
| 00:13:36 | 0.0667 | 0 | 0 | 0 |
| 00:13:51 | 0.289 | 0 | 0.222 | 0 |
| 00:14:06 | 1.71 | 0 | 1.64 | 0 |
| 00:14:21 | 3.11 | 0 | 2.84 | 0 |
| 00:14:36 | 4.29 | 0 | 2.62 | 2.08 |
| 00:14:51 | 4.29 | 0 | 1.2 | 3.15 |
| 00:15:06 | 4.31 | 0 | 0 | 4.21 |
| 00:15:21 | 4.31 | 0 | 0 | 4.24 |
| 00:15:36 | 4.29 | 0 | 0.467 | 3.76 |
| 00:15:51 | 4.27 | 0 | 1.87 | 2.33 |

## Ver en Grafana

http://localhost:3000/d/fixture2030-monitoreo?from=1793405616000&to=1793405753000
