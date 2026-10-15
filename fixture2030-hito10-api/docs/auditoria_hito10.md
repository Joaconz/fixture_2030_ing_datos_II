# Auditoría — Hito 10: API REST integrada (FastAPI)

Auditoría posterior a la implementación con el método de `/auditar-hito` (generaliza `fixture2030-mongodb/docs/HITO4_AUDIT_SPEC.md`). Fecha: 2026-10-15. PR auditado: [Joaconz/fixture_2030_ing_datos_II#13](https://github.com/Joaconz/fixture_2030_ing_datos_II/pull/13), rama `claude/hito-10-api-rest-fixture-f1dca3`, commit `ccac21d`.

**Insumos contra los que se auditó:** el PDF del enunciado (*Hito 10 — Requisitos Técnicos: API REST Integrada del Fixture 2030*, RF1–RF20, RNF1–RNF18, §5–§12) y la Clase 11 (*Acceso a BD NoSQL desde aplicaciones*). La numeración RF/RNF de abajo es la del enunciado.

## Resumen ejecutivo

- **El hito está bien resuelto y la evidencia del PR se reprodujo.** Contra las 5 bases reales en Docker: 191 pruebas unitarias OK, 32 de integración OK (con contraste contra `mongosh`, `cypher-shell`, `cqlsh` y `redis-cli`), Newman 39 requests / 150 aserciones OK, schemathesis 641 casos / 0 fallas. Mismos números que declara el PR.
- **Un incumplimiento objetivo, corregido:** un artefacto generado (`.schemathesis/…/manifest.json`) estaba versionado y cambia en cada corrida.
- **Un faltante contra el enunciado, no corregible por nosotros:** RF8 (IRIS). Es una decisión de alcance que depende del profesor (H2 en el estado canónico).
- **Cosas de más** respecto del enunciado y de la Clase 11: ver §4. La más grande es el front `web/` (60 archivos, ~8.000 líneas): el enunciado no pide ningún front. No se tocó nada de esto; queda señalado para que el equipo decida.

## 1. Tabla de requisitos

### Requisitos funcionales

| ID | Requisito (resumen del enunciado) | Evidencia | Estado |
|---|---|---|---|
| RF1 | Servicio HTTP con recursos del Fixture 2030 | FastAPI levantada; `GET /health/dependencias` → las 5 fuentes `UP` | PASS |
| RF2 | Casos de uso documentados antes de las rutas | `docs/casos_de_uso.md` (CU1–CU13) con las columnas de §5.1; cada ruta del OpenAPI tiene su CU | PASS |
| RF3 | Endpoints MongoDB (equipos/jugadores) | `GET /equipos/ARG` y `/jugadores` paginado; `test_equipo_coincide_con_mongosh`, `test_plantel_paginado_completo_sin_repetidos` | PASS |
| RF4 | Endpoints Neo4j con Cypher parametrizado | `/partidos/{id}`, `/eventos`, `/equipos/{c}/partidos`; `grep` de `.format(`/concatenación en `adapters/neo4j.py` → sin coincidencias; integración contra `cypher-shell` | PASS |
| RF5 | Comentarios en Cassandra respetando la partición del Hito 6 | `GET/POST /partidos/{id}/comentarios`; consulta siempre con `(partido_id, ventana, bucket)`; el único `f"…"` en CQL interpola el keyspace de configuración, no entrada del cliente | PASS |
| RF6 | Sesión/dato temporal en Redis (ausente o expirada) | `GET /sesiones/{id}`: 200 / 404 `SESSION_NOT_FOUND` / 403 `SESSION_BLOCKED`; con Redis detenido: 503 en 22 ms (distinto de 404) | PASS |
| RF7 | Estadísticas InfluxDB con intervalo/agregación acotados | `desde`/`hasta` con zona horaria, ventana ≤ 3 h, `raw/1m/5m`, `limit ≤ 2000`; SQL con `$param`; sin puntos → 200 `puntos: []` | PASS |
| RF8 | Endpoint sobre IRIS | No implementado. Documentado como fuente no cubierta (`docs/coherencia_tpo.md` §2). Ver §3 | **No cubierto — pendiente de confirmar con el profesor** |
| RF9 | Separar HTTP, caso de uso y acceso a la base | `app/routes` → `app/services` (+`ports.py`) → `app/adapters`; `grep` de imports de drivers (`pymongo`, `neo4j`, `cassandra`, `redis`, `httpx`) fuera de `adapters/` → sin coincidencias | PASS |
| RF10 | Validar ruta, query y cuerpo antes de consultar | `GET /equipos/arg` → 400 `VALIDATION_ERROR` sin tocar Mongo; patrones en `schemas/common.py`; `limit`, ventanas y cursores acotados | PASS |
| RF11 | Respuestas de éxito, ausencia, validación, conflicto, dependencia caída y error interno | 200/201/204, 404, 400, 409 (`INVALID_TRANSITION`, `MISSING_FIN_PARTIDO`, `MATCH_FINALIZED`…), 503, 500 seguro (`test_core.py`) | PASS |
| RF12 | Formato de error único sin secretos | `{code, message, requestId, details?}` en todos los errores; test con `password=… mongodb://u:p@host` verifica que no se filtra | PASS |
| RF13 | OpenAPI + Swagger UI | `openapi/openapi.yaml` (3.1.0, `servers`, tags por módulo, 99 `example`); `/docs` y `/openapi.json` → 200; `test_openapi_drift.py` falla si el YAML se desactualiza | PASS |
| RF14 | Postman/cURL con rutas principales y errores | Colección + environment sin secretos; Newman: 39 requests, **150/150** aserciones, 0 fallas | PASS |
| RF15 | Pruebas: éxito, inválido, inexistente, dependencia caída | Unit + integración + contrato + Newman. Dependencia caída reproducida a mano (ver §2) | PASS |
| RF16 | Configuración separada de secretos | `.env.example` sin secretos; `NEO4J_PASSWORD` vacío; token de Influx leído de archivo ignorado (`secrets/`) | PASS |
| RF17 | Evidencia de que cada endpoint llega a su fuente y cumple el contrato | 32 pruebas de integración que contrastan con clientes nativos + schemathesis 641/641 | PASS |
| RF18 | Request ID y correlación con logs | `X-Request-Id` en cada respuesta (eco del enviado) y `request_id` en los logs del acceso y del adaptador (visto en `docker logs`) | PASS |
| RF19 | Lectura vs. escritura e idempotencia | `docs/casos_de_uso.md` §4 y `docs/idempotencia.md`; la repetición con la misma `Idempotency-Key` está cubierta por las pruebas de integración (32 OK) y por Newman | PASS |
| RF20 | Código, docs, contratos y pruebas en GitHub | PR #13 con 5 commits por ola (esqueleto → adaptadores/pruebas → docs → front/code review → README) | PASS |

### Requisitos no funcionales

| ID | Aspecto | Evidencia | Estado |
|---|---|---|---|
| RNF1 | Separación de responsabilidades | Rutas de 29–75 líneas; lógica en `services/`, drivers en `adapters/` | PASS |
| RNF2 | Contrato = implementación | Test de drift + schemathesis (641 casos, `response_schema_conformance`) + Newman | PASS |
| RNF3 | Validar antes de consultar | `GET /equipos/arg` → 400 sin consulta a Mongo (RF10); la validación es declarativa (Pydantic) y corre antes del servicio | PASS |
| RNF4 | Respuestas consistentes | Un solo esquema de error; paginación `{items, nextCursor}` | PASS |
| RNF5 | Aislamiento de fuentes | Ver RF9 | PASS |
| RNF6 | Configuración por entorno | Todo sale de `app/config/settings.py` (variables de entorno / `.env` ignorado) | PASS |
| RNF7 | Sin secretos publicados | Sin `.env`, `secrets/`, token ni URI con credenciales versionados; `.gitignore` los excluye. Nota: ver §3, punto 3 (contraseña de desarrollo de Neo4j) | PASS, con nota |
| RNF8 | Timeouts | `DEP_TIMEOUT_S=2.0` en cada driver + `wait_for`; documentado en `conectividad_y_configuracion.md` §4 | PASS |
| RNF9 | Dependencia caída ≠ request colgada ni dato técnico | Cassandra detenida: 503 en 11 ms; Redis detenido: 503 en 22 ms (sesiones) y 200 `BYPASS` (detalle de partido); Influx detenida: 503 en 25 ms; Neo4j con `docker pause`: **503 a 2,01 s**. Tras reiniciar Cassandra, `/health/dependencias` volvió a `OK` sin reiniciar la API | PASS |
| RNF10 | Logs útiles sin secretos | Logs JSON con ruta, método, `request_id`, dependencia, operación, resultado y `duracion_ms`; sin cuerpos ni credenciales | PASS |
| RNF11 | Reproducibilidad por README | README y `conectividad_y_configuracion.md` §5 completos. **No se siguió literal:** los scripts son bash (`.venv/bin`) y la auditoría se hizo en Windows; la API se corrió en un contenedor `python:3.12` con las mismas variables | No verificado literalmente |
| RNF12 | Paginación y límites | `limit` con máximo en todas las listas; cursores opacos; ventana de Influx ≤ 3 h | PASS |
| RNF13 | Consulta ligada a un patrón de acceso | Mongo por `{equipoId, posicion}`; Neo4j por partición de partido; Cassandra por partición; Redis por clave; Influx por `partido_id` + tiempo. Sin escaneos | PASS |
| RNF14 | Idempotencia documentada | `docs/idempotencia.md` | PASS |
| RNF15 | Legibilidad | Estructura navegable y nombres por módulo | PASS |
| RNF16 | GitHub con acceso al docente | Repositorio e historial OK; el acceso del docente no se puede ver desde acá | No verificable — falta insumo |
| RNF17 | Integridad de datos | Identificadores, timestamps y estados preservados (contraste con clientes nativos) | PASS |
| RNF18 | Rendimiento con método y evidencia | `docs/rendimiento.md` declara método, volumen, entorno y limitaciones (200 requests secuenciales, notebook Apple Silicon). **Las cifras no se re-midieron** (otro equipo y otro SO); se verificó que el método esté descripto | PASS (documental) |

### Estructura de §8 y §9

Los 9 apartados de §8 existen (`casos_de_uso`, `arquitectura_y_adaptadores`, `contratos_y_errores`, `conectividad_y_configuracion`, `idempotencia`, `pruebas_y_evidencia`, `seguridad`, `rendimiento`, `coherencia_tpo`). El árbol de §9 está completo (`README.md`, `app/{routes,services,adapters,schemas,config}`, `openapi/`, `postman/`, `tests/{unit,integration,README.md}`, `scripts/{iniciar_api,verificar_conectividad,ejecutar_pruebas}`, `docs/`, `.gitignore`).

## 2. Cómo se verificó

Entorno: Windows 11, Docker Desktop. Bases: MongoDB, Neo4j, Cassandra, Redis e InfluxDB 3 en contenedores; cargas de muestra de cada hito más `sembrar_demo_neo4j.cypher`. API en `python:3.12-slim` (el driver de Cassandra no carga en Python 3.13 y el 3.11 local estaba roto).

| Comando | Resultado |
|---|---|
| `pytest tests/unit` | 191 passed |
| `pytest tests/integration -m integration` | 32 passed (con Mongo limpio; ver el primer intento en §3, punto 4) |
| `newman run postman/fixture2030_collection.json -e …` | 39 requests, 150/150 aserciones |
| `schemathesis run openapi/openapi.yaml --include-method GET …` | 641 generados, 641 pasaron (2 corridas). Ver nota abajo |
| `node load/seed.js` ×2 contra Mongo 7 vacío | 64 equipos, 1.472 jugadores, 1.472 DNI únicos, ambas veces |
| Cassandra / Redis / Influx detenidas; Neo4j con `docker pause` | 503 en 11 / 22 / 25 ms; 503 a 2,01 s |

**Nota sobre schemathesis.** La primera corrida dio 1 falla: un 503 de `/partidos/PAR-A-5/estadisticas` a los 2.005 ms (timeout de 2 s de InfluxDB en la primera consulta en frío, con mi API en contenedor llegando por `host.docker.internal`). Las dos corridas siguientes dieron 641/641. Es el timeout funcionando como está diseñado, no un bug de la API, pero muestra que **la primera consulta a Influx en frío puede rozar el límite de 2 s**; está bien documentado (`conectividad_y_configuracion.md` §4).

## 3. Cambios aplicados y puntos señalados

### Cambios aplicados automáticamente

1. **Artefacto generado versionado.** `fixture2030-hito10-api/.schemathesis/default/cache/crashes/manifest.json` estaba en el repositorio y cambia en cada corrida de contrato (la mía lo modificó). La Clase 11 pide excluir "artefactos generados". Se quitó del índice y se agregó `.schemathesis/` al `.gitignore`.

### Decisiones **no tocadas**, para revisión humana

1. **RF8 (IRIS) sin implementar.** El enunciado pide el endpoint y su restricción "Cobertura" dice que hay que cubrir los módulos que el equipo "haya desarrollado y pueda ejecutar". El equipo desarrolló IRIS en el Hito 9 (el volumen `fixture2030_iris_durable` sigue en esta máquina). El PR lo justifica con la reentrega del Hito 3, pero el ok del profesor no cubre explícitamente RF8. Registrado como **H2** en `docs/ESTADO-CANONICO-NECESIDADES.md`. Riesgo de nota: alto si el profesor no lo acepta. Camino de menor costo si hace falta: agregar el adaptador IRIS como sexto módulo (la arquitectura por puertos lo permite).
2. **Cosas de más** (§4).
3. **Contraseña de desarrollo de Neo4j en el repo.** `fixture2030` aparece literal en comandos de `docs/` y como default de `NEO4J_PASSWORD` en `tests/integration/conftest.py` y los scripts. Es el mismo valor que ya publica `fixture2030-neo4j/.env.example` (Hito 5, aprobado) y el PR lo documenta (`pruebas_y_evidencia.md`). RNF7 dice "no publicar passwords": lo más estricto sería leerla siempre de `NEO4J_PASSWORD`. No se cambió porque toca varios archivos y es una decisión del equipo.
4. **Mongo desactualizado en mi notebook.** El primer intento de integración dio 31/32: el Mongo local tenía 2.673 jugadores con DNI repetidos (carga vieja, anterior al seed determinístico). No es un defecto del PR; confirma que el seed hace upsert y no limpia, así que quien tenga datos viejos debe partir de un Mongo vacío. El README del PR no lo advierte.

### Gaps de documentación

- Agregar al README una línea que diga que `seed.js` no borra datos previos (ver punto 4).
- Confirmar con el profesor RF8 y, si lo acepta, citar la respuesta en `coherencia_tpo.md` §2 (hoy figura como "a confirmar").

## 4. Qué hay de más (pedido: "que no haya hechas cosas de más")

Criterio: se compara con el enunciado y con lo visto en la Clase 11. Sólo se listan cosas que ninguno de los dos pide.

| # | Qué es | Dónde | Por qué es de más | Recomendación |
|---|---|---|---|---|
| 1 | **Front React + TypeScript** (Vite, Vitest, ESLint, tipos generados del OpenAPI) | `web/` — 60 archivos, ~8.000 líneas (la API en sí son ~3.300) | El enunciado pide una API, OpenAPI y Postman/Swagger como forma de explorarla (RF13, RF14). No menciona ningún front, y dice que se evalúa "sobre el repositorio, la API, la documentación y las pruebas" | **Sacarlo del PR.** Es lo más grande y lo más claro |
| 2 | Configuración para el front: CORS, Private Network Access para Vercel, `CORS_ORIGINS`, referencias a Vercel en docs | `app/main.py` (~10 líneas), `settings.py`, `.env.example`, `conectividad_y_configuracion.md` | Sólo existe para que ande el front | Sacarla junto con el front |
| 3 | `POST /partidos/{id}/eventos`: alta de eventos con reglas por tipo de evento (12 tipos), `secuencia` serializada, `Idempotency-Key` | `routes/partidos.py`, `services/eventos.py` (158 líneas), 32 tests, `sembrar_demo_neo4j.cypher`, colección Postman | RF4 y §5.3 piden **consultar** partidos, eventos y relaciones en Neo4j. El alta de eventos no se pide ni se vio en clase | Decisión del equipo. Si se saca, `PATCH /estado` sigue siendo defendible, pero hay que ver cómo se demuestra el cierre (hoy depende de este alta) |
| 4 | Caché cache-aside en Redis del detalle del partido (`X-Cache`, invalidación al escribir) | `adapters/redis.py`, `services/partidos.py` | No está en el enunciado ni en la clase (la pregunta guía 19 sólo pregunta *qué podría* cachearse). Es la única request que combina dos fuentes | **Defendible:** §6 permite integraciones "justificadas por el caso de uso" y el PR trae medición (5,9 → 1,5 ms). Dejarlo sólo si el equipo puede explicarlo |
| 5 | `GET /health` y `GET /health/dependencias` | `routes/salud.py` | El enunciado pide *documentar cómo verificar* la conectividad (§5.13, `verificar_conectividad.*`), no un endpoint | Chico y útil para RNF9; dejar |

**Lo que está justificado y no cuenta como de más:** `PATCH /partidos/{id}/estado` (sustituye a la "transición validada" que la Clase 11 y §5.10 ubican en IRIS), `DELETE /sesiones/{id}` (§5.3 pide "invalidación"), `POST /comentarios` (RF5 lo admite "cuando corresponda"), las agregaciones `1m/5m` (RF7), schemathesis (la clase pide pruebas de contrato) y los documentos de §8.

## 5. Estado final

| Medida | Valor |
|---|---|
| RF cumplidos | 19 de 20 (RF8 pendiente) |
| RNF cumplidos | 16 de 18 (RNF11 y RNF16 no verificables literalmente) |
| Pruebas | 191 unit + 32 integración + 150 aserciones Newman + 641 casos schemathesis, todos OK |
| Cambios aplicados | 1 (artefacto generado) |
| Decisiones señaladas | RF8 (H2), lo de más (§4), contraseña de desarrollo, advertencia del seed |
