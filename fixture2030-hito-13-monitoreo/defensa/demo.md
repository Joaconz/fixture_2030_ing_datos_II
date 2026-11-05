# Demo controlada y plan B (RF13, RNF7)

Comandos desde la raíz del repositorio. Todo es de laboratorio: no se borran volúmenes y la carga es de solo lectura (RNF5, RNF11).

## 1. Media hora antes

```bash
cp -n fixture2030-neo4j/.env.example fixture2030-neo4j/.env      # si no existe
(cd fixture2030-mongodb && docker compose up -d)
(cd fixture2030-neo4j && docker compose up -d)
(cd fixture2030-cassandra && docker compose -f docker-compose.yml -f docker-compose.monitoreo.yml up -d)
(cd fixture2030-redis && docker compose up -d)
(cd fixture2030-influxdb && docker compose up -d)
bash fixture2030-hito-13-monitoreo/scripts/iniciar_monitoreo.sh
bash fixture2030-hito10-api/scripts/iniciar_api.sh               # en otra terminal
```

Chequeo (tiene que salir con código 0, 11 targets UP):

```bash
bash fixture2030-hito-13-monitoreo/scripts/verificar_targets.sh
curl -s localhost:8000/health/dependencias
```

Abrir en pestañas: Grafana (http://localhost:3000, dashboard *Fixture 2030 — Monitoreo*, rango "Last 15 minutes"), Prometheus `/alerts`, Swagger (http://localhost:8000/docs). **Ocultar** cualquier `.env` o terminal con credenciales (RNF6).

## 2. Secuencia en vivo (bloques "Operación" y "Evidencia")

| Paso | Acción | Qué decir |
|---|---|---|
| 1 | Swagger: `GET /partidos/PAR-D16-01/comentarios?limit=50` | Cassandra: lee la ventana del partido repartida en buckets; nunca escanea todo el partido |
| 2 | Swagger: `GET /equipos/ARG` | MongoDB: un documento por equipo, lectura por clave |
| 3 | Swagger: `GET /health/dependencias` | La API ve cada base por separado; si una cae, solo esa queda DOWN |
| 4 | Lanzar la carga: `bash fixture2030-hito-13-monitoreo/scripts/ejecutar_carga_observada.sh` (2 min; seguir hablando) | Mientras corre, en Grafana: *Requests por segundo* sube a ~400; *Latencia p95 de cada base* muestra Cassandra; fila Cassandra: p99 interno en ~1 ms |
| 5 | Al terminar, abrir el informe que imprime | Cassandra 1 ms por dentro, la API 42–91 ms al 97 % de CPU: el cuello es la API, la base tiene margen |
| 6 | (Si sobra tiempo) `bash fixture2030-hito-13-monitoreo/scripts/ejecutar_prueba_controlada.sh redis` (4 min) | Redis pasa a CAÍDA, la alerta a firing, sesiones da 503 y equipos sigue en 200: la falla queda en su módulo |

Si no hay tiempo para el paso 6, mostrar el informe ya generado (plan B).

## 3. Plan B (RNF7)

| Si falla… | Hacer |
|---|---|
| Docker o una base no levanta | Mostrar las capturas [`../evidencia/dashboards/`](../evidencia/dashboards/) y los informes de `evidencia/`; seguir con la explicación de decisiones (es lo que se evalúa) |
| La API no arranca | Consultas nativas: `docker exec -it fixture2030-cassandra cqlsh`, `docker exec -it fixture2030-redis redis-cli`, Neo4j Browser en http://localhost:7474 |
| Neo4j da "credencial rechazada" | Falta `fixture2030-neo4j/.env` (paso 1); reiniciar la API después de crearlo |
| InfluxDB da "sin configurar" | Falta el token (`sh fixture2030-influxdb/scripts/inicializacion.sh`); si no se puede, decirlo: es una limitación conocida del laboratorio |
| Grafana no muestra datos | Rango de tiempo (arriba a la derecha) y `verificar_targets.sh`; si sigue, mostrar las consultas directo en Prometheus (http://localhost:9090/graph) con [`../docs/metricas_y_consultas.md`](../docs/metricas_y_consultas.md) |
| No hay red ni notebook | El repositorio en GitHub: README, `docs/` y `evidencia/` alcanzan para defender cada decisión con su evidencia |

## 4. Después

```bash
bash fixture2030-hito-13-monitoreo/scripts/limpiar_entorno.sh    # conserva las series
```

Las bases se apagan desde su carpeta con `docker compose down` (sin `-v`).
