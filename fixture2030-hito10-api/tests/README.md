# Pruebas de la API REST integrada (Hito 10)

Todos los comandos se corren desde `fixture2030-hito10-api/`. El punto de entrada
único es `scripts/ejecutar_pruebas.sh`; los reportes (JUnit) y las evidencias quedan en
`docs/evidencia/` con fecha en el nombre. Ningún script imprime contraseñas ni tokens.

| Tipo | Comando | Necesita | Qué demuestra (§5.12) |
|---|---|---|---|
| Unitarias | `bash scripts/ejecutar_pruebas.sh unit` | Sólo `.venv` (sin Docker) | Reglas de cada caso de uso, validación antes de tocar la fuente, formato único de error, 503 ante fuente caída, cache-aside |
| Integración | `bash scripts/ejecutar_pruebas.sh integration` | Las cinco fuentes en Docker | Los adaptadores reales contra las bases cargadas en los Hitos 4–8 |
| Contrato | `bash scripts/ejecutar_pruebas.sh contrato` | API en `:8000` + fuentes | Que las respuestas reales cumplen `openapi/openapi.yaml` |
| Funcionales (Newman) | `bash scripts/ejecutar_pruebas.sh newman` | API + fuentes + datos de demo | Cada endpoint de punta a punta, errores esperados y el flujo de cierre |
| Dependencia caída | `bash scripts/prueba_dependencia_caida.sh [fuente]` | API + Docker | 503 acotado por timeout, degradación de la caché y recuperación sin reiniciar |
| Latencia | `bash scripts/medir_latencia.sh [N]` | API + fuentes | p50/p95/máx por fuente con método explícito (RNF18) |
| Conectividad | `bash scripts/verificar_conectividad.sh` | Docker | Contenedor, puerto y comando nativo de cada fuente, y `/health/dependencias` |

`bash scripts/ejecutar_pruebas.sh todo` corre unit → integration → contrato → newman y se
detiene en la primera falla.

## 1. Unitarias (`tests/unit`, sin Docker)

```bash
.venv/bin/python -m pytest -q          # o: bash scripts/ejecutar_pruebas.sh unit
```

La app real se arma con `create_app()` y cada fuente se reemplaza por un adaptador falso
mediante `app.dependency_overrides` (fixture `make_client` en `tests/unit/conftest.py`):

- `FuenteCaida(nombre)`: todo método lanza `DependencyUnavailableError` → la ruta debe dar 503.
- `FuenteNoTocar(nombre)`: falla el test si el servicio llega a la fuente; prueba que la
  entrada inválida se rechaza con 400 **antes** de consultar (RNF3).
- `fakes_<fuente>.py`: implementaciones en memoria de cada puerto (`app/services/ports.py`).

Qué cubre cada archivo de este módulo:

| Archivo | Caso | Cubre |
|---|---|---|
| `test_estadisticas.py` | CU12 | Ventana invertida o vacía (`INVALID_TIME_WINDOW`), > 3 h (`TIME_WINDOW_TOO_LARGE`), sin zona horaria, parámetros fuera de contrato: 400 sin tocar InfluxDB; ventana de exactamente 3 h válida; sin puntos → 200 `puntos: []`; `limit + 1` para `truncado`; InfluxDB caído → 503 (nunca lista vacía) |
| `test_adapter_influx.py` | CU12 | Con `httpx.MockTransport`: SQL **parametrizado** (los valores del cliente no aparecen en el texto SQL, viajan en `params`), cabecera `Authorization`, `LIMIT` validado, `date_bin` + `last_value` + `max` (nunca `sum` sobre acumulados), mapeo de filas y tiempo UTC con zona, columnas NULL ausentes, 200 `[]` → vacío, 400/401/403/404/5xx y errores de red → 503, sin token → 503 sin llamar a InfluxDB, `/health` sin token |
| `test_partidos_detalle.py` | CU4 | MISS → HIT con el mismo cuerpo y TTL configurado; Redis caído → `BYPASS`; SET fallido → `BYPASS` sin error; 404 `MATCH_NOT_FOUND` sin cachear la ausencia; caché corrupta → MISS y se sobrescribe; Neo4j caído sin caché → 503, con caché vigente → HIT |
| `test_salud.py` | CU13 | Cinco UP → 200 `OK`; una DOWN → 503 con el mismo cuerpo; timeout informado; excepción inesperada → DOWN sin filtrar hosts ni credenciales; ping no implementado → DOWN; pings en paralelo |
| `test_core.py` | Transversal | 400 en lugar de 422, `X-Request-Id`, formato único, CORS/PNA |
| `test_openapi_drift.py` | Contrato | `openapi/openapi.yaml` coincide con el que genera la app (`scripts/exportar_openapi.py`) |

## 2. Integración (`tests/integration`, con Docker)

```bash
bash scripts/verificar_conectividad.sh      # primero: las cinco fuentes OK
bash scripts/ejecutar_pruebas.sh integration
# = .venv/bin/python -m pytest tests/integration -m integration -p no:cacheprovider
```

Usan los adaptadores reales contra los contenedores (`fixture2030_mongo`, `fixture2030-neo4j`,
`fixture2030-cassandra`, `fixture2030-redis`, `fixture2030-influxdb`) con los datos de los
Hitos 4–8. La contraseña de Neo4j y el token de InfluxDB se leen del entorno / `.env` /
`fixture2030-influxdb/secrets/admin-token.json` (ignorados por git).

## 3. Contrato (Schemathesis 4.31)

```bash
bash scripts/iniciar_api.sh                 # en otra terminal
bash scripts/ejecutar_pruebas.sh contrato
```

Genera requests a partir de `openapi/openapi.yaml` (fases `examples`, `coverage`, `fuzzing`)
y verifica `not_a_server_error`, `status_code_conformance`, `content_type_conformance`,
`response_headers_conformance`, `response_schema_conformance` y `negative_data_rejection`
(una entrada inválida debe ser 4xx). Corrida acotada y reproducible: `--max-examples 30`
(`CONTRATO_MAX_EJEMPLOS`), `--seed 2030` (`CONTRATO_SEMILLA`), un worker.

Por defecto sólo se prueban las operaciones **GET**: el fuzzing de los POST/PATCH/DELETE
escribiría eventos y comentarios basura en las bases de demo. `CONTRATO_ESCRITURAS=1`
las incluye (re-sembrar después con `scripts/sembrar_demo_neo4j.cypher`). Las fuentes tienen
que estar arriba: un 503 legítimo cuenta como falla de `not_a_server_error`.

## 4. Funcionales con Newman (`postman/`)

```bash
bash scripts/ejecutar_pruebas.sh newman
# = newman run postman/fixture2030_collection.json -e postman/fixture2030_environment.json
```

Preparación (una vez antes de cada corrida completa):
1. sesiones de demo de Redis recién cargadas (`fixture2030-redis`): tienen TTL de 30 min;
2. partido de demo en estado inicial:
   `docker exec -i fixture2030-neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" < scripts/sembrar_demo_neo4j.cypher`.

Carpetas: Salud · Equipos/MongoDB · Partidos/Neo4j (detalle MISS→HIT) · Comentarios/Cassandra
(publicación 201 y reintento 200 con `Idempotent-Replayed`, paginación con `nextCursor`
encadenado) · Sesiones/Redis (200|404 sólo en la sesión de demo por el TTL, 404, 403,
DELETE 204 y repetido 404) · Estadísticas/InfluxDB (raw truncado, 1m, ventana invertida,
> 3 h, sin datos) · Escenarios de error · Flujo de cierre de `PAR-DEMO-API` (POST GOL 201 →
reintento 200 → PATCH 409 `MISSING_FIN_PARTIDO` → FIN_PARTIDO 201 → PATCH 200 con marcador
1–1 → PATCH 409 `INVALID_TRANSITION` → POST 409 `MATCH_FINALIZED`).

Cada request manda un `X-Request-Id` fijo (`pm-…`) para encontrarla en los logs de la API, y
sus tests verifican: status exacto, `code` en los errores, `requestId` del cuerpo = cabecera
`X-Request-Id`, y la forma del cuerpo. La `Idempotency-Key` base (`idemKey`) la genera el
pre-request de la colección una vez por corrida.

## 5. Dependencia caída

```bash
bash scripts/prueba_dependencia_caida.sh redis      # o mongodb | neo4j | cassandra | influxdb
```

Mide un endpoint de la fuente con la fuente arriba, hace `docker stop`, repite (esperado: 503
`DEPENDENCY_UNAVAILABLE` en menos de `DEP_TIMEOUT_S + 1` s y `/health/dependencias` 503; para
Redis además `/partidos/PAR-A-1` sigue 200 con `X-Cache: BYPASS`), hace `docker start`, espera
healthy y verifica que la API se recupera sin reiniciarse. Sólo `stop`/`start`: nunca borra
contenedores ni volúmenes, y un `trap` vuelve a arrancar la fuente si el script se interrumpe.
Evidencia: `docs/evidencia/dependencia_caida_<fuente>_<fecha>.md`.

## 6. Latencia (RNF18)

```bash
bash scripts/medir_latencia.sh          # N = 200 por endpoint
bash scripts/medir_latencia.sh 500
```

N requests secuenciales por endpoint (uno por fuente + detalle de partido en HIT y en MISS),
tiempo `%{time_total}` de curl en la misma notebook, percentiles por rango más cercano. El
encabezado del script describe el método completo. Evidencia:
`docs/evidencia/latencia_<fecha>.md` con fecha, `uname -a`, CPUs, memoria, versión de la API y N.
