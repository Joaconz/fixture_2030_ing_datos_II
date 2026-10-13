# Contratos, validación y errores — Hito 10

**Ingeniería de Datos II · Fixture 2030** — Santiago Pazos, Valentina Frisoli, Joaquín Núñez

El contrato completo (paths, parámetros, cuerpos, schemas, ejemplos y códigos) es [`../openapi/openapi.yaml`](../openapi/openapi.yaml). **Se genera desde el código** (`scripts/exportar_openapi.py`) y un test (`tests/unit/test_openapi_drift.py`) falla si el archivo versionado no coincide con lo que expone la API; además schemathesis lo contrasta contra el servidor real (ver [`pruebas_y_evidencia.md`](./pruebas_y_evidencia.md)). Con la API corriendo: Swagger UI en <http://localhost:8000/docs>, ReDoc en `/redoc`, JSON en `/openapi.json`.

## 1. Mapa de endpoints

| Método y ruta | Caso de uso | Fuente · operación | Éxito | Errores |
|---|---|---|---|---|
| `GET /equipos/{codigo}` | CU1 | MongoDB · `find_one` por `_id` con proyección | 200 | 400, 404 `TEAM_NOT_FOUND`, 503 |
| `GET /equipos/{codigo}/jugadores` | CU2 | MongoDB · `find` por índice `{equipoId, posicion}`, cursor por dorsal | 200 | 400 (`INVALID_CURSOR`), 404, 503 |
| `GET /equipos/{codigo}/partidos` | CU3 | Neo4j · recorrido `PARTICIPA_EN` | 200 | 400, 404, 503 |
| `GET /partidos/{partidoId}` | CU4 | Neo4j + caché Redis (cache-aside, `X-Cache`) | 200 | 400, 404 `MATCH_NOT_FOUND`, 503 |
| `GET /partidos/{partidoId}/eventos` | CU5 | Neo4j · Cypher por `(partidoId, secuencia)` | 200 (vacío válido) | 400 (`INVALID_CURSOR`), 404, 503 |
| `POST /partidos/{partidoId}/eventos` | CU6 | Neo4j · transacción de escritura + reglas N8 | 201 / 200 replay | 400 (`EVENT_RULE_VIOLATION`), 404, 409 (6 códigos), 503 |
| `PATCH /partidos/{partidoId}/estado` | CU7 | Neo4j · transacción de escritura (cierre CP) | 200 | 400, 404, 409 (`INVALID_TRANSITION`, `MISSING_FIN_PARTIDO`), 503 |
| `GET /partidos/{partidoId}/comentarios` | CU8 | Cassandra · Q0 + particiones `(partido, ventana, bucket)` | 200 (vacío válido) | 400 (`INVALID_CURSOR`), 404, 503 |
| `POST /partidos/{partidoId}/comentarios` | CU9 | Cassandra · `LOGGED BATCH` en dos tablas | 201 / 200 replay | 400 (`COMMENT_OUTSIDE_MATCH_WINDOW`), 404, 503 |
| `GET /sesiones/{sesionId}` | CU10 | Redis · `HGETALL` + `TTL` | 200 | 400, 403 `SESSION_BLOCKED`, 404 `SESSION_NOT_FOUND`, 503 |
| `DELETE /sesiones/{sesionId}` | CU11 | Redis · `MULTI` `SREM` + `DEL` `EXEC` | 204 | 400, 404, 503 |
| `GET /partidos/{partidoId}/estadisticas` | CU12 | InfluxDB 3 · SQL parametrizado, `date_bin` | 200 (vacío válido) | 400 (`INVALID_TIME_WINDOW`, `TIME_WINDOW_TOO_LARGE`), 503 |
| `GET /health` | — | ninguna | 200 | — |
| `GET /health/dependencias` | CU13 | las cinco · ping con timeout | 200 | 503 (mismo cuerpo, alguna `DOWN`) |

Tags de OpenAPI por módulo: `Equipos · MongoDB`, `Partidos · Neo4j`, `Comentarios · Cassandra`, `Sesiones · Redis`, `Estadísticas · InfluxDB`, `Salud`. No hay autenticación en este hito (la sesión se consulta como recurso, no se usa como credencial): ver [`seguridad.md`](./seguridad.md).

## 2. Validación antes de consultar (RF10 / RNF3)

Todo lo siguiente lo rechaza Pydantic/FastAPI **antes** de entrar al servicio; ningún adaptador se llama (hay tests con un adaptador que falla si se lo toca: `FuenteNoTocar`).

| Entrada | Regla |
|---|---|
| `codigo` (path) | `^[A-Z]{3}$` |
| `partidoId` (path) | `^PAR-[A-Z0-9]{1,8}(-[A-Z0-9]{1,8}){0,2}$` |
| `sesionId` (path) | `^[A-Za-z0-9-]{3,64}$` |
| `limit` | jugadores 1–50 (20), partidos de equipo 1–20 (10), eventos 1–200 (50), comentarios 1–50 (20), estadísticas 1–2000 (500) |
| `cursor` | `^[A-Za-z0-9_-]{1,200}={0,2}$`; además el servicio lo decodifica antes de consultar y, si no corresponde a ese listado o partido, responde 400 `INVALID_CURSOR` |
| `posicion` | `Arquero` · `Defensor` · `Mediocampista` · `Delantero` |
| `tipo` (eventos) | uno de los 12 `:TipoEvento` del catálogo N8 |
| `desde`, `hasta` | fecha-hora ISO 8601 **con zona horaria**; el servicio exige `desde < hasta` y `hasta − desde ≤ 3 h` |
| `agregacion` | `raw` · `1m` · `5m` |
| `equipo` (estadísticas) | `^[A-Z]{3}$` |
| `Idempotency-Key` (header, obligatorio en los POST) | `^[A-Za-z0-9_-]{8,64}$` |
| Cuerpo de evento | `tipo` del catálogo, `minuto` 0–130, `condicionEquipo` LOCAL/VISITANTE, `dorsalProtagonista` 1–99, sin campos extra |
| Cuerpo de comentario | `usuarioId` `^USR-[A-Z0-9]{3,12}$`, `alias` 1–40, `contenido` 1–500, `creadoEn` con zona horaria, `minutoPartido` 0–130, `hinchada`, `idioma`, sin campos extra |
| Cuerpo de cambio de estado | sólo `{"estado": "FINALIZADO"}` |

**Reglas por tipo de evento (N8)** — se aplican en el servicio, también antes de tocar Neo4j, y juntan todas las violaciones en `details` (400 `EVENT_RULE_VIOLATION`):

| Tipo | `condicionEquipo` | `dorsalProtagonista` | `minuto` |
|---|---|---|---|
| `INICIO_PARTIDO` | prohibida | prohibido | sólo 0 |
| `FIN_PARTIDO` | prohibida | prohibido | 0–130 |
| `CORNER` | obligatoria | opcional | 0–130 |
| `PASE`, `ATAJADA`, `ASISTENCIA`, `GOL`, `PENAL`, `FALTA`, `TARJETA_AMARILLA`, `TARJETA_ROJA`, `SUSTITUCION` | obligatoria | obligatorio | 0–130 |

Las reglas que dependen del **estado** del partido (finalizado, ya hay `FIN_PARTIDO`, `INICIO`/`FIN` únicos, el minuto no retrocede respecto del último evento, tipo presente en el catálogo) se chequean dentro de la transacción de escritura, porque tienen que ser atómicas con el alta: devuelven 409.

## 3. Formato único de error (RF12 / RNF4)

```json
{
  "code": "MATCH_NOT_FOUND",
  "message": "No existe el partido PAR-X-99.",
  "requestId": "req-3f9c2a1b7d4e5f60",
  "details": [{"campo": "path.partido_id", "problema": "..."}]
}
```

- `requestId` es el mismo valor de la cabecera `X-Request-Id` y de las líneas de log de esa request.
- `details` sólo aparece en validaciones (qué campo y qué problema) y en 503 (qué dependencia).
- Nunca se incluyen URIs, hosts, puertos, credenciales, consultas, parámetros internos ni trazas. Un error inesperado responde 500 `INTERNAL_ERROR` con un mensaje fijo; el tipo de excepción queda sólo en el log (test `test_error_inesperado_da_500_seguro_con_request_id`, que fuerza una excepción con una contraseña en el mensaje y verifica que no sale).
- FastAPI responde 422 por defecto a la validación; esta API lo reemplaza por **400** (`core/errors.py`) y el OpenAPI no documenta 422 (test `test_contrato_no_documenta_422`).
- Rutas inexistentes: 404 `ROUTE_NOT_FOUND`; método no permitido: 405 `METHOD_NOT_ALLOWED`, con el mismo formato.

## 4. Tabla de códigos

| HTTP | `code` | Significado | Dónde |
|---|---|---|---|
| 400 | `VALIDATION_ERROR` | Parámetro, query, header o cuerpo fuera de contrato | todas |
| 400 | `INVALID_CURSOR` | Cursor que no decodifica o no corresponde al listado/partido | jugadores, eventos, comentarios |
| 400 | `EVENT_RULE_VIOLATION` | El cuerpo no cumple las reglas del tipo de evento | POST eventos |
| 400 | `COMMENT_OUTSIDE_MATCH_WINDOW` | `creadoEn` fuera del tramo −15′/+125′ del partido | POST comentarios |
| 400 | `INVALID_TIME_WINDOW` | `desde ≥ hasta` | estadísticas |
| 400 | `TIME_WINDOW_TOO_LARGE` | Ventana mayor a 3 h | estadísticas |
| 403 | `SESSION_BLOCKED` | La sesión existe pero está `BLOQUEADA` | GET sesión |
| 404 | `TEAM_NOT_FOUND` | Equipo inexistente en la fuente consultada | equipos |
| 404 | `MATCH_NOT_FOUND` | Partido inexistente (en comentarios: sin fila de Q0) | partidos, eventos, comentarios |
| 404 | `SESSION_NOT_FOUND` | Sesión inexistente o expirada (Redis ya la borró) | sesiones |
| 409 | `MATCH_FINALIZED` | Evento sobre un partido `FINALIZADO` | POST eventos |
| 409 | `EVENT_AFTER_FIN` | Evento posterior a `FIN_PARTIDO` | POST eventos |
| 409 | `DUPLICATE_UNIQUE_EVENT` | Segundo `INICIO_PARTIDO` o `FIN_PARTIDO` | POST eventos |
| 409 | `EVENT_OUT_OF_ORDER` | El `minuto` es anterior al del último evento registrado del partido | POST eventos |
| 409 | `EVENT_TYPE_NOT_IN_CATALOG` | El tipo no existe como `:TipoEvento` en el grafo | POST eventos |
| 409 | `IDEMPOTENCY_KEY_REUSED` | Misma clave con otro cuerpo | POST eventos |
| 409 | `INVALID_TRANSITION` | El partido no está `PROGRAMADO` (p. ej. cierre repetido) | PATCH estado |
| 409 | `MISSING_FIN_PARTIDO` | Cierre sin el evento `FIN_PARTIDO` | PATCH estado |
| 503 | `DEPENDENCY_UNAVAILABLE` | Fuente caída, rechazo de conexión o timeout; incluye `Retry-After: 5` | todas las que consultan una fuente |
| 500 | `INTERNAL_ERROR` | Error inesperado; detalle sólo en logs | todas |

## 5. Ausencia, vacío y caída: cómo se distinguen (preguntas guía 4–6, 12)

| Situación | Respuesta |
|---|---|
| Recurso que no existe | 404 con `code` de dominio |
| Recurso que existe y no tiene elementos (partido sin eventos, sin comentarios, ventana sin puntos) | 200 con lista vacía |
| La fuente no responde | 503 `DEPENDENCY_UNAVAILABLE` — nunca 200 vacío |
| Clave Redis inexistente | 404 `SESSION_NOT_FOUND` (Redis respondió que no está) |
| Redis no disponible | 503 (Redis no respondió) |
| Estadísticas de un `partidoId` que InfluxDB no conoce | 200 vacío: InfluxDB no es la fuente de verdad de la existencia del partido (lo es Neo4j); se documenta en lugar de agregar una segunda consulta |

## 6. Cabeceras

| Cabecera | Dirección | Uso |
|---|---|---|
| `X-Request-Id` | request (opcional) / response (siempre) | Correlación con los logs; si el cliente manda uno seguro (`^[A-Za-z0-9._-]{1,64}$`) se respeta |
| `Idempotency-Key` | request (POST) | Idempotencia de altas — ver [`idempotencia.md`](./idempotencia.md) |
| `Idempotent-Replayed: true` | response | El POST era un reintento: 200 con el recurso ya existente |
| `X-Cache` | response (`GET /partidos/{id}`) | `HIT`, `MISS` o `BYPASS` |
| `Retry-After: 5` | response (503) | Sugerencia de reintento |

## 7. Paginación y límites (RNF12)

| Endpoint | Estrategia |
|---|---|
| Jugadores | `limit` + cursor opaco del último dorsal (orden por dorsal) |
| Eventos | `limit` + cursor opaco de la última secuencia |
| Comentarios | `limit` + cursor opaco `[versión, hash del partido, ventana, último creado_en, último comentario_id]`. Los buckets de una ventana se mezclan en un orden total (`creado_en DESC, comentario_id ASC`), así que una sola posición por ventana alcanza para continuar en todos los buckets sin repetir ni saltear. Trabajo acotado por request: ≤ 64 lecturas de partición y ≤ 500 filas examinadas; si se alcanza el tope la página vuelve corta pero con `nextCursor`. La última página puede venir vacía con `nextCursor: null`. Sólo se devuelven comentarios `PUBLICADO` (filtrado en la aplicación, documentado) |
| Partidos de equipo | `limit` ≤ 20 (un equipo juega a lo sumo 4–8 partidos en el fixture cargado) |
| Estadísticas | ventana ≤ 3 h + `limit` ≤ 2000 puntos + `truncado` |
