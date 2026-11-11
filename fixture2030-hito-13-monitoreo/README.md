# Hito 13 · Monitoreo con Prometheus + Grafana y defensa final

Capa de observabilidad del Fixture 2030: **Prometheus** recolecta métricas (modelo *pull*) de la API y de las bases, **Grafana** las muestra en cinco dashboards provisionados, y un conjunto de **alertas** dice cuándo actuar. Sobre esa evidencia se arma la defensa ante la FIFA.

| Qué buscás | Dónde |
|---|---|
| Qué se monitorea y cómo | [`docs/inventario_de_componentes.md`](docs/inventario_de_componentes.md) |
| Configuración de Prometheus, consultas PromQL, UP/DOWN | [`docs/metricas_y_consultas.md`](docs/metricas_y_consultas.md) |
| Alertas y por qué cada umbral | [`docs/alertas_y_umbral.md`](docs/alertas_y_umbral.md) |
| Evidencia, qué se midió y qué no | [`docs/limitaciones_y_evidencia.md`](docs/limitaciones_y_evidencia.md) |
| Métricas internas de Neo4j (exporter propio) e InfluxDB (token) | [`docs/metricas_neo4j_e_influxdb.md`](docs/metricas_neo4j_e_influxdb.md) |
| Qué significa cada panel | [`grafana/README.md`](grafana/README.md) |
| Decisiones de arquitectura y defensa | [`docs/decisiones_de_arquitectura.md`](docs/decisiones_de_arquitectura.md), [`docs/defensa_final.md`](docs/defensa_final.md), [`defensa/`](defensa/) |

```
fixture2030-hito-13-monitoreo/
├── docker-compose.yml          prometheus, grafana, node-exporter, exporters de MongoDB, Redis y Neo4j, blackbox
├── neo4j-exporter/             exporter propio de Neo4j (Python, solo biblioteca estándar)
├── prometheus.yml              jobs y targets (scrape cada 15 s)
├── blackbox.yml                sondas TCP / HTTP de disponibilidad
├── prometheus/reglas-o-alertas.yml
├── grafana/{provisioning,dashboards,README.md}
├── scripts/                    iniciar_monitoreo · preparar_token_influxdb · verificar_targets · ejecutar_prueba_controlada · limpiar_entorno
├── docs/                       inventario, métricas, alertas, limitaciones, decisiones, defensa
├── evidencia/                  targets, prueba de falla, capturas de los dashboards
└── defensa/                    guion de 20 minutos, demo, presentación
```

Fuera de esta carpeta, el hito también cambió:
- [`../fixture2030-hito10-api/app/core/metricas.py`](../fixture2030-hito10-api/app/core/metricas.py): la API expone `GET /metrics` (RF4).
- [`../fixture2030-cassandra/docker-compose.monitoreo.yml`](../fixture2030-cassandra/docker-compose.monitoreo.yml): override que agrega el agente JMX de Prometheus a Cassandra.

## 1. Requisitos

Docker Desktop (probado en macOS, Apple Silicon), `curl`, `python3` y `bash`. Para la API: Python 3.12 (`uv` o `venv`, lo resuelve `iniciar_api.sh`). Puertos libres: 3000, 9090, 9100, 9115, 9121, 9216, 9474, 7070 y 8000.

## 2. Preparar la demo (una sola vez por notebook)

Las credenciales de laboratorio **no están en el repo** (RNF6). Sin ellas, Neo4j e InfluxDB responden 503:

```bash
cp fixture2030-neo4j/.env.example fixture2030-neo4j/.env        # contraseña de desarrollo de Neo4j
sh fixture2030-influxdb/scripts/inicializacion.sh                # crea el token de InfluxDB en secrets/ (se muestra UNA vez)
```

(Desde la raíz del repositorio.) Si InfluxDB ya tenía un token que se perdió, ver [`../fixture2030-influxdb/secrets/README.md`](../fixture2030-influxdb/secrets/README.md).

### Token de InfluxDB para Prometheus

El `/metrics` de InfluxDB exige ese mismo token de administración. Prometheus lo lee de `fixture2030-influxdb/secrets/prometheus-token` (ignorado por git, como `admin-token.json`): **no hay secretos en el repo**. Lo genera, a partir de `admin-token.json`, este script, que `iniciar_monitoreo.sh` ya llama en cada arranque:

```bash
bash fixture2030-hito-13-monitoreo/scripts/preparar_token_influxdb.sh
```

Si `admin-token.json` no existe, el script avisa y el target `influxdb` queda DOWN hasta crearlo (`inicializacion.sh`) y volver a correrlo; no hace falta reiniciar Prometheus, que relee el archivo en cada scrape. Detalle en [`docs/metricas_neo4j_e_influxdb.md`](docs/metricas_neo4j_e_influxdb.md).

## 3. Levantar la plataforma

Cada base se levanta desde su carpeta; el monitoreo no depende del orden (lo que esté apagado se ve CAÍDO). Desde la raíz del repositorio:

```bash
(cd fixture2030-mongodb && docker compose up -d)
(cd fixture2030-neo4j && docker compose up -d)
(cd fixture2030-cassandra && docker compose -f docker-compose.yml -f docker-compose.monitoreo.yml up -d)
(cd fixture2030-redis && docker compose up -d)
(cd fixture2030-influxdb && docker compose up -d)
```

**Cargar datos de laboratorio** (idempotentes; solo la primera vez o para restaurar): cada módulo lo explica en su README — MongoDB [`load/seed.js`](../fixture2030-mongodb/README.md), Neo4j [`estructura.cypher` + `carga.cypher`](../fixture2030-neo4j/README.md), Cassandra [esquema y muestra](../fixture2030-cassandra/README.md), Redis [`carga_muestra.sh`](../fixture2030-redis/README.md), InfluxDB [`inicializacion.sh` y carga](../fixture2030-influxdb/README.md).

**API** (en otra terminal; queda en primer plano):

```bash
bash fixture2030-hito10-api/scripts/iniciar_api.sh
```

**Monitoreo:**

```bash
bash fixture2030-hito-13-monitoreo/scripts/iniciar_monitoreo.sh
```

| Servicio | URL |
|---|---|
| Grafana | http://localhost:3000 — `admin` / `fixture2030` (desarrollo) — abre en el dashboard *Fixture 2030 — Monitoreo*; Neo4j e InfluxDB por dentro en *Fixture 2030 — Neo4j e InfluxDB* |
| Prometheus | http://localhost:9090 — *Status → Targets* y *Alerts* |
| Métricas de la API | http://localhost:8000/metrics |
| Métricas de Cassandra | http://localhost:7070/metrics |
| Métricas de Neo4j (exporter propio) | http://localhost:9474/metrics |

Los cinco dashboards están en la carpeta *Fixture 2030* de Grafana; cada uno tiene arriba los links a los demás (conservan el rango de tiempo):

| Dashboard | URL | Qué responde |
|---|---|---|
| 1. Resumen y SLAs | `/d/fixture2030-monitoreo` | ¿Está todo arriba? ¿Hay alertas? ¿Se cumplen latencia < 100 ms y disponibilidad 99,99 %? |
| 2. API integrada | `/d/fixture2030-api` | Tráfico, latencia por ruta y errores de la API del Hito 10 |
| 3. Comparación entre bases | `/d/fixture2030-comparacion-bases` | Cuánto tarda y cómo termina cada llamada de la API a cada base |
| 4. Bases por dentro | `/d/fixture2030-bases` | Métricas internas de las cinco bases: MongoDB, Redis, Cassandra, Neo4j e InfluxDB |
| 5. Infraestructura | `/d/fixture2030-infraestructura` | Recursos del host y salud del propio Prometheus |

## 4. Verificar

```bash
bash fixture2030-hito-13-monitoreo/scripts/verificar_targets.sh            # tabla de targets y bases; código 1 si hay alguno DOWN
bash fixture2030-hito-13-monitoreo/scripts/verificar_targets.sh --guardar  # además la guarda en evidencia/
```

Esperado con todo arriba: 13 targets UP (los 11 anteriores más `neo4j` e `influxdb`) y las 5 bases con `probe_success = 1`.

## 5. Repetir la demostración

1. **Estado:** dashboard *1. Resumen y SLAs*, fila *Estado de salud* (todo OK).
2. **Tráfico:** usar el front, Swagger (http://localhost:8000/docs) o la colección de Postman del Hito 10; se mueven los dashboards *2. API integrada* y *3. Comparación entre bases*, y los SLAs del *1*.
3. **Falla controlada** (≈ 4 minutos; solo `docker stop` / `docker start`, no toca datos):

   ```bash
   bash fixture2030-hito-13-monitoreo/scripts/ejecutar_prueba_controlada.sh redis   # o mongodb | cassandra | neo4j
   ```

   Durante la prueba: la base pasa a CAÍDA en ~10 s, la alerta `BaseNoResponde` a firing en ~70 s, y la API responde 503 solo en las rutas de esa base. Deja el informe en `evidencia/prueba_de_falla_<base>_<fecha>.md`.
4. **Carga observada** (≈ 2 minutos; k6 en Docker, solo lecturas):

   ```bash
   bash fixture2030-hito-13-monitoreo/scripts/ejecutar_carga_observada.sh
   ```

   Compara la latencia de la API con la de Cassandra (desde la API y por dentro) y la CPU de cada uno. Deja el informe en `evidencia/carga_observada_<fecha>.md`.

Guion completo y plan B si algo falla en vivo: [`defensa/demo.md`](defensa/demo.md).

## 6. Limpiar

```bash
bash fixture2030-hito-13-monitoreo/scripts/limpiar_entorno.sh                 # apaga el monitoreo, conserva las series
bash fixture2030-hito-13-monitoreo/scripts/limpiar_entorno.sh --borrar-datos  # además borra SOLO los datos de Prometheus y Grafana (pide "si")
```

Nunca borra volúmenes de las bases (RNF11). Cada base se apaga desde su carpeta con `docker compose down` (conserva los datos).

## 7. Persistencia

Igual que Redis, Cassandra, InfluxDB e IRIS: **volúmenes nombrados** (`fixture2030_prometheus_data`, `fixture2030_grafana_data`) respaldados por `~/docker/data/prometheus` y `~/docker/data/grafana` (las crea `iniciar_monitoreo.sh`). Retención de Prometheus: 15 días.

## 8. Cómo llegan los exporters a las bases

Cada módulo tiene su propio compose y su propia red. Los exporters no se suman a esas redes: llegan por los puertos publicados en la notebook a través de `host.docker.internal`. Así el monitoreo arranca aunque las bases estén apagadas y no hubo que tocar los compose de otros hitos (salvo el override opcional de Cassandra). Probado en Docker Desktop (macOS); en Linux, Redis e InfluxDB publican solo en `127.0.0.1` y no son alcanzables así (ver [limitaciones](docs/limitaciones_y_evidencia.md)).
