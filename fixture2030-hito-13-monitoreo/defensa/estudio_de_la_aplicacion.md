# Estudio de la aplicación — para defenderla

Material de repaso para los tres integrantes. La consigna exige que **cualquiera pueda responder sobre cualquier módulo**, así que acá está el sistema completo por dentro: qué hace cada pieza, cómo está construida, qué números hay que saber y qué preguntas difíciles pueden venir.

Complementa (no repite) a:
- [`../docs/defensa_final.md`](../docs/defensa_final.md): la frase central y las respuestas cortas a las preguntas de la consigna.
- [`../docs/decisiones_de_arquitectura.md`](../docs/decisiones_de_arquitectura.md): la ficha de cada base (por qué vive ahí cada dato).
- [`guion_de_20_minutos.md`](guion_de_20_minutos.md) y [`demo.md`](demo.md): qué se dice y qué se muestra.

**Cómo estudiarlo.** Primero §1–§3 (el sistema entero, 20 min). Después §4 completo, aunque no hayas hecho esa base. Después §5–§6 (la API por dentro, que es lo que más se pregunta). Al final, §11 (números) y §13 (autoevaluación en voz alta, sin mirar).

---

## 1. El sistema en un dibujo

```
            Hincha (front web/)      Swagger · Postman · curl      k6 (Hito 12)
                     │                         │                       │
                     └────────────┬────────────┴───────────────────────┘
                                  ▼
                 API REST integrada — FastAPI, Python 3.12, un proceso
                 routes/ → services/ → adapters/ (uno por base) + /metrics
                                  │
   ┌──────────────┬───────────────┼───────────────┬────────────────┐
   ▼              ▼               ▼               ▼                ▼
 MongoDB        Neo4j          Cassandra        Redis          InfluxDB 3 Core
 documental     grafo          columnar         clave-valor    series temporales
 N1 equipos y   N2 partidos    N6 comentarios   N5 sesiones    N7 estadísticas
 jugadores      N3 eventos                      + caché del     en vivo
                N8 tipos                        partido

   ▲ todo lo mira Prometheus (exporters, agente JMX, sondas, /metrics de la API) → Grafana (5 dashboards) + 8 alertas
```

**Idea que hay que poder decir sin pensar:** cada dato tiene un acceso dominante distinto y vive en el modelo que mejor resuelve ese acceso. La API es la única que integra: **cada ruta consulta una sola base** (salvo el detalle de partido, que usa Neo4j + la caché de Redis) y no hay transacciones entre bases. Por eso **si una base se cae, solo falla su módulo**, y eso está medido (prueba de falla de Redis).

**IRIS (objetos)** se implementó en un hito pero **salió de la arquitectura** en la reentrega del Hito 3, con el OK del profesor del 13/10/2026: Partidos y Tipos de evento estaban duplicados en IRIS y en Neo4j, y la duplicación ya había producido un calendario inconsistente (`PAR-A-1` con equipos distintos en cada base).

## 2. Mapa del repositorio (y la trampa de la numeración)

Las carpetas no siguen la numeración de la guía del TPO. Si preguntan "¿dónde está el Hito X?", esta es la tabla:

| Carpeta | Qué es | Número en la guía |
|---|---|---|
| `docs/hito-1…`, `hito-2…`, `hito-3…` | Análisis de requisitos, matriz de decisión, arquitectura distribuida y CAP | 1, 2, 3 |
| `fixture2030-mongodb/` | N1 Equipos y jugadores | 4 |
| `fixture2030-neo4j/` | N3 Eventos (y, desde la reentrega, N2 y N8) | 5 |
| `fixture2030-cassandra/` | N6 Comentarios | 6 |
| `fixture2030-redis/` | N5 Sesiones y caché | 7 |
| `fixture2030-influxdb/` | N7 Estadísticas en vivo | 8 |
| `fixture2030-iris/` | Modelo de objetos (histórico, fuera de la arquitectura) | "Hito 9" del repo |
| `fixture2030-replicacion-cap/` | Replica set de MongoDB y anillo de Cassandra, failover | **Hito 9 de la guía** |
| `fixture2030-hito10-api/` | API REST integrada + front web | 10 |
| `fixture2030-hito11-conectividad/` | Diagnóstico de conectividad por capas de la API | 11 del repo |
| `fixture2030-carga-masiva/` | Carga del volumen completo en las 5 bases | **Hito 11 de la guía** |
| `fixture2030-hito12-carga/` | Prueba de carga de la API con k6 y una optimización | 12 |
| `fixture2030-hito-13-monitoreo/` | Prometheus + Grafana y la defensa | 13 |

Índice de verdad de cada necesidad N1–N9: [`docs/ESTADO-CANONICO-NECESIDADES.md`](../../docs/ESTADO-CANONICO-NECESIDADES.md).

## 3. Las nueve necesidades y dónde quedó cada una

| # | Necesidad | Modelo (Hito 2) | Hoy | Consistencia (Hito 3) |
|---|---|---|---|---|
| N1 | Equipos y jugadores | Documental · MongoDB | Implementada | CP en escritura, AP en lectura |
| N2 | Partidos | Objetos → **Grafo · Neo4j** (reentrega) | Implementada | **Cierre CP**; ingesta de eventos AP |
| N3 | Eventos | Grafo · Neo4j | Implementada | AP con orden causal |
| N4 | Usuarios | Documental · MongoDB | **No implementada** | AP + consistencia de sesión |
| N5 | Sesiones | Clave-valor · Redis | Implementada | AP, TTL, local por región |
| N6 | Comentarios | Columnar · Cassandra | Implementada | AP, N=3 R=1 W=1 |
| N7 | Estadísticas en vivo | Series temporales · InfluxDB | Implementada | AP, orden monótono por partido |
| N8 | Tipos de evento | Objetos → **Grafo · Neo4j** (reentrega) | Implementada (12 `:TipoEvento`) | Fuerte sobre el catálogo |
| N9 | Auditoría e históricos | Columnar · Cassandra (otro keyspace) | **No implementada** | AP, W=QUORUM |

N4 y N9 son una pregunta probable: ver §12.

---

## 4. Cada base por dentro

Para cada una: qué guarda, cómo está modelada, cómo la usa la API y dónde mirar el código.

### 4.1 MongoDB — equipos y jugadores (N1)

- **Datos:** 64 equipos y 1.664 jugadores (26 por equipo, fijo, por corrección del profesor al Hito 4).
- **Modelo:** colecciones `equipos` y `jugadores`, con validación de esquema (`fixture2030-mongodb/init/01-validators.js`). `_id` del equipo = código FIFA (`ARG`). Índice `{equipoId: 1, posicion: 1}` para el plantel.
- **Carga:** `fixture2030-mongodb/load/seed.js`, **determinista** (sin aleatoriedad: el DNI sale de una fórmula). Correrla dos veces da el mismo resultado: eso fue una corrección del profesor.
- **Cómo la usa la API:**
  - `GET /equipos/{codigo}` → `find_one({_id})` con proyección (nunca devuelve el documento entero).
  - `GET /equipos/{codigo}/jugadores` → `find` con `hint` al índice, orden por dorsal y un cursor opaco que codifica el último dorsal.
- **Por qué documental:** se lee el equipo completo de una vez desde seis países y casi no cambia durante el torneo.
- **Replicación medida** (`fixture2030-replicacion-cap/`): replica set de 3 nodos. Si se mata el primario, se elige uno nuevo a los 9,99 s, con 0 escrituras perdidas de 226. Si se lo detiene ordenadamente, cede el lugar en 0,59 s. Para que la escritura sea realmente CP hace falta `w: "majority"`: con `w: 1` (el default) no alcanza, y eso corrige un detalle del Hito 3.

### 4.2 Neo4j — partidos, eventos y tipos de evento (N2, N3, N8)

- **Datos:** 127 partidos (grupos → final), 1.572 eventos y 12 `:TipoEvento`. También hay 1.282 jugadores y 64 equipos propios del grafo (ver H1 en §12). La **final** (`PAR-FINAL`) está `PROGRAMADO` y sin eventos.
- **Modelo:**
  - Nodos `:Equipo`, `:Jugador`, `:Partido`, `:Sede`, `:Grupo`, `:Evento` y `:TipoEvento`, con restricciones de unicidad (`fixture2030-neo4j/queries/estructura.cypher`).
  - Relaciones principales:
    - `(Equipo)-[:PARTICIPA_EN {condicion: LOCAL|VISITANTE}]->(Partido)`
    - `(Partido)-[:SE_JUEGA_EN]->(Sede)`
    - `(Evento)-[:OCURRE_EN]->(Partido)`
    - `(Evento)-[:ES_DE_TIPO]->(TipoEvento)`
    - `(Evento)-[:SIGUIENTE_EVENTO]->(Evento)`: la cadena ordenada del partido
    - `(Evento)-[:PROTAGONIZADO_POR]->(Jugador)`
    - `CAUSA_DE` entre eventos, y las del enunciado: `ANOTA`, `ASISTE`, `RECIBE_TARJETA` y `REEMPLAZA`.
- **El marcador no se guarda mientras se juega:** se **deriva contando los eventos `GOL`** por `condicionEquipo`. Así no puede haber un marcador que contradiga los eventos.
- **Carga:** `carga.cypher` con `MERGE` (idempotente).
- **Cómo la usa la API:**
  - Lecturas: partidos de un equipo, detalle del partido y timeline de eventos ordenada por `secuencia`. Todo el Cypher es parametrizado y los recorridos están acotados (un partido y sus vecinos).
  - **Alta de evento** (`POST /partidos/{id}/eventos`): una transacción de escritura que (1) toma un bloqueo sobre el `:Partido`, lo que serializa altas concurrentes; (2) chequea idempotencia, que el partido no esté finalizado, que no haya ya un `FIN_PARTIDO`, que el minuto no retroceda y que el tipo exista; (3) crea el evento con `secuencia = max + 1` y sus relaciones.
  - **Cierre** (`PATCH /partidos/{id}/estado`): transacción que exige `PROGRAMADO` y un `FIN_PARTIDO`, cuenta los `GOL` y fija estado, goles y `cerradoEn`. **Es la operación CP del Hito 3:** no puede haber dos resultados oficiales.
- **Reglas por tipo de evento (N8):** qué campos lleva un `GOL`, un `CORNER` o un `INICIO_PARTIDO` se valida **en la API** (`services/eventos.py`), no en la base. El motor solo garantiza que el tipo exista y sea único. Trade-off aceptado: la API es el único camino de escritura.
- **Por qué grafo:** recorridos ("quién asistió el gol del minuto 80", la cadena de eventos) y relaciones partido–equipo–sede.
- **Supernodos:** cada `:TipoEvento` acumula relaciones (`PASE` ya tiene 294). Las consultas arrancan desde el partido, nunca desde el tipo.
- **Límite de la edición Community:** una sola instancia, sin réplicas, y no expone métricas en Prometheus. Para el monitoreo se escribió un exporter propio (`neo4j-exporter/neo4j_exporter.py`).

### 4.3 Cassandra — comentarios (N6)

- **Datos:** 1.050.000 comentarios en la carga masiva (2.100.000 filas, porque se guardan en dos tablas).
- **Modelo** (`fixture2030-cassandra/scripts/esquema.cql`, keyspace `fixture2030_comentarios`):

```
comentarios_por_partido   PRIMARY KEY ((partido_id, ventana, bucket), creado_en DESC, comentario_id)
comentarios_por_usuario   PRIMARY KEY ((usuario_id, mes), creado_en, comentario_id)
config_particion_partido  PRIMARY KEY (partido_id)   → buckets, ventana_minutos, inicio
interacciones_por_comentario
```

- **La clave de partición es la decisión más importante del sistema:**
  - `ventana` = el `creado_en` redondeado hacia abajo a 10 minutos.
  - `bucket` = `crc32(comentario_id) % buckets`.
  - En el minuto 90 de un partido caliente, las escrituras **no caen todas en la misma partición** (hotspot): se reparten entre los buckets de esa ventana.
  - Los partidos de audiencia MÁXIMA tienen más buckets (`PAR-D16-01`, ARG–BEL, tiene 4).
- **Resultado medido de esa decisión:** `PAR-D16-01` tiene 300.000 comentarios (32 veces el promedio), pero su partición más grande queda en 16.161 filas y 2,3 MB. Sin ventana ni buckets sería una sola partición de 300.000 filas.
- **Cómo lee la API** `GET /partidos/{id}/comentarios` (`services/comentarios.py`):
  1. Lee la configuración del partido (Q0): cuántos buckets, de cuánto es la ventana y a qué hora empieza.
  2. Calcula las ventanas del partido (de −15′ a +125′ desde el inicio).
  3. Empieza por la ventana más reciente y lee **todos sus buckets en paralelo**.
  4. Mezcla los resultados ordenando por `creado_en` descendente.
  5. Devuelve un **cursor opaco** (versión, huella del partido, ventana y posición) para pedir la página siguiente.

  En `PAR-D16-01` son **5 llamadas a Cassandra por GET**: Q0 + 4 buckets.
- **Cómo escribe** `POST /partidos/{id}/comentarios`:
  - Un `LOGGED BATCH` con las dos tablas: quedan las dos iguales o ninguna.
  - El `comentario_id` sale de un hash del usuario y la `Idempotency-Key`, así que un reintento escribe la misma clave primaria. En Cassandra un `INSERT` es un upsert: no se duplica.
- **Consistencia:** `LOCAL_ONE` en la API (R=1, W=1 del Hito 3): AP, eventual.
- **Por qué no LWT (`IF NOT EXISTS`) para la idempotencia:** usa Paxos y contradice el W=1 elegido para aguantar el pico de escritura.
- **Replicación medida** (anillo de 3 nodos, RF=3):
  - Con un nodo caído, ONE y QUORUM siguen escribiendo y leyendo; ALL falla.
  - **Consistencia eventual vista en vivo:** con W=ONE y un nodo caído durante la escritura, al volver ese nodo lee 0 filas. Recién lee 1 después del hinted handoff (13 s) o de un `nodetool repair`.

### 4.4 Redis — sesiones y caché (N5)

- **Claves:**
  - `f30:ses:{id}`: HASH con **TTL deslizante de 1.800 s** (30 min) y tope absoluto de 12 h.
  - `f30:usr:{usuario}:sesiones`: SET que funciona como índice de las sesiones de cada usuario.
  - `f30:cache:partido:{id}`: STRING JSON con `SET … EX 60`.
- **Cómo la usa la API:**
  - `GET /sesiones/{id}` → `HGETALL` + `TTL` en un pipeline. **No renueva** el TTL. Si la sesión está bloqueada, responde 403.
  - `DELETE /sesiones/{id}` → `WATCH` + `MULTI` (`SREM` del índice + `DEL` de la sesión) + `EXEC`: atómico, sin Lua.
  - **Cache-aside del detalle de partido** (`GET /partidos/{id}`): si la copia está en Redis responde `X-Cache: HIT`; si no, lee Neo4j, guarda la copia por 60 s y responde `MISS`. Si Redis falla, responde `BYPASS` y sigue con Neo4j: **la caché caída nunca da un error**. Las escrituras sobre el partido (alta de evento, cierre) borran la copia.
- **Carrera conocida y aceptada:** un `MISS` que lee justo antes de un cierre y escribe la copia después del `DEL` deja un dato viejo hasta 60 s. Es la ventana de frescura que aceptó el Hito 7.
- **Por qué sin réplica entre regiones, a propósito:** perder una sesión solo obliga a volver a entrar. Replicarla entre regiones agrega latencia a cada request para proteger un dato descartable.
- **Volumen:** 100.000 usuarios en la carga masiva ≈ 61 MB. Con el `maxmemory` de 256 MB entrarían unos 400.000 usuarios simultáneos antes de empezar a desalojar claves.
- **Prueba de falla del Hito 13:** con Redis caído, las sesiones dan 503 y MongoDB sigue en 200. La caída se detectó a los 10 s, la alerta saltó a los 72 s y la API se recuperó 13 s después del `docker start`, sin reiniciarla.

### 4.5 InfluxDB 3 Core — estadísticas en vivo (N7)

- **Datos:** 10.094.400 puntos, cargados en ~46 s en la carga masiva. Bases `fixture2030_vivo` (detalle por segundo, retención de 45 días) y `fixture2030_historico` (resúmenes, sin vencimiento). La API lee la tabla `estadisticas_equipo`.
- **Cómo la usa la API** `GET /partidos/{id}/estadisticas?desde&hasta&agregacion=raw|1m|5m`:
  - SQL por HTTP (`/api/v3/query_sql`) con parámetros.
  - El intervalo de `date_bin` sale de un diccionario cerrado, nunca del texto del cliente.
  - Agrega con `last_value` para la posesión y `max` para los acumulados (sumar acumulados daría un número inventado).
  - La ventana máxima es de 3 h.
- **Token:** la API lo lee de un archivo local fuera de git (`fixture2030-influxdb/secrets/admin-token.json`). Nunca va al repo ni a los logs.
- **Vacío vs. caído:** un 200 con `[]` es "no hay datos". Un error de token, de base o de tabla se responde como 503, nunca como lista vacía.
- **Límites de la edición Core:**
  - No replica, así que la réplica de N7 que pedía el Hito 3 no es implementable con esta edición.
  - No compacta: con ~1.000 archivos Parquet, una consulta sobre todo el torneo superó el tope de archivos por consulta. Por eso las consultas se acotan por tiempo y los resúmenes van a la base histórica.

---

## 5. La API por dentro (`fixture2030-hito10-api/`)

### 5.1 Capas

```
routes/    contrato HTTP: valida path/query/body con Pydantic, elige el código de estado. 2–3 líneas por ruta.
services/  casos de uso: reglas (p. ej. reglas por tipo de evento), cursores, decide 404/409.
           ports.py define con Protocol qué espera de cada adaptador.
adapters/  uno por base: conexión, consulta parametrizada, mapeo, traducción de errores.
core/      errores, X-Request-Id, logs JSON, inyección de dependencias, métricas.
```

**Por qué importa:** los servicios no conocen el driver. Los tests unitarios reemplazan los adaptadores por falsos (`tests/unit/fakes_*.py`) y corren **sin Docker**. Cambiar un driver no toca rutas ni servicios.

### 5.2 La pieza común: `adapters/base.py::ejecutar`

Toda operación contra cualquier base pasa por acá:
- **timeout** propio por base → si se pasa, **504** `DEPENDENCY_TIMEOUT`;
- **excepción de disponibilidad del driver** → **503** `DEPENDENCY_UNAVAILABLE`, nunca un 200 vacío;
- una línea de log por operación, con dependencia, operación, resultado, duración y motivo, **sin parámetros ni datos**.

**Conexiones perezosas:** la API arranca aunque una base esté caída. Esa base responde 503 y, cuando vuelve, la API la toma sin reiniciarse.

### 5.3 Errores

Hay un formato único para todos los errores: `{code, message, requestId, details}`. El `requestId` es el mismo que el header `X-Request-Id` y que el de las líneas de log de esa request: con eso se correlaciona un error con su log.

Reglas que se cumplen siempre:
- La validación responde **400** (no el 422 por defecto de FastAPI).
- Los mensajes nunca muestran hosts, credenciales, consultas ni trazas.
- Un error inesperado responde 500 con un mensaje fijo.

Códigos que conviene saber de memoria:

| Código | Cuándo |
|---|---|
| `TEAM_NOT_FOUND` | 404, el equipo no existe |
| `MATCH_NOT_FOUND` | 404, el partido no existe |
| `EVENT_RULE_VIOLATION` | 400, p. ej. un `GOL` sin dorsal |
| `INVALID_TRANSITION` | 409, cerrar un partido que ya está cerrado |
| `MISSING_FIN_PARTIDO` | 409, cerrar sin el evento `FIN_PARTIDO` |
| `IDEMPOTENCY_KEY_REUSED` | 409, misma clave con otro cuerpo |
| `COMMENT_OUTSIDE_MATCH_WINDOW` | 400, comentario fuera del tramo del partido |
| `SESSION_BLOCKED` | 403, sesión bloqueada |

Detalle en `docs/contratos_y_errores.md`.

### 5.4 Idempotencia (los dos POST exigen `Idempotency-Key`)

| Escritura | Cómo se evita el duplicado |
|---|---|
| Evento (Neo4j) | `eventoId` = hash de la clave. Se guarda la `huella` del cuerpo: misma huella → 200 replay; otra huella → 409 |
| Comentario (Cassandra) | La clave primaria sale de la clave de idempotencia y del `creadoEn`, y el upsert no duplica |
| Cierre (Neo4j) | No usa clave: es una transición con precondición. El reintento da 409 sin cambiar nada |
| Borrar sesión (Redis) | El efecto ya es idempotente; el reintento da 404 |

El front genera la clave **por intento lógico, no por envío** (`web/src/hooks/useIdempotentSender.ts`): un doble clic manda la misma clave.

### 5.5 Salud y métricas

- `GET /health`: el proceso vive.
- `GET /health/ready`: "lista" si MongoDB y Neo4j responden (las esenciales). "Lista degradada" si falla otra.
- `GET /health/dependencias`: las cinco bases, con estado, latencia y motivo de la falla (`conexion`, `timeout`, `autenticacion` o `contexto`). IRIS aparece como `NOT_CONFIGURED`.
- `GET /metrics` (`core/metricas.py`): requests por ruta y status, latencia de cada request y **latencia de cada base vista desde la API**. Es lo que permite separar "la API está lenta" de "la base está lenta".

### 5.6 Contrato y pruebas

- `openapi/openapi.yaml` **se genera desde el código**, y un test falla si el archivo y el código no coinciden (drift).
- schemathesis lo contrasta contra el servidor real, y Newman corre la colección de Postman.
- Hay pruebas unitarias sin Docker, de integración contra las bases reales y de "dependencia caída" para cada base (`docs/evidencia/dependencia_caida_*.md`).

## 6. Dos recorridos completos (para explicarlos en voz alta)

**Leer comentarios:** `GET /partidos/PAR-D16-01/comentarios?limit=50`
1. El middleware asigna un `X-Request-Id`. Pydantic valida el `partidoId` contra un patrón y el `limit` entre 1 y 50.
2. El servicio lee la configuración del partido: Q0 en Cassandra o, con `COMENTARIOS_CONFIG_CACHE_S > 0`, la caché en memoria del Hito 12. Si el partido no tiene configuración → 404.
3. Calcula las ventanas del partido y empieza por la más reciente. Lee sus 4 buckets en paralelo, cada uno con la clave de partición completa (nunca un escaneo), y los mezcla por `creado_en`.
4. Si no alcanzó el `limit`, pasa a la ventana anterior. Arma el cursor.
5. Responde 200 con `items` y `nextCursor`. Se registran la métrica de la request y la de cada llamada a Cassandra.

**Cargar un gol y cerrar el partido:**
1. `POST /partidos/PAR-DEMO-API/eventos` con `Idempotency-Key` y `{"tipo":"GOL","minuto":70,"condicionEquipo":"VISITANTE","dorsalProtagonista":9}`.
2. Pydantic valida los campos. El servicio aplica las reglas del tipo (un `GOL` exige equipo y dorsal) y, si no las cumple, responde 400 sin tocar Neo4j.
3. Transacción en Neo4j: bloqueo del partido → ¿la clave ya existe? → ¿partido finalizado? → ¿ya hay `FIN_PARTIDO`? → ¿el minuto retrocede? → crea el evento con `secuencia = max + 1` y sus relaciones.
4. Se borra la copia en caché del partido en Redis. Si Redis no responde, la escritura no falla: la copia vence sola en 60 s.
5. Responde 201. El mismo POST repetido responde 200 con `Idempotent-Replayed: true`.
6. `POST … {"tipo":"FIN_PARTIDO","minuto":90}` y después `PATCH /partidos/PAR-DEMO-API/estado {"estado":"FINALIZADO"}`: cuenta los `GOL` y fija el marcador. Repetir el cierre da 409 `INVALID_TRANSITION`.

## 7. El front (`fixture2030-hito10-api/web/`)

- React + TypeScript + Vite. El diseño viene de Google Stitch (`stitch/DESIGN.md`, `PRODUCT.md`). El enunciado no lo pedía; el profesor dijo que se podía hacer.
- **Los tipos se generan del contrato OpenAPI** (`npm run gen:api` → `src/api/schema.d.ts`): si la API cambia, el front no compila.
- **Pantallas del hincha:**
  - `/`: inicio, con buscador por código FIFA.
  - `/equipos/:codigo`: ficha, plantel y partidos del equipo.
  - `/partidos/:id`: pestañas de eventos y comentarios, estadísticas y alineaciones.
- **Vistas de operación**, a las que se llega por URL: `/partidos/:id/mesa` (alta de eventos y cierre), `/sesiones/:id` y `/salud`.
- **El hincha no ve qué base guarda cada dato:** las pantallas no nombran ninguna base. Cada panel falla por separado: si se cae Cassandra, la línea de tiempo de eventos sigue funcionando.
- **Estados diseñados:** cargando, vacío (la final sin eventos), no encontrado (`/equipos/URU`, por H1), dato inválido y fuente no disponible (con botón de reintento y el ID de solicitud). Capturas en `docs/evidencia/front-stitch/`.

## 8. Carga masiva (Hito 11 de la guía, `fixture2030-carga-masiva/`)

- **Qué hace:** un orquestador (`scripts/orquestador.py`) carga el volumen completo en las cinco bases, **con el cargador de cada módulo, sin reescribirlo**, en modo paralelo o secuencial. Después valida la integridad (incluidos los cruces entre bases), reporta tiempos y recursos y analiza cómo quedaron distribuidos los datos.
- **Aislamiento:** todo lo que levanta se llama `f30cm-*`, usa puertos propios y empieza desde volúmenes vacíos. No toca las instancias compartidas.
- **Resultados (14/11/2026):**

| | Paralelo | Secuencial |
|---|---:|---:|
| Reloj hasta la última carga | 382,6 s | **324,5 s** |
| Cassandra | 188,1 s | 133,7 s |
| InfluxDB (10 M puntos) | 46,3 s | 46,4 s |
| Chequeos de integridad | 25/26 | 25/26 |

- **El paralelo fue más lento.** Con la memoria libre en la VM de Docker, solo MongoDB y Redis entraron juntos; el resto corrió de a una, como en el secuencial. Además, Cassandra tiene mucha dispersión entre corridas (153–169 s con la misma configuración). La primera corrida, con las cinco bases a la vez, **colgó Docker Desktop 37 minutos**. Desde entonces hay `mem_limit` por contenedor, admisión por presupuesto de memoria y un vigía que corta la corrida si falta memoria.
- **El chequeo que falla (1 de 26) es H1:** 12 de los 64 equipos no coinciden entre MongoDB y Neo4j. Todos los `partido_id` de Cassandra, Redis e InfluxDB sí existen en Neo4j (0 faltantes).
- **Optimización:** se probó la concurrencia del cargador de Cassandra, con 3 repeticiones por valor. Medianas: 128 → 158,3 s; **256 → 120,7 s (−23,8 %)**; 512 → 157,9 s. Una de las tres corridas con 256 quedó igual que las de 128, así que la mejora es **probable pero no demostrada**, y no se cambió el valor por defecto.

## 9. Prueba de carga de la API (Hito 12, `fixture2030-hito12-carga/`)

- **Flujo:** el pico de comentarios después de un gol en `PAR-D16-01`, pasando por la API hacia Cassandra. 80 % lecturas y 20 % publicaciones, generado con k6.
- **Línea base:** 364 req/s con 0 % de errores. Integridad verificada leyendo Cassandra directo: escritos = confirmados, sin duplicados.
- **Optimización:** la caché en memoria de la configuración de partición (Q0), activable con una variable. Mismo código, cambia solo esa variable.
  - Eliminó el **99,98 %** de las lecturas de Q0 (58.281 → 13) y bajó un 7 % la CPU de Cassandra.
  - **No se afirma mejora de latencia:** quedó dentro de la variación entre corridas.
- **Hipótesis H2:** el límite es la CPU de la API (~95 %), no Cassandra. El Hito 13 la confirmó con métricas: Cassandra responde con p99 de 1,1 ms por dentro, mientras la API tarda 42–91 ms al 97 % de CPU.
- **Limpieza entre corridas:** cada corrida escribe ~12.000 comentarios en la ventana pico. Sin limpiar, la segunda corrida trabaja sobre una partición más grande y la comparación cambia de signo (se comprobó).

## 10. Monitoreo (Hito 13, esta carpeta)

- **Prometheus** lee 9 jobs cada 15 s y guarda 15 días. Hay 13 targets.

| Job | Qué lee |
|---|---|
| `prometheus` | Prometheus mismo |
| `node-exporter` | Infraestructura |
| `mongodb` | Exporter de MongoDB |
| `redis` | Exporter de Redis |
| `cassandra` | Agente JMX |
| `neo4j` | Exporter propio |
| `influxdb` | `/metrics` de InfluxDB, con token |
| `salud-bases` | Sondas TCP/HTTP del blackbox exporter a las cinco bases |
| `fixture-api` | `/metrics` de la API |

- **Grafana:** 5 dashboards: 1. Resumen y SLAs · 2. API integrada · 3. Comparación entre bases · 4. Bases por dentro · 5. Infraestructura.
- **Cómo se diagnostica una latencia alta:** dashboard 2 (p95 por ruta) → 3 (cada base vista desde la API) → 4 (la base por dentro). Si la base por dentro está rápida y vista desde la API está lenta, el problema es la API.
- **8 alertas:**
  - `BaseNoResponde`
  - `TargetSinScrape`
  - `ApiErroresAltos`
  - `ApiLatenciaAlta`
  - `CassandraEscriturasEncoladas` (más de 100 tareas pendientes en MutationStage)
  - `Neo4jNoResponde`
  - `Neo4jConsultaLenta`
  - `InfluxDBEscriturasRechazadas`

  Cada alerta tiene riesgo y responsable en `docs/alertas_y_umbral.md`.
- **Medido, exporter o inferido:** la consigna pide distinguir de dónde sale cada métrica.
  - Directo: la API mide sus requests.
  - Exporter: MongoDB, Redis, Cassandra por JMX, InfluxDB.
  - Sonda: disponibilidad TCP/HTTP.
  - Exporter propio limitado: Neo4j Community solo deja consultar algunas cosas.

---

## 11. Números para saber de memoria

| Qué | Número |
|---|---|
| Equipos / jugadores (MongoDB) | 64 / 1.664 (26 por equipo) |
| Partidos / eventos / tipos (Neo4j) | 127 / 1.572 / 12 |
| Comentarios (Cassandra) | 1.050.000 (2,1 M filas en dos tablas) |
| Usuarios con sesión (Redis) | 100.000 (~61 MB) |
| Puntos (InfluxDB) | 10.094.400 |
| Partido caliente | `PAR-D16-01` (ARG–BEL): 300.000 comentarios, 4 buckets, partición máxima de 16.161 filas / 2,3 MB |
| Partición de comentarios | `(partido_id, ventana de 10 min, bucket)` |
| N/R/W de comentarios | 3 / 1 / 1 (en la API, `LOCAL_ONE`) |
| TTL de sesión / caché de partido | 1.800 s deslizante, tope de 12 h / 60 s |
| Hito 12 | 364 req/s, 0 errores; caché Q0 −99,98 % de lecturas |
| Hito 13, carga observada | ~400 req/s; Cassandra p99 1,1 ms por dentro; API 42 ms p50 / 91 ms p95 al 97 % de CPU |
| Prueba de falla de Redis | detectada a 10 s, alerta a 72 s, recuperada 13 s después del start |
| Carga masiva | secuencial 324,5 s · paralelo 382,6 s · integridad 25/26 |
| Failover MongoDB | elección a 9,99 s (`kill`), 0 escrituras perdidas |
| Cassandra, consistencia eventual | 0 filas → 1 tras el hinted handoff (13 s) |
| Escala del problema real | 2–3 M de usuarios, picos de >100.000 req/s. **Medido: ~400 req/s en una notebook** |

## 12. Preguntas difíciles que no están en `defensa_final.md`

**¿Por qué Partidos en Neo4j si la matriz del Hito 2 decía Objetos?**
La matriz le daba a Objetos un margen de solo **0,10** sobre la segunda opción, o sea, una decisión frágil. Al implementar, Partidos quedó duplicado en IRIS y en el grafo (los eventos ya vivían en el grafo y necesitan al partido) y produjo un calendario inconsistente real. La reentrega del Hito 3 lo movió y el profesor la aprobó. El cierre sigue siendo CP: lo garantiza una transacción de Neo4j.

**¿Por qué no implementaron N4 (Usuarios) ni N9 (Auditoría)?**
Los hitos de implementación se organizaron por modelo, no por necesidad ("el objetivo es que para los hitos desarrolles y practiques cada modelo", dijo el profesor), y N1, N3, N5, N6 y N7 cubren los cinco motores vigentes. N4 iría en MongoDB (otra colección, mismo motor que N1) y N9 en Cassandra (otro keyspace con su propia partición y W=QUORUM). No agregan un modelo nuevo, sino más del mismo. Hoy lo más cercano a usuarios son los 100.000 perfiles cacheados con sesión en Redis. Respuesta honesta: es alcance pendiente, no una contradicción del diseño.

**¿Los equipos de MongoDB y de Neo4j son los mismos? (H1)**
No del todo: 52 de los 64 códigos coinciden. Neo4j se generó en el Hito 5 con otro roster (`URU`/`URY`, `CHI`/`CHL` y países distintos). Se decidió no parchearlo a medias, y por eso **la API nunca cruza las dos bases por código de equipo**: la ficha sale de MongoDB y los partidos de Neo4j, por separado. La carga masiva lo detecta como el único chequeo de integridad que falla. Unificar el roster es el primer arreglo pendiente.

**¿Midieron replicación o es todo diseño?**
Se midió **por separado**, en `fixture2030-replicacion-cap/`:
- Replica set de MongoDB de 3 nodos, con failover sin escrituras perdidas.
- Anillo de Cassandra de 3 nodos con RF=3: niveles ONE/QUORUM/ALL con un nodo caído y consistencia eventual observada.

El sistema integrado que se defiende (API + monitoreo) corre con **un nodo por base**. Multirregión, Neo4j con réplicas (Enterprise) e InfluxDB replicado (Core no replica) siguen siendo diseño.

**¿Qué corrigió la prueba de replicación respecto del Hito 3?**
Tres cosas:
1. "La escritura confirma en el primario" no alcanza para que MongoDB sea CP: hace falta `w: "majority"`.
2. Neo4j Community no puede confirmar eventos por mayoría.
3. InfluxDB 3 Core no replica.

Además apareció una tarea de operación que el Hito 3 no tenía: `nodetool repair` periódico en Cassandra.

**¿Por qué el `creadoEn` del comentario lo manda el cliente?**
El torneo es de 2030 y el reloj es simulado. El comentario tiene que caer dentro de las ventanas del partido (de −15′ a +125′); si no, se rechaza con 400. Además, `creadoEn` forma parte de la clave primaria, y por eso un reintento idéntico no duplica.

**¿Qué pasa si dos personas cargan un evento del mismo partido a la vez?**
La transacción toma un bloqueo de escritura sobre el `:Partido`: las dos altas se serializan. No hay secuencias repetidas ni dos `FIN_PARTIDO`.

**¿Por qué el modo paralelo de la carga masiva fue más lento?**
Por memoria: la VM de Docker tenía ~2,5 GiB de presupuesto, solo dos bases entraron juntas y Cassandra varía mucho entre corridas. Paralelizar sin recursos no acelera; la primera corrida en paralelo total colgó Docker. Es un resultado, no un error, y está documentado.

**¿Por qué Neo4j Community y no Enterprise?**
Es la edición libre para el laboratorio. El costo está documentado: sin réplicas, sin métricas para Prometheus (se escribió un exporter propio) y sin particionamiento horizontal. En producción el diseño pide Enterprise o un clúster equivalente.

**¿Qué es lo primero que cambiarían para producción?**
1. Varios procesos de la API, porque es el límite medido, con la caché de Q0 activa para no multiplicar las lecturas a Cassandra.
2. Unificar el roster de equipos (H1).
3. `w: "majority"` en MongoDB.
4. Más nodos de Cassandra, subiendo los buckets de los partidos de audiencia máxima.
5. Autenticación en las escrituras (hoy están abiertas en `localhost`).

**¿La API tiene autenticación?**
No: es laboratorio, y está documentado en `docs/seguridad.md`. La sesión se consulta como recurso, no se usa como credencial. Lo que sí está cuidado:
- Cypher, CQL y SQL parametrizados.
- Validación antes de consultar.
- Errores sin datos internos.
- Secretos fuera del repo y de los logs.

## 13. Autoevaluación (responder en voz alta, sin mirar)

1. Dibujá el sistema y decí qué ruta usa dos bases.
2. ¿Cuál es la clave de partición de comentarios y qué problema resuelve? ¿Cuántas llamadas hace un GET en el partido caliente y por qué?
3. ¿Qué pasa, paso a paso, cuando se carga un `GOL` dos veces con la misma clave? ¿Y con otra clave?
4. ¿Por qué el cierre del partido es CP y los comentarios son AP? ¿Dónde se ve eso en el código?
5. Si Redis se cae, ¿qué endpoints fallan, cuáles siguen y qué pasa con el detalle de partido?
6. ¿Cómo distinguís, con Grafana, si la lentitud es de la API o de Cassandra?
7. ¿Qué diferencia hay entre 503 y 504 en esta API?
8. ¿Qué se midió en un nodo, qué se midió con réplicas y qué es solo diseño?
9. ¿Por qué salió IRIS y qué se perdió con eso?
10. ¿Qué es H1 y por qué la API no cruza MongoDB con Neo4j?
11. ¿Por qué la carga en paralelo no ganó?
12. ¿Qué optimización hicieron en el Hito 12, qué mejoró y qué **no** pueden afirmar?

---

## 14. Preguntas posibles de compañeros y del profesor

Las de §12 son las "trampa" de nuestro propio sistema. Estas son las que suele hacer alguien que lo ve por primera vez (compañeros) o que evalúa los conceptos de la materia (profesor). La respuesta es corta a propósito: decirla en 20–30 segundos y ofrecer mostrar la evidencia.

### 14.1 Del profesor (conceptos de la materia aplicados al TPO)

**¿Qué dice el teorema CAP y dónde lo aplicaron?**
Ante una partición de red, un sistema distribuido tiene que elegir entre consistencia y disponibilidad. No lo elegimos por sistema, lo elegimos **por operación**: el cierre del partido es CP (espera antes que confirmar dos resultados), y los comentarios, las sesiones y las estadísticas son AP (responden con lo local y reconcilian después). La misma base (Neo4j) tiene una operación CP (cierre) y otra AP (ingesta de eventos).

**¿Qué significan N, R y W, y por qué eligieron 3/1/1 para comentarios?**
N = copias del dato, W = cuántas tienen que confirmar una escritura, R = cuántas se consultan en una lectura. Con R + W > N la lectura siempre ve la última escritura; con 1 + 1 < 3 no, y lo aceptamos: un comentario que tarda unos segundos en aparecer no rompe nada, pero rechazar escrituras en el minuto 90 sí. Lo vimos en el laboratorio de replicación: con W=ONE y un nodo caído, ese nodo leyó 0 filas hasta el hinted handoff.

**¿Por qué solo Cassandra tiene N/R/W y no las otras?**
Porque es la única base de las nuestras con replicación sin líder y quórum configurable por operación. MongoDB tiene primario y secundarios (se habla de `writeConcern`/`readConcern`), Redis es local por región sin réplica, y para InfluxDB la corrección del profesor al Hito 3 fue dejar la réplica como conceptual, sin N/R/W.

**¿Qué es consistencia eventual y cómo la mostraron?**
Que, si no hay escrituras nuevas, todas las copias terminan iguales, pero no inmediatamente. Evidencia: `fixture2030-replicacion-cap/scripts/cassandra_consistencia_eventual.sh` (0 filas → 1 fila tras el hinted handoff, o tras `nodetool repair` si no hubo hints).

**¿Qué diferencia hay entre escalar vertical y horizontal, y qué base escala cómo?**
Vertical = una máquina más grande; horizontal = más máquinas. Cassandra escala horizontal (la clave de partición reparte los datos entre nodos); MongoDB escala lecturas con réplicas y escrituras con sharding (todavía no hace falta: 400 KB de datos); Neo4j Community solo vertical; Redis con Redis Cluster por hash slots; InfluxDB Core, vertical.

**¿Cómo modelaron en Cassandra? ¿Partieron de las entidades o de las consultas?**
De las consultas (query-first): una tabla por consulta. "Comentarios de un partido" y "comentarios de un usuario" son dos tablas con los mismos datos y distinta clave. Es desnormalización a propósito, y se escriben juntas en un `LOGGED BATCH` para que no queden distintas.

**¿Qué es una partición caliente (hotspot) y cómo la evitaron?**
Una partición que recibe mucho más tráfico que el resto y satura un solo nodo. Si la clave fuera solo `partido_id`, el partido de ARG en el minuto 90 iría todo a un nodo. Por eso la clave es `(partido, ventana de 10 min, bucket)`. Medido: el partido con 32 veces el promedio de comentarios no supera 16.161 filas por partición.

**¿Por qué embebieron o referenciaron en MongoDB?**
Los datos del equipo (ranking, grupo, DT) van embebidos porque se leen siempre juntos. Los jugadores van en otra colección con `equipoId` porque se paginan y se filtran por posición: embebidos en el equipo, el documento crecería y no se podría paginar con índice.

**¿Qué índices crearon y para qué consulta?**
MongoDB: `{equipoId: 1, posicion: 1}` para el plantel filtrado. Neo4j: restricciones de unicidad (que también son índices) sobre partido, evento, tipo, equipo, jugador, sede y grupo. Cassandra: no hay índices secundarios; el acceso es siempre por clave de partición completa. Redis: el SET `f30:usr:{usuario}:sesiones` hace de índice inverso.

**¿Qué ventaja concreta da el grafo frente a un documental para los eventos?**
Las preguntas son recorridos: el evento siguiente, quién asistió a quién, qué causó qué (`CAUSA_DE`). En un documental serían varias consultas y el armado en la aplicación; en el grafo es un patrón de Cypher acotado a un partido.

**¿Qué es el TTL y por qué es importante para las sesiones?**
Tiempo de vida de una clave: Redis la borra solo cuando vence. Las sesiones vencen a los 30 min sin uso (TTL deslizante) y como máximo a las 12 h. Sin TTL habría que programar un proceso de limpieza.

**¿Por qué series temporales para las estadísticas y no Cassandra, que también escribe rápido?**
Porque la consulta dominante es por rango de tiempo con agregación por minuto (`date_bin`), con retención automática (45 días para el detalle). InfluxDB lo trae resuelto; en Cassandra habría que modelar los cubos de tiempo y calcular los agregados a mano.

**¿Qué es idempotencia y por qué la necesitan?**
Que repetir la misma operación deje el mismo resultado. En una red, un cliente que no recibe respuesta reintenta: sin idempotencia, se duplica el gol o el comentario. Los POST exigen `Idempotency-Key` (ver §5.4).

**¿Cómo garantizan la integridad si no hay transacciones entre bases?**
No hace falta una transacción entre bases porque ninguna operación escribe en dos bases a la vez: cada escritura toca una sola (el borrado de la caché de Redis no es parte de la transacción y, si falla, la copia vence en 60 s). Los identificadores (`partido_id`, `usuario_id`) son compartidos y la carga masiva verifica que todo `partido_id` de Cassandra, Redis e InfluxDB exista en Neo4j.

**¿Qué es operacional y qué es analítico en su sistema?**
Operacional: todo lo que sirve la API en vivo. Analítico (diseñado, no implementado): el Data Mart del Hito 12, alimentado con el histórico de comentarios y los resúmenes de `fixture2030_historico`.

**¿Qué agrega Prometheus que no tengan los logs?**
Series numéricas en el tiempo, consultables (PromQL) y con alertas. Los logs dicen qué pasó en una request; las métricas dicen cuánto y con qué tendencia. Las usamos juntas: el `X-Request-Id` de un error lleva al log de esa request.

**¿Cuál es la diferencia entre p50, p95 y p99?**
Percentiles de latencia: el 50 %, 95 % o 99 % de las requests tardaron eso o menos. El promedio esconde la cola lenta; la experiencia del peor 5 % se ve en el p95. Por eso los SLAs y las alertas usan p95.

### 14.2 De compañeros (curiosidad práctica)

**¿Cinco bases no es demasiado para un proyecto así?**
Para el laboratorio, sí es más trabajo, y lo decimos (cinco formas de respaldar, monitorear, actualizar). Para el problema real (2–3 M de usuarios con accesos opuestos), una sola base degrada algún acceso. Y la ventaja se midió: si una se cae, el resto sigue.

**¿Por qué Python y FastAPI?**
Hay drivers oficiales para las cinco bases, FastAPI valida con Pydantic y genera el contrato OpenAPI desde el código, y es asíncrono, así que una request espera a la base sin bloquear a las otras. El costo medido: un proceso de Python usa un núcleo y fue el cuello de botella.

**¿Cómo se levanta todo?**
Cada base tiene su `docker compose up -d` en su carpeta; después `iniciar_monitoreo.sh` y `iniciar_api.sh`. La secuencia exacta está en [`demo.md`](demo.md) §1. Nunca `down -v` (borra los volúmenes).

**¿Cuánta memoria hace falta?**
Todo corrió en una Mac de 24 GB con una VM de Docker de 7,75 GiB. Solo el anillo de Cassandra de 3 nodos usa ~2,4 GB. La carga masiva con todo en paralelo colgó Docker: por eso tiene límites de memoria y un vigía.

**¿Los datos son reales?**
Son sintéticos y **deterministas**: cada cargador genera exactamente lo mismo en cada corrida (fue una corrección del profesor). Eso permite comparar corridas y verificar integridad con números exactos.

**¿Por qué el partido de ARG–BEL?**
`PAR-D16-01` es el partido que se definió como audiencia MÁXIMA en los Hitos 6 y 8: el caso peor para la escritura de comentarios. Todo lo que se prueba bajo carga se prueba ahí.

**¿Qué pasa si se cae la API?**
Hoy es un solo proceso: se cae todo el acceso, aunque las bases sigan bien. Es el punto único de falla del laboratorio; la mejora propuesta es varias instancias detrás de un balanceador.

**¿Por qué no usaron una base relacional?**
Ver `defensa_final.md`: el problema es escalar escrituras en picos y servir baja latencia desde seis países con datos de forma muy distinta. El Hito 12 tiene la comparación con una alternativa relacional (`fixture2030-hito12-carga/docs/comparacion_relacional.md`).

**¿El front habla directo con las bases?**
No: solo con la API. El front no sabe qué base guarda cada dato, y cada panel maneja su error por separado.

**¿Cómo probaron que funciona?**
Tests unitarios sin Docker (con adaptadores falsos), de integración contra las bases reales, contrato con schemathesis, Postman con Newman, pruebas de base caída para cada una, carga con k6 y la prueba de falla con Prometheus mirando.

**¿Qué fue lo más difícil?**
Respuesta sugerida (que cada uno la adapte): la partición de Cassandra con cursor sobre varios buckets, el cierre del partido sin condiciones de carrera, y que el monitoreo de Neo4j Community necesitó un exporter propio. Y en la carga masiva, que paralelizar sin memoria no acelera.

**¿Qué harían distinto si empezaran de nuevo?**
Definir un solo roster de equipos desde el principio (H1), y no implementar el modelo de objetos para un dato que ya vivía en el grafo (lo que llevó a sacar IRIS).
