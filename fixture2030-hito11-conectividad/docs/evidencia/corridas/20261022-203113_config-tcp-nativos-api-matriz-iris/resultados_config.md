# Capa 0 — configuración

- Fecha (UTC) de inicio: 2026-10-22T20:31:13Z
- Commit: `sin-git`
- Entorno: notebook-docker-desktop
- Origen de la prueba: notebook (host) · Darwin arm64 · python 3.12.15
- Timeouts: conexión 2 s · operación 3 s · API 8 s
- Secretos: ninguno se imprime; toda salida pasa por `registro.redactar` (RNF7/RNF8).

| Fecha (UTC) | Producto | Capa | Prueba | Objetivo / contexto | Resultado | ms | Detalle | Interpretación | No demuestra |
|---|---|---|---|---|---|---:|---|---|---|
| 2026-10-22T20:31:13Z | iris | configuracion | `IRIS_HOST (host)` | `IRIS_HOST=127.0.0.1` | **OK** |  | origen: configuracion-ejemplo.env | valor utilizable por las pruebas | que el servidor exista en ese host/puerto |
| 2026-10-22T20:31:13Z | iris | configuracion | `IRIS_PORT (puerto)` | `IRIS_PORT=1972` | **OK** |  | origen: configuracion-ejemplo.env | valor utilizable por las pruebas | que el servidor exista en ese host/puerto |
| 2026-10-22T20:31:13Z | iris | configuracion | `IRIS_PORTAL_URL (url)` | `IRIS_PORTAL_URL=http://127.0.0.1:52773` | **OK** |  | origen: configuracion-ejemplo.env | valor utilizable por las pruebas | que el servidor exista en ese host/puerto |
| 2026-10-22T20:31:13Z | iris | configuracion | `IRIS_NAMESPACE (nombre)` | `IRIS_NAMESPACE=USER` | **OK** |  | origen: configuracion-ejemplo.env | valor utilizable por las pruebas | que el servidor exista en ese host/puerto |
| 2026-10-22T20:31:13Z | api | configuracion | `API_URL (url)` | `API_URL=http://localhost:8000` | **OK** |  | origen: entorno | valor utilizable por las pruebas | que el servidor exista en ese host/puerto |
| 2026-10-22T20:31:13Z | mongodb | configuracion | `API vs hito: host:puerto` | `API=localhost:27017 · hito=localhost:27017` | **OK** |  | coinciden | la evaluación apunta al mismo destino que la API | que ese destino responda |
| 2026-10-22T20:31:13Z | mongodb | configuracion | `API vs hito: database` | `API=fixture2030 · hito=fixture2030` | **OK** |  | coinciden | la evaluación apunta al mismo destino que la API | que ese destino responda |
| 2026-10-22T20:31:13Z | neo4j | configuracion | `API vs hito: host:puerto Bolt` | `API=localhost:7687 · hito=localhost:7687` | **OK** |  | coinciden | la evaluación apunta al mismo destino que la API | que ese destino responda |
| 2026-10-22T20:31:13Z | neo4j | configuracion | `API vs hito: database` | `API=neo4j · hito=neo4j` | **OK** |  | coinciden | la evaluación apunta al mismo destino que la API | que ese destino responda |
| 2026-10-22T20:31:13Z | cassandra | configuracion | `API vs hito: host:puerto` | `API=127.0.0.1:9042 · hito=127.0.0.1:9042` | **OK** |  | coinciden | la evaluación apunta al mismo destino que la API | que ese destino responda |
| 2026-10-22T20:31:13Z | cassandra | configuracion | `API vs hito: keyspace` | `API=fixture2030_comentarios · hito=fixture2030_comentarios` | **OK** |  | coinciden | la evaluación apunta al mismo destino que la API | que ese destino responda |
| 2026-10-22T20:31:13Z | redis | configuracion | `API vs hito: host:puerto/db` | `API=127.0.0.1:6379/0 · hito=127.0.0.1:6379/0` | **OK** |  | coinciden | la evaluación apunta al mismo destino que la API | que ese destino responda |
| 2026-10-22T20:31:13Z | influxdb | configuracion | `API vs hito: url` | `API=http://127.0.0.1:8181 · hito=http://127.0.0.1:8181` | **OK** |  | coinciden | la evaluación apunta al mismo destino que la API | que ese destino responda |
| 2026-10-22T20:31:13Z | influxdb | configuracion | `API vs hito: database` | `API=fixture2030_vivo · hito=fixture2030_vivo` | **OK** |  | coinciden | la evaluación apunta al mismo destino que la API | que ese destino responda |
| 2026-10-22T20:31:13Z | api | configuracion | `timeout de dependencias de la API (DEP_TIMEOUT_S)` | `dep_timeout_s=2.0` | **OK** |  | health_cache_s=5.0 · ready_esenciales=mongodb,neo4j | ninguna operación de la API espera indefinidamente (RNF5/RNF12) | que el timeout sea el adecuado bajo carga (Hito 12) |
| 2026-10-22T20:31:14Z | api | configuracion | `config local ignorada por git` | `config/configuracion.env` | **SKIP** |  | no se pudo verificar: la carpeta no es un repositorio git (copia ZIP) o falta git | SKIP = verificación no ejecutada; NO significa que el archivo esté versionado |  |
