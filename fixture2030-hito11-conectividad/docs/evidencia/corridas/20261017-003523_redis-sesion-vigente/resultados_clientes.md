# Capas 3-6 — protocolo, identidad, contexto y operación (drivers)

- Fecha (UTC) de inicio: 2026-10-17T00:35:24Z
- Commit: `ea51b8f`
- Entorno: notebook-docker-desktop
- Origen de la prueba: notebook (host) · Windows AMD64 · python 3.13.7
- Timeouts: conexión 2 s · operación 3 s · API 8 s
- Secretos: ninguno se imprime; toda salida pasa por `registro.redactar` (RNF7/RNF8).

| Fecha (UTC) | Producto | Capa | Prueba | Objetivo / contexto | Resultado | ms | Detalle | Interpretación | No demuestra |
|---|---|---|---|---|---|---:|---|---|---|
| 2026-10-17T00:35:24Z | redis | protocolo | `PING (RESP)` | `127.0.0.1:6379/0` | **OK** | 38.8 | PONG | el servidor habla RESP y responde | que exista ninguna clave |
| 2026-10-17T00:35:24Z | redis | protocolo | `INFO server` | `127.0.0.1:6379/0` | **OK** |  | Redis 8.10.2 · modo standalone | versión observada (RNF18) |  |
| 2026-10-17T00:35:25Z | redis | autenticacion | `ACL WHOAMI` | `127.0.0.1:6379/0` | **N/C** |  | usuario 'default' sin contraseña (requirepass vacío, publicado sólo en 127.0.0.1 — Hito 7) | N/C: con contraseña, un cliente sin AUTH recibiría NOAUTH (identidad), no un error de red |  |
| 2026-10-17T00:35:25Z | redis | autorizacion | `ACL del usuario` | `127.0.0.1:6379/0` | **N/C** |  | usuario default con todos los comandos | N/C: con ACL restrictiva un comando prohibido da NOPERM → la API responde 503 motivo `autorizacion` |  |
| 2026-10-17T00:35:25Z | redis | contexto | `INFO keyspace db0` | `127.0.0.1:6379/0` | **OK** |  | keys=4189 · expires=4186 | la base lógica que usa la API (REDIS_URL …/0) es la consultada | que las claves de la demo estén cargadas |
| 2026-10-17T00:35:25Z | redis | operacion | `EXISTS + TYPE + HLEN + TTL (sin leer valores)` | `f30:ses:demo-ses-0000001-1` | **OK** | 2.9 | vigente: EXISTS 1 · TYPE hash · 10 campos · vence en 1768 s | sesión de demo presente y con TTL: la API responderá 200 | el contenido de la sesión (no se lee: dato personal) |
| 2026-10-17T00:35:25Z | redis | operacion | `control: clave inexistente` | `f30:ses:diag-no-existe` | **OK** | 2.8 | EXISTS 0 · TTL -2 | ausencia válida (TTL -2): Redis responde; 'clave ausente' ≠ 'Redis caído' |  |
| 2026-10-17T00:35:41Z | redis | operacion | `control: Redis no disponible (puerto sin listener)` | `127.0.0.1:6380` | **OK** | 16030.9 | ConnectionError: Error 10061 connecting to 127.0.0.1:6380. No se puede establecer una conexión ya que el equipo de destino denegó expresamente dicha conexión | Redis no disponible = ConnectionError en el cliente (la API: 503), distinto de clave ausente (404) |  |
| 2026-10-17T00:35:46Z | redis | protocolo | `redis-cli PING` | `dentro del contenedor fixture2030-redis` | **OK** | 2524.6 | PONG | RESP responde con el cliente oficial | que exista la clave |
| 2026-10-17T00:35:46Z | redis | operacion | `redis-cli EXISTS/TYPE/TTL` | `f30:ses:demo-ses-0000001-1` | **OK** | 2524.6 | EXISTS 1 · TYPE hash · TTL 1747 | clave presente; vence en 1747 s | el contenido de la sesión (no se lee) |
