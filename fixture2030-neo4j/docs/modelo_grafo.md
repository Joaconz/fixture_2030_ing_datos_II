# Modelo de grafo — Hito 5 · Fixture 2030

**Asignatura:** Ingeniería de Datos II · **Grupo 2**
**Integrantes:** Santiago Pazos, Valentina Frisoli, Joaquín Núñez
**Motor:** Neo4j (`neo4j:latest`, Community Edition) sobre Docker Compose

---

## 1. Visión general del subgrafo

```
                 (:Grupo)
                 ▲       ▲
      PERTENECE_A│       │CORRESPONDE_A
                 │       │
   (:Jugador)──JUEGA_EN──▶(:Equipo)──PARTICIPA_EN──▶(:Partido)──SE_JUEGA_EN──▶(:Sede)
        ▲                                               ▲
        │PROTAGONIZADO_POR                              │OCURRE_EN
        │                                               │
        └──────────────────────(:Evento)────────────────┘
                                 │  │  │
                    ES_DE_TIPO   │  │  └──SIGUIENTE_EVENTO──▶(:Evento)   ← orden total
                                 │  └─────CAUSA_DE──────────▶(:Evento)   ← dependencia causal
                                 ▼
                           (:TipoEvento)

  Relaciones del enunciado, DERIVADAS de los eventos (carga.cypher, paso 18):

   (:Jugador)──PARTICIPA / ANOTA / RECIBE_TARJETA──▶(:Partido)
   (:Jugador)──ASISTE──▶(:Jugador goleador)
   (:Jugador entra)──REEMPLAZA──▶(:Jugador sale)
```

Siete etiquetas y quince tipos de relación: diez del modelo de eventos y las cinco que pide el enunciado (`PARTICIPA`, `ANOTA`, `ASISTE`, `RECIBE_TARJETA`, `REEMPLAZA`), que se derivan de los eventos (§3.2). Todo el módulo se apoya en una idea:
**lo que en el módulo documental es un campo de referencia, acá es una arista recorrible.**

---

## 2. Etiquetas de nodo, atributos y cardinalidades

### 2.1 `:Equipo` — 64 nodos

| Atributo | Tipo | Identificación | Origen |
|---|---|---|---|
| `equipoId` | String `^[A-Z]{3}$` | **Clave natural, UNIQUE** | = `equipos._id` (código FIFA) del Hito 4 |
| `nombre` | String | — | Hito 4 |
| `confederacion` | String (CONMEBOL / UEFA / CAF / AFC / CONCACAF / OFC) | indexado | Hito 4 |
| `rankingFifa` | Integer 1–64 | — | Hito 4 |
| `entrenador` | String | — | Hito 4 |
| `ciudadBase` | String | — | Hito 4 (campo `sede`, renombrado para no confundirlo con `:Sede`) |
| `colorPrincipal` | String | — | Hito 4 (`colores.principal`) |
| `fechaAlta` | DateTime | — | Hito 4 |

**No se replica** `equipos.grupo`: se convierte en la relación `PERTENECE_A`.
**No se replica** `equipos.cantidadJugadores`: en el Hito 4 es una denormalización explícita; acá es `count((:Jugador)-[:JUEGA_EN]->(equipo))`, un recorrido de un salto.

### 2.2 `:Jugador` — 1.282 nodos

| Atributo | Tipo | Identificación | Origen |
|---|---|---|---|
| `dni` | String `^[0-9]{7,8}$` | **Clave natural, UNIQUE** | = `jugadores.dni` del Hito 4 (índice único) |
| `nombre`, `apellido` | String | indexado compuesto | Hito 4 |
| `posicion` | String (Arquero / Defensor / Mediocampista / Delantero) | indexado | Hito 4 (mismo enum) |
| `dorsal` | Integer 1–99 | — | Hito 4 |
| `nacionalidad` | String | — | derivado del equipo |
| `fechaNacimiento` | Date | — | Hito 4 |
| `fechaAlta` | DateTime | — | Hito 4 |

**No se replica** `jugadores._id` (ObjectId): es un detalle interno del motor documental y atarlo acá crearía un acoplamiento que la restricción del enunciado pide evitar.
**No se replica** `jugadores.equipoId`: es la relación `JUEGA_EN`.
**No se replican** `jugadores.estadisticas.{goles, asistencias, partidos}`: se derivan del subgrafo de eventos (ver `consultas_grafo.cypher`, bloque 2.3).

### 2.3 `:Partido` — 127 nodos (96 + 16 + 8 + 4 + 2 + 1)

| Atributo | Tipo | Identificación |
|---|---|---|
| `partidoId` | String `PAR-<grupo>-<n>` / `PAR-D16-<nn>` / `PAR-OCT-<nn>` / `PAR-CUA-<nn>` / `PAR-SEM-<nn>` / `PAR-FINAL` | **UNIQUE** |
| `fase` | String (GRUPOS / DIECISEISAVOS / OCTAVOS / CUARTOS / SEMIFINAL / FINAL) | indexado (compuesto con `estado`) |
| `grupo` | String A–P | solo fase de grupos |
| `jornada` | Integer 1–8 (1–3 grupos, 4 dieciseisavos … 8 final) | — |
| `ordenGlobal` | Integer 0–126 | orden determinista del torneo; elige el guion de eventos |
| `fechaHora` | DateTime | indexado |
| `estado` | String (PROGRAMADO / FINALIZADO) | indexado |
| `golesLocal`, `golesVisitante` | Integer | **derivados** del conteo de eventos `GOL` |

| Fase | Partidos | Estado tras la carga | Eventos |
|---|---:|---|---:|
| GRUPOS | 96 | FINALIZADO | 1.152 |
| DIECISEISAVOS | 16 | FINALIZADO | 220 |
| OCTAVOS | 8 | FINALIZADO | 116 |
| CUARTOS | 4 | FINALIZADO | 52 |
| SEMIFINAL | 2 | FINALIZADO | 32 |
| FINAL | 1 | **PROGRAMADO** | 0 |
| **Total** | **127** | | **1.572** |

La carga es una foto del torneo **en la víspera de la final** (sin partido por el tercer puesto). Ver §5.

### 2.4 `:Evento` — 1.572 nodos

| Atributo | Tipo | Rol |
|---|---|---|
| `eventoId` | String `<partidoId>-EV-<nn>` | **UNIQUE**, prefijado por su partición |
| `partidoId` | String | **clave de partición (Hito 3)**, indexado con `secuencia` |
| `secuencia` | Integer | **reloj lógico monótono dentro de la partición** |
| `tipo` | String | indexado; valida contra `:TipoEvento` |
| `minuto` | Integer 0–90 | minuto de juego |
| `timestamp` | DateTime | derivado de `fechaHora + minuto` |
| `condicionEquipo` | String (LOCAL / VISITANTE) | resuelve el equipo protagonista |
| `dorsalProtagonista` | Integer | resuelve el jugador protagonista (en `SUSTITUCION`, el que entra) |
| `dorsalSaliente` | Integer | solo en `SUSTITUCION`: el que sale; resuelve `REEMPLAZA` |
| `regionOrigen` | String (AMERICAS / EUROPA / AFRICA) | región de ingesta y de réplica (Hito 3) |

`secuencia` **no es un timestamp de reloj de pared**: es un contador local a la partición. Esa distinción es central — un sistema AP no puede asumir un reloj global sincronizado, pero sí puede garantizar un orden local monótono.

### 2.5 `:Sede` — 16 nodos

| Atributo | Tipo | Identificación |
|---|---|---|
| `sedeId` | String `<PAIS>-<COD>` (ej. `URU-CEN`) | **UNIQUE** |
| `nombre`, `ciudad`, `pais` | String | — |
| `region` | String (AMERICAS / EUROPA / AFRICA) | indexado — región de réplica del Hito 3 |
| `capacidad` | Integer | — |

### 2.6 `:Grupo` — 16 nodos

| Atributo | Tipo | Identificación |
|---|---|---|
| `grupoId` | String A–P | **UNIQUE**, = `equipos.grupo` del Hito 4 |
| `nombre` | String | — |
| `orden` | Integer 1–16 | orden determinista |
| `fase` | String | GRUPOS |

### 2.7 `:TipoEvento` — 12 nodos

| Atributo | Tipo | Identificación |
|---|---|---|
| `tipoEventoId` | String (`GOL`, `ASISTENCIA`, …) | **UNIQUE** |
| `nombre` | String | — |
| `categoria` | String (JUEGO / DISCIPLINA / ADMINISTRATIVO) | — |
| `afectaMarcador` | Boolean | `true` solo para `GOL` |
| `origen` | String | marca que es una **réplica local de solo lectura** del catálogo N8 |

---

## 3. Relaciones: tipo, dirección y cardinalidad

| Relación | Dirección | Cardinalidad | Propiedades | Por qué esa dirección |
|---|---|---|---|---|
| `JUEGA_EN` | `(:Jugador)` → `(:Equipo)` | N:1 (1.282 → 64) | `dorsal`, `desde`, `rol` | El jugador es el lado que cambia de equipo; el equipo es el destino estable. Además refleja el sentido de la referencia del Hito 4 (`jugadores.equipoId → equipos._id`). |
| `PERTENECE_A` | `(:Equipo)` → `(:Grupo)` | N:1 (64 → 16) | — | El equipo pertenece al grupo, no al revés. |
| `PARTICIPA_EN` | `(:Equipo)` → `(:Partido)` | N:M, **exactamente 2 por partido** | `condicion` (LOCAL / VISITANTE) | Un solo tipo de relación con una propiedad discriminante, en lugar de dos tipos `ES_LOCAL` / `ES_VISITANTE`. Ver §5. |
| `SE_JUEGA_EN` | `(:Partido)` → `(:Sede)` | N:1 (127 → 16) | — | El partido se programa en una sede; la sede preexiste al partido. |
| `CORRESPONDE_A` | `(:Partido)` → `(:Grupo)` | N:1 (96 → 16) | — | Solo para partidos de fase de grupos. |
| `OCURRE_EN` | `(:Evento)` → `(:Partido)` | N:1 (1.572 → 126) | — | **Materializa la partición.** El evento apunta a su partido: la partición es una propiedad del evento, no del partido. |
| `ES_DE_TIPO` | `(:Evento)` → `(:TipoEvento)` | N:1 (1.572 → 12) | — | Validación contra el catálogo. |
| `PROTAGONIZADO_POR` | `(:Evento)` → `(:Jugador)` | N:1 | — | El evento identifica a su autor. |
| `SIGUIENTE_EVENTO` | `(:Evento)` → `(:Evento)` | 1:1, **dentro del mismo partido** | — | **Orden total** de la partición. Cadena lineal: `sec n → sec n+1`. |
| `CAUSA_DE` | `(:Evento causa)` → `(:Evento efecto)` | N:M, **dentro del mismo partido** | — | **Orden causal.** Subconjunto estricto del orden total: solo los pares donde un evento es causa del otro. |

### 3.1 Por qué dos relaciones de orden y no una

| | `SIGUIENTE_EVENTO` | `CAUSA_DE` |
|---|---|---|
| Qué expresa | "pasó justo después" | "pasó *por causa de*" |
| Estructura | cadena lineal, 1 sucesor | grafo dirigido acíclico |
| Cantidad | 1.446 | 702 |
| Se puede reordenar sin romper nada | sí, es solo presentación | **no**, invertirla es una inconsistencia |

Colapsarlas en una sola perdería exactamente la distinción que el Hito 3 necesita: la sustitución del minuto 62 es **posterior** al gol del minuto 13 pero no es **consecuencia** suya. La consistencia causal solo obliga a respetar `CAUSA_DE`; el orden total puede reordenarse al reconciliar réplicas sin violar nada.

### 3.2 Relaciones del enunciado: `PARTICIPA`, `ANOTA`, `ASISTE`, `RECIBE_TARJETA`, `REEMPLAZA`

El enunciado pide estas cinco relaciones. En este modelo el hecho deportivo ya existe como `:Evento` (con partición, reloj lógico y causalidad, que son el eje del Hito 3), así que las cinco se cargan como **proyección derivada** del subgrafo de eventos (`carga.cypher`, paso 18) y no como una segunda fuente cargada a mano. El modelo de eventos **no se quita**: la API (Hito 10) sigue leyendo y escribiendo eventos.

| Relación | Dirección | Se deriva de | Cardinalidad | Propiedades | Cantidad |
|---|---|---|---|---|---:|
| `PARTICIPA` | `(:Jugador)` → `(:Partido)` | protagonista de al menos un evento del partido, o jugador que salió reemplazado | N:M, a lo sumo 1 por (jugador, partido) | `condicion` (LOCAL / VISITANTE), `eventos` (cuántos protagonizó) | 1.248 |
| `ANOTA` | `(:Jugador)` → `(:Partido)` | evento `GOL` + `PROTAGONIZADO_POR` | N:M, 1 por gol | `eventoId`, `minuto` | 220 |
| `ASISTE` | `(:Jugador asistidor)` → `(:Jugador goleador)` | evento `ASISTENCIA` que es `CAUSA_DE` un `GOL` | N:M, 1 por asistencia | `eventoId`, `golEventoId`, `partidoId`, `minuto` | 220 |
| `RECIBE_TARJETA` | `(:Jugador)` → `(:Partido)` | evento `TARJETA_AMARILLA` / `TARJETA_ROJA` | N:M, 1 por tarjeta | `eventoId`, `tipo` (AMARILLA / ROJA), `minuto` | 136 |
| `REEMPLAZA` | `(:Jugador entra)` → `(:Jugador sale)` | evento `SUSTITUCION` (`dorsalProtagonista` entra, `dorsalSaliente` sale) | N:M, 1 por sustitución | `eventoId`, `partidoId`, `minuto` | 136 |

**Origen y destino.** Las que describen lo que un jugador hizo *en un partido* (participar, convertir, ser amonestado) van de `:Jugador` a `:Partido`: es el mismo criterio "de lo que varía hacia lo estable" del resto del modelo, y deja el partido a un salto. Las que vinculan **a dos jugadores** van de jugador a jugador, porque ese es el dato que agregan: `ASISTE` dice *a quién* se asistió (el partido queda como propiedad) y `REEMPLAZA` dice *quién entró por quién*. Con `ASISTE` hacia `:Partido` se perdería la sociedad asistidor-goleador, que es la pregunta de la consulta 7.1; con `REEMPLAZA` hacia `:Partido`, la cadena de reemplazos de la 7.3 no existiría.

**`PARTICIPA` no es `PARTICIPA_EN`.** Son dos niveles del mismo partido:

| | `PARTICIPA_EN` | `PARTICIPA` |
|---|---|---|
| Origen | `:Equipo` | `:Jugador` |
| Qué dice | el equipo **está programado** en el partido (fixture) | el jugador **actuó** en el partido |
| Existe desde | que se arma el cruce (también en la final sin jugar) | que hay eventos del partido |
| Cantidad | exactamente 2 por partido (254) | entre 8 y 13 por partido jugado (1.248) |
| Propiedades | `condicion` | `condicion`, `eventos` |

Se usa el nombre del enunciado para la relación del jugador. La del equipo ya existía y la usan la API y todas las consultas de fixture: renombrarla rompería contratos sin aportar nada.

**`PARTICIPA` se deriva de los eventos, no del plantel.** "Jugó" = protagonizó al menos un evento o salió reemplazado. Derivarla del plantel (`JUEGA_EN` × `PARTICIPA_EN`) daría unos 20 jugadores por equipo y por partido sin ningún dato que lo respalde; con eventos, cada arista tiene su evidencia. El costo: los que estuvieron en cancha sin figurar en ningún evento no aparecen (ver `decisiones.md` §4.3).

**Idempotencia.** Las cuatro relaciones que nacen de un evento llevan su `eventoId` en el patrón del `MERGE`: dos goles del mismo jugador en el mismo partido son dos `ANOTA`, y reejecutar la carga no agrega una tercera. `PARTICIPA` es una por (jugador, partido) y su conteo se fija con `SET` a un valor calculado. Antes de derivar, el paso 18 borra las proyecciones cuyo evento ya no existe, así que converge al estado de los eventos, igual que el marcador.

**Coherencia.** Como son derivadas, se auditan contra su origen: la consulta 6.7 de `consultas_grafo.cypher` verifica que cada gol tenga su `ANOTA`, cada asistencia causal su `ASISTE`, cada tarjeta su `RECIBE_TARJETA` y cada sustitución su `REEMPLAZA`; que ninguna proyección quede sin su evento, y que todo goleador o amonestado tenga `PARTICIPA`. Todo da 0.

---

## 4. Restricciones e índices

### 4.1 Restricciones de unicidad (7)

`Equipo.equipoId` · `Jugador.dni` · `Partido.partidoId` · `Sede.sedeId` · `Evento.eventoId` · `Grupo.grupoId` · `TipoEvento.tipoEventoId`

Cada una crea su índice de respaldo, que es lo que hace que los `MERGE` de la carga sean *seeks* y no *scans*.

### 4.2 Índices (9)

| Índice | Entidad | Consulta que optimiza |
|---|---|---|
| `(partidoId, secuencia)` **compuesto** | `:Evento` | Timeline de un partido en orden — el acceso dominante del torneo |
| `(tipo)` | `:Evento` | Goles / tarjetas / asistencias del torneo |
| `(fechaHora)` | `:Partido` | "¿Qué se juega hoy?" |
| `(fase, estado)` **compuesto** | `:Partido` | "¿Qué partidos de eliminatoria faltan jugar?" |
| `(posicion)` | `:Jugador` | Equivalente de `{equipoId:1, posicion:1}` del Hito 4 — la parte `equipoId` la resuelve la relación |
| `(apellido, nombre)` **compuesto** | `:Jugador` | Equivalente de `{apellido:1, nombre:1}` del Hito 4 — listado alfabético |
| `(confederacion)` | `:Equipo` | Cortes por confederación |
| `(region)` | `:Sede` | Agrupación por región de réplica |
| `(condicion)` **de relación** | `:PARTICIPA_EN` | Filtro local/visitante, presente en casi toda consulta de fixture |

### 4.3 Restricciones de existencia — no disponibles

El equivalente en grafo de los validadores `$jsonSchema` con `validationLevel: strict` del Hito 4 son las *existence constraints*, que **solo existen en Neo4j Enterprise**. La imagen `neo4j:latest` de la materia es Community. Quedan declaradas y comentadas en `estructura.cypher`, y su función la cumplen:

1. el `ON CREATE SET` de `carga.cypher`, que siempre asigna las propiedades obligatorias;
2. el **bloque 6 de auditoría** de `consultas_grafo.cypher`, que verifica los mismos invariantes a posteriori (eventos huérfanos, tipos desconocidos, jugadores sin equipo, partidos mal formados, cadenas rotas, marcador inconsistente). Todos deben devolver `0`.

Es una degradación consciente, no un olvido: se cambia validación *en escritura* por auditoría *verificable*.

---

## 5. Decisiones de modelado que merecen justificación

**Un solo `PARTICIPA_EN` con propiedad, en vez de `ES_LOCAL` / `ES_VISITANTE`.**
Con dos tipos, cada consulta de fixture que no distingue condición (ej. "todos los partidos de Argentina") tendría que escribir `-[:ES_LOCAL|ES_VISITANTE]->`. Con un tipo y una propiedad indexada, el caso general es un patrón simple y el caso específico agrega `{condicion: 'LOCAL'}`. Costo: la cardinalidad "exactamente un local y un visitante" no la garantiza el motor y hay que auditarla (consulta 6.4).

**`Grupo` como nodo y no como propiedad.**
En MongoDB `grupo: "A"` es correcto: la pregunta natural es "traeme los equipos del grupo A", un filtro. En el grafo la pregunta natural cambia a "¿qué separa a estos dos equipos?", y ahí el grupo es un punto de paso del recorrido. Además permite colgar del grupo la programación (`CORRESPONDE_A`) sin repetir la letra en cada partido.

> **Nota (13/10/2026) — reentrega del Hito 3.** Con el ok del profesor, el modelo de objetos (IRIS) salió de la arquitectura y **este módulo pasó a ser la fuente de verdad** de los tipos de evento (N8) y de los partidos (N2), además de los eventos (N3). `:TipoEvento` y `:Partido` dejan de ser réplicas de otro motor. El texto de esta sección se conserva como se entregó en el Hito 5. Ver [`../../docs/hito-3-arquitectura-distribuida/hito-3-arquitectura-distribuida.md`](../../docs/hito-3-arquitectura-distribuida/hito-3-arquitectura-distribuida.md), sección "Revisión de la asignación del modelo de objetos (reentrega)".

**`TipoEvento` replicado localmente y de solo lectura.**
El Hito 3 asignó los tipos de evento (N8) a un motor de objetos con prioridad **CP**. Tener una copia local acá permite validar y agrupar sin consultar otro subsistema en el camino caliente — que es justamente lo que un módulo AP no puede permitirse. La copia **no es autoritativa**: si el catálogo cambia, este módulo se actualiza por propagación, no al revés.

**El marcador es derivado, no cargado.**
`golesLocal` / `golesVisitante` se calculan contando eventos `GOL`. Así el marcador nunca puede contradecir al timeline. En el Hito 4 el equivalente (`estadisticas`) está denormalizado y se documentó como una limitación ("si se insertan o eliminan jugadores fuera del flujo estándar, debe recalcularse"). Acá esa clase de desincronización es estructuralmente imposible, y la consulta 6.6 lo verifica.

**El cuadro eliminatorio completo: 127 partidos, foto en la víspera de la final.**
El enunciado pide 127 partidos: 96 de grupos + 16 dieciseisavos + 8 octavos + 4 cuartos + 2 semifinales + 1 final (sin tercer puesto). Sin fase eliminatoria el grafo del torneo son 16 componentes conexas aisladas; las llaves son las aristas que las unen y hacen demostrable la conectividad de RF9. Hasta semifinales todo está **jugado** (FINALIZADO, con eventos); la **final queda PROGRAMADO**, con sus dos equipos y sin eventos.

Por qué no todas las eliminatorias sin jugar: cada `:Partido` necesita un LOCAL y un VISITANTE (lo exige la API y lo audita la consulta 6.4), y los equipos de una ronda solo se conocen si la anterior se jugó. Por qué no la final también jugada: así queda un partido real del torneo que la API puede jugar y cerrar, y que sirve de estado vacío (`GET /partidos/PAR-FINAL/eventos` → 200 con `[]`).

**El ganador de cada llave lo fija el guion.** En eliminatoria no hay empates. El guion de eventos se elige con `ordenGlobal % 3`, como en grupos, y cada variante tiene un ganador (`% 3 = 1` gana el visitante 1-2; si no, el local 1-0 o 2-0). Así la ronda siguiente se arma de forma determinista sin esperar a que la anterior tenga eventos, y la consulta 6.8 verifica que quien pasó de ronda es quien ganó según el marcador **derivado** de los goles.

---

## 6. Volumen cargado

Valores reales de la carga desde una base vacía (salida completa en [`evidencia/127_partidos_relaciones_20261111.md`](./evidencia/127_partidos_relaciones_20261111.md)):

| Etiqueta | Nodos | | Relación | Aristas |
|---|---:|---|---|---:|
| `:Evento` | 1.572 | | `:ES_DE_TIPO` | 1.572 |
| `:Jugador` | 1.282 | | `:OCURRE_EN` | 1.572 |
| `:Partido` | 127 | | `:PROTAGONIZADO_POR` | 1.572 |
| `:Equipo` | 64 | | `:SIGUIENTE_EVENTO` | 1.446 |
| `:Sede` | 16 | | `:JUEGA_EN` | 1.282 |
| `:Grupo` | 16 | | `:PARTICIPA` *(enunciado)* | 1.248 |
| `:TipoEvento` | 12 | | `:CAUSA_DE` | 702 |
| **Total** | **3.089** | | `:PARTICIPA_EN` | 254 |
| | | | `:ANOTA` *(enunciado)* | 220 |
| | | | `:ASISTE` *(enunciado)* | 220 |
| | | | `:RECIBE_TARJETA` *(enunciado)* | 136 |
| | | | `:REEMPLAZA` *(enunciado)* | 136 |
| | | | `:SE_JUEGA_EN` | 127 |
| | | | `:CORRESPONDE_A` | 96 |
| | | | `:PERTENECE_A` | 64 |
| | | | **Total** | **10.647** |

Los valores exactos se obtienen con el paso 19 de `carga.cypher` o el bloque 6.9 de `consultas_grafo.cypher`, y **son idénticos después de reejecutar `carga.cypher`** (RNF4).
