# Fixture 2030 — Hito 5 · Módulo de Grafos (Neo4j)

**Ingeniería de Datos II · Grupo 2** — Santiago Pazos, Valentina Frisoli, Joaquín Núñez

Subgrafo del Mundial 2030: equipos, jugadores, grupos, sedes, partidos y **eventos deportivos encadenados causalmente**. Todo el hito se maneja con Cypher; no hay API, ni interfaz, ni scripts en otro lenguaje.

**Dataset (pedido del enunciado):** **127 partidos** (96 de grupos + 16 dieciseisavos + 8 octavos + 4 cuartos + 2 semifinales + 1 final, sin tercer puesto) y **1.572 eventos**. Nodos `Equipo`, `Jugador`, `Partido`, `Evento` (más `Grupo`, `Sede`, `TipoEvento`) y las relaciones **`PARTICIPA`, `ANOTA`, `ASISTE`, `RECIBE_TARJETA`, `REEMPLAZA`**, derivadas de los eventos. **19 consultas complejas** y un análisis de relaciones. El torneo queda en la víspera de la final: todo jugado hasta semifinales y la final `PROGRAMADO`.

> **Entorno validado el 2026-09-08** con la imagen `neo4j:latest`; **revalidado el 2026-11-11** (127 partidos y relaciones del enunciado) con Neo4j 2026.09.0 Community.
> Registrar acá la versión concreta con la que se pruebe (ver [§6](#6-registro-de-la-versión-probada)): la etiqueta `latest` cambia y esa trazabilidad la pide el enunciado (RNF1).

---

## 1. Estructura del módulo

```
fixture2030-neo4j/
├── docker-compose.yml          servicio neo4j:latest, volúmenes nombrados, healthcheck
├── .env.example                credenciales por variable de entorno (copiar a .env)
├── import/                     insumos de importación (vacío: la carga es pura Cypher)
├── queries/
│   ├── estructura.cypher       7 restricciones de unicidad + 9 índices
│   ├── carga.cypher            carga idempotente completa (MERGE, sin aleatoriedad): 127 partidos,
│   │                           1.572 eventos y las 5 relaciones del enunciado (paso 18)
│   ├── crud.cypher             create / read / update / delete con filtros precisos
│   └── consultas_grafo.cypher  patrones multi-salto, análisis causal, camino, centralidad,
│                               relaciones del enunciado (bloque 7) y su análisis (bloque 8)
├── docs/
│   ├── modelo_grafo.md         etiquetas, atributos, direcciones, cardinalidades, índices
│   ├── decisiones.md           razonamiento técnico y vínculo con los Hitos 1 a 4
│   └── evidencia/              capturas del Hito 5 y salida real de la carga de 127 partidos
└── README.md
```

---

## 2. Requisitos

- Docker Desktop (o Docker Engine) con Docker Compose V2.
- ~2 GB de RAM libres. El compose limita el heap a 1 GB y la page cache a 512 MB.
- Puertos `7474` y `7687` libres. Si están ocupados, cambiarlos en el `.env`.

---

## 3. Levantar el ambiente

```bash
cd fixture2030-neo4j

# 1) Credenciales locales (RNF8). El .env NO se versiona.
cp .env.example .env

# 2) Levantar Neo4j
docker compose up -d

# 3) Esperar a que el healthcheck lo marque healthy (~40-60 s la primera vez,
#    porque descarga los plugins APOC y GDS)
docker compose ps
```

Cuando la columna `STATUS` diga `healthy`, abrir **http://localhost:7474**
Usuario `neo4j`, contraseña `fixture2030` (o la que se haya puesto en el `.env`).

Ver los logs mientras arranca:

```bash
docker compose logs -f neo4j
```

---

## 4. Ejecutar la carga sin duplicar datos

Los archivos `.cypher` del repositorio están montados dentro del contenedor en `/queries`, así que se ejecutan sin copiar nada.

```bash
# 1) Restricciones e índices — SIEMPRE antes de la carga
docker compose exec neo4j cypher-shell -u neo4j -p fixture2030 -f /queries/estructura.cypher

# 2) Carga del subgrafo
docker compose exec neo4j cypher-shell -u neo4j -p fixture2030 -f /queries/carga.cypher
```

> **El orden importa.** Las restricciones de unicidad crean el índice de respaldo que hace que cada `MERGE` de la carga sea un *seek*. Sin ellas la carga funciona pero es mucho más lenta, y deja de estar protegida contra duplicados en escrituras concurrentes.

### 4.1 Demostrar la idempotencia (RNF4)

Este es el chequeo que pide explícitamente el enunciado: la carga no debe duplicar nada al reejecutarse.

```bash
# Correr la carga por segunda vez
docker compose exec neo4j cypher-shell -u neo4j -p fixture2030 -f /queries/carga.cypher
```

Los conteos del último bloque (paso 19) deben ser **idénticos** a los de la primera corrida. Estos son los reales, de dos corridas desde una base vacía ([evidencia](./docs/evidencia/127_partidos_relaciones_20261111.md)):

| Etiqueta | Nodos | | Relación | Aristas |
|---|---:|---|---|---:|
| `Evento` | 1572 | | `ES_DE_TIPO` | 1572 |
| `Jugador` | 1282 | | `OCURRE_EN` | 1572 |
| `Partido` | 127 | | `PROTAGONIZADO_POR` | 1572 |
| `Equipo` | 64 | | `SIGUIENTE_EVENTO` | 1446 |
| `Sede` | 16 | | `JUEGA_EN` | 1282 |
| `Grupo` | 16 | | `PARTICIPA` *(enunciado)* | 1248 |
| `TipoEvento` | 12 | | `CAUSA_DE` | 702 |
| **Total** | **3089** | | `PARTICIPA_EN` | 254 |
| | | | `ANOTA` *(enunciado)* | 220 |
| | | | `ASISTE` *(enunciado)* | 220 |
| | | | `RECIBE_TARJETA` *(enunciado)* | 136 |
| | | | `REEMPLAZA` *(enunciado)* | 136 |
| | | | `SE_JUEGA_EN` | 127 |
| | | | `CORRESPONDE_A` | 96 |
| | | | `PERTENECE_A` | 64 |

Y por fase:

| Fase | Partidos | Estado | Eventos |
|---|---:|---|---:|
| GRUPOS | 96 | FINALIZADO | 1152 |
| DIECISEISAVOS | 16 | FINALIZADO | 220 |
| OCTAVOS | 8 | FINALIZADO | 116 |
| CUARTOS | 4 | FINALIZADO | 52 |
| SEMIFINAL | 2 | FINALIZADO | 32 |
| FINAL | 1 | PROGRAMADO | 0 |

**Por qué no se duplica:** todo se escribe con `MERGE` sobre clave natural (`equipoId`, `dni`, `partidoId`, `eventoId`, …) y ningún valor se genera con `rand()`, `randomUUID()` ni `datetime()` "de ahora". Es la misma estrategia que el Hito 4 resolvió con `bulkWrite` + upsert. Las relaciones del enunciado llevan el `eventoId` de su evento en el `MERGE`.

**Las relaciones del enunciado son derivadas.** `PARTICIPA`, `ANOTA`, `ASISTE`, `RECIBE_TARJETA` y `REEMPLAZA` se calculan en el paso 18 a partir de los `:Evento` (que siguen siendo la fuente, y los que usa la API). `PARTICIPA` (jugador → partido, quién actuó) convive con `PARTICIPA_EN` (equipo → partido, quién está programado). Origen, destino y propiedades de cada una: [`docs/modelo_grafo.md` §3.2](./docs/modelo_grafo.md#32-relaciones-del-enunciado-participa-anota-asiste-recibe_tarjeta-reemplaza).

### 4.2 Probar el CRUD y las consultas

```bash
docker compose exec neo4j cypher-shell -u neo4j -p fixture2030 -f /queries/crud.cypher
docker compose exec neo4j cypher-shell -u neo4j -p fixture2030 -f /queries/consultas_grafo.cypher
```

`crud.cypher` es **repetible**: crea sus entidades de demostración al principio y las elimina al final, así que al terminar el grafo vuelve al estado exacto que dejó `carga.cypher`. La verificación del bloque 4.5 debe devolver `0, 0, 0`.

---

## 5. Probar el subgrafo en Neo4j Browser

Abrir **http://localhost:7474** y pegar estas consultas. Las tres primeras devuelven grafo dibujable; el resto, tablas.

**5.1 · La jugada completa de un gol** — el corazón del hito:

```cypher
MATCH ruta = (i:Evento)-[:CAUSA_DE*1..5]->(g:Evento {tipo:'GOL'})
WHERE g.partidoId = 'PAR-A-2' AND NOT ()-[:CAUSA_DE]->(i)
RETURN ruta;
```

**5.2 · El timeline completo de un partido, con protagonistas:**

```cypher
MATCH (n:Evento {partidoId:'PAR-A-1'})-[:PROTAGONIZADO_POR]->(j:Jugador)
RETURN n, j;
```

**5.3 · Un partido con todo su contexto (equipos, sede, grupo, eventos):**

```cypher
MATCH (p:Partido {partidoId:'PAR-A-1'})
OPTIONAL MATCH (p)<-[r1:PARTICIPA_EN]-(e:Equipo)
OPTIONAL MATCH (p)-[r2:SE_JUEGA_EN]->(s:Sede)
OPTIONAL MATCH (p)<-[r3:OCURRE_EN]-(n:Evento)
RETURN p, r1, e, r2, s, r3, n;
```

**5.4 · Verificar la consistencia causal del Hito 3** — debe devolver `0, 0`:

```cypher
MATCH (c:Evento)-[:CAUSA_DE]->(f:Evento)
RETURN sum(CASE WHEN c.secuencia >= f.secuencia THEN 1 ELSE 0 END) AS violacionesDeOrden,
       sum(CASE WHEN c.partidoId <> f.partidoId THEN 1 ELSE 0 END) AS cruzanParticion;
```

**5.5 · Ver el plan de ejecución de una consulta** (equivalente del `explain()` del Hito 4):

```cypher
PROFILE MATCH (n:Evento {partidoId:'PAR-A-1'}) RETURN n ORDER BY n.secuencia;
```

Buscar `NodeIndexSeek` sobre `evento_particion_partido`. Si aparece `NodeByLabelScan`, el índice no se creó — volver a correr `estructura.cypher`.

**5.6 · Las relaciones del enunciado alrededor de un partido** (goles, asistencias, tarjetas, cambios y quién actuó):

```cypher
MATCH (p:Partido {partidoId:'PAR-OCT-01'})<-[r:PARTICIPA|ANOTA|RECIBE_TARJETA]-(j:Jugador)
OPTIONAL MATCH (j)-[x:ASISTE|REEMPLAZA]-(otro:Jugador)
  WHERE x.partidoId = p.partidoId
RETURN p, r, j, x, otro;
```

**5.7 · El camino de los dos finalistas por el cuadro:**

```cypher
MATCH (:Partido {fase:'FINAL'})<-[:PARTICIPA_EN]-(e:Equipo)
MATCH ruta = (e)-[:PARTICIPA_EN]->(p:Partido)<-[:PARTICIPA_EN]-(:Equipo)
WHERE p.fase <> 'GRUPOS'
RETURN ruta;
```

---

## 6. Registro de la versión probada

El enunciado exige usar `neo4j:latest` y, a cambio, documentar con qué versión concreta se validó.

```bash
docker compose exec neo4j cypher-shell -u neo4j -p fixture2030 \
  "CALL dbms.components() YIELD name, versions, edition RETURN name, versions, edition;"
```

| Fecha de prueba | Versión de Neo4j | Edición | Observaciones |
|---|---|---|---|
| 2026-09-08 | *(completar con la salida del comando)* | Community | Sin incompatibilidades detectadas |
| 2026-11-11 | Neo4j Kernel 2026.09.0 · Cypher 5 y 25 (`neo4j@sha256:91fb0bf2…`) | Community | Carga de 127 partidos y relaciones del enunciado. Contenedor de prueba sin los plugins APOC/GDS (ninguna consulta los usa). Ver [evidencia](./docs/evidencia/127_partidos_relaciones_20261111.md) |

**Incompatibilidades conocidas de usar `latest`:**

- Las **restricciones de existencia** (`REQUIRE ... IS NOT NULL`) son exclusivas de Enterprise. En Community fallan. Están escritas y comentadas en `estructura.cypher`, y su función la cumple el bloque 6 de auditoría de `consultas_grafo.cypher`.
- La **sintaxis de proyección de GDS** cambia entre versiones mayores. Por eso las consultas de centralidad del hito (bloque 4.1 y 4.2) están resueltas en **Cypher puro**, y el bloque GDS queda comentado como opcional.

---

## 7. Comandos útiles

```bash
# Estado y logs
docker compose ps
docker compose logs -f neo4j

# Shell interactiva de Cypher
docker compose exec neo4j cypher-shell -u neo4j -p fixture2030

# Detener conservando los datos (volúmenes nombrados, RNF2)
docker compose down

# Detener y BORRAR TODO (volúmenes incluidos) — para reproducir la carga desde cero
docker compose down -v
```

---

## 8. Reproducir el hito desde cero

Secuencia completa para un integrante ajeno al desarrollo (RNF3):

```bash
git clone <repo> && cd <repo>/fixture2030-neo4j
cp .env.example .env
docker compose up -d
sleep 60                                   # o esperar a que `docker compose ps` diga healthy
docker compose exec neo4j cypher-shell -u neo4j -p fixture2030 -f /queries/estructura.cypher
docker compose exec neo4j cypher-shell -u neo4j -p fixture2030 -f /queries/carga.cypher
docker compose exec neo4j cypher-shell -u neo4j -p fixture2030 -f /queries/carga.cypher   # idempotencia
docker compose exec neo4j cypher-shell -u neo4j -p fixture2030 -f /queries/consultas_grafo.cypher
```

---

## 9. Relación con los hitos previos

- **Hito 3** — Neo4j (Eventos en vivo, N3) es **AP**, con **consistencia causal**, **partición por partido** y **réplica multi-región asíncrona**. Cómo lo respeta el modelo está desarrollado en [`docs/decisiones.md` §3.2–3.4](./docs/decisiones.md).
- **Hito 4** — módulo documental (MongoDB) de equipos y jugadores. **No hay integración por código**: la relación es semántica, por identificadores. Se reutilizan sus mismas claves naturales (`equipos._id` = código FIFA, `jugadores.dni`), como exige RF5 / RNF6.
- **Hito 10 (API)** — lee y escribe este grafo (`GET /partidos/{id}`, eventos, cierre). Con el cuadro completo, `PAR-FINAL` es el partido del torneo que queda `PROGRAMADO` y sin eventos; `PAR-DEMO-API` sigue siendo el de la demo de escritura.
- **Actualizar una base que ya tenía la carga anterior (112 partidos):** alcanza con volver a correr `carga.cypher`. Los dieciseisavos pasan de `PROGRAMADO` a `FINALIZADO` con sus eventos, se crean las 15 llaves restantes y se derivan las relaciones del enunciado; no hace falta borrar el volumen.

---

## 10. Alcance

Fuera de alcance por decisión del enunciado: API REST, interfaz web, caché, series temporales, monitoreo, y cualquier integración por código con MongoDB. El módulo es el modelo de grafo, la carga y las operaciones Cypher.
