# Topología y entornos (RF2, RNF3)

## 1. Quién se conecta con quién

```
 Navegador / Postman / curl / scripts del Hito 11          (todos en la notebook)
        │ HTTP :8000  (evaluación: instancia de esta rama en :8001; fallas de config: instancia temporal en :8011)
        ▼
 API Fixture 2030 — proceso uvicorn EN LA NOTEBOOK (no es un contenedor)
        │  por los puertos PUBLICADOS en localhost / 127.0.0.1
        ├── MongoDB    localhost:27017   MongoDB wire ──► contenedor fixture2030_mongo      red fixture2030-hito4-mongodb_default
        ├── Neo4j      localhost:7687    Bolt         ──► contenedor fixture2030-neo4j      red fixture2030-net
        │              (localhost:7474   HTTP Browser: lo usan las personas, no la API)
        ├── Cassandra  127.0.0.1:9042    CQL          ──► contenedor fixture2030-cassandra  red fixture2030-cassandra-net
        ├── Redis      127.0.0.1:6379    RESP         ──► contenedor fixture2030-redis      red fixture2030-redis_default
        ├── InfluxDB   127.0.0.1:8181    HTTP         ──► contenedor fixture2030-influxdb   red fixture2030-influxdb-net
        └── IRIS       127.0.0.1:1972    Superserver  ──► (no levantado: fuera de la arquitectura)
```

| Componente | Dónde corre | Origen de sus conexiones |
|---|---|---|
| Bases NoSQL (Hitos 4–8) | un contenedor por módulo, cada uno con su propio `docker-compose.yml` y su propia red | — |
| API del Hito 10 | proceso Python en la notebook | la notebook, por los puertos publicados |
| Scripts de este hito (`prueba_tcp.py`, `prueba_drivers.py`, `prueba_api.py`) | notebook | **el mismo origen que la API**: misma resolución de nombres, mismos puertos y, en `prueba_drivers.py`, el mismo `.venv` y los mismos drivers |
| CLIs nativos sin instalar en la notebook (`cypher-shell`, `cqlsh`, `influxdb3`) | dentro de su contenedor (`docker exec`) | **otro origen**: prueban protocolo, contexto y operación, no la ruta notebook → puerto publicado. El registro lo marca como *origen: dentro del contenedor* |

Cada fila de evidencia tiene un campo `origen` (por ejemplo `notebook (host) · Darwin arm64 · python 3.14.5`), así que siempre se sabe desde dónde se probó.

## 2. `localhost` no significa lo mismo en todos lados

Se probó en la corrida [`20261017-001129_completa`](evidencia/corridas/20261017-001129_completa/resultados_tcp.md) (escenarios de `prueba_tcp.py --escenarios`). Para observar la red Docker sin descargar imágenes, se usó un contenedor que ya existía:

| Desde | Destino | Resultado | Qué muestra |
|---|---|---|---|
| notebook | `localhost:27017` | conecta | el puerto publicado de Mongo está en la notebook |
| contenedor `fixture2030-cassandra` | `localhost:27017` | **connection refused** | dentro de un contenedor, `localhost` es el propio contenedor: ahí no hay Mongo |
| contenedor `fixture2030-cassandra` | `cassandra:9042` | conecta | en su red Compose, el servicio se alcanza por **nombre de servicio y puerto interno** |
| contenedor `fixture2030-cassandra` | `fixture2030_mongo:27017` | **host no resuelto** | cada módulo tiene su red: el DNS de Docker no resuelve contenedores de otras redes |
| contenedor `fixture2030-cassandra` | `host.docker.internal:27017` | conecta | Docker Desktop expone la notebook con ese nombre |
| notebook | `<ip-lan>:6379` y `<ip-lan>:8181` | **connection refused** | Redis e InfluxDB se publican sólo en `127.0.0.1`: desde la LAN no hay listener |
| notebook | `<ip-lan>:27017` | conecta | Mongo se publica en `0.0.0.0`: también se alcanza desde la LAN (sin autenticación; aceptable sólo en un laboratorio, ver limitaciones) |

### Si la API corriera en un contenedor

No se ejecuta así, pero el procedimiento ya lo contempla. Sólo cambian las variables, no el código:

| Variable | API en la notebook (actual) | API en un contenedor unido a cada red | API en un contenedor (Docker Desktop, sin unir redes) |
|---|---|---|---|
| `MONGO_URI` | `mongodb://localhost:27017` | `mongodb://mongodb:27017` (servicio `mongodb`) | `mongodb://host.docker.internal:27017` |
| `NEO4J_URI` | `bolt://localhost:7687` | `bolt://neo4j:7687` | `bolt://host.docker.internal:7687` |
| `CASSANDRA_HOSTS` | `127.0.0.1` | `cassandra` | `host.docker.internal` |
| `REDIS_URL` | `redis://127.0.0.1:6379/0` | `redis://redis:6379/0` | **no funciona**: Redis se publica sólo en 127.0.0.1 del host. Habría que unir la red |
| `INFLUX_URL` | `http://127.0.0.1:8181` | `http://influxdb:8181` | igual que Redis: publicado sólo en loopback |

Un contenedor sólo resuelve los nombres de las redes a las que está unido (`docker network connect`). En la tercera columna, "publicado en 127.0.0.1" del host no se ve desde la VM de Docker Desktop como `host.docker.internal`.

## 3. Puertos publicados e internos

En este laboratorio el puerto interno y el publicado coinciden (`27017→27017`, `7687→7687`…). La diferencia está en **en qué interfaz** se publica y **desde qué red** se llega:

- **Publicado en `0.0.0.0`** (Mongo, Neo4j, Cassandra): alcanzable desde la notebook y desde la LAN.
- **Publicado en `127.0.0.1`** (Redis, InfluxDB, IRIS): sólo desde la notebook. Fue una decisión de seguridad de los Hitos 7 y 8, porque no tienen contraseña o tienen un token de administración.
- **Puerto interno** (`cassandra:9042`): sólo desde un contenedor de la misma red Compose.

Que el puerto publicado y el interno coincidan es una casualidad de esta configuración. Si un `docker-compose.yml` publicara `"9043:9042"`, la API en la notebook tendría que usar `9043` y un contenedor de la red seguiría usando `9042`. El error típico de "puerto incorrecto" (usar el interno desde el host) se reprodujo apuntando Mongo a `27018`: **connection refused**, aunque Mongo está vivo en `27017`.

## 4. Entorno de las corridas de este hito

| Dato | Valor |
|---|---|
| Notebook | macOS (Darwin arm64), Docker Desktop |
| Intérprete de los scripts | `python3` 3.14 (stdlib) · `.venv` de la API con Python 3.12 para los drivers |
| Drivers | pymongo 4.18.3 · neo4j 6.4.0 · cassandra-driver 3.30.1 · redis-py 8.1.0 · httpx 0.28.1 |
| Clientes en la notebook | `mongosh`, `redis-cli`, `nc`, `curl` (`cypher-shell`, `cqlsh` e `influxdb3` desde su contenedor) |
| API evaluada | rama `claude/hito-11-conectividad-bb3fbc`, en `http://localhost:8001` (`config/configuracion.env` local). En `:8000` seguía corriendo la instancia del Hito 10, que no se tocó |
| Versiones observadas | MongoDB 7.0.40 · Neo4j 2026.07.1 community · Cassandra 5.0.9 · Redis 8.10.2 · InfluxDB 3 Core 3.12.0 |
