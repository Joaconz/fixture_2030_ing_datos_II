# Matriz de conectividad (RF16, RNF9, RNF17, RNF18)

La genera `scripts/generar_matriz.py` a partir de los JSONL de cada corrida: no se escribe a mano y no supone que algún producto esté disponible. Una dependencia que no se probó queda **NO_PROBADO**, nunca DISPONIBLE.

## 1. Estados

| Estado | Regla (en este orden) | Requisito |
|---|---|---|
| **NO_CONFIGURADO** | el producto no forma parte del entorno: todas sus filas son N/C (IRIS) | restricción "Productos" |
| **NO_DISPONIBLE** | alguna prueba de base dio FAIL. El diagnóstico nombra la **primera capa** que falló y el siguiente paso | RNF9 · RNF10 |
| **DEGRADADO** | ninguna FAIL, alguna WARN (sin contar las observaciones de higiene, que van en otra columna) | RNF9 |
| **NO_PROBADO** | no se incluyó en la corrida, o faltan las capas clave (protocolo y operación) por SKIP | RNF9 |
| **DESCONOCIDO** | el diagnóstico se ejecutó pero no pudo terminar ni clasificar | RNF9 |
| **DISPONIBLE** | todas las pruebas ejecutadas dieron OK (o N/C donde la capa no aplica) | RNF17: **sólo en ese momento y para esa prueba** |

Las filas de control ("control: …"), los escenarios provocados y las fallas controladas **no cambian el estado**: se cuentan en la columna "Controles" (OK = la falla provocada se observó como se esperaba).

En `/health/dependencias`, la API usa los nombres equivalentes en inglés (`UP`, `DOWN`, `NOT_CONFIGURED`, `UNKNOWN`), que se explican en [`health_readiness.md`](health_readiness.md).

## 2. Matriz vigente

Corrida [`20261017-001129_completa`](evidencia/corridas/20261017-001129_completa/matriz.md) · 2026-10-17T00:11:29Z → 00:11:46Z · commit `71a1625` · entorno `notebook-docker-desktop` · origen: notebook (host), Darwin arm64 · API `http://localhost:8001`.

| Dependencia | Estado | Config | DNS | TCP | Protocolo | Autent. | Autoriz. | Contexto | Operación | API | ms TCP | ms operación (driver) | ms API | Controles | Diagnóstico | Siguiente paso | Observaciones (no cambian el estado) |
|---|---|---|---|---|---|---|---|---|---|---|---:|---:|---:|---|---|---|---|
| **mongodb** | **DISPONIBLE** | OK | OK | OK | OK | N/C | N/C | OK | OK | OK | 0.4 | 2.5–4.1 | 1.2–3.4 | 3/3 | todas las pruebas ejecutadas terminaron bien en esta corrida (no garantiza rendimiento) | — | — |
| **neo4j** | **DISPONIBLE** | OK | OK | OK | OK | OK | OK | OK | OK | OK | 0.4–0.5 | 1.8–20 | 4.4–15 | 2/2 | todas las pruebas ejecutadas terminaron bien en esta corrida (no garantiza rendimiento) | — | NEO4J_PASSWORD distinto de los valores públicos: es la credencial de desarrollo documentada en un .env.example versionado; archivo del secreto fuera de git: legible por otros usuarios (0o644) |
| **cassandra** | **DISPONIBLE** | OK | OK | OK | OK | N/C | N/C | OK | OK | OK | 0.2 | 1.6–1.8 | 2.6–8.5 | 3/3 | todas las pruebas ejecutadas terminaron bien en esta corrida (no garantiza rendimiento) | — | — |
| **redis** | **DISPONIBLE** | OK | OK | OK | OK | N/C | N/C | OK | OK | OK | 0.2 | 3.0 | 2.0–2.3 | 3/3 | todas las pruebas ejecutadas terminaron bien en esta corrida (no garantiza rendimiento) | — | — |
| **influxdb** | **DISPONIBLE** | OK | OK | OK | OK | OK | OK | OK | OK | OK | 0.2 | 19 | 1.3–9.9 | 5/5 | todas las pruebas ejecutadas terminaron bien en esta corrida (no garantiza rendimiento) | — | — |
| **iris** | **NO_CONFIGURADO** | OK | OK | N/C | N/C | N/C | N/C | N/C | N/C | OK | — | — | 1.0 | 0/0 | fuera del entorno de prueba: no se inventan resultados | ninguno: IRIS está fuera de la arquitectura vigente | — |
| **api** | **DISPONIBLE** | OK | — | — | — | — | — | — | — | OK | — | — | 1.7–49 | 1/1 | todas las pruebas ejecutadas terminaron bien en esta corrida (no garantiza rendimiento) | — | — |

Pruebas ejecutadas por capa (archivo → capa): [`resultados_config.md`](evidencia/corridas/20261017-001129_completa/resultados_config.md) (0) · [`resultados_tcp.md`](evidencia/corridas/20261017-001129_completa/resultados_tcp.md) (1–2 y 7/7 escenarios de §5.3) · [`resultados_clientes.md`](evidencia/corridas/20261017-001129_completa/resultados_clientes.md) (3–6, drivers + CLI) · [`resultados_api.md`](evidencia/corridas/20261017-001129_completa/resultados_api.md) (API, 19 rutas + "API no alcanzable", con la tabla de log por request-id).

Totales: OK 128 · WARN 2 · FAIL 0 · SKIP 0 · N/C 18. Las 2 WARN son observaciones (credencial de desarrollo de Neo4j y permisos `0644` de su `.env` local) y no cambian el estado.

**Limitaciones de esta matriz:** las latencias son de un único cliente secuencial en una notebook y **no** son una medida de rendimiento (Hito 12). "DISPONIBLE" no garantiza disponibilidad permanente. Las capas de autenticación y autorización son N/C donde el laboratorio no tiene autenticación. Detalle en [`limitaciones_y_coherencia.md`](limitaciones_y_coherencia.md).

## 3. Cambios de estado registrados (RF20, RF21)

| Momento | Dependencia | Estado antes → durante → después | Qué cambió | Evidencia |
|---|---|---|---|---|
| 2026-10-17 00:16:27Z | Redis | UP → **DOWN** (`no responde`) → UP | `docker stop` / `docker start`: la API se recuperó sin reiniciarse; readiness `LISTA` → `LISTA_DEGRADADA` → `LISTA` | [`fallas_controladas.md`](evidencia/corridas/20261017-001625_fallas-controladas/fallas_controladas.md) |
| 2026-10-17 00:16:51Z | MongoDB | UP → **DOWN** (`no responde`) → UP | `docker stop` / `docker start`: readiness → **`NO_LISTA` (503)** → `LISTA` | ídem |
| 2026-10-17 00:17:12Z | InfluxDB | UP → **DOWN** (`timeout`, 504) → UP | `docker pause` / `docker unpause` | ídem |
| 2026-10-17 00:17:36Z → 00:18:15Z | Neo4j, Cassandra, MongoDB, InfluxDB, Redis | instancia temporal: DOWN / NOT_CONFIGURED según la variable rota | 10 configuraciones incorrectas, una por vez; la configuración correcta nunca cambió | ídem §3.4 |
| 2026-10-17 00:35:51Z → 2026-10-19 19:30:12Z | Redis | sesión de demo `demo-ses-0000001-1`: vigente (`EXISTS 1`, `TTL` 1747 s) → **vencida** (`EXISTS 0`, `TTL -2`) · Redis **DISPONIBLE** en ambas | Cambió el **dato**, no la dependencia: `GET /sesiones/demo-ses-0000001-1` pasó de **200** (`ACTIVA`) a **404** `SESSION_NOT_FOUND` (no 503); `redis-cli` y el driver dieron PONG en las dos corridas y `/health/ready` siguió `LISTA`. La segunda corrida se hizo bastante después de los 30 min del TTL (la espera se extendió), así que el valor medido es «ya vencida», no el instante exacto del vencimiento | [`20261017-003523_redis-sesion-vigente`](evidencia/corridas/20261017-003523_redis-sesion-vigente/matriz.md) · [`20261019-192936_redis-sesion-vencida`](evidencia/corridas/20261019-192936_redis-sesion-vencida/matriz.md) |
