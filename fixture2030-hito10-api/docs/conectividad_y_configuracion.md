# Conectividad y configuración — Hito 10

**Ingeniería de Datos II · Fixture 2030** — Santiago Pazos, Valentina Frisoli, Joaquín Núñez

## 1. Desde dónde corre cada componente

| Componente | Dónde corre | Cómo llega a las fuentes |
|---|---|---|
| Cinco bases (Hitos 4–8) | Contenedores Docker en la notebook, cada uno con su `docker-compose.yml` | — |
| **API** | Proceso Python en la notebook (no en un contenedor), `127.0.0.1:8000` | Por los puertos publicados en `localhost` |
| Front `web/` | `npm run dev` en la notebook (`:5173`) o Vercel (HTTPS) | Llama a `http://localhost:8000` desde el navegador de la notebook |
| Pruebas (pytest, Newman, schemathesis) | Notebook | API en `localhost:8000`; contraste nativo con `docker exec` |

**Notebook vs. contenedor (§5.13):** desde la notebook los hosts son `localhost`/`127.0.0.1` y los puertos publicados. Si la API se corriera dentro de un contenedor, `localhost` sería el propio contenedor: habría que unirlo a las redes de los módulos (`fixture2030-net`, `fixture2030-cassandra-net`, `fixture2030-influxdb-net`) y usar los nombres de servicio (`neo4j`, `cassandra`, `influxdb`…) en las variables, o `host.docker.internal` en Docker Desktop. No hace falta tocar código: sólo `.env`.

## 2. Hosts, puertos y contexto de cada fuente

| Fuente | Contenedor | Puerto en la notebook | Contexto | Autenticación |
|---|---|---|---|---|
| MongoDB 7 | `fixture2030_mongo` | `27017` | db `fixture2030` | ninguna (laboratorio) |
| Neo4j | `fixture2030-neo4j` | `7687` (Bolt), `7474` (Browser) | database `neo4j` | usuario/contraseña por `.env` |
| Cassandra | `fixture2030-cassandra` | `9042` | keyspace `fixture2030_comentarios`, DC `datacenter1` | ninguna (laboratorio) |
| Redis | `fixture2030-redis` | `127.0.0.1:6379` | base lógica 0 | ninguna, sólo loopback |
| InfluxDB 3 Core | `fixture2030-influxdb` | `127.0.0.1:8181` | db `fixture2030_vivo` | token local (archivo ignorado por git) |

IRIS (Hito 9) no se levanta: está fuera de la arquitectura vigente ([`coherencia_tpo.md`](./coherencia_tpo.md) §2).

## 3. Variables de entorno

Se cargan del entorno o de `fixture2030-hito10-api/.env` (ignorado por git; plantilla en `.env.example`). El código no tiene hosts ni puertos fijos: todo sale de `app/config/settings.py`.

| Variable | Default | Uso |
|---|---|---|
| `API_HOST` / `API_PORT` | `127.0.0.1` / `8000` | Dónde escucha la API |
| `LOG_LEVEL` | `INFO` | Nivel de log |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Orígenes del front (agregar el dominio de Vercel) |
| `DEP_TIMEOUT_S` | `2.0` | Timeout por operación contra una fuente (RNF8) |
| `MONGO_URI` / `MONGO_DB` | `mongodb://localhost:27017` / `fixture2030` | MongoDB |
| `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` / `NEO4J_DATABASE` | `bolt://localhost:7687` / `neo4j` / *(vacío)* / `neo4j` | Neo4j |
| `CASSANDRA_HOSTS` / `CASSANDRA_PORT` / `CASSANDRA_KEYSPACE` / `CASSANDRA_DC` | `127.0.0.1` / `9042` / `fixture2030_comentarios` / `datacenter1` | Cassandra |
| `REDIS_URL` / `CACHE_PARTIDO_TTL_S` | `redis://127.0.0.1:6379/0` / `60` | Redis y TTL de la caché del detalle |
| `INFLUX_URL` / `INFLUX_DB` | `http://127.0.0.1:8181` / `fixture2030_vivo` | InfluxDB 3 |
| `INFLUX_TOKEN` o `INFLUX_TOKEN_FILE` | — / `../fixture2030-influxdb/secrets/admin-token.json` | Token (preferentemente el archivo) |

## 4. Timeouts (RNF8)

| Fuente | Timeout del driver | Corte de la API |
|---|---|---|
| MongoDB | `serverSelectionTimeoutMS`, `connectTimeoutMS`, `socketTimeoutMS` = `DEP_TIMEOUT_S` | `wait_for(DEP_TIMEOUT_S)` |
| Neo4j | `connection_timeout`, `connection_acquisition_timeout`, `max_transaction_retry_time` = `DEP_TIMEOUT_S` | `wait_for(DEP_TIMEOUT_S)` |
| Cassandra | `connect_timeout`, `control_connection_timeout`, `request_timeout` = `DEP_TIMEOUT_S` | `wait_for` hasta 3 × `DEP_TIMEOUT_S` (puede incluir conexión inicial + dos rangos) |
| Redis | `socket_connect_timeout`, `socket_timeout` = `DEP_TIMEOUT_S` | `wait_for(DEP_TIMEOUT_S)` |
| InfluxDB | `httpx.Timeout(DEP_TIMEOUT_S)` | `wait_for(DEP_TIMEOUT_S)` |

Medido: con cada fuente detenida, 503 entre 2 ms (conexión rechazada) y 2,01 s (driver que reintenta); con la fuente colgada (`docker pause`), 503 a los 2,0 s. Ver `evidencia/dependencia_caida_*.md` y `evidencia/dependencia_lenta_pause_*.md`.

## 5. Procedimiento: de cero a la API funcionando

Desde la raíz del repositorio:

```bash
# 1. Carpetas de datos que usan los volúmenes nombrados (una sola vez)
mkdir -p ~/docker/data/cassandra ~/docker/data/redis ~/docker/data/influxdb

# 2. Levantar las cinco fuentes (cada módulo con su compose)
(cd fixture2030-mongodb   && docker compose -p fixture2030-hito4-mongodb up -d)
(cd fixture2030-neo4j     && cp -n .env.example .env && docker compose up -d)
(cd fixture2030-cassandra && docker compose up -d)
(cd fixture2030-redis     && docker compose up -d)
(cd fixture2030-influxdb  && sh scripts/inicializacion.sh)   # crea el token local y las bases

# 3. Cargas de muestra de cada hito (idempotentes)
(cd fixture2030-mongodb/load && npm install && node seed.js)
docker exec -i fixture2030-neo4j cypher-shell -u neo4j -p fixture2030 < fixture2030-neo4j/queries/estructura.cypher
docker exec -i fixture2030-neo4j cypher-shell -u neo4j -p fixture2030 < fixture2030-neo4j/queries/carga.cypher
docker exec fixture2030-cassandra cqlsh -f /scripts/esquema.cql
docker exec fixture2030-cassandra cqlsh -f /scripts/carga_muestra.cql
docker exec fixture2030-redis sh /scripts/carga_muestra.sh
(cd fixture2030-influxdb && docker compose run --rm herramientas scripts/generacion_puntos.py --perfil muestra \
                         && docker compose run --rm herramientas scripts/carga_lotes.py --perfil muestra)

# 4. Partido de demo para el flujo de cierre (reseteable)
docker exec -i fixture2030-neo4j cypher-shell -u neo4j -p fixture2030 < fixture2030-hito10-api/scripts/sembrar_demo_neo4j.cypher

# 5. API
cd fixture2030-hito10-api
cp .env.example .env            # completar NEO4J_PASSWORD con la de fixture2030-neo4j/.env
bash scripts/verificar_conectividad.sh
bash scripts/iniciar_api.sh     # Swagger UI: http://localhost:8000/docs
```

Notas:
- `-p fixture2030-hito4-mongodb` evita que Compose confunda el módulo con otro proyecto de la notebook que también se llame `fixture2030-mongodb` (pasó en esta notebook: Compose usa el nombre de la carpeta como nombre de proyecto).
- `fixture2030-neo4j` pide la contraseña de desarrollo del `.env` del módulo; `fixture2030` es el valor de su `.env.example`, no un secreto real.
- Las sesiones de muestra de Redis vencen 30 min después de la carga (TTL deslizante del Hito 7): recargar antes de una demo.

## 6. Verificar cada dependencia

- `bash scripts/verificar_conectividad.sh`: por fuente, contenedor corriendo, puerto abierto y un comando nativo (`mongosh ping`, `cypher-shell 'RETURN 1'`, `cqlsh SELECT release_version`, `redis-cli PING`, `curl /health`), y al final `GET /health/dependencias` si la API está arriba. Sale con código ≠ 0 si algo falla.
- `curl http://localhost:8000/health/dependencias`: estado y latencia por fuente (200 si todas `UP`, 503 si alguna `DOWN`).

## 7. Detener sin borrar datos

```bash
# API: Ctrl+C en la terminal de iniciar_api.sh
(cd fixture2030-mongodb && docker compose -p fixture2030-hito4-mongodb stop)
for m in neo4j cassandra redis influxdb; do (cd fixture2030-$m && docker compose stop); done
```

`stop` (o `down` sin `-v`) conserva los volúmenes nombrados. **No** usar `docker compose down -v`, `docker volume rm` ni los scripts de limpieza de cada módulo si se quieren conservar las cargas. La prueba de dependencia caída sólo hace `docker stop`/`docker start` (o `pause`/`unpause`).
