# Health, readiness y diagnóstico por dependencia (§5.6)

Se **implementan** en la API del Hito 10. Los dos primeros endpoints son del Hito 10 y se cambiaron en este hito; `/health/ready` es nuevo. Código: `fixture2030-hito10-api/app/routes/salud.py` y `app/services/salud.py`.

| Endpoint | Pregunta | Toca las bases | Respuesta |
|---|---|---|---|
| `GET /health` | **Liveness**: ¿el proceso de la API está vivo? | **no** | 200 `{"estado":"OK"}` |
| `GET /health/ready` | **Readiness**: ¿puede recibir tráfico para su caso central? | usa el chequeo profundo (cacheado) | 200 `LISTA` / 200 `LISTA_DEGRADADA` / **503 `NO_LISTA`** |
| `GET /health/dependencias` | **Diagnóstico por dependencia**: ¿en qué estado está cada producto? | sí: ping + contexto, en paralelo, con timeout | 200 si todas las de la arquitectura están `UP`; 503 con **el mismo cuerpo** si no |

## 1. Estados con significado definido (RNF9)

Por dependencia:

| Estado | Significado | Cuándo se observó |
|---|---|---|
| `UP` | el chequeo configurado (ping **y** contexto) terminó bien en esta verificación | corrida completa |
| `DOWN` | se intentó y falló; `detalle`: `timeout`, `no responde`, `credencial rechazada`, `sin permiso`, `contexto inexistente`, `respuesta inválida` | fallas controladas |
| `NOT_CONFIGURED` | el módulo no está preparado en este entorno: falta su configuración (token de Influx) o está fuera de la arquitectura (IRIS, con `enArquitectura: false`) | caso `influx-sin-token`; IRIS siempre |
| `UNKNOWN` | se intentó, pero el error no se pudo clasificar | se vio con `AuthenticationRateLimit` de Neo4j antes de clasificarlo (H11-5) |

Global (`/health/dependencias.estado`): `OK` si todas las de la arquitectura están `UP`, `DEGRADADO` si no. IRIS (`enArquitectura: false`) no degrada el estado global.

Readiness (`/health/ready.estado`), con `READY_ESENCIALES=mongodb,neo4j` (configurable):

| Estado | Regla | HTTP | Ejemplo observado |
|---|---|---|---|
| `LISTA` | todas `UP` | 200 | corrida completa |
| `LISTA_DEGRADADA` | las esenciales `UP`, alguna otra no | 200 + `noDisponibles` | Redis detenido, InfluxDB en pausa |
| `NO_LISTA` | alguna esencial no está `UP` | **503** | MongoDB detenido |

**Por qué mongodb y neo4j son las esenciales:** son la fuente de verdad del Fixture (equipos y partidos, N1/N2/N3/N8). Sin ellas ningún caso de uso tiene sentido. Comentarios, sesiones, caché y estadísticas son módulos que se pueden degradar: sus rutas responden 503/504 de forma identificable, y el detalle de partido sigue funcionando sin la caché (`X-Cache: BYPASS`).

## 2. Qué verifica cada ping (Hito 11)

El chequeo del Hito 10 sólo verificaba que el servidor respondiera. En este hito se agregó la verificación del **contexto** donde es barato hacerlo, porque un servicio que responde no es lo mismo que un servicio usable (ver H11-1 y H11-6 en [`diagnostico_de_fallas.md`](diagnostico_de_fallas.md)):

| Fuente | Ping | Detecta |
|---|---|---|
| MongoDB | `ping` + `listCollections(filter={name:"equipos"}, nameOnly)` | caída, rechazo, **database mal escrita** (Mongo no da error por sí solo) |
| Neo4j | `RETURN 1` en una transacción de lectura **sobre `NEO4J_DATABASE`** | caída, credencial (`AuthError`, `Security.*`), **database inexistente** |
| Cassandra | `SELECT release_version FROM system.local`, después de preparar las sentencias de la API en el keyspace | caída, **keyspace o tabla inexistente** (falla la preparación) |
| Redis | `PING` | caída, rechazo, `NOAUTH` / `NOPERM` |
| InfluxDB | `GET /health` + `SELECT 1` **con el token** sobre `INFLUX_DB` | caída, pausa, **token inválido o ausente**, **database inexistente** |

## 3. Timeouts, frecuencia y costo

- **Timeout:** cada ping corre dentro de `ejecutar()` con `DEP_TIMEOUT_S` (2 s), en paralelo (`asyncio.gather`). El peor caso de `/health/dependencias` es ≈ `DEP_TIMEOUT_S`, no la suma: con InfluxDB en pausa respondió en **2,01 s** y con todo `UP` en 12–25 ms.
- **Frecuencia:** el resultado se guarda **`HEALTH_CACHE_S` = 5 s** en `CacheSalud` y lo comparten `/health/dependencias` y `/health/ready`. Mientras está vigente se responde con `desdeCache: true` y el mismo `verificadoEn`. Las verificaciones concurrentes esperan a la que está en curso (*single-flight*, un `asyncio.Lock`): cien sondeos simultáneos generan **un** chequeo. Hay una prueba unitaria: tres requests seguidas → un solo ping (`test_resultado_se_reutiliza_dentro_del_ttl`).
- **Costo por chequeo:** a lo sumo 7 operaciones triviales (2 en Mongo, 1 en Neo4j, 1 en Cassandra, 1 en Redis, 2 HTTP en Influx), sin leer datos del dominio. Con un sondeo cada 1 s desde un balanceador, eso da como máximo un chequeo cada 5 s por instancia de la API.
- **Las requests normales nunca disparan el chequeo profundo.** Cada ruta usa sólo su adaptador, y un adaptador caído corta en `DEP_TIMEOUT_S` sin afectar a las demás rutas (escenarios 3.1–3.3: con Redis, Mongo o Influx caídos, las otras fuentes siguieron respondiendo 200).
- **Front y monitoreo:** el indicador de conexión del front sondea `/health/dependencias` cada `HEALTH_POLL_MS` y gracias a la caché no multiplica las conexiones. Muestra sólo las fuentes con `enArquitectura: true`.
- Con `HEALTH_CACHE_S=0` se desactiva la caché. Así lo usan los escenarios de configuración incorrecta, para ver cada cambio al instante.

## 4. Lo que no hace (y por qué)

- No hay reintentos dentro del chequeo: un `DOWN` es lo que se observó en ese intento. El siguiente chequeo (5 s después) puede dar otro resultado.
- No hay *circuit breaker*. Con `DEP_TIMEOUT_S` acotado y sin reintentos, una fuente caída cuesta a lo sumo `DEP_TIMEOUT_S` por request. Bajo carga (Hito 12) podría convenir dejar de llamar a una fuente que viene fallando, y queda anotado como una mejora posible.
- El `detalle` es una categoría pública. Nunca incluye hosts, URIs, usuarios ni el texto del error del driver. El tipo de excepción y el motivo van al log con el `request_id`.
