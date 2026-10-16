# Casos de uso de la API — Hito 10

**Ingeniería de Datos II · Fixture 2030** — Santiago Pazos, Valentina Frisoli, Joaquín Núñez

> RF2: este documento se escribió **antes** de las rutas. Cada endpoint de [`contratos_y_errores.md`](./contratos_y_errores.md) existe porque hay un caso de uso acá que lo necesita; no hay endpoints genéricos ni consultas libres (§5.1 y restricción "Diseño" del enunciado).

## 1. Consumidores

| Consumidor | Qué hace con la API |
|---|---|
| **App del hincha** (web/móvil; en este hito, el front `web/`) | Ve fichas de equipos y planteles, el detalle y el timeline de un partido, comentarios y estadísticas en vivo; publica comentarios; su sesión se valida en cada request |
| **Mesa de control del partido** (operador/veedor del organizador) | Registra eventos del partido y lo cierra cuando terminó |
| **Moderación / soporte** | Consulta e invalida sesiones (por ejemplo, ante un bloqueo) |
| **Operación de la plataforma** | Verifica la conectividad de las fuentes |

## 2. Fuente de cada módulo (heredada, no redecidida)

| Necesidad (estado canónico) | Fuente vigente | Hito que la implementó |
|---|---|---|
| N1 Equipos y jugadores | MongoDB | Hito 4 |
| N2 Partidos | **Neo4j** (desde la reentrega del Hito 3, 13/10/2026) | Hito 5 |
| N3 Eventos | Neo4j | Hito 5 |
| N5 Sesiones | Redis | Hito 7 |
| N6 Comentarios | Cassandra | Hito 6 |
| N7 Estadísticas en vivo | InfluxDB 3 Core | Hito 8 |
| N8 Tipos de evento | **Neo4j** (desde la reentrega del Hito 3) | Hito 5 |
| N4 Usuarios, N9 Auditoría | — (no implementadas en ningún hito) | — |

IRIS (RF8) queda **fuera**: ver [`coherencia_tpo.md`](./coherencia_tpo.md) §2.

## 3. Casos de uso

Columnas pedidas por §5.1: consumidor · entrada · fuente · respuesta esperada · si no existe · si la fuente está caída · tipo de operación · criterio de éxito.

### CU1 — Ver la ficha de un equipo
- **Consumidor:** app del hincha. **Entrada:** código FIFA (3 letras mayúsculas).
- **Fuente:** MongoDB, `equipos` por `_id` con proyección (Hito 4).
- **Respuesta:** nombre, confederación, ranking, grupo, DT, sede, colores, cantidad de jugadores.
- **No existe:** 404 `TEAM_NOT_FOUND`. **Fuente caída:** 503 `DEPENDENCY_UNAVAILABLE`.
- **Tipo:** lectura. **Éxito:** 200 con los mismos valores que `db.equipos.findOne({_id})` en `mongosh`.

### CU2 — Ver el plantel de un equipo, filtrado por posición y paginado
- **Consumidor:** app del hincha. **Entrada:** código FIFA, `posicion` opcional, `limit` 1–50, `cursor`.
- **Fuente:** MongoDB, `jugadores` por `{equipoId, posicion}` (índice `idx_jugadores_equipoId_posicion`), orden por dorsal.
- **Respuesta:** página de jugadores + `nextCursor`.
- **No existe:** 404 `TEAM_NOT_FOUND` si el equipo no existe (no se devuelve una lista vacía ambigua). **Fuente caída:** 503.
- **Tipo:** lectura. **Éxito:** recorriendo todas las páginas se obtienen los 23 jugadores del equipo, sin repetidos.

### CU3 — Ver los partidos de un equipo
- **Consumidor:** app del hincha. **Entrada:** código FIFA, `limit` 1–20.
- **Fuente:** Neo4j, recorrido `(:Equipo)-[:PARTICIPA_EN]->(:Partido)`.
- **Respuesta:** partidos con fecha, estado, condición (local/visitante), rival y marcador.
- **No existe:** 404 `TEAM_NOT_FOUND` si el `:Equipo` no está en el grafo. **Fuente caída:** 503.
- **Tipo:** lectura. **Éxito:** coincide con el mismo `MATCH` en `cypher-shell`.
- ⚠️ Los códigos de equipo del grafo no son idénticos a los de Mongo para algunos países (Hallazgo H1): la API **no** cruza Mongo y Neo4j por código de equipo. Ver [`coherencia_tpo.md`](./coherencia_tpo.md) §3.

### CU4 — Ver el detalle de un partido
- **Consumidor:** app del hincha (la consulta más frecuente durante el torneo).
- **Entrada:** `partidoId`.
- **Fuentes:** Neo4j (partido + equipos + sede + marcador derivado de los `GOL`) con **cache-aside en Redis** (`f30:cache:partido:{id}`, `SET … EX 60`), que es exactamente el patrón P5/P6 que diseñó el Hito 7. Es la única integración de dos fuentes en una request, y se justifica por la frecuencia de lectura.
- **Respuesta:** detalle + cabecera `X-Cache: HIT | MISS | BYPASS`.
- **No existe:** 404 `MATCH_NOT_FOUND` (no se cachea la ausencia). **Redis caído:** se sirve desde Neo4j con `X-Cache: BYPASS` (degradación documentada; la caché es optimización, no fuente). **Neo4j caído:** 503 si no hay copia en caché; si hay copia vigente, se sirve con `HIT` (dato con hasta 60 s de antigüedad, igual que en el Hito 7).
- **Tipo:** lectura. **Éxito:** primer pedido `MISS`, el siguiente dentro de 60 s `HIT`, ambos con el mismo cuerpo.

### CU5 — Ver el timeline de eventos de un partido
- **Consumidor:** app del hincha. **Entrada:** `partidoId`, `tipo` opcional (uno de los 12 del catálogo N8), `limit` 1–200, `cursor`.
- **Fuente:** Neo4j, `(:Evento)-[:OCURRE_EN]->(:Partido)` en orden de `secuencia` (índice `evento_particion_partido`).
- **Respuesta:** página de eventos con protagonista.
- **No existe:** 404 `MATCH_NOT_FOUND`; un partido existente **sin eventos** (por ejemplo, un dieciseisavos sin jugar) responde **200 con `items: []`** — son casos distintos (§5.6). **Fuente caída:** 503.
- **Tipo:** lectura. **Éxito:** mismos eventos y orden que el `MATCH` equivalente.

### CU6 — Registrar un evento del partido (mesa de control)
- **Consumidor:** mesa de control. **Entrada:** `partidoId`, cabecera `Idempotency-Key`, cuerpo `{tipo, minuto, condicionEquipo?, dorsalProtagonista?}`.
- **Fuente:** Neo4j. Las **reglas de cada tipo de evento (N8)** se validan en la API, que es el único camino de escritura (decisión de la reentrega del Hito 3): qué campos exige cada tipo, `INICIO_PARTIDO` y `FIN_PARTIDO` únicos, nada después de `FIN_PARTIDO`, el minuto no puede ser anterior al del último evento, nada en un partido `FINALIZADO`, tipo presente en el catálogo `:TipoEvento`.
- **Respuesta:** 201 con el evento creado (`secuencia` = siguiente del partido).
- **No existe:** 404 `MATCH_NOT_FOUND`. **Regla violada:** 400 `EVENT_RULE_VIOLATION` (campo exigido ausente) o 409 (`MATCH_FINALIZED`, `EVENT_AFTER_FIN`, `DUPLICATE_UNIQUE_EVENT`, `EVENT_OUT_OF_ORDER`). **Fuente caída:** 503 (no se escribió nada: la transacción no llegó a confirmarse).
- **Tipo:** creación. **Idempotencia:** el `eventoId` se deriva de la clave; repetir la request responde 200 con el mismo evento y `Idempotent-Replayed: true`, sin duplicar. Misma clave con otro cuerpo: 409 `IDEMPOTENCY_KEY_REUSED`.
- **Éxito:** el evento aparece una sola vez en `cypher-shell` aunque la request se repita.

### CU7 — Cerrar un partido (transición validada del dominio)
- **Consumidor:** mesa de control. **Entrada:** `partidoId`, cuerpo `{estado: "FINALIZADO"}`.
- **Fuente:** Neo4j, en **una transacción de escritura** (cierre CP de N2, Hito 3): sólo desde `PROGRAMADO`, exige el evento `FIN_PARTIDO`, y el marcador se **deriva** de los eventos `GOL` (no se acepta un marcador enviado por el cliente).
- **Respuesta:** 200 con el detalle actualizado; se invalida la caché del detalle en Redis.
- **No existe:** 404. **Transición inválida:** 409 `INVALID_TRANSITION` (ya finalizado) o 409 `MISSING_FIN_PARTIDO`. **Fuente caída:** 503.
- **Tipo:** actualización. **Idempotencia:** no es idempotente a propósito — repetir el cierre responde 409 (el estado ya cambió) y no altera nada.
- **Éxito:** `estado = FINALIZADO` y marcador igual a la cuenta de `GOL` por lado en el grafo.

### CU8 — Leer los comentarios de un partido
- **Consumidor:** app del hincha. **Entrada:** `partidoId`, `limit` 1–50, `cursor`.
- **Fuente:** Cassandra. Primero Q0 (`config_particion_partido`: buckets y ventana), después las particiones `(partido_id, ventana, bucket)` de la más reciente a la más antigua, mezclando los buckets por `creado_en DESC` (patrones Q1/Q3 del Hito 6).
- **Respuesta:** página + `nextCursor` opaco.
- **No existe:** 404 `MATCH_NOT_FOUND` si no hay fila de Q0. Partido sin comentarios: 200 vacío. **Fuente caída:** 503 (nunca un 200 vacío).
- **Tipo:** lectura. **Éxito:** recorrer todas las páginas devuelve todos los comentarios publicados del partido, sin repetidos, en orden descendente.

### CU9 — Publicar un comentario
- **Consumidor:** app del hincha. **Entrada:** `partidoId`, `Idempotency-Key`, cuerpo `{usuarioId, alias, contenido, creadoEn, …}`.
- **Fuente:** Cassandra, `LOGGED BATCH` en `comentarios_por_partido` y `comentarios_por_usuario` (W1 del Hito 6), consistencia `LOCAL_ONE` (W=1 del Hito 3).
- **Respuesta:** 201 con el comentario.
- **No existe:** 404 si el partido no tiene Q0; 400 `COMMENT_OUTSIDE_MATCH_WINDOW` si `creadoEn` cae fuera del tramo del partido (−15′ a +125′). **Fuente caída:** 503.
- **Tipo:** creación. **Idempotencia:** `comentario_id` se deriva de la clave y `creadoEn` viene en el cuerpo, así que la clave primaria completa es determinista: reenviar la request es un upsert sobre la misma fila (200 + `Idempotent-Replayed: true`). Ver [`idempotencia.md`](./idempotencia.md).
- **Éxito:** una sola fila en cada tabla aunque la request se repita (verificado en `cqlsh`).

### CU10 — Validar una sesión
- **Consumidor:** app del hincha (en cada request autenticado) y soporte.
- **Entrada:** id de sesión. **Fuente:** Redis, `HGETALL f30:ses:{id}` + `TTL`.
- **Respuesta:** campos públicos de la sesión y TTL restante. **No** se exponen contadores internos (`solicitudes`).
- **No existe / expiró:** 404 `SESSION_NOT_FOUND` (Redis borra la clave al vencer el TTL: inexistente y expirada son la misma respuesta). **Bloqueada:** 403 `SESSION_BLOCKED`. **Redis caído:** 503 — distinto de 404 (§5.8).
- **Tipo:** lectura. La consulta **no renueva** el TTL (la renovación es del flujo de login, fuera de este hito).
- **Éxito:** mismos campos que `redis-cli HGETALL`.

### CU11 — Invalidar una sesión
- **Consumidor:** soporte/moderación. **Entrada:** id de sesión.
- **Fuente:** Redis, `MULTI` `SREM f30:usr:{usuario}:sesiones {id}` + `DEL f30:ses:{id}` `EXEC` (comandos nativos, sin Lua, como quedó el Hito 7).
- **Respuesta:** 204. **No existe:** 404. **Redis caído:** 503.
- **Tipo:** invalidación. **Idempotencia:** el efecto es idempotente (la sesión queda invalidada); la respuesta del reintento es 404, documentado.

### CU12 — Ver estadísticas de un partido en una ventana temporal
- **Consumidor:** app del hincha (panel de estadísticas). **Entrada:** `partidoId`, `desde`, `hasta` (con zona horaria, ventana ≤ 3 h), `agregacion` `raw|1m|5m`, `equipo` opcional, `limit` ≤ 2000.
- **Fuente:** InfluxDB 3, SQL parametrizado sobre `estadisticas_equipo` (P1/P2/P4 del Hito 8); en `1m`/`5m` se agrega con `date_bin`, `last_value` para la posesión y `max` para los contadores acumulados.
- **Respuesta:** puntos, cantidad y `truncado`.
- **Ventana inválida:** 400. **Sin puntos:** 200 con `puntos: []` (la existencia del partido no la decide InfluxDB). **Fuente caída o sin token:** 503.
- **Tipo:** lectura. **Éxito:** mismos valores que la consulta SQL equivalente por `curl` a `/api/v3/query_sql`.

### CU13 — Verificar la conectividad de las fuentes
- **Consumidor:** operación. **Fuente:** las cinco, con un ping acotado por timeout, en paralelo.
- **Respuesta:** estado por fuente; 200 si todas están `UP`, 503 si alguna está `DOWN` (mismo cuerpo).
- **Tipo:** lectura.

## 4. Lectura vs. escritura (RF19)

| Operación | Tipo | Garantía ante reintentos |
|---|---|---|
| CU1–CU5, CU8, CU10, CU12, CU13 | Lectura | Sin efectos |
| CU6 Registrar evento | Creación | Idempotente por `Idempotency-Key` |
| CU7 Cerrar partido | Actualización | No idempotente por diseño: el reintento da 409 y no cambia nada |
| CU9 Publicar comentario | Creación | Idempotente por `Idempotency-Key` + `creadoEn` |
| CU11 Invalidar sesión | Invalidación | Efecto idempotente; el reintento responde 404 |
