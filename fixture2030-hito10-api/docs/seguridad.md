# Seguridad: secretos, logs y archivos excluidos — Hito 10

**Ingeniería de Datos II · Fixture 2030** — Santiago Pazos, Valentina Frisoli, Joaquín Núñez

## 1. Secretos (RNF6 / RNF7)

| Secreto | Dónde vive | Cómo lo lee la API |
|---|---|---|
| Contraseña de Neo4j | `.env` local de la API (o `fixture2030-neo4j/.env`), ignorados por git | `NEO4J_PASSWORD` → `SecretStr` |
| Token de InfluxDB 3 | `fixture2030-influxdb/secrets/admin-token.json` (lo crea el Hito 8, ignorado por git) | `INFLUX_TOKEN` o `INFLUX_TOKEN_FILE` → sólo en la cabecera `Authorization` |
| URIs de Mongo y Redis | `.env` (no llevan credenciales en el laboratorio) | `SecretStr` igual, por si un ambiente agrega usuario/contraseña |

- `.env.example` versionado, **sin valores secretos** (`NEO4J_PASSWORD=` vacío).
- `.gitignore` excluye `.env`, `.env.*` (salvo el ejemplo), `secrets/`, `*.token`, `.venv/`, `web/.env.local`, `web/.vercel/`, logs crudos.
- MongoDB, Cassandra y Redis no tienen autenticación en el laboratorio (decisión de los Hitos 4, 6 y 7: nodo de desarrollo; Redis e InfluxDB publicados sólo en `127.0.0.1`). Es configuración de desarrollo, no de producción.
- Antes del PR se corre un barrido de secretos sobre lo versionado (`git grep` de tokens `apiv3_`, `Bearer`, contraseñas y URIs con credenciales): resultado en [`pruebas_y_evidencia.md`](./pruebas_y_evidencia.md) §6.

## 2. Qué se loguea y qué no (RNF10)

Cada línea es JSON con `request_id`.

| Se registra | No se registra |
|---|---|
| Método, plantilla de ruta y path, status, duración (log de acceso) | Cuerpos de request y de respuesta |
| Dependencia, operación, resultado (`ok`, `timeout`, `no_disponible`, `dominio:<code>`), duración | Parámetros de consultas, Cypher/CQL/SQL, valores de sesión |
| Tipo de excepción en errores inesperados y en fallas de dependencia | Trazas completas (pueden contener URIs), tokens, contraseñas, cabecera `Authorization` |

Los loggers de los drivers quedan en `WARNING` (algunos escriben hosts en `INFO`) y el log de acceso de uvicorn se reemplaza por el propio. Ejemplo real: [`evidencia/logs_correlacion_request_id.md`](./evidencia/logs_correlacion_request_id.md).

## 3. Respuestas al consumidor (RF12 / RNF9)

- Formato único sin datos internos: ni hosts, ni puertos, ni consultas, ni stack traces (ver [`contratos_y_errores.md`](./contratos_y_errores.md) §3). Un `AuthError` de Neo4j o un 401 de InfluxDB se informan como `DEPENDENCY_UNAVAILABLE`, sin decir que la credencial falló.
- Se expone sólo lo que el caso de uso necesita: proyección en Mongo, campos públicos de la sesión (sin `solicitudes`), DTOs explícitos en todas las fuentes (`extra="forbid"` también en las entradas).

## 4. Superficie de acceso (restricción "Diseño")

- No hay endpoints que reciban nombres de colecciones, tablas, keyspaces, etiquetas, relaciones, comandos ni consultas. Todas las consultas son fijas y parametrizadas (Cypher con `$param`, CQL preparado, SQL de InfluxDB con `params`); los únicos valores interpolados son enteros ya validados (`LIMIT`) o constantes de un diccionario cerrado (intervalo de `date_bin`).
- `X-Request-Id` del cliente sólo se acepta si cumple `^[A-Za-z0-9._-]{1,64}$` (evita inyección en logs).

## 5. CORS y front público

- `CORS_ORIGINS` lista explícita (front local `:5173` y el dominio de Vercel); un origen no listado no recibe `Access-Control-Allow-Origin` (test `test_origen_no_permitido_no_recibe_cors`).
- `allow_private_network=True`: el front HTTPS de Vercel puede llamar a `http://localhost:8000` (Private Network Access de Chrome). Sólo funciona en la notebook donde corre la API: la API **no** se publica en internet.
- Sin autenticación de usuarios en este hito: las escrituras (eventos, cierre, comentarios, invalidar sesiones) están abiertas a quien llegue a `localhost:8000`. Es una limitación conocida del laboratorio; en producción irían detrás de autenticación y roles (mesa de control, moderación).
