# Capas 3-6 — protocolo, identidad, contexto y operación (drivers)

- Fecha (UTC) de inicio: 2026-10-19T19:29:39Z
- Commit: `ea51b8f+cambios-locales`
- Entorno: notebook-docker-desktop
- Origen de la prueba: notebook (host) · Windows AMD64 · python 3.13.7
- Timeouts: conexión 2 s · operación 3 s · API 8 s
- Secretos: ninguno se imprime; toda salida pasa por `registro.redactar` (RNF7/RNF8).

| Fecha (UTC) | Producto | Capa | Prueba | Objetivo / contexto | Resultado | ms | Detalle | Interpretación | No demuestra |
|---|---|---|---|---|---|---:|---|---|---|
| 2026-10-19T19:29:41Z | redis | protocolo | `PING (RESP)` | `127.0.0.1:6379/0` | **OK** | 45.0 | PONG | el servidor habla RESP y responde | que exista ninguna clave |
| 2026-10-19T19:29:42Z | redis | protocolo | `INFO server` | `127.0.0.1:6379/0` | **OK** |  | Redis 8.10.2 · modo standalone | versión observada (RNF18) |  |
| 2026-10-19T19:29:42Z | redis | autenticacion | `ACL WHOAMI` | `127.0.0.1:6379/0` | **N/C** |  | usuario 'default' sin contraseña (requirepass vacío, publicado sólo en 127.0.0.1 — Hito 7) | N/C: con contraseña, un cliente sin AUTH recibiría NOAUTH (identidad), no un error de red |  |
| 2026-10-19T19:29:43Z | redis | autorizacion | `ACL del usuario` | `127.0.0.1:6379/0` | **N/C** |  | usuario default con todos los comandos | N/C: con ACL restrictiva un comando prohibido da NOPERM → la API responde 503 motivo `autorizacion` |  |
| 2026-10-19T19:29:43Z | redis | contexto | `INFO keyspace db0` | `127.0.0.1:6379/0` | **OK** |  | keys=3 · expires=0 | la base lógica que usa la API (REDIS_URL …/0) es la consultada | que las claves de la demo estén cargadas |
| 2026-10-19T19:29:44Z | redis | operacion | `EXISTS + TYPE + HLEN + TTL (sin leer valores)` | `f30:ses:demo-ses-0000001-1` | **OK** | 79.1 | ausente: EXISTS 0 · TTL -2 | ausente. Redis no distingue 'expiró' de 'nunca existió' (ambas dan TTL -2); el servidor expiró 10447 claves desde que arrancó y la carga de muestra del Hito 7 pone 30 min de TTL, así que lo más probable es que haya vencido. La API responderá 404, no 503: Redis está disponible. Recargar: docker exec fixture2030-redis sh /scripts/carga_muestra.sh | el contenido de la sesión (no se lee: dato personal) |
| 2026-10-19T19:29:44Z | redis | operacion | `control: clave inexistente` | `f30:ses:diag-no-existe` | **OK** | 3.5 | EXISTS 0 · TTL -2 | ausencia válida (TTL -2): Redis responde; 'clave ausente' ≠ 'Redis caído' |  |
| 2026-10-19T19:29:59Z | redis | operacion | `control: Redis no disponible (puerto sin listener)` | `127.0.0.1:6380` | **OK** | 14654.3 | ConnectionError: Error 10061 connecting to 127.0.0.1:6380. No se puede establecer una conexión ya que el equipo de destino denegó expresamente dicha conexión | Redis no disponible = ConnectionError en el cliente (la API: 503), distinto de clave ausente (404) |  |
| 2026-10-19T19:30:06Z | redis | protocolo | `redis-cli PING` | `dentro del contenedor fixture2030-redis` | **OK** | 3344.7 | PONG | RESP responde con el cliente oficial | que exista la clave |
| 2026-10-19T19:30:06Z | redis | operacion | `redis-cli EXISTS/TYPE/TTL` | `f30:ses:demo-ses-0000001-1` | **OK** | 3344.7 | EXISTS 0 · TYPE none · TTL -2 | clave ausente (inexistente o vencida: Redis no las distingue). Redis está disponible: la API dará 404 | el contenido de la sesión (no se lee) |
