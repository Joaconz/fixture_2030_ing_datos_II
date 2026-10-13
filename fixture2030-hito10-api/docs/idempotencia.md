# Idempotencia, reintentos y escritura segura — Hito 10

**Ingeniería de Datos II · Fixture 2030** — Santiago Pazos, Valentina Frisoli, Joaquín Núñez

> RF19 / RNF14 / §5.7: qué endpoints leen, cuáles escriben y qué pasa si una escritura se repite por un reintento (respuesta perdida, doble clic, timeout del cliente).

## 1. Resumen

| Endpoint | Tipo | Si se repite |
|---|---|---|
| Todos los `GET` | Lectura | Sin efectos. `GET /sesiones/{id}` además **no renueva** el TTL |
| `POST /partidos/{id}/eventos` | Creación (Neo4j) | Misma `Idempotency-Key` + mismo cuerpo → 200 con el mismo evento y `Idempotent-Replayed: true`, sin duplicar. Misma clave + otro cuerpo → 409 `IDEMPOTENCY_KEY_REUSED` |
| `PATCH /partidos/{id}/estado` | Actualización (Neo4j) | **No idempotente por diseño:** el primer cierre da 200; el reintento da 409 `INVALID_TRANSITION` y no cambia nada (el estado final es el mismo) |
| `POST /partidos/{id}/comentarios` | Creación (Cassandra) | Misma clave + mismo `creadoEn` → misma clave primaria → upsert sobre la misma fila; la API lo detecta y responde 200 + `Idempotent-Replayed: true` |
| `DELETE /sesiones/{id}` | Invalidación (Redis) | El efecto es idempotente (la sesión queda invalidada); la respuesta del reintento es 404 `SESSION_NOT_FOUND` |
| Invalidación de caché (interna) | `DEL` en Redis | Idempotente; si Redis no responde, la copia vence sola en 60 s |

## 2. Eventos (Neo4j)

- `Idempotency-Key` es **obligatoria** (400 si falta). El cliente la genera por intento lógico, no por envío: el reintento manda la misma.
- `eventoId = "{partidoId}-API-" + sha256(clave)[:12]`: el identificador del nodo sale de la clave, así un reintento apunta al mismo nodo (restricción de unicidad `evento_id_unico` del Hito 5 como red de seguridad).
- El nodo guarda `huella = sha256(cuerpo canónico)`. En la transacción de escritura, si el `eventoId` ya existe: misma huella → replay (200), otra huella → 409. La verificación de idempotencia ocurre **antes** que las reglas de estado: reintentar un evento que se dio de alta antes del cierre sigue dando 200 después del cierre (la respuesta original se perdió, el evento sí existe).
- **Concurrencia:** la transacción toma un bloqueo de escritura sobre el `:Partido` al inicio. Dos altas simultáneas del mismo partido se serializan: no hay secuencias repetidas ni dos `FIN_PARTIDO`. Dos reintentos simultáneos con la misma clave: el segundo ve el nodo creado por el primero y responde replay.
- **Cambios parciales:** imposibles — nodo, propiedades y relaciones se crean en una sola transacción; si Neo4j cae a mitad, no se confirma nada y la respuesta es 503 (reintentar con la misma clave es seguro).
- Verificado en vivo: `test_flujo_de_cierre_completo` repite el POST y comprueba con `cypher-shell` que hay **un** nodo con ese `eventoId`.

## 3. Cierre del partido (Neo4j)

- Una transacción de escritura: exige `PROGRAMADO` y un `FIN_PARTIDO`, deriva el marcador de los `GOL` y cambia el estado. Es la operación CP del Hito 3 para N2.
- No se hizo idempotente con clave porque la operación ya es una **transición de estado con precondición**: el reintento encuentra el estado cambiado y responde 409 sin efectos. El consumidor que recibe 409 `INVALID_TRANSITION` puede leer `GET /partidos/{id}` y confirmar `FINALIZADO`.
- Después de confirmar se invalida `f30:cache:partido:{id}`.

## 4. Comentarios (Cassandra)

- En Cassandra un `INSERT` es un upsert: escribir dos veces la misma clave primaria deja **una** fila. La API se apoya en eso, con una clave primaria determinista:
  - `comentario_id = "{partidoId}-API-" + sha256(usuarioId + ":" + clave)[:16]`;
  - `creado_en = creadoEn` del cuerpo, truncado a milisegundos (Cassandra guarda ms; sin truncar, la lectura por clave no coincidiría);
  - `ventana` = piso de `creado_en` al ancho de Q0; `bucket = crc32(comentario_id) % buckets` (misma fórmula del Hito 6).
- Antes de escribir se lee por clave primaria completa (barato: una partición, una fila). Si existe → 200 replay; si no → `LOGGED BATCH` en `comentarios_por_partido` y `comentarios_por_usuario` (las dos vistas quedan iguales o el batch se reintenta completo).
- **Carrera de dos reintentos simultáneos:** ambos pueden no ver la fila y escribir: el resultado sigue siendo una sola fila por tabla (upsert de la misma clave con los mismos valores). Lo único que cambia es que los dos reciben 201.
- **Límite documentado:** la garantía exige reenviar **la misma request** (misma clave y mismo `creadoEn`). Si un cliente reusa la clave con otro `creadoEn`, la clave primaria cambia y se crea otra fila: Cassandra no ofrece una restricción de unicidad sobre `comentario_id` solo, y agregar una tabla de claves de idempotencia con `IF NOT EXISTS` (LWT, Paxos) contradiría el AP/W=1 del Hito 3 para N6. Misma clave con otro contenido pero igual `creadoEn`: responde 200 con el comentario original (no se sobrescribe).
- Por qué `creadoEn` viene del cliente: los partidos del laboratorio ocurren en 2030 (reloj del torneo simulado) y cada comentario debe caer en las ventanas del partido (−15′ a +125′ del inicio, Hito 6). Un `creadoEn` fuera de ese tramo se rechaza con 400 `COMMENT_OUTSIDE_MATCH_WINDOW`.
- Verificado en vivo: `test_publicar_comentario_idempotente` repite el POST y comprueba con `cqlsh` que hay una fila.

## 5. Sesiones y caché (Redis)

- `DELETE /sesiones/{id}`: `WATCH` sobre la sesión, luego `MULTI` `SREM` del índice del usuario + `DEL` `EXEC`. Las dos claves cambian juntas o ninguna (no queda un índice apuntando a una sesión borrada). Si otra operación modifica la sesión entre el `WATCH` y el `EXEC`, la transacción aborta y se reintenta una vez; si vuelve a abortar responde 503 en lugar de borrar a ciegas.
- Invalidación de caché tras escribir en Neo4j: `DEL` es idempotente. Si Redis no responde, la escritura no falla (ya está confirmada) y el detalle puede quedar viejo hasta 60 s — el mismo tope de frescura que aceptó el Hito 7.
