# Coherencia con el TPO — Hito 10

**Ingeniería de Datos II · Fixture 2030** — Santiago Pazos, Valentina Frisoli, Joaquín Núñez

> §8 del enunciado: "relación con los módulos y decisiones de los hitos anteriores". Este documento dice de dónde sale cada decisión que la API hereda, qué se verificó contra el código real (no contra los README) y qué limitaciones quedan abiertas. Fuente de verdad del estado de cada necesidad: [`../../docs/ESTADO-CANONICO-NECESIDADES.md`](../../docs/ESTADO-CANONICO-NECESIDADES.md).

## 1. Verificación del plan antes de implementar (`/validar-hito`, 13/10/2026)

Cada afirmación del plan se contrastó con el estado canónico, los Hitos 2/3 y el código de cada módulo. Resultado posible: **Consistente**, **Contradice** (y qué se hizo), **No verificable**.

| Afirmación del plan | Verificado contra | Resultado | Acción |
|---|---|---|---|
| Equipos y jugadores viven en MongoDB, db `fixture2030`, `equipos._id` = código FIFA, `jugadores{dni, equipoId, posicion, dorsal}` con índice `{equipoId, posicion}` | `fixture2030-mongodb/init/01-validators.js`, `load/seed.js` | Consistente | — |
| Partidos (N2) y Tipos de evento (N8) se leen y escriben en **Neo4j** | Estado canónico, filas N2 y N8 (reentrega del Hito 3, 13/10/2026) | Consistente | IRIS fuera; RF8 documentado en §2 |
| El cierre del partido es CP: transición validada en una transacción, sólo con todos los eventos | Hito 3 (sección de revisión del modelo de objetos) y estado canónico N2 | Consistente | `PATCH /partidos/{id}/estado` en `execute_write`, exige `FIN_PARTIDO` |
| Las reglas de cada tipo de evento se validan en la API (único camino de escritura); el motor garantiza la unicidad del tipo | Estado canónico N8; `estructura.cypher` (`tipoevento_id_unico`) | Consistente | Tabla de reglas en el servicio de eventos |
| `:Partido{estado PROGRAMADO/FINALIZADO, golesLocal, golesVisitante}`; marcador derivado de los `GOL` por `condicionEquipo` | `carga.cypher` pasos 6, 7 y 12 | Consistente | El cierre recalcula el marcador igual que el paso 12 |
| Los eventos llevan `equipoId` | `carga.cypher` paso 7 | **Contradice** (llevan `condicionEquipo` LOCAL/VISITANTE + `dorsalProtagonista`) | El contrato del evento usa `condicionEquipo` y `dorsalProtagonista`, como el grafo |
| Comentarios: PK `((partido_id, ventana, bucket), creado_en DESC, comentario_id)`, Q0 en `config_particion_partido`, `comentario_id` determinista, bucket = `crc32(comentario_id) % buckets` | `fixture2030-cassandra/scripts/esquema.cql`, `generador.py` | Consistente | — |
| Consistencia de comentarios R=1 / W=1 | Hito 3, N6 | Consistente | `LOCAL_ONE` en lectura y escritura |
| PAR-A-1 tiene 24 comentarios | `carga_muestra.cql` (80 filas entre PAR-A-1 y PAR-D16-01) y `cqlsh` en vivo | Consistente: 24 filas de carga (23 `PUBLICADO` + 1 `PENDIENTE`); PAR-D16-01 tiene 56 (52 + 2 + 2) en 4 buckets | La API devuelve sólo los `PUBLICADO` (23 y 52, más los creados por las pruebas con id `-API-`) |
| Sesiones `f30:ses:{id}` HASH; cerrar = `SREM` + `DEL` en `MULTI/EXEC`; caché `f30:cache:partido:{id}` `SET … EX 60` | `fixture2030-redis/docs/modelo_clave_valor.md`, `scripts/sesiones.redis`, `scripts/cache.redis`; PR #11 (sin Lua) | Consistente | Sin `EVAL`/`FCALL` en el adaptador |
| La sesión de demo `demo-ses-0000001-1` está disponible | `carga_muestra.sh`: TTL de inactividad 1800 s | **Contradice parcialmente**: vence 30 min después de la carga | Las pruebas de integración recargan la muestra de Redis antes de correr; la colección Postman lo advierte |
| Estadísticas en `fixture2030_vivo.estadisticas_equipo`, contadores `_acum` agregados con `max`/`last` | `fixture2030-influxdb/docs/modelo_multidimensional.md`, `scripts/comun.py` | Consistente | — |
| El seed de PAR-DEMO-API incluye `FIN_PARTIDO` | Diseño del flujo de demo | **Ajustado** | Sin `FIN_PARTIDO`: así se puede mostrar 409 `MISSING_FIN_PARTIDO` y después el alta de `FIN_PARTIDO` y el cierre |

## 2. Fuente no cubierta: IRIS (RF8)

El enunciado pide un endpoint sobre IRIS (RF8, §5.10). En la reentrega del Hito 3 (13/10/2026, con el ok del profesor) Partidos (N2) y Tipos de evento (N8) dejaron el modelo de objetos y pasaron a Neo4j; el módulo IRIS del Hito 9 quedó como entrega histórica, fuera de la arquitectura vigente. La restricción "Cobertura" del enunciado pide cubrir los módulos que el equipo puede ejecutar **documentando cualquier fuente que no esté disponible**: eso hace esta sección.

Lo que el enunciado ubica en IRIS se resuelve sobre la fuente vigente:

| Lo que pedía §5.10 | Dónde se resuelve ahora |
|---|---|
| Detalle de una entidad compleja | `GET /partidos/{id}` (partido + equipos + sede + marcador, Neo4j) |
| Transición validada del dominio | `PATCH /partidos/{id}/estado` (cierre CP en una transacción de escritura de Neo4j) |
| Diferenciar entidad inexistente, transición inválida y dependencia caída | 404 `MATCH_NOT_FOUND`, 409 `INVALID_TRANSITION` / `MISSING_FIN_PARTIDO`, 503 |
| Reglas de la entidad (antes, métodos de la clase) | Reglas por tipo de evento en el servicio + catálogo `:TipoEvento` |

⚠️ **A confirmar con el profesor:** que el ok a la reentrega del Hito 3 cubra también no implementar RF8 con IRIS. Si no lo cubre, el adaptador se agregaría como sexto módulo sin tocar las rutas existentes (la arquitectura por puertos lo permite).

## 3. Hallazgo H1 en la API: equipos de Mongo vs. equipos del grafo

El roster de 64 equipos del grafo (Hito 5) no es el de Mongo (Hito 4): hay códigos FIFA distintos para el mismo país (`URU`/`URY`, `CHI`/`CHL`, `PAR`/`PRY`, `KSA`/`SAU`) y países que están en uno y no en el otro. **No se tapa en la API:**

- La API **no une** Mongo y Neo4j por código de equipo en una misma respuesta. `GET /equipos/{codigo}` y `/jugadores` leen sólo Mongo; `GET /equipos/{codigo}/partidos` lee sólo el grafo. Para `ARG` coinciden; para un código que sólo existe en una base, una ruta responde 200 y la otra 404, y eso es correcto: cada una informa lo que tiene su fuente.
- Los cruces que sí hace la API son por `partido_id`, que es el mismo en Neo4j, Cassandra, Redis e InfluxDB (los cuatro módulos usan el calendario del Hito 5).
- Los jugadores de un evento (`protagonista`) salen del grafo, no de Mongo: el `dni` del grafo no corresponde al de Mongo.
- Resolverlo de fondo sigue siendo la tarea pendiente de H1 (unificar el roster). Se deja registrado en el estado canónico.

Además, en esta sesión se corrió `load/seed.js` dos veces contra un Mongo real (requisito pendiente de H1): ver `pruebas_y_evidencia.md`.

## 4. Decisiones heredadas que la API respeta

| Decisión | Origen | Cómo la respeta la API |
|---|---|---|
| Clave natural en lugar de ids autogenerados | Hito 4 §4, Hito 5 `estructura.cypher` §1 | Rutas por `codigo`, `partidoId`, `sesionId`; ids de escritura derivados de la `Idempotency-Key` |
| Partición de eventos por partido, `secuencia` como reloj lógico | Hito 3 (N3), Hito 5 | El alta asigna `secuencia = max + 1` dentro del partido, serializada por un bloqueo de escritura sobre el nodo |
| Comentarios AP, W=1, partición compuesta | Hito 3 (N6), Hito 6 | `LOCAL_ONE`; el endpoint siempre tiene la clave de partición; nunca un recorrido del keyspace |
| Sesiones locales con TTL, sin renovar desde lecturas ajenas al login | Hito 7 | `GET /sesiones` no renueva el TTL |
| Caché del detalle de partido 60 s + invalidación al escribir | Hito 7, P5/P6 | Cache-aside en `GET /partidos/{id}`, `DEL` después de registrar un evento o cerrar |
| Contadores acumulados: `max`/`last`, nunca `sum` | Hito 8 | Agregaciones `1m`/`5m` |
| Sin Lua ni Redis Functions | PR #11 | Sólo comandos nativos y `MULTI/EXEC` |
