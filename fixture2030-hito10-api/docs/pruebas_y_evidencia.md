# Pruebas y evidencia — Hito 10

**Ingeniería de Datos II · Fixture 2030** — Santiago Pazos, Valentina Frisoli, Joaquín Núñez

> RF15 / RF17 / §5.12. Cómo correr cada prueba: [`../tests/README.md`](../tests/README.md). Todas las evidencias de `evidencia/` se generaron con los scripts del repo el **13/10/2026** en la notebook descripta en [`rendimiento.md`](./rendimiento.md) §2; ninguna es una respuesta copiada a mano.

## 1. Resumen de la corrida

| Prueba | Herramienta | Resultado | Evidencia |
|---|---|---|---|
| Unitarias (sin Docker, adaptadores falsos) | pytest | **190 / 190** | [`pruebas_unitarias_20261013-194201.md`](./evidencia/pruebas_unitarias_20261013-194201.md) |
| Integración (API real ↔ 5 fuentes, contraste nativo) | pytest + `docker exec` | **32 / 32** | [`pruebas_integracion_20261013-194201.md`](./evidencia/pruebas_integracion_20261013-194201.md) |
| Funcionales de punta a punta | Newman (Postman) | **39 requests, 150 / 150 aserciones** | [`pruebas_newman_20261013-193859.xml`](./evidencia/pruebas_newman_20261013-193859.xml) |
| Contrato OpenAPI ↔ servidor | schemathesis 4.31 | **641 casos, 0 fallas** (operaciones de lectura) | [`pruebas_contrato_20261013-193906.xml`](./evidencia/pruebas_contrato_20261013-193906.xml) |
| Contrato versionado ↔ código | pytest (`test_openapi_drift`) | OK | incluido en unitarias |
| Dependencia caída (`docker stop`), las 5 fuentes | `prueba_dependencia_caida.sh` | **5 / 5 OK** | `dependencia_caida_<fuente>_*.md` |
| Dependencia colgada (`docker pause`) | script ad hoc en el doc | 503 a los 2,0 s en Redis, Cassandra e InfluxDB | [`dependencia_lenta_pause_20261013-194058.md`](./evidencia/dependencia_lenta_pause_20261013-194058.md) |
| Latencia | `medir_latencia.sh` | p50/p95/máx por fuente | [`latencia_20261013-194117.md`](./evidencia/latencia_20261013-194117.md) |
| Correlación request-id ↔ logs | curl + log de uvicorn | OK | [`logs_correlacion_request_id.md`](./evidencia/logs_correlacion_request_id.md) |
| Cargas de muestra previas | scripts de cada hito | OK | [`cargas/`](./evidencia/cargas/) |

## 2. Cobertura de §5.12

| Pedido del enunciado | Dónde se prueba |
|---|---|
| Una request válida por módulo | Integración: `test_equipo_coincide_con_mongosh`, `test_eventos_coinciden_con_cypher`, `test_comentarios_paginacion_completa_y_ordenada`, `test_sesion_coincide_con_redis_cli`, `test_estadisticas_raw_y_agregadas`; Newman: carpetas 01–05 |
| Un parámetro inválido | `test_equipo_codigo_invalido_400`, `test_eventos_tipo_invalido_400`, `test_plantel_limite_fuera_de_rango_400`, `test_publicar_comentario_sin_zona_horaria_400`, `test_cierre_estado_no_permitido_400`; unitarias con `FuenteNoTocar` (la fuente no se llega a consultar) |
| Un recurso inexistente | `test_equipo_inexistente_404`, `test_eventos_partido_inexistente_404`, `test_comentarios_partido_inexistente_404`, `test_cierre_partido_inexistente_404` |
| Respuesta vacía válida | `test_eventos_partido_sin_eventos_200_vacio` (PAR-D16-01), `test_estadisticas_ventana_sin_datos_200_vacio` |
| Sesión ausente o expirada | `test_sesion_inexistente_404`; unitarias: hash parcial (vencida entre lectura y renovación) → 404; bloqueada → 403 |
| Dependencia detenida o inaccesible | `prueba_dependencia_caida.sh` × 5 fuentes, `docker pause` × 3, unitarias con `FuenteCaida` en cada ruta |
| Escritura repetida | `test_flujo_de_cierre_completo` (POST evento ×2 → 1 nodo en `cypher-shell`; misma clave con otro cuerpo → 409; cierre ×2 → 409), `test_publicar_comentario_idempotente` (POST ×2 → 1 fila en `cqlsh`), `test_cerrar_sesion_y_repetir` |
| Límites, paginación, ventanas | `test_plantel_paginado_completo_sin_repetidos` (contra `countDocuments`), `test_comentarios_paginacion_completa_y_ordenada` (1 y 4 buckets), `test_estadisticas_ventana_*`, `raw` truncado a `limit` |
| Documentación y respuesta real compatibles | schemathesis (641 casos), test de drift, Newman valida forma de cada cuerpo |

## 3. Contraste con clientes nativos (RF17)

Cada endpoint llega a la fuente que le corresponde y devuelve lo mismo que su cliente nativo. Los tests de integración hacen la comparación automáticamente:

| Endpoint | Cliente nativo | Qué se compara |
|---|---|---|
| `GET /equipos/ARG` | `mongosh` `db.equipos.findOne({_id:"ARG"})` | nombre |
| `GET /equipos/ARG/jugadores` (todas las páginas) | `mongosh` `countDocuments({equipoId:"ARG"})` | cantidad, sin repetidos |
| `GET /equipos/ARG/partidos` | `cypher-shell` `MATCH (:Equipo)-[:PARTICIPA_EN]->(p)` | cantidad |
| `GET /partidos/PAR-A-1/eventos` | `cypher-shell` `count` de `OCURRE_EN` | cantidad y orden por secuencia |
| `POST /partidos/PAR-DEMO-API/eventos` ×2 | `cypher-shell` `MATCH (e:Evento {eventoId})` | un solo nodo |
| `PATCH /partidos/PAR-DEMO-API/estado` | `cypher-shell` `GOL` por `condicionEquipo` | marcador derivado |
| `GET /partidos/{id}/comentarios` (todas las páginas) | `cqlsh` sobre `comentarios_por_usuario` | todos los `PUBLICADO` presentes, sin repetidos, orden descendente |
| `POST /partidos/PAR-A-1/comentarios` ×2 | `cqlsh` `count(*)` por `comentario_id` | una sola fila |
| `GET /sesiones/demo-ses-0000001-1` | `redis-cli HGET … usuario_id` | usuario |
| `GET /sesiones/…` no renueva | `redis-cli TTL` | TTL no aumenta |
| `DELETE /sesiones/demo-ses-0000002-1` | `redis-cli EXISTS` y `SISMEMBER` del índice | hash e índice borrados juntos |
| `GET /partidos/PAR-A-1` (MISS → HIT) | `redis-cli TTL f30:cache:partido:PAR-A-1` | copia con TTL ≤ 60 s |
| Alta de `FIN_PARTIDO` | `redis-cli EXISTS f30:cache:partido:PAR-DEMO-API` | caché invalidada |
| `GET /partidos/PAR-A-1/estadisticas` | consulta SQL equivalente a `/api/v3/query_sql` (verificada por el agente del módulo al implementar; 1m en 30 min = 60 puntos, 2 equipos × 30 tramos) | cantidad de puntos |

## 4. Dependencia caída: resultados

| Fuente detenida | Endpoint | HTTP | Tiempo | Notas |
|---|---|---:|---:|---|
| Redis | `GET /sesiones/…` | 503 | 3 ms | `GET /partidos/PAR-A-1` sigue 200 con `X-Cache: BYPASS` |
| MongoDB | `GET /equipos/ARG` | 503 | 2,01 s | el driver reintenta la selección de servidor hasta el timeout |
| Neo4j | `GET /partidos/PAR-A-1/eventos` | 503 | 2,01 s | ídem |
| InfluxDB | `GET /partidos/PAR-A-1/estadisticas` | 503 | 3 ms | conexión rechazada |
| Cassandra | `GET /partidos/PAR-A-1/comentarios` | 503 | 6 ms | `NoHostAvailable` inmediato |

En todos los casos: formato único con `code: DEPENDENCY_UNAVAILABLE`, `/health/dependencias` en 503 con esa fuente `DOWN`, y al volver la fuente la API responde 200 **sin reiniciarse**. Con `docker pause` (proceso colgado, puerto abierto) el corte es exactamente el timeout: 2,0 s.

## 5. Prueba de contrato: alcance

schemathesis genera requests a partir de `openapi/openapi.yaml` (ejemplos, cobertura de límites y fuzzing) y valida status, cabeceras y schemas de cada respuesta. Por defecto sólo se ejercitan las operaciones de **lectura**, para no llenar las bases de demo con eventos y comentarios aleatorios (en particular, el fuzzing podría registrar eventos o cerrar partidos `PAR-D16-*` que están `PROGRAMADO`). Las escrituras quedan cubiertas por integración y Newman con datos controlados; `CONTRATO_ESCRITURAS=1 bash scripts/ejecutar_pruebas.sh contrato` las incluye si se quiere correr sobre una base descartable.

## 6. Barrido de secretos antes del PR

```bash
git grep -nE "apiv3_[A-Za-z0-9]{8,}|Bearer [A-Za-z0-9._-]{12,}|mongodb://[^/@]+:[^/@]+@|redis://:[^@]+@" -- fixture2030-hito10-api
git ls-files fixture2030-hito10-api | grep -E "(^|/)\.env$|secrets/|\.token$"
```

Resultado (13/10/2026): dos coincidencias, ambas esperadas — el propio comando en este documento y un secreto **ficticio** en `tests/unit/test_core.py` (`password=secreto mongodb://u:p@host`), que la prueba usa justamente para verificar que un error inesperado no lo filtra. Ningún `.env`, `secrets/` ni token versionado. Las únicas contraseñas presentes son la de desarrollo de Neo4j `fixture2030` como default de los scripts de prueba — el mismo valor que publica `fixture2030-neo4j/.env.example` del Hito 5 — y el `.env.example` de la API, con `NEO4J_PASSWORD` vacío). Las evidencias se revisaron con el mismo patrón.

## 7. Datos que dejan las pruebas

- Comentarios creados por las pruebas en PAR-A-1, con `comentario_id` `PAR-A-1-API-…` (se distinguen de la carga del Hito 6).
- PAR-DEMO-API queda `FINALIZADO` después del flujo de cierre: `scripts/sembrar_demo_neo4j.cypher` lo vuelve a `PROGRAMADO` y borra los eventos que no son de la siembra (lo ejecuta el fixture de integración antes de cada corrida).
- `DELETE` de `demo-ses-0000002-1`: la recarga de Redis (`carga_muestra.sh`) lo restaura.
