# Fixture 2030 — Replicación y CAP

> **Grupo N°2** · Ingeniería de Datos II · Pazos / Núñez / Frisoli
> Corresponde al **"Hito 9: Replicación y CAP"** de la guía del TPO. La numeración de carpetas del repositorio no sigue la de la guía: el "Hito 9" del repo es el módulo de IRIS (`fixture2030-iris/`), que quedó fuera de la arquitectura vigente.

Lleva a varios nodos las dos bases del TPO cuya replicación pide la guía, con su esquema y sus datos reales, y prueba qué pasa cuando un nodo cae:

| Pide la guía | Dónde está |
|---|---|
| Configuración Master-Slave en MongoDB | Replica set de 3 nodos (1 primario + 2 secundarios) con equipos y jugadores del Hito 4 — [`docker-compose.yml`](docker-compose.yml), [`scripts/mongo_iniciar.sh`](scripts/mongo_iniciar.sh) |
| Configuración Peer-to-Peer en Cassandra | Anillo de 3 nodos, keyspace de comentarios del Hito 6 con RF = 3 — [`scripts/cassandra_iniciar.sh`](scripts/cassandra_iniciar.sh) |
| Análisis CAP para cada subsistema | [`docs/analisis_cap.md`](docs/analisis_cap.md) (las 5 fuentes vigentes, contrastado con el Hito 3) |
| Documentar decisiones | [`docs/decisiones.md`](docs/decisiones.md) |
| Pruebas de failover | [`scripts/mongo_failover.sh`](scripts/mongo_failover.sh), [`scripts/cassandra_failover.sh`](scripts/cassandra_failover.sh) |
| Validar consistencia eventual | [`scripts/cassandra_consistencia_eventual.sh`](scripts/cassandra_consistencia_eventual.sh) (y la lectura vieja en un secundario de [`scripts/mongo_lecturas_y_concerns.sh`](scripts/mongo_lecturas_y_concerns.sh)) |
| Evidencia | [`evidencia/`](evidencia/): salida real de cada script, con fecha, comando y commit |

## Resultados en una línea

Medido el 11/11/2026 con Docker Desktop en Windows, volúmenes vacíos y el commit que figura en cada archivo de evidencia. Detalle y lectura CAP en [`docs/analisis_cap.md`](docs/analisis_cap.md).

| Prueba | Resultado |
|---|---|
| Replica set de MongoDB | 64 equipos y 1 472 jugadores iguales en los 3 nodos; 2.ª corrida de `mongo_iniciar.sh`: 0 insertados, nada reconfigurado |
| Lecturas desde secundarios | `secondary` reparte entre los dos secundarios; con la replicación congelada un secundario devuelve el valor anterior |
| writeConcern (mediana) | `w:1` 2,0 ms · `w:"majority"` 12,0 ms · `w:3` 3,0 ms |
| readConcern con la replicación congelada | `local` → valor nuevo · `majority` → valor anterior · `linearizable` → no responde en 3 s |
| Failover MongoDB, `kill` del primario | elección a los **9,99 s** (`electionTimeout`), primera escritura del cliente a los **11,61 s**, 0 errores y 0 escrituras perdidas de 226; el nodo vuelve como SECONDARY y se pone al día en 24 ms |
| Failover MongoDB, `stop` del primario | elección a los **0,59 s** (el primario cede el lugar), hueco de **0,27 s**, 0 errores de 244 |
| Anillo de Cassandra | 3 nodos UN, RF = 3, `Owns (effective)` 100 % en cada uno; 112 / 80 / 80 filas del Hito 6 leídas con ALL |
| Cassandra con un nodo caído | ONE y QUORUM: escriben y leen. ALL: falla al escribir y al leer (`Unavailable`, 3 requeridas, 2 vivas). Al volver, hint entregado y ALL funciona otra vez |
| Consistencia eventual (W = ONE) | Con el nodo caído durante la escritura, al volver lee **0 filas**; tras el *hinted handoff* (13 s) lee **1**. Sin hints, sigue en **0** a los 30 s y recién lee **1** tras `nodetool repair` (5 s) |
| RAM | Cassandra ~810–845 MiB por nodo con heap de 256 MB (~2,4 GB el anillo); MongoDB 157–178 MiB por nodo |

**Contraste con el Hito 3** (explicado en `docs/analisis_cap.md`): N1 CP en escritura / AP en lectura y N6 AP con N=3, R=1, W=1 se confirman. Lo que no coincide se dice ahí sin tocar el Hito 3: (1) "la escritura confirma en el primario" no alcanza para CP, hace falta `w: "majority"`; (2) Neo4j no confirma una escritura de eventos "en la región de ingesta" sin mayoría, como pide el Hito 3 para N3; (3) InfluxDB 3 Core no replica, así que la réplica de N7 no se puede implementar con esa edición. Se agrega además una tarea de operación que el Hito 3 no mencionaba: `nodetool repair` periódico.

## Requisitos

- Docker Desktop (o Docker Engine) con Compose v2 y **~2 GB libres** para el clúster que se esté probando. Los dos clústeres se levantan **de a uno**.
- Bash (Git Bash en Windows) y Python 3 (solo para resumir el log del escritor del failover de MongoDB).
- No hace falta Node ni drivers: la carga de MongoDB corre en un contenedor `node:20-alpine` y todo lo demás con `mongosh`, `cqlsh` y `nodetool` dentro de los contenedores.
- Imágenes: `mongo:7.0` y `cassandra:latest` (las mismas que los módulos del Hito 4 y del Hito 6; la versión de Cassandra queda registrada en la evidencia).

## Cómo correrlo

Todo desde esta carpeta. Cada script guarda su salida en `evidencia/<script>_<fecha>.txt`.

### MongoDB

```bash
bash scripts/mongo_iniciar.sh
```

```bash
bash scripts/mongo_lecturas_y_concerns.sh
```

```bash
bash scripts/mongo_failover.sh kill
```

```bash
bash scripts/mongo_failover.sh stop
```

```bash
docker compose --profile mongo stop -t 60
```

`mongo_iniciar.sh` es idempotente: reejecutarlo no reconfigura el replica set ni duplica datos. Para conectarse desde la notebook a un nodo puntual: `mongosh "mongodb://127.0.0.1:27041/?directConnection=true"` (27042, 27043 para los otros). La cadena con `replicaSet=` solo funciona dentro de la red de Docker, porque los miembros se anuncian como `mongo1..3`.

### Cassandra

```bash
bash scripts/cassandra_iniciar.sh
```

```bash
bash scripts/cassandra_failover.sh
```

```bash
bash scripts/cassandra_consistencia_eventual.sh
```

```bash
docker compose --profile cassandra stop -t 60
```

El anillo tarda de 2 a 9 minutos en formarse según la memoria libre (los nodos se unen de a uno). `cqlsh` desde la notebook: puertos 19041–19043.

## Limpiar

Apagar sin perder datos (los volúmenes `fixture2030_rep_*` quedan):

```bash
docker compose --profile mongo --profile cassandra stop -t 60
```

Borrar todo lo de este módulo, datos incluidos (solo toca el proyecto `fixture2030-replicacion`, no los módulos de un nodo):

```bash
docker compose --profile mongo --profile cassandra --profile carga down -v
```

## Estructura

```
fixture2030-replicacion-cap/
├── docker-compose.yml            # perfiles mongo (3 nodos + carga) y cassandra (3 nodos)
├── scripts/
│   ├── _comun.sh                 # funciones compartidas (evidencia, mongosh, cqlsh, nodetool)
│   ├── mongo_init_rs.js          # rs.initiate idempotente
│   ├── mongo_iniciar.sh          # levantar, replica set, esquema y carga del Hito 4
│   ├── mongo_lecturas_y_concerns.sh
│   ├── mongo_escritor.js         # escritor continuo w:majority usado en el failover
│   ├── analizar_escritor.py      # resumen de lo que vio ese escritor
│   ├── mongo_failover.sh
│   ├── cassandra_iniciar.sh      # levantar, RF=3, esquema y carga del Hito 6
│   ├── cassandra_failover.sh     # ONE / QUORUM / ALL con un nodo caído, hinted handoff
│   └── cassandra_consistencia_eventual.sh
├── docs/
│   ├── analisis_cap.md
│   └── decisiones.md
└── evidencia/
```

Esquema y datos **no se copian**: se montan de `../fixture2030-mongodb/` y `../fixture2030-cassandra/scripts/`.

## Limitaciones

- **Una sola máquina.** "Partición" es la caída de un nodo; no se probó una partición de red con los dos lados vivos, ni dos nodos caídos, ni varias regiones o datacenters (el Hito 3 replica por región). Las latencias son de un solo host.
- **Solo MongoDB y Cassandra se replican**, que es lo que pide la guía. Neo4j (Community) e InfluxDB (3 Core) no tienen replicación en las ediciones que usa el TPO; Redis sí la tiene, pero queda en un nodo. Su análisis CAP es de diseño.
- **N4 Usuarios y N9 Auditoría no están implementados** en el repo; se analizan sin medir (salvo que una escritura QUORUM se sostiene con un nodo caído, que es lo que necesita N9).
- **Memoria.** Con la notebook al límite de RAM, Docker Desktop respondió `500 Internal Server Error` durante segundos y un primario de MongoDB se abortó solo (detalle en `docs/analisis_cap.md` §2.4). Por eso los clústeres se prueban de a uno y los scripts reintentan solo ante errores de la API de Docker.
- **Heap de 256 MB en Cassandra**: alcanza para la carga de muestra, no para producción ni para la carga masiva del Hito 6.
- **`docker compose stop`** usa 10 s de gracia por defecto y MongoDB a veces tarda más en apagarse (sale con código 137). Usar `-t 60`, como en los comandos de arriba.
