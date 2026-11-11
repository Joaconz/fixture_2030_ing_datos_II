# Fixture 2030 — Carga masiva de datos (Hito 11 del PDF)

**Ingeniería de Datos II** — Santiago Pazos, Valentina Frisoli, Joaquín Núñez

Carga del **volumen completo** en las cinco bases de la arquitectura vigente, cada una con el cargador que ya tiene su módulo, en paralelo o en secuencia. Después de la carga: validación de integridad (con cruces entre bases), reporte de tiempos y recursos, una optimización medida antes y después, y el análisis de cómo quedan distribuidos los datos.

> Numeración: este es el **Hito 11 de la guía del TPO** ("Carga Masiva de Datos"). En el repo, `fixture2030-hito11-conectividad/` y `fixture2030-hito12-carga/` son otras cosas: conectividad de la API y prueba de carga de la API con k6. IRIS quedó fuera de la arquitectura con aprobación del profesor y no se carga.

<!-- RESULTADOS -->

## Qué pide el PDF y dónde está

| Pedido del Hito 11 | Dónde |
|---|---|
| Cargar el volumen completo en todas las BD | `scripts/orquestador.py` → corridas en [`evidencia/corridas/`](evidencia/corridas/) |
| Scripts de carga para cada BD | Los de cada módulo, sin reescribir: [`docs/orquestacion.md`](docs/orquestacion.md) §1 |
| Carga en paralelo | `--modo paralelo` (con admisión por memoria) vs `--modo secuencial` |
| Validación de integridad | `scripts/validacion.py`: conteos, duplicados, `partido_id` → Neo4j, equipos MongoDB ↔ Neo4j (H1) |
| Reporte de tiempos | `reporte.md` / `reporte.json` de cada corrida + [`evidencia/comparacion_paralelo_vs_secuencial.md`](evidencia/comparacion_paralelo_vs_secuencial.md) |
| Optimización de carga | [`docs/optimizacion.md`](docs/optimizacion.md) |
| Análisis de distribución | [`docs/distribucion_y_escalabilidad.md`](docs/distribucion_y_escalabilidad.md) |

## Volumen

| Base | Módulo | Cargador (del módulo) | Volumen |
|---|---|---|---|
| MongoDB | `fixture2030-mongodb` | `load/seed.js` | 64 equipos, 1.664 jugadores |
| Neo4j | `fixture2030-neo4j` | `queries/estructura.cypher` + `carga.cypher` | 127 partidos, 1.572 eventos, relaciones PARTICIPA / ANOTA / ASISTE / RECIBE_TARJETA / REEMPLAZA |
| Cassandra | `fixture2030-cassandra` | `scripts/esquema.cql` + `carga_masiva.py` | 1.050.000 comentarios (2.100.000 filas en dos vistas) |
| Redis | `fixture2030-redis` | `carga_muestra.sh` + `carga_volumen.sh 100000` | 100.000 usuarios con sesión y TTL |
| InfluxDB | `fixture2030-influxdb` | `inicializacion.sh` + `carga_lotes.py --perfil completo` | 10.094.400 puntos |

## Cómo correrlo

Requisitos: Docker Desktop (Compose v2.24+ por `!override`) y Python ≥ 3.10 en la notebook (solo biblioteca estándar). Las imágenes son las de cada módulo, más `node:20-alpine` para el cargador de MongoDB.

```bash
python fixture2030-carga-masiva/scripts/orquestador.py --modo paralelo
```

```bash
python fixture2030-carga-masiva/scripts/orquestador.py --modo secuencial
```

Cada corrida empieza desde volúmenes vacíos, apaga y borra todo lo suyo al terminar y deja `evidencia/corridas/<fecha>_<modo>/` con `reporte.md`, `reporte.json`, `salida.txt` (la salida completa de cada cargador) y `recursos.csv`. Todo lo que levanta se llama `f30cm-*` y usa puertos propios: **no toca** las instancias compartidas `fixture2030-*` ni otros contenedores ([`docs/orquestacion.md`](docs/orquestacion.md) §3).

Opciones útiles: `--bases cassandra influxdb` (solo algunas), `--orden ...` (orden de admisión), `--max-paralelo N`, `--cassandra-concurrencia N`, `--influx-hilos N`, `--influx-lote N`, `--etiqueta x`, `--conservar` (no apaga; para inspeccionar).

Comparar corridas:

```bash
python fixture2030-carga-masiva/scripts/comparar.py fixture2030-carga-masiva/evidencia/corridas/<A> fixture2030-carga-masiva/evidencia/corridas/<B> --salida fixture2030-carga-masiva/evidencia/comparacion_x.md
```

## Memoria: por qué el modo paralelo no arranca todo a la vez

La primera corrida arrancó las cinco bases juntas y **colgó Docker Desktop** durante 37 minutos ([`evidencia/cuelgue_20261111.md`](evidencia/cuelgue_20261111.md)). Desde entonces:

- cada contenedor de la prueba tiene `mem_limit`;
- el modo paralelo admite una base solo si su reserva entra en el presupuesto, que es la RAM de la VM menos la RAM de los contenedores ajenos y un margen;
- cada base se valida y se apaga apenas termina su carga;
- un **vigía** corta la corrida y mata los contenedores `f30cm-*` si la VM o el host se quedan sin memoria, o si Docker deja de responder.

## Estructura

```
fixture2030-carga-masiva/
├── compose/            override de cada módulo: nombres f30cm-*, puertos, mem_limit, cargadores
├── scripts/
│   ├── orquestador.py  limpieza → insumos → fases por base → cruces → reporte
│   ├── comun.py        docker compose de cada módulo, las 5 bases, clientes, docker stats, vigía
│   ├── validacion.py   integridad por base + referencias cruzadas
│   ├── distribucion.py análisis de distribución por base
│   └── comparar.py     corridas lado a lado
├── docs/
│   ├── orquestacion.md               diseño, aislamiento, memoria, cambios en otros módulos
│   ├── optimizacion.md               hipótesis, antes/después, resultado
│   └── distribucion_y_escalabilidad.md
└── evidencia/
    ├── corridas/<fecha>_<modo>/      reporte.md / .json, salida.txt, recursos.csv
    ├── modulos/                      evidencia propia de los cargadores de Cassandra e InfluxDB
    ├── comparacion_*.md / .json
    └── cuelgue_20261111.md
```

## Cambios en otros módulos

Solo dos scripts de `fixture2030-influxdb/scripts/`. `inicializacion.sh` y `autorizacion_local.sh` aceptan variables opcionales (`SECRETS_DIR`, `EVIDENCIA_DIR`, `INFLUX_VOLUME`) y esperan al contenedor del proyecto en curso en vez de `fixture2030-influxdb` fijo. Sin esto, inicializar la instancia de la prueba **pisaba el token** de la instancia compartida. Sin las variables hacen lo mismo que antes. Ningún cargador cambió. Detalle en [`docs/orquestacion.md`](docs/orquestacion.md) §4.
