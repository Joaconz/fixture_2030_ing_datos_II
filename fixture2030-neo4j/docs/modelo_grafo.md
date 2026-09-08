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
```

Siete etiquetas, nueve tipos de relación. Todo el módulo se apoya en una idea:
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

### 2.3 `:Partido` — 112 nodos (96 de grupos + 16 dieciseisavos)

| Atributo | Tipo | Identificación |
|---|---|---|
| `partidoId` | String `PAR-<grupo>-<n>` / `PAR-D16-<nn>` | **UNIQUE** |
| `fase` | String (GRUPOS / DIECISEISAVOS) | indexado (compuesto con `estado`) |
| `grupo` | String A–P | solo fase de grupos |
| `jornada` | Integer 1–4 | — |
| `ordenGlobal` | Integer 0–111 | orden determinista del torneo |
| `fechaHora` | DateTime | indexado |
| `estado` | String (PROGRAMADO / FINALIZADO) | indexado |
| `golesLocal`, `golesVisitante` | Integer | **derivados** del conteo de eventos `GOL` |

### 2.4 `:Evento` — 1.152 nodos

| Atributo | Tipo | Rol |
|---|---|---|
| `eventoId` | String `<partidoId>-EV-<nn>` | **UNIQUE**, prefijado por su partición |
| `partidoId` | String | **clave de partición (Hito 3)**, indexado con `secuencia` |
| `secuencia` | Integer | **reloj lógico monótono dentro de la partición** |
| `tipo` | String | indexado; valida contra `:TipoEvento` |
| `minuto` | Integer 0–90 | minuto de juego |
| `timestamp` | DateTime | derivado de `fechaHora + minuto` |
| `condicionEquipo` | String (LOCAL / VISITANTE) | resuelve el equipo protagonista |
| `dorsalProtagonista` | Integer | resuelve el jugador protagonista |
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
| `SE_JUEGA_EN` | `(:Partido)` → `(:Sede)` | N:1 (112 → 16) | — | El partido se programa en una sede; la sede preexiste al partido. |
| `CORRESPONDE_A` | `(:Partido)` → `(:Grupo)` | N:1 (96 → 16) | — | Solo para partidos de fase de grupos. |
| `OCURRE_EN` | `(:Evento)` → `(:Partido)` | N:1 (1.152 → 96) | — | **Materializa la partición.** El evento apunta a su partido: la partición es una propiedad del evento, no del partido. |
| `ES_DE_TIPO` | `(:Evento)` → `(:TipoEvento)` | N:1 (1.152 → 12) | — | Validación contra el catálogo. |
| `PROTAGONIZADO_POR` | `(:Evento)` → `(:Jugador)` | N:1 | — | El evento identifica a su autor. |
| `SIGUIENTE_EVENTO` | `(:Evento)` → `(:Evento)` | 1:1, **dentro del mismo partido** | — | **Orden total** de la partición. Cadena lineal: `sec n → sec n+1`. |
| `CAUSA_DE` | `(:Evento causa)` → `(:Evento efecto)` | N:M, **dentro del mismo partido** | — | **Orden causal.** Subconjunto estricto del orden total: solo los pares donde un evento es causa del otro. |

### 3.1 Por qué dos relaciones de orden y no una

| | `SIGUIENTE_EVENTO` | `CAUSA_DE` |
|---|---|---|
| Qué expresa | "pasó justo después" | "pasó *por causa de*" |
| Estructura | cadena lineal, 1 sucesor | grafo dirigido acíclico |
| Cantidad | 1.056 | 512 |
| Se puede reordenar sin romper nada | sí, es solo presentación | **no**, invertirla es una inconsistencia |

Colapsarlas en una sola perdería exactamente la distinción que el Hito 3 necesita: la sustitución del minuto 62 es **posterior** al gol del minuto 13 pero no es **consecuencia** suya. La consistencia causal solo obliga a respetar `CAUSA_DE`; el orden total puede reordenarse al reconciliar réplicas sin violar nada.

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

**`TipoEvento` replicado localmente y de solo lectura.**
El Hito 3 asignó los tipos de evento (N8) a un motor de objetos con prioridad **CP**. Tener una copia local acá permite validar y agrupar sin consultar otro subsistema en el camino caliente — que es justamente lo que un módulo AP no puede permitirse. La copia **no es autoritativa**: si el catálogo cambia, este módulo se actualiza por propagación, no al revés.

**El marcador es derivado, no cargado.**
`golesLocal` / `golesVisitante` se calculan contando eventos `GOL`. Así el marcador nunca puede contradecir al timeline. En el Hito 4 el equivalente (`estadisticas`) está denormalizado y se documentó como una limitación ("si se insertan o eliminan jugadores fuera del flujo estándar, debe recalcularse"). Acá esa clase de desincronización es estructuralmente imposible, y la consulta 6.6 lo verifica.

**Los dieciseisavos se cargan aunque el hito no los pida.**
Sin fase eliminatoria el grafo del torneo son 16 componentes conexas aisladas y toda consulta de camino entre grupos distintos devuelve vacío. Las 16 llaves son las aristas que unen las componentes, y son lo que hace demostrable la consulta de conectividad de RF9.

---

## 6. Volumen cargado

| Etiqueta | Nodos | | Relación | Aristas (aprox.) |
|---|---:|---|---|---:|
| `:Jugador` | 1.282 | | `:SIGUIENTE_EVENTO` | 1.056 |
| `:Evento` | 1.152 | | `:JUEGA_EN` | 1.282 |
| `:Partido` | 112 | | `:OCURRE_EN` | 1.152 |
| `:Equipo` | 64 | | `:ES_DE_TIPO` | 1.152 |
| `:Sede` | 16 | | `:PROTAGONIZADO_POR` | 1.152 |
| `:Grupo` | 16 | | `:CAUSA_DE` | 512 |
| `:TipoEvento` | 12 | | `:PARTICIPA_EN` | 224 |
| **Total** | **2.654** | | `:SE_JUEGA_EN` | 112 |
| | | | `:PERTENECE_A` / `:CORRESPONDE_A` | 64 / 96 |

Los valores exactos se obtienen con el bloque 6.7 de `consultas_grafo.cypher`, y **deben ser idénticos después de reejecutar `carga.cypher`** (RNF4).
