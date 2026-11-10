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

RESULTADOS

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
docker compose --profile mongo stop
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
docker compose --profile cassandra stop
```

El anillo tarda unos minutos en formarse (los nodos se unen de a uno). `cqlsh` desde la notebook: puertos 19041–19043.

## Limpiar

Apagar sin perder datos (los volúmenes `fixture2030_rep_*` quedan):

```bash
docker compose --profile mongo --profile cassandra stop
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

LIMITACIONES
