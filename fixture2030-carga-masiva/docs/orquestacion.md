# Orquestación de la carga masiva

Cómo está armado el orquestador, qué corre exactamente en cada base y qué hubo que tocar en los otros módulos para poder llamarlos desde acá.

## 1. Principio: los cargadores son los de cada módulo

El orquestador **no tiene lógica de carga propia**. Llama, sin cambios, al cargador que cada módulo ya usaba para su hito:

| Base | Módulo | Preparación (no cuenta como carga) | Carga (lo que se cronometra) | Volumen |
|---|---|---|---|---|
| MongoDB 7.0 | `fixture2030-mongodb` | `init/01-validators.js` (lo corre la imagen al crear el contenedor) + `npm ci` | `node load/seed.js` | 64 equipos + 1.664 jugadores |
| Neo4j | `fixture2030-neo4j` | `cypher-shell -f /queries/estructura.cypher` | `cypher-shell -f /queries/carga.cypher` | 127 partidos, 1.572 eventos, relaciones del enunciado |
| Cassandra 5 | `fixture2030-cassandra` | `cqlsh -f /scripts/esquema.cql` + `pip install cassandra-driver` | `python scripts/carga_masiva.py` | 1.050.000 comentarios (2.100.000 filas: dos vistas) |
| Redis | `fixture2030-redis` | — | `sh /scripts/carga_muestra.sh` + `sh /scripts/carga_volumen.sh 100000` | 100.000 usuarios con sesión y TTL (+ la muestra del hito) |
| InfluxDB 3 Core | `fixture2030-influxdb` | `sh scripts/inicializacion.sh` (token + 3 bases con retención) | `python scripts/carga_lotes.py --perfil completo` | 10.094.400 puntos |

En Redis se carga también la muestra del hito, igual que hace `correr_volumen.sh` del módulo: los 100.000 usuarios del volumen no nombran partidos, y la muestra trae el ranking de tendencia y la votación MVP, que son las claves con `partido_id` que la validación cruza contra Neo4j.

Los insumos de InfluxDB (`data/lp/completo/*.lp.gz`, ~1,4 GB) los produce `generacion_puntos.py` del módulo. Son deterministas: el orquestador los genera **una vez**, si faltan, y los reutiliza. Esa generación se informa aparte y no entra en el tiempo de carga (es producir el archivo de entrada, no escribir en la base).

## 2. Fases y tiempos

Cada base pasa por cinco fases, cronometradas por separado desde la notebook (`time.perf_counter`):

1. **arranque**: `docker compose up -d --wait` del servicio principal, hasta que el healthcheck da *healthy*.
2. **preparación**: esquema/estructura y dependencias del cargador (tabla de arriba).
3. **carga**: el cargador del módulo. **Es lo que se compara.**
4. **verificación**: validación de integridad (`validacion.py`) y análisis de distribución (`distribucion.py`) de esa base, todavía arriba. Guarda lo que necesitan los cruces: `partido_id` y equipos.
5. **apagado**: `down -v` y borrado de su carpeta de datos, para devolverle la memoria a la VM.

Se registran inicio y fin de cada fase relativos al arranque de la corrida (así se ve el solapamiento en paralelo), la duración, el volumen y el throughput de la carga (`volumen / segundos de carga`). Cassandra e InfluxDB además informan la tasa que mide su propio cargador (que descuenta generación de datos y lectura de archivos); las dos cifras se muestran juntas y no se mezclan.

El **total** principal es el reloj desde que arranca la primera base hasta que **termina la última carga**. También se informa el reloj total (con verificación y apagado), la suma de las cargas y la suma de arranque + preparación + carga. En secuencial, el reloj es aproximadamente esa suma; en paralelo, la diferencia es lo que gana el paralelismo.

Los **cruces entre bases** (todo `partido_id` de Cassandra, Redis e InfluxDB existe en Neo4j; equipos MongoDB ↔ Neo4j, hallazgo H1) se calculan al final, sobre lo que guardó cada verificación. No hace falta tener las cinco bases arriba a la vez.

Modos:

- `--modo paralelo` (por defecto): **admisión por presupuesto de memoria** (§5). Recorre la cola en el orden de `--orden` y arranca la primera base cuya reserva entre en lo que queda del presupuesto. Cuando una base se apaga, devuelve su reserva y se vuelve a mirar la cola. `--max-paralelo N` agrega un tope de bases simultáneas.
- `--modo secuencial`: una detrás de otra, en `--orden` (por defecto MongoDB → Neo4j → Cassandra → InfluxDB → Redis).
- `--sin-presupuesto`: las cinco a la vez, sin control. Es lo que colgó Docker Desktop ([`evidencia/cuelgue_20261111.md`](../evidencia/cuelgue_20261111.md)); queda solo para documentarlo.

## 3. Aislamiento de la prueba

Las cinco bases compartidas del equipo (`fixture2030_mongo`, `fixture2030-neo4j`, `fixture2030-cassandra`, `fixture2030-redis`, `fixture2030-influxdb`) siguen corriendo durante la prueba y **no se tocan**. Para eso cada base se levanta con el compose de su módulo **más un override** de `compose/` que solo cambia nombres:

| | Proyecto compose | Contenedor | Volúmenes | Red | Puerto (127.0.0.1) |
|---|---|---|---|---|---|
| MongoDB | `f30cm-mongodb` | `f30cm-mongodb` | `f30cm_mongo_data` | `f30cm-mongodb_default` | 27130 |
| Neo4j | `f30cm-neo4j` | `f30cm-neo4j` | `f30cm_neo4j_{data,logs,plugins}` | `f30cm-neo4j-net` | 37474 / 37687 |
| Cassandra | `f30cm-cassandra` | `f30cm-cassandra` | `f30cm_cassandra_data` → `~/docker/data/f30cm/cassandra` | `f30cm-cassandra-net` | 19142 |
| Redis | `f30cm-redis` | `f30cm-redis` | `f30cm_redis_data` → `~/docker/data/f30cm/redis` | `f30cm-redis_default` | 16380 |
| InfluxDB | `f30cm-influxdb` | `f30cm-influxdb` | `f30cm_influxdb_data` → `~/docker/data/f30cm/influxdb` | `f30cm-influxdb-net` | 18182 |

Imagen, configuración (memoria de las JVM, `redis.conf`, plugins de Neo4j), healthchecks y scripts montados son los del módulo. Además, los overrides:

- ponen `restart: "no"` (que la prueba no reviva sola si Docker se reinicia);
- agregan a MongoDB un **healthcheck** (el compose del módulo no tiene) que responde por la IP del contenedor: mientras corre `init/` mongod escucha solo en 127.0.0.1, así que *healthy* = init terminado;
- agregan a MongoDB un contenedor `cargador` (`node:20-alpine`) que copia `load/` adentro y corre `npm ci` + `node seed.js`: `node_modules` no ensucia el repo ni pasa por el disco de Windows;
- cambian la carpeta de **evidencia** de los cargadores de Cassandra e InfluxDB a `evidencia/modulos/` de este módulo (no se pisa la evidencia de los otros hitos);
- arrancan el cargador de Cassandra con `sleep infinity` para ejecutar adentro, por separado, el `pip install` (preparación) y `carga_masiva.py` (carga). El entrypoint del módulo hace las dos cosas juntas y le cargaría a Cassandra el tiempo de descarga del driver.

Cada corrida empieza con `down -v` de los cinco proyectos `f30cm-*` y el borrado de `~/docker/data/f30cm/*`: **siempre desde volúmenes vacíos**. Al final hace lo mismo (salvo `--conservar`).

## 4. Cambios en otros módulos

Solo uno, en `fixture2030-influxdb/scripts/` (documentado también en su encabezado):

| Archivo | Cambio | Por qué |
|---|---|---|
| `inicializacion.sh` | Esperaba el healthcheck con `docker inspect fixture2030-influxdb` (nombre fijo). Ahora usa `docker compose ps -q influxdb`. | Con otro proyecto de compose el nombre fijo apuntaba a la instancia **compartida** (ya healthy): la espera pasaba sin esperar a la nueva. Para el uso normal da lo mismo. |
| `inicializacion.sh`, `autorizacion_local.sh` | Variables opcionales `SECRETS_DIR` (carpeta del token, por defecto `secrets`), `EVIDENCIA_DIR` (por defecto `docs/evidencia`) e `INFLUX_VOLUME` (por defecto `fixture2030_influxdb_data`). | Sin esto, inicializar la instancia de la prueba **sobrescribía `secrets/admin-token.json`** de la instancia compartida (el token viejo no valida contra el servidor nuevo y el script crea otro en el mismo archivo) y pisaba `docs/evidencia/01_inicializacion.txt` del Hito 8. |

Con las variables sin definir, los dos scripts hacen exactamente lo mismo que antes. Ningún cargador (`seed.js`, `carga.cypher`, `carga_masiva.py`, `carga_volumen.sh`, `carga_lotes.py`) cambió.

## 5. Memoria: `mem_limit` y presupuesto

La primera corrida arrancó las cinco bases a la vez y **colgó Docker Desktop**: el motor devolvió 500, después dejó de responder, y WSL también. Los números están en [`evidencia/cuelgue_20261111.md`](../evidencia/cuelgue_20261111.md). En resumen: la VM tiene 7.864 MiB y ya había ~4.425 MiB ocupados por 17 contenedores ajenos (Supabase y las instancias compartidas del equipo). Las cinco bases de la prueba juntas piden más que lo que quedaba, y el host Windows (16 GB) estaba con ~1,3 GB libres y paginando la VM.

Dos medidas, las dos en este módulo (los composes de los otros módulos no cambian):

**`mem_limit` por contenedor** (`compose/*.yml`). Si un contenedor se pasa, el kernel lo mata dentro de su cgroup y no se lleva puesta toda la VM.

| Contenedor | `mem_limit` | Por qué ese valor |
|---|---:|---|
| `f30cm-neo4j` | 2g | heap 1 G + page cache 512 M del compose del módulo + memoria nativa (medido: 1.365 MiB) |
| `f30cm-cassandra` | 2g | `MAX_HEAP_SIZE` 1 G del módulo + off-heap (la compartida usa ~1,6 GiB) |
| `f30cm-influxdb` | 2g | búferes de ingesta y WAL de InfluxDB 3 Core |
| `f30cm-mongodb` | 768m | WiredTiger dimensiona su caché con el límite del cgroup |
| `f30cm-redis` | 512m | `maxmemory 256mb` de `redis.conf` + fork del AOF |
| cargador de Cassandra | 768m | `carga_masiva.py` y el recorrido de validación (conjuntos de 1,05 M de ids) |
| herramientas de InfluxDB | 512m | `carga_lotes.py` deja como mucho 2 × hilos lotes de ~7 MB en vuelo |
| cargador de MongoDB | 384m | `npm ci` + `node seed.js` |

**Admisión por presupuesto** (modo paralelo). El presupuesto se calcula al empezar: RAM de la VM − RAM de los contenedores ajenos − margen (`--margen-mib`, 768 por defecto). La reserva de cada base es la suma de sus `mem_limit`: MongoDB 1.152, Neo4j 2.048, Cassandra 2.816, InfluxDB 2.560 y Redis 512 MiB. Las cinco juntas reservan 9.088 MiB, más que toda la VM. Si la base siguiente no entra ni sola (no hay nada corriendo), arranca igual con un aviso, porque no hay forma de cargarla con menos memoria.

Las reservas son topes, no consumos: el pico real queda por debajo. Por eso el presupuesto es conservador. Con los contenedores ajenos apagados (no es decisión de esta prueba), el mismo orquestador admitiría más bases a la vez sin cambiar nada.

## 6. Recursos

`docker stats --no-stream` en bucle (cada llamada tarda ~2 s) durante todas las fases. Se guardan **todos** los contenedores: los `f30cm-*` son la prueba (en `recursos.csv` de cada corrida) y el resto es carga de fondo de la VM que no es de esta prueba (otras instancias), que se informa como total porque compite por la misma memoria. En cada muestra y en cada admisión se registra también la RAM disponible del host.
