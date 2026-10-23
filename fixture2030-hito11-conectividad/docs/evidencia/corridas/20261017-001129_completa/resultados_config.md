# Capa 0 — configuración

- Fecha (UTC) de inicio: 2026-10-17T00:11:29Z
- Commit: `71a1625`
- Entorno: notebook-docker-desktop
- Origen de la prueba: notebook (host) · Darwin arm64 · python 3.12.13
- Timeouts: conexión 2 s · operación 3 s · API 8 s
- Secretos: ninguno se imprime; toda salida pasa por `registro.redactar` (RNF7/RNF8).

| Fecha (UTC) | Producto | Capa | Prueba | Objetivo / contexto | Resultado | ms | Detalle | Interpretación | No demuestra |
|---|---|---|---|---|---|---:|---|---|---|
| 2026-10-17T00:11:29Z | api | configuracion | `API_URL (url)` | `API_URL=http://localhost:8001` | **OK** |  | origen: entorno | valor utilizable por las pruebas | que el servidor exista en ese host/puerto |
| 2026-10-17T00:11:29Z | mongodb | configuracion | `MONGO_HOST (host)` | `MONGO_HOST=localhost` | **OK** |  | origen: configuracion-ejemplo.env | valor utilizable por las pruebas | que el servidor exista en ese host/puerto |
| 2026-10-17T00:11:29Z | mongodb | configuracion | `MONGO_PORT (puerto)` | `MONGO_PORT=27017` | **OK** |  | origen: configuracion-ejemplo.env | valor utilizable por las pruebas | que el servidor exista en ese host/puerto |
| 2026-10-17T00:11:29Z | mongodb | configuracion | `MONGO_DB (nombre)` | `MONGO_DB=fixture2030` | **OK** |  | origen: configuracion-ejemplo.env | valor utilizable por las pruebas | que el servidor exista en ese host/puerto |
| 2026-10-17T00:11:29Z | neo4j | configuracion | `NEO4J_HOST (host)` | `NEO4J_HOST=localhost` | **OK** |  | origen: configuracion-ejemplo.env | valor utilizable por las pruebas | que el servidor exista en ese host/puerto |
| 2026-10-17T00:11:29Z | neo4j | configuracion | `NEO4J_BOLT_PORT (puerto)` | `NEO4J_BOLT_PORT=7687` | **OK** |  | origen: configuracion-ejemplo.env | valor utilizable por las pruebas | que el servidor exista en ese host/puerto |
| 2026-10-17T00:11:29Z | neo4j | configuracion | `NEO4J_HTTP_PORT (puerto)` | `NEO4J_HTTP_PORT=7474` | **OK** |  | origen: configuracion-ejemplo.env | valor utilizable por las pruebas | que el servidor exista en ese host/puerto |
| 2026-10-17T00:11:29Z | neo4j | configuracion | `NEO4J_DATABASE (nombre)` | `NEO4J_DATABASE=neo4j` | **OK** |  | origen: configuracion-ejemplo.env | valor utilizable por las pruebas | que el servidor exista en ese host/puerto |
| 2026-10-17T00:11:29Z | neo4j | configuracion | `NEO4J_USER (nombre)` | `NEO4J_USER=neo4j` | **OK** |  | origen: configuracion-ejemplo.env | valor utilizable por las pruebas | que el servidor exista en ese host/puerto |
| 2026-10-17T00:11:29Z | cassandra | configuracion | `CASSANDRA_HOST (host)` | `CASSANDRA_HOST=127.0.0.1` | **OK** |  | origen: configuracion-ejemplo.env | valor utilizable por las pruebas | que el servidor exista en ese host/puerto |
| 2026-10-17T00:11:30Z | cassandra | configuracion | `CASSANDRA_PORT (puerto)` | `CASSANDRA_PORT=9042` | **OK** |  | origen: configuracion-ejemplo.env | valor utilizable por las pruebas | que el servidor exista en ese host/puerto |
| 2026-10-17T00:11:30Z | cassandra | configuracion | `CASSANDRA_KEYSPACE (nombre)` | `CASSANDRA_KEYSPACE=fixture2030_comentarios` | **OK** |  | origen: configuracion-ejemplo.env | valor utilizable por las pruebas | que el servidor exista en ese host/puerto |
| 2026-10-17T00:11:30Z | cassandra | configuracion | `CASSANDRA_DC (nombre)` | `CASSANDRA_DC=datacenter1` | **OK** |  | origen: configuracion-ejemplo.env | valor utilizable por las pruebas | que el servidor exista en ese host/puerto |
| 2026-10-17T00:11:30Z | redis | configuracion | `REDIS_HOST (host)` | `REDIS_HOST=127.0.0.1` | **OK** |  | origen: configuracion-ejemplo.env | valor utilizable por las pruebas | que el servidor exista en ese host/puerto |
| 2026-10-17T00:11:30Z | redis | configuracion | `REDIS_PORT (puerto)` | `REDIS_PORT=6379` | **OK** |  | origen: configuracion-ejemplo.env | valor utilizable por las pruebas | que el servidor exista en ese host/puerto |
| 2026-10-17T00:11:30Z | redis | configuracion | `REDIS_DB (entero)` | `REDIS_DB=0` | **OK** |  | origen: configuracion-ejemplo.env | valor utilizable por las pruebas | que el servidor exista en ese host/puerto |
| 2026-10-17T00:11:30Z | influxdb | configuracion | `INFLUX_URL (url)` | `INFLUX_URL=http://127.0.0.1:8181` | **OK** |  | origen: configuracion-ejemplo.env | valor utilizable por las pruebas | que el servidor exista en ese host/puerto |
| 2026-10-17T00:11:30Z | influxdb | configuracion | `INFLUX_DB (nombre)` | `INFLUX_DB=fixture2030_vivo` | **OK** |  | origen: configuracion-ejemplo.env | valor utilizable por las pruebas | que el servidor exista en ese host/puerto |
| 2026-10-17T00:11:30Z | iris | configuracion | `IRIS_HOST (host)` | `IRIS_HOST=127.0.0.1` | **OK** |  | origen: configuracion-ejemplo.env | valor utilizable por las pruebas | que el servidor exista en ese host/puerto |
| 2026-10-17T00:11:30Z | iris | configuracion | `IRIS_PORT (puerto)` | `IRIS_PORT=1972` | **OK** |  | origen: configuracion-ejemplo.env | valor utilizable por las pruebas | que el servidor exista en ese host/puerto |
| 2026-10-17T00:11:30Z | iris | configuracion | `IRIS_PORTAL_URL (url)` | `IRIS_PORTAL_URL=http://127.0.0.1:52773` | **OK** |  | origen: configuracion-ejemplo.env | valor utilizable por las pruebas | que el servidor exista en ese host/puerto |
| 2026-10-17T00:11:30Z | iris | configuracion | `IRIS_NAMESPACE (nombre)` | `IRIS_NAMESPACE=USER` | **OK** |  | origen: configuracion-ejemplo.env | valor utilizable por las pruebas | que el servidor exista en ese host/puerto |
| 2026-10-17T00:11:30Z | neo4j | configuracion | `NEO4J_PASSWORD definido (sin mostrar el valor)` | `archivo fixture2030-neo4j/.env` | **OK** |  | definido (11 caracteres) | la prueba de identidad podrá ejecutarse | que el servidor lo acepte |
| 2026-10-17T00:11:30Z | neo4j | configuracion | `NEO4J_PASSWORD distinto de los valores públicos` | `comparado con .env.example y config no secreta` | **WARN** |  | es la credencial de desarrollo documentada en un .env.example versionado | no es un secreto real: sirve en el laboratorio, no en un entorno compartido | nada sobre el servidor |
| 2026-10-17T00:11:30Z | neo4j | configuracion | `archivo del secreto fuera de git` | `fixture2030-neo4j/.env` | **WARN** |  | legible por otros usuarios (0o644) | el secreto no se publica en el repositorio (RNF7) | que el valor sea vigente |
| 2026-10-17T00:11:30Z | influxdb | configuracion | `token de InfluxDB definido (sin mostrar el valor)` | `archivo fixture2030-influxdb/secrets/admin-token.json` | **OK** |  | definido (92 caracteres) | la prueba de identidad podrá ejecutarse | que el servidor lo acepte |
| 2026-10-17T00:11:30Z | influxdb | configuracion | `archivo del secreto fuera de git` | `fixture2030-influxdb/secrets/admin-token.json` | **OK** |  | ignorado por git, permisos 0o600 | el secreto no se publica en el repositorio (RNF7) | que el valor sea vigente |
| 2026-10-17T00:11:30Z | mongodb | configuracion | `credencial` | `MONGO_USER vacío` | **N/C** |  | laboratorio sin autenticación (decisión del Hito 4) | la capa de autenticación se informa como N/C, no como OK |  |
| 2026-10-17T00:11:30Z | cassandra | configuracion | `credencial` | `sin usuario` | **N/C** |  | laboratorio sin autenticación: AllowAllAuthenticator (Hito 6) | la capa de autenticación se informa como N/C, no como OK |  |
| 2026-10-17T00:11:30Z | redis | configuracion | `credencial` | `sin usuario` | **N/C** |  | laboratorio sin autenticación: sin requirepass, sólo 127.0.0.1 (Hito 7) | la capa de autenticación se informa como N/C, no como OK |  |
| 2026-10-17T00:11:30Z | iris | configuracion | `IRIS_HABILITADO` | `IRIS_HABILITADO=0` | **N/C** |  | fuera de la arquitectura vigente desde la reentrega del Hito 3 | se declara NOT_CONFIGURED: no se inventan resultados |  |
| 2026-10-17T00:11:30Z | mongodb | configuracion | `API vs hito: host:puerto` | `API=localhost:27017 · hito=localhost:27017` | **OK** |  | coinciden | la evaluación apunta al mismo destino que la API | que ese destino responda |
| 2026-10-17T00:11:30Z | mongodb | configuracion | `API vs hito: database` | `API=fixture2030 · hito=fixture2030` | **OK** |  | coinciden | la evaluación apunta al mismo destino que la API | que ese destino responda |
| 2026-10-17T00:11:31Z | neo4j | configuracion | `API vs hito: host:puerto Bolt` | `API=localhost:7687 · hito=localhost:7687` | **OK** |  | coinciden | la evaluación apunta al mismo destino que la API | que ese destino responda |
| 2026-10-17T00:11:31Z | neo4j | configuracion | `API vs hito: database` | `API=neo4j · hito=neo4j` | **OK** |  | coinciden | la evaluación apunta al mismo destino que la API | que ese destino responda |
| 2026-10-17T00:11:31Z | cassandra | configuracion | `API vs hito: host:puerto` | `API=127.0.0.1:9042 · hito=127.0.0.1:9042` | **OK** |  | coinciden | la evaluación apunta al mismo destino que la API | que ese destino responda |
| 2026-10-17T00:11:31Z | cassandra | configuracion | `API vs hito: keyspace` | `API=fixture2030_comentarios · hito=fixture2030_comentarios` | **OK** |  | coinciden | la evaluación apunta al mismo destino que la API | que ese destino responda |
| 2026-10-17T00:11:31Z | redis | configuracion | `API vs hito: host:puerto/db` | `API=127.0.0.1:6379/0 · hito=127.0.0.1:6379/0` | **OK** |  | coinciden | la evaluación apunta al mismo destino que la API | que ese destino responda |
| 2026-10-17T00:11:31Z | influxdb | configuracion | `API vs hito: url` | `API=http://127.0.0.1:8181 · hito=http://127.0.0.1:8181` | **OK** |  | coinciden | la evaluación apunta al mismo destino que la API | que ese destino responda |
| 2026-10-17T00:11:31Z | influxdb | configuracion | `API vs hito: database` | `API=fixture2030_vivo · hito=fixture2030_vivo` | **OK** |  | coinciden | la evaluación apunta al mismo destino que la API | que ese destino responda |
| 2026-10-17T00:11:31Z | api | configuracion | `timeout de dependencias de la API (DEP_TIMEOUT_S)` | `dep_timeout_s=2.0` | **OK** |  | health_cache_s=5.0 · ready_esenciales=mongodb,neo4j | ninguna operación de la API espera indefinidamente (RNF5/RNF12) | que el timeout sea el adecuado bajo carga (Hito 12) |
| 2026-10-17T00:11:31Z | api | configuracion | `config local ignorada por git` | `config/configuracion.env` | **OK** |  | cubierta por .gitignore | valores propios o secretos no se versionan |  |
