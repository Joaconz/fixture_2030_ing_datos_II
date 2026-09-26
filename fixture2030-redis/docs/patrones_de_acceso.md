# Patrones de acceso — Hito 7 · Caché de Usuarios y Sesiones (Redis)

**Ingeniería de Datos II · Grupo 2** — Santiago Pazos, Valentina Frisoli, Joaquín Núñez

> Este documento va **antes** que el modelo de claves (RF2). Cada clave de [`modelo_clave_valor.md`](./modelo_clave_valor.md) existe porque un patrón de esta lista la necesita (RNF4).

---

## 1. Problema de concurrencia

El escenario del Hito 1 exige sostener **2–3 millones de usuarios simultáneos** y picos de **más de 100.000 solicitudes/s**, concentrados en las horas de partidos de alta audiencia. Eso produce cuatro tipos de tráfico que un motor de disco no absorbe bien y que Redis (memoria, un hilo de ejecución de comandos) sí:

| Tráfico | Por qué presiona |
|---|---|
| **Validación de sesión** | Todo request autenticado debe saber "¿quién es y sigue vigente?". Es una lectura + una renovación en **cada** request: la operación más frecuente del sistema. |
| **Lecturas repetidas de lo mismo** | Miles de usuarios piden la misma ficha de partido o el mismo marcador en el mismo segundo; sin caché cada uno llega a MongoDB. |
| **Ráfagas de escritura sobre un mismo dato** | Tras un gol, miles de usuarios votan al MVP o abren el mismo partido a la vez: muchas actualizaciones simultáneas sobre pocas claves. |
| **Estado que debe desaparecer solo** | Sesiones inactivas, copias vencidas y rankings por hora: si el sistema tuviera que recorrerlas para borrarlas, el barrido competiría con el tráfico. |

El Hito 3 ya fijó la naturaleza de este dato: **Sesiones (N5) es AP, consistencia eventual, vigencia por TTL, local por región, sin réplica entre regiones**; perder una sesión es tolerable ("en el peor caso se repite un login"). Usuarios (N4) y Partidos (N2) viven en MongoDB y son la **fuente de verdad** de lo que aquí se cachea.

### Supuestos de carga (declarados, no medidos en producción)

| Supuesto | Valor | Origen |
|---|---|---|
| Usuarios simultáneos | 2–3 millones | Hito 1 |
| Requests autenticados por usuario activo | 1 cada ~10–30 s (heartbeat de partido en vivo) | Supuesto del grupo |
| Lecturas de ficha de partido por segundo en pico | del orden de 10⁴–10⁵ | Derivado del pico de 100.000 req/s del Hito 1 |
| Cambios de la ficha de un partido | unos pocos por partido (gol, tarjeta, cierre) | Supuesto del grupo |
| Sesiones en el laboratorio | 2.200 (2.000 usuarios) | [`concurrencia_y_pruebas.md`](./concurrencia_y_pruebas.md) §1 |

---

## 2. Patrones

Las frecuencias son **esperadas por diseño** (supuestos de arriba), no medidas.

| # | Patrón | Quién | Entrada | Respuesta | Frecuencia esperada | Temporal / fuente de verdad | Estructura Redis y por qué |
|---|---|---|---|---|---|---|---|
| **P1** | Crear sesión (login) | Servicio de autenticación | usuario, rol, región, dispositivo | `session_id` | Alta al arrancar partidos populares | **Temporal.** La credencial vive en el módulo de Usuarios (Mongo N4); Redis sólo guarda el estado de la visita | **HASH** `f30:ses:{id}`: varios atributos con nombre, leídos y actualizados por campo sin reescribir todo |
| **P2** | Validar y renovar sesión | Cualquier request autenticado | `session_id` | usuario, región, rol — o "no existe" | **Muy alta** (cada request) | Temporal | El mismo HASH + `EXPIRE` (TTL deslizante) dentro de una función atómica |
| **P3** | Cerrar una sesión / cerrar todas las de un usuario | Usuario (logout), cambio de contraseña, moderación | `session_id` o `usuario_id` | confirmación | Baja | Temporal | **SET** `f30:usr:{u}:sesiones` como índice: "todas las sesiones de X" sin recorrer el keyspace |
| **P4** | Bloquear una sesión | Moderador | `session_id` | rechazo en el siguiente request | Muy baja | Temporal | Campo `estado` del HASH: el bloqueo se aplica sin borrar (queda rastro hasta que venza) |
| **P5** | Consultar la ficha/marcador de un partido | Cualquier usuario | `partido_id` | JSON de la ficha | **Muy alta** (miles/s por partido en vivo) | **Copia.** Fuente: MongoDB N2 Partidos | **STRING** JSON `f30:cache:partido:{id}`: se lee entero y se sirve tal cual; TTL 60 s |
| **P6** | Actualizar/invalidar la copia cuando cambia el partido | Servicio de partidos, tras confirmar en Mongo | `partido_id` | copia borrada, versión nueva | Baja (unos pocos por partido) | Fuente: MongoDB | **STRING** contador `…:ver` (versión): evita que un lector lento repueble con un dato viejo |
| **P7** | Consultar el perfil de un usuario | Servicios de la app | `usuario_id` | perfil | Alta | **Copia.** Fuente: MongoDB N4 Usuarios | **HASH** `f30:cache:usuario:{id}:perfil`: campos leíbles por separado; TTL 900 s |
| **P8** | Emitir un voto MVP (una vez por usuario) | Usuario | `partido_id`, `usuario_id`, candidato | contó / ya había votado | Ráfagas (miles en pocos minutos) | **Dato propio del módulo** mientras la votación está abierta (ver ciclo de vida §5) | **SET** de votantes (unicidad) + **ZSET** de candidatos (ranking) |
| **P9** | Ver el ranking MVP | Cualquier usuario | `partido_id` | top-N con votos | Alta | Igual que P8 | **ZSET**: ya ordenado; `ZREVRANGE 0 N-1` es O(log n + N) |
| **P10** | Registrar una visita a un partido (tendencia) | Cada apertura de partido | `partido_id`, hora | — | **Muy alta** | **Temporal**: sólo importa la hora en curso | **ZSET** por hora `f30:rank:tendencia:{yyyymmddHH}`: `ZINCRBY` atómico y ranking sin ordenar en la app |
| **P11** | Partidos más vistos ahora (RF9) | Portada de la app | hora actual | top-N partidos | Alta | Temporal | El mismo ZSET de P10 |

---

## 3. Qué queda fuera de Redis, a propósito

| Dato | Por qué no vive acá | Dónde vive |
|---|---|---|
| Credenciales y datos maestros del usuario | Redis no reemplaza a una base persistente (enunciado §7): perder la caché no puede perder cuentas | MongoDB N4 |
| Ficha oficial y marcador de un partido | El marcador oficial debe ser CP (Hito 3, N2); Redis sólo guarda una copia de vida corta | MongoDB N2 |
| Comentarios de un partido | Volumen y escritura intensiva: modelo columnar | Cassandra (Hito 6) |
| Relaciones entre eventos y jugadores | Consulta de grafo | Neo4j (Hito 5) |
| Resultado final de la votación MVP una vez cerrada | Si el negocio necesita conservarlo, debe pasar a la fuente de verdad al cerrar (ver ciclo de vida §5) | MongoDB (fuera del alcance de este hito) |

## 4. Consultas que este módulo **no** resuelve

- "Todas las sesiones activas del torneo": exigiría recorrer todo el keyspace (RNF8). Si el producto lo pidiera, se mantendría un contador (`INCR`/`DECR`) o un ZSET por región, no una búsqueda.
- "Sesiones por dispositivo o por región": no hay índice secundario; no está en los patrones declarados.
