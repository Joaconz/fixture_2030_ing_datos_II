# Fixture 2030 — Hito 10 · API REST integrada

**Ingeniería de Datos II** — Santiago Pazos, Valentina Frisoli, Joaquín Núñez

API REST (FastAPI) que expone casos de uso del Fixture Mundial 2030 sobre los módulos NoSQL de los hitos anteriores, cada uno con su propio adaptador:

| Fuente | Módulo | Qué expone la API |
|---|---|---|
| MongoDB (Hito 4) | Equipos y jugadores | Ficha del equipo, plantel paginado |
| Neo4j (Hito 5 + reentrega del Hito 3) | Partidos, eventos y tipos de evento | Detalle del partido, partidos de un equipo, timeline, **alta de eventos validada por tipo** y **cierre validado del partido** |
| Cassandra (Hito 6) | Comentarios | Lectura paginada por partición y alta idempotente |
| Redis (Hito 7) | Sesiones y caché | Validar/invalidar sesión; caché del detalle de partido |
| InfluxDB 3 Core (Hito 8) | Estadísticas en vivo | Ventana temporal cruda o agregada |
| IRIS (Hito 9) | — | **No cubierta**: fuera de la arquitectura desde la reentrega del Hito 3 ([`docs/coherencia_tpo.md`](docs/coherencia_tpo.md) §2) |

Además, un front de consumo en [`web/`](web/) (React + TypeScript) para recorrer los casos de uso desde el navegador.

## Requisitos

- Docker Desktop (o Docker Engine + Compose v2) con los cinco módulos del repo.
- Python **3.12** (con `uv`, o `python3.12 -m venv`). Probado con 3.12.
- Node 20+ para la carga de Mongo (`fixture2030-mongodb/load`) y para el front; `newman` (`npm i -g newman`) para la colección Postman.
- `curl` y bash (macOS, Linux o WSL).

## Puesta en marcha (orden de ejecución)

1. **Fuentes y cargas de muestra:** seguir [`docs/conectividad_y_configuracion.md`](docs/conectividad_y_configuracion.md) §5 (levanta los cinco contenedores, corre las cargas idempotentes de cada hito y siembra el partido de demo `PAR-DEMO-API`).
2. **Configuración:**
   ```bash
   cd fixture2030-hito10-api
   cp .env.example .env     # completar NEO4J_PASSWORD (la de fixture2030-neo4j/.env); el resto tiene defaults
   ```
   El token de InfluxDB no se copia: la API lo lee del archivo local que creó el Hito 8 (`../fixture2030-influxdb/secrets/admin-token.json`, ignorado por git).
3. **Verificar conectividad:** `bash scripts/verificar_conectividad.sh`
4. **Iniciar la API:** `bash scripts/iniciar_api.sh` (crea `.venv` e instala `requirements.txt` si falta). Escucha en `http://localhost:8000`.
5. **Explorar:** Swagger UI en <http://localhost:8000/docs> · contrato en [`openapi/openapi.yaml`](openapi/openapi.yaml) · salud en <http://localhost:8000/health/dependencias>.
6. **Postman:** importar [`postman/fixture2030_collection.json`](postman/fixture2030_collection.json) y el environment [`postman/fixture2030_environment.json`](postman/fixture2030_environment.json) (sin secretos; `baseUrl=http://localhost:8000`). Correr las carpetas en orden; antes de una corrida completa, volver a sembrar `PAR-DEMO-API` y recargar las sesiones de Redis (vencen a los 30 min). Por consola: `bash scripts/ejecutar_pruebas.sh newman`.
7. **Pruebas:** `bash scripts/ejecutar_pruebas.sh unit` (sin Docker) · `integration` · `contrato` · `newman` · `todo`. Detalle en [`tests/README.md`](tests/README.md).
8. **Detener sin borrar datos:** `Ctrl+C` en la API y `docker compose stop` en cada módulo (nunca `down -v`) — ver [`docs/conectividad_y_configuracion.md`](docs/conectividad_y_configuracion.md) §7.

### Ejemplos con cURL

```bash
BASE=http://localhost:8000
curl -i "$BASE/equipos/ARG"
curl "$BASE/equipos/ARG/jugadores?posicion=Delantero&limit=5"
curl -i "$BASE/partidos/PAR-A-1"                         # X-Cache: MISS, después HIT
curl "$BASE/partidos/PAR-A-1/eventos?tipo=GOL"
curl "$BASE/partidos/PAR-D16-01/eventos"                 # 200 con items: [] (partido sin jugar)
curl "$BASE/partidos/PAR-A-1/comentarios?limit=5"        # seguir con ?cursor=<nextCursor>
curl -i "$BASE/sesiones/demo-ses-0000001-1"
curl "$BASE/partidos/PAR-A-1/estadisticas?desde=2030-06-09T13:00:00Z&hasta=2030-06-09T13:30:00Z&agregacion=1m"

# Escrituras (idempotentes por Idempotency-Key)
curl -i -X POST "$BASE/partidos/PAR-DEMO-API/eventos" -H 'Content-Type: application/json' \
     -H 'Idempotency-Key: demo-gol-0001' -d '{"tipo":"GOL","minuto":70,"condicionEquipo":"VISITANTE","dorsalProtagonista":9}'
curl -i -X POST "$BASE/partidos/PAR-DEMO-API/eventos" -H 'Content-Type: application/json' \
     -H 'Idempotency-Key: demo-fin-0001' -d '{"tipo":"FIN_PARTIDO","minuto":90}'
curl -i -X PATCH "$BASE/partidos/PAR-DEMO-API/estado" -H 'Content-Type: application/json' -d '{"estado":"FINALIZADO"}'
curl -i -X POST "$BASE/partidos/PAR-A-1/comentarios" -H 'Content-Type: application/json' \
     -H 'Idempotency-Key: demo-com-0001' \
     -d '{"usuarioId":"USR-0000042","alias":"hincha42","contenido":"¡Golazo!","creadoEn":"2030-06-09T13:47:00Z"}'
curl -i -X DELETE "$BASE/sesiones/demo-ses-0000002-1"

# Errores
curl -i "$BASE/equipos/arg"                              # 400 VALIDATION_ERROR
curl -i "$BASE/partidos/PAR-X-99/eventos"                # 404 MATCH_NOT_FOUND
curl -i "$BASE/sesiones/demo-ses-0000033-1"              # 403 SESSION_BLOCKED
```

## Estructura

```
fixture2030-hito10-api/
├── app/
│   ├── main.py            arma la app (lifespan, middleware, routers, OpenAPI)
│   ├── config/            settings.py — variables de entorno, sin secretos
│   ├── core/              errores, request-id, logs JSON, inyección de dependencias
│   ├── routes/            contrato HTTP por recurso
│   ├── services/          casos de uso + ports.py (interfaces de los adaptadores)
│   ├── adapters/          mongo · neo4j · cassandra · redis · influx (+ base.py: timeout/503/log)
│   └── schemas/           modelos Pydantic de request/response y de error
├── openapi/openapi.yaml   contrato generado desde el código (test de drift)
├── postman/               colección + environment (sin secretos)
├── tests/                 unit/ (sin Docker) · integration/ (contra Docker) · README.md
├── scripts/               iniciar_api · verificar_conectividad · ejecutar_pruebas · exportar_openapi ·
│                          sembrar_demo_neo4j.cypher · prueba_dependencia_caida · medir_latencia
├── docs/                  análisis (§8) + evidencia/
└── web/                   front React + TypeScript (Vite)
```

## Documentación (§8 del enunciado)

| Apartado | Documento |
|---|---|
| Casos de uso | [`docs/casos_de_uso.md`](docs/casos_de_uso.md) |
| Arquitectura y adaptadores | [`docs/arquitectura_y_adaptadores.md`](docs/arquitectura_y_adaptadores.md) |
| Mapa de endpoints, contratos, validación y errores | [`docs/contratos_y_errores.md`](docs/contratos_y_errores.md) |
| Conectividad y configuración | [`docs/conectividad_y_configuracion.md`](docs/conectividad_y_configuracion.md) |
| Idempotencia | [`docs/idempotencia.md`](docs/idempotencia.md) |
| Pruebas y evidencia | [`docs/pruebas_y_evidencia.md`](docs/pruebas_y_evidencia.md) |
| Seguridad | [`docs/seguridad.md`](docs/seguridad.md) |
| Rendimiento básico | [`docs/rendimiento.md`](docs/rendimiento.md) |
| Coherencia con el TPO | [`docs/coherencia_tpo.md`](docs/coherencia_tpo.md) |
| Auditoría del hito | [`docs/auditoria_hito10.md`](docs/auditoria_hito10.md) |

## Limitaciones conocidas

- RF8 (IRIS) no se implementa: decisión de la reentrega del Hito 3 — ⚠️ a confirmar con el profesor.
- Los equipos de Mongo y del grafo no son el mismo roster (Hallazgo H1): la API no los cruza por código.
- Sin autenticación de usuarios: las escrituras quedan abiertas en `localhost` (laboratorio).
- Cifras de rendimiento de un único cliente secuencial en una notebook ([`docs/rendimiento.md`](docs/rendimiento.md) §4).
