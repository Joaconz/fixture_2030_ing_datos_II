# Dependencia lenta (docker pause): el proceso no responde pero el puerto sigue abierto

- Fecha (UTC): 2026-10-13T19:40:58Z · DEP_TIMEOUT_S = 2.0 s · método: `docker pause` → curl → `docker unpause` (sin pérdida de datos)

| Fuente | Request | HTTP | Tiempo (s) | code |
|---|---|---:|---:|---|
| fixture2030-redis | `GET /sesiones/demo-ses-0000001-1` | 503 | 2.006324 | DEPENDENCY_UNAVAILABLE |
| fixture2030-cassandra | `GET /partidos/PAR-A-1/comentarios?limit=5` | 503 | 2.007152 | DEPENDENCY_UNAVAILABLE |
| fixture2030-influxdb | `GET /partidos/PAR-A-1/estadisticas?desde=2030-06-09T13:00:00Z&hasta=2030-06-09T13:30:00Z` | 503 | 2.006782 | DEPENDENCY_UNAVAILABLE |
