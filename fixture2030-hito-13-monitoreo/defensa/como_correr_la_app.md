# Cómo correr la aplicación

Todos los comandos en un solo lugar: las cinco bases, el monitoreo, la API y el front, más lo que hay que preparar antes de la demo. Junta lo que estaba repartido en [`demo.md`](demo.md) §1, la "Preparación" de [`guion_presentacion_final.md`](guion_presentacion_final.md) y [`fixture2030-hito10-api/docs/conectividad_y_configuracion.md`](../../fixture2030-hito10-api/docs/conectividad_y_configuracion.md) §5. Si algo no coincide, mandan esos documentos.

**Todo se corre desde la raíz del repo** (`fixture_2030_ing_datos_II/`), salvo que el comando diga `cd`. **Nunca `docker compose down -v`**: borra los datos.

Deck de la presentación: artifact de Claude **"Fixture 2030 — Defensa final"** (no está en el repo).

---

## 0. ¿Ya está corriendo?

```bash
docker ps --format '{{.Names}}\t{{.Status}}' | grep fixture2030
```

Si aparecen `fixture2030_mongo`, `fixture2030-neo4j`, `fixture2030-cassandra`, `fixture2030-redis`, `fixture2030-influxdb`, `fixture2030-prometheus` y `fixture2030-grafana` en `Up`, las bases y el monitoreo ya están. En ese caso:
- si es **la primera vez en esta carpeta**, hacé §1 (solo los pasos de configuración: no hace falta recargar datos);
- si no, saltá a §3.

## 1. Requisitos y configuración (una sola vez por carpeta)

Requisitos: Docker Desktop con ~7,7 GB, Python 3.12 (o `uv`), Node 20+ y npm.

```bash
mkdir -p ~/docker/data/cassandra ~/docker/data/redis ~/docker/data/influxdb
```

Contraseña de desarrollo de Neo4j (`fixture2030`, la del `.env.example`, no es un secreto real):

```bash
cp -n fixture2030-neo4j/.env.example fixture2030-neo4j/.env
```

Configuración de la API. Después de copiarla, abrir `fixture2030-hito10-api/.env` y completar `NEO4J_PASSWORD=fixture2030`:

```bash
cp -n fixture2030-hito10-api/.env.example fixture2030-hito10-api/.env
```

**Token de InfluxDB.** La API lo lee de `fixture2030-influxdb/secrets/admin-token.json`, que no se versiona. Tiene que ser el token de la instancia que está corriendo:
- si la instancia ya existe, copiar el archivo desde la carpeta donde se creó (otro clon o worktree que ya tenga `fixture2030-influxdb/secrets/admin-token.json`);
- si es una instancia nueva, se crea solo en el paso de InfluxDB de §2;
- si se perdió, `sh fixture2030-influxdb/scripts/autorizacion_local.sh`.

Sin token, la pestaña Estadísticas sale vacía y `/salud` muestra InfluxDB caído.

Dependencias del front:

```bash
(cd fixture2030-hito10-api/web && npm ci)
```

La API crea su `.venv` sola la primera vez que se inicia.

## 2. Levantar las bases y cargar datos (solo si no están)

Liberar memoria primero: si hay contenedores de otros proyectos, detenerlos con `docker stop <nombre>` (sin borrarlos). Con poca memoria, Cassandra no arranca.

Las cinco bases, una por una:

```bash
(cd fixture2030-mongodb && docker compose -p fixture2030-hito4-mongodb up -d)
```

```bash
(cd fixture2030-neo4j && docker compose up -d)
```

```bash
(cd fixture2030-cassandra && docker compose -f docker-compose.yml -f docker-compose.monitoreo.yml up -d)
```

```bash
(cd fixture2030-redis && docker compose up -d)
```

InfluxDB: la primera vez, `inicializacion.sh` crea las bases y el token. Si el contenedor ya existe, alcanza con `docker start fixture2030-influxdb` (tiene `pull_policy: always` y, sin buena red, `docker compose up` se queda descargando la imagen).

```bash
(cd fixture2030-influxdb && sh scripts/inicializacion.sh)
```

**Cargas de datos** (idempotentes: se pueden repetir sin duplicar). Solo si las bases están vacías o tienen una carga vieja:

```bash
(cd fixture2030-mongodb/load && npm ci && node seed.js)
```

```bash
docker exec -i fixture2030-neo4j cypher-shell -u neo4j -p fixture2030 < fixture2030-neo4j/queries/estructura.cypher
```

```bash
docker exec -i fixture2030-neo4j cypher-shell -u neo4j -p fixture2030 < fixture2030-neo4j/queries/carga.cypher
```

```bash
docker exec fixture2030-cassandra cqlsh -f /scripts/esquema.cql
```

```bash
docker exec fixture2030-cassandra cqlsh -f /scripts/carga_muestra.cql
```

```bash
docker exec fixture2030-redis sh /scripts/carga_muestra.sh
```

Estadísticas de InfluxDB (las de la demo, con los goles alineados a Neo4j; ~15 s):

```bash
cd fixture2030-influxdb && python3 scripts/generacion_puntos.py --perfil completo && python3 scripts/carga_lotes.py --perfil completo --tabla estadisticas_equipo && cd ..
```

Monitoreo (Prometheus, Grafana y exporters):

```bash
bash fixture2030-hito-13-monitoreo/scripts/iniciar_monitoreo.sh
```

## 3. Cada vez que se usa la app (y 30 min antes de la defensa)

**1. Partido de demo limpio.** Sin esto, la mesa de control (D6) no funciona porque el partido quedó cerrado del ensayo anterior:

```bash
docker exec -i fixture2030-neo4j cypher-shell -u neo4j -p fixture2030 < fixture2030-hito10-api/scripts/sembrar_demo_neo4j.cypher
```

**2. Sesiones de Redis.** Vencen a los 30 minutos: correrlo lo más cerca posible de la presentación.

```bash
docker exec fixture2030-redis sh /scripts/carga_muestra.sh
```

**3. API** (en una terminal aparte; queda corriendo en http://localhost:8000):

```bash
bash fixture2030-hito10-api/scripts/iniciar_api.sh
```

**4. Front** (en otra terminal; tiene que quedar en el puerto **5173**, que es el que la API acepta):

```bash
cd fixture2030-hito10-api/web && npm run dev
```

**5. Chequeo.** Los dos tienen que salir bien: 13 targets UP y las cinco bases en `UP`.

```bash
bash fixture2030-hito-13-monitoreo/scripts/verificar_targets.sh
```

```bash
curl -s localhost:8000/health/dependencias
```

En el navegador: la ficha de ARG con **26** jugadores, `/partidos/PAR-D16-01` con eventos, comentarios y estadísticas con Goles **1–0**. Después de resembrar el partido de demo, esperar un minuto antes de abrir la mesa (el detalle queda en la caché de Redis hasta 60 s), o borrar la caché como en el bloque de abajo.

### Ensayar la demo otra vez

Lo único que la demo deja cambiado es **D6**: ARG–BRA (`PAR-DEMO-API`) queda FINALIZADO, con un evento de fin, y no acepta otro cierre. Después de cada ensayo, desde la raíz del repo:

```bash
docker exec -i fixture2030-neo4j cypher-shell -u neo4j -p fixture2030 < fixture2030-hito10-api/scripts/sembrar_demo_neo4j.cypher && docker exec fixture2030-redis redis-cli DEL f30:cache:partido:PAR-DEMO-API
```

- Deja el partido PROGRAMADO, con sus 3 eventos de carga (inicio, pase, gol de Fernández) y sin fin. La última línea que imprime tiene que decir `"PROGRAMADO", NULL`.
- El `DEL` borra la caché del detalle en Redis, así no hay que esperar el minuto. Después, recargar la pestaña de la mesa.
- Probado el 20/11/2026: cerrar (409) → fin (201) → cerrar (200) → cerrar otra vez (409) → reinicio → cerrar da otra vez 409 `MISSING_FIN_PARTIDO`.
- Si el cierre da **2–0** en lugar de 1–0, en el paso 3 de D6 se registró un gol de más (condición *Local* o dorsal 9). Reiniciar y repetir.

No hace falta reiniciar nada más: D4 suma un comentario por ensayo, pero no aparece en la lista; D1, D2, D3, D5 y D7 solo leen. Las sesiones de Redis (paso opcional) vencen a los 30 minutos: volver a correr el paso 2.

No apagar entre ensayos: Docker Desktop con los contenedores `fixture2030-*` y `fixture2030_mongo`, ni las terminales de la API (8000) y del front (5173).

## 4. Direcciones

| Qué | URL |
|---|---|
| Front | http://localhost:5173 |
| Mesa de control de la demo | http://localhost:5173/partidos/PAR-DEMO-API/mesa |
| Salud de las fuentes (front) | http://localhost:5173/salud |
| Swagger (plan B si el front no levanta) | http://localhost:8000/docs |
| Grafana (usuario y contraseña en [`../grafana/README.md`](../grafana/README.md)) | http://localhost:3000 |
| Prometheus | http://localhost:9090 |
| Neo4j Browser | http://localhost:7474 |

## 5. Si algo falla

| Síntoma | Qué hacer |
|---|---|
| `docker ps` responde "500 Internal Server Error" | La VM de Docker se colgó: `docker desktop restart` (tarda unos minutos) |
| Cassandra no arranca o se reinicia | Falta memoria: detener contenedores de otros proyectos |
| MongoDB: "container name already in use" | Se levantó sin `-p fixture2030-hito4-mongodb`. Usar el comando de §2 tal cual |
| Neo4j: "credencial rechazada" | Falta `fixture2030-neo4j/.env` o `NEO4J_PASSWORD` en el `.env` de la API; reiniciar la API |
| Estadísticas vacías o InfluxDB DOWN | Falta el token (§1) |
| ARG con 23 jugadores | Carga vieja de MongoDB: correr `node seed.js` (§2) |
| ARG–BEL con Goles 0–2 en Estadísticas | Carga vieja de InfluxDB: correr la carga de estadísticas de §2 |
| La mesa dice "solo disponible mientras el partido está PROGRAMADO" | Correr el paso 1 de §3, esperar un minuto y recargar |
| El front no conecta con la API | ¿La API está en `:8000` y el front en `:5173`? Otro puerto lo bloquea CORS |
| Grafana sin datos | Revisar el rango de tiempo (arriba a la derecha) y `verificar_targets.sh` |

Plan B completo de la demo: [`guion_presentacion_final.md`](guion_presentacion_final.md) §"Plan B de la demo".

## 6. Apagar sin borrar datos

`Ctrl+C` en las terminales de la API y del front. Después:

```bash
bash fixture2030-hito-13-monitoreo/scripts/limpiar_entorno.sh
```

Las bases, desde su carpeta, con `docker compose stop` (o `docker compose down`, **nunca** `down -v`).
