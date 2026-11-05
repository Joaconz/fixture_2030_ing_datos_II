# Decisiones de arquitectura (RF14, RF15, §6.4)

Resumen para la defensa de **por qué cada dato vive donde vive**, con enlaces a la fuente de cada decisión y a la evidencia. Las decisiones se tomaron en el Hito 2 (matriz) y el Hito 3 (distribución, CAP); la reentrega del Hito 3 movió Partidos y Tipos de evento de IRIS a Neo4j. Estado de cada necesidad: [`docs/ESTADO-CANONICO-NECESIDADES.md`](../../docs/ESTADO-CANONICO-NECESIDADES.md).

**Qué es diseño y qué es laboratorio (RNF8):** N=3, réplicas por región y quórum son **decisiones de diseño** (Hito 3). En el laboratorio cada base corre en **un nodo**. Lo que se midió está marcado como tal.

## 1. Por base

### MongoDB — documental (N1 Equipos y jugadores)

| | |
|---|---|
| Qué guarda | 64 equipos y 1.472 jugadores (23 por equipo), con datos anidados (plantel, ranking, grupo) |
| Qué acceso lo motivó | Leer un equipo completo por su código, y sus jugadores, desde seis países (lectura intensiva, escritura rara) |
| Estructura | Colecciones `equipos` y `jugadores` con validación de esquema (`init/01-validators.js`); `_id` = código FIFA |
| Carga y recuperación | `load/seed.js` determinista (mismo resultado en cada corrida, verificado 15/10/2026); la API lee por `_id` (`GET /equipos/{codigo}`) |
| Distribución (diseño) | Sin partición (catálogo chico); 3 copias, réplica de lectura por región, escritura en el primario |
| Consistencia | CP en escritura, AP en lectura (consistencia de sesión) |
| Ante una falla | Rutas de equipos y jugadores → 503; el resto del Fixture sigue (MongoDB no está en el camino de comentarios, sesiones ni estadísticas) |
| Trade-off | Ventana de segundos con dato viejo en otra región tras un cambio; se acepta porque un equipo casi no cambia durante el torneo |
| Evidencia | Seed idempotente ([ESTADO-CANONICO H1](../../docs/ESTADO-CANONICO-NECESIDADES.md)); exporter con `mongodb_up` y operaciones por tipo; ruta de control en 200 durante la caída de Redis ([prueba de falla](../evidencia/prueba_de_falla_redis_20261030-211553.md)) |

### Neo4j — grafo (N2 Partidos, N3 Eventos, N8 Tipos de evento)

| | |
|---|---|
| Qué guarda | Partidos, sedes, grupos, eventos de cada partido y el catálogo de 12 `:TipoEvento` |
| Qué acceso lo motivó | Recorridos: eventos de un partido en orden, quién asistió a quién, relaciones partido–equipo–sede; y un cierre de partido sin contradicciones |
| Estructura | Nodos con restricciones de unicidad (`estructura.cypher`: equipo, jugador, partido, sede, evento, grupo, tipo de evento). El **marcador no se guarda**: se calcula contando los eventos `GOL` |
| Carga y recuperación | `carga.cypher` con `MERGE` (idempotente). La API recorre con Cypher; el cierre es `PATCH /partidos/{id}/estado` en una transacción que exige `FIN_PARTIDO` |
| Distribución (diseño) | Partición por partido (el partido con sus eventos); 3 copias, el cierre confirma por mayoría en el nodo autoritativo |
| Consistencia | **Cierre CP** (no puede haber dos resultados oficiales); **ingesta de eventos AP** con orden causal. Son operaciones distintas en el mismo motor |
| Ante una falla | Sin partidos ni eventos → 503 en esas rutas; el cierre espera antes que confirmar un resultado dudoso |
| Trade-off | Las reglas de cada tipo de evento (qué campos lleva un Gol o una Tarjeta) se validan en la API, no en la base: una escritura que no pase por la API no queda validada. Se acepta porque el catálogo es chico y estable y la API es el único camino de escritura (Hito 3, reentrega) |
| Evidencia | Reentrega del Hito 3: el calendario duplicado en IRIS ya había producido una inconsistencia real (`PAR-A-1` con equipos distintos). Monitoreo: solo sonda y latencia desde la API (Community no expone métricas) |

### Cassandra — columnar (N6 Comentarios)

| | |
|---|---|
| Qué guarda | Comentarios de los hinchas durante cada partido, por partido y por usuario; interacciones |
| Qué acceso lo motivó | Escritura masiva concentrada en momentos (un gol, el final) y lectura de "los últimos N comentarios de este partido" |
| Estructura | Keyspace `fixture2030_comentarios`. `comentarios_por_partido` con clave `((partido_id, ventana, bucket), creado_en, comentario_id)`: ventana de 10 minutos y `bucket = crc32(comentario_id) % buckets`. `comentarios_por_usuario` por `(usuario_id, mes)`. Las dos se escriben en el mismo `LOGGED BATCH`. `config_particion_partido` dice cuántos buckets tiene cada partido |
| Carga y recuperación | Carga masiva del Hito 6; la API lee la configuración del partido y después, en paralelo, los buckets de la ventana (en el partido caliente `PAR-D16-01`: 5 llamadas a Cassandra por GET, medido) y escribe con idempotencia por clave |
| Distribución (diseño) | La partición compuesta reparte el pico de un partido entre varios nodos; **N=3, R=1, W=1** (en la API, `LOCAL_ONE`) |
| Consistencia | AP, eventual: un comentario puede tardar en aparecerle a otro hincha |
| Ante una falla | Sin comentarios (503), el resto sigue; con W=1, ante saturación se siguen aceptando escrituras a costa de lecturas menos frescas |
| Trade-off | Sin búsquedas arbitrarias (solo los accesos modelados); dos tablas por la misma información (desnormalización); los buckets solo pueden crecer |
| Evidencia | Hito 12: 364 req/s, 0 errores, integridad sin duplicados. Hito 13: con 2.000 lecturas/s, **p99 de 1,1 ms por dentro** ([carga observada](../evidencia/carga_observada_20261030-212441.md)) |

### Redis — clave-valor (N5 Sesiones y caché)

| | |
|---|---|
| Qué guarda | Sesiones de usuario y la caché del detalle de partido |
| Qué acceso lo motivó | Lectura por clave en cada request, con vencimiento automático |
| Estructura | `f30:ses:{id}` HASH con **TTL deslizante de 1.800 s y tope absoluto de 12 h**; `f30:usr:{usuario}:sesiones` SET (índice); `f30:cache:partido:{id}` STRING JSON con `SET … EX` (**60 s** por defecto) |
| Carga y recuperación | `carga_muestra.sh` determinista (`DBSIZE = 4203` en 3 corridas); la API lee por clave |
| Distribución (diseño) | Local a cada región, **sin réplica entre regiones**, a propósito |
| Consistencia | AP, eventual |
| Ante una falla | Se pierden las sesiones de esa región y el usuario vuelve a entrar; la caché de partido se reconstruye desde Neo4j |
| Trade-off | Durabilidad débil (asumida: perder una sesión es tolerable); la caché puede mostrar un dato de hasta 60 s |
| Evidencia | **Prueba de falla:** caída detectada a los 10 s, alerta a los 72 s, API 503 en sesiones mientras MongoDB seguía en 200; recuperación 13 s después del `docker start` ([informe](../evidencia/prueba_de_falla_redis_20261030-211553.md)) |

### InfluxDB 3 Core — series temporales (N7 Estadísticas en vivo)

| | |
|---|---|
| Qué guarda | Estadísticas por segundo de cada equipo en cada partido (posesión, tiros, etc.) |
| Qué acceso lo motivó | Ingesta continua y consultas por rango de tiempo y agregaciones por minuto |
| Estructura | Base `fixture2030_vivo` (retención 45 días, detalle por segundo) y `fixture2030_historico` (resúmenes, sin vencimiento); tabla `estadisticas_equipo` |
| Carga y recuperación | Carga por lotes concurrente: **10.094.400 puntos en 55,2 s** (Hito 8); la API consulta por partido y rango |
| Distribución (diseño) | Por partido + intervalo; réplica de bajo factor en la región de ingesta (conceptual, sin N/R/W) |
| Consistencia | AP, eventual con orden monótono por partido |
| Ante una falla | Sin estadísticas en vivo (503); el resto sigue |
| Trade-off | Retención fija al crear la base; puntos individuales prescindibles gracias al resumen por minuto |
| Evidencia | Hito 8 (`docs/pruebas_y_rendimiento.md`). Monitoreo: sonda y latencia desde la API; sin métricas internas (el `/metrics` de Influx exige el token de administración) |

### IRIS — objetos (fuera de la arquitectura vigente)

Se implementó en el Hito 9 y se sacó en la reentrega del Hito 3 (aprobada por el profesor el 13/10/2026): Partidos y Tipos de evento quedaban **duplicados** en IRIS y en el grafo, y la duplicación ya había producido un calendario distinto entre módulos. La ventaja del modelo de objetos (clases con reglas sin traducción) se aprovecha cuando la aplicación usa esas clases; acá la consume una API REST en Python que valida en su propia capa. **Qué se perdió:** las reglas por tipo de evento dentro del modelo. No se monitorea porque no corre en el sistema que se defiende.

## 2. Preguntas transversales

**¿Por qué no una única base?** Porque los accesos son opuestos: el cierre de un partido necesita consistencia fuerte; los comentarios del minuto 90, escribir sin esperar a nadie; las sesiones, vencerse solas; las estadísticas, agregarse por tiempo. Una sola estructura obliga a resignar el acceso dominante de alguno. El costo es operar cinco productos (ver §3).

**¿Cómo se relacionan los módulos sin que una base resuelva todo?** Por la **API**: cada ruta usa una sola fuente y los identificadores (`partido_id`, `usuario_id`) son compartidos. No hay transacciones entre bases; por eso **una base caída no tumba a las demás** (verificado en la prueba de falla).

**¿Qué es operacional y qué analítico?** Operacional: todo lo que sirve la API. Proyectable a una vista analítica: el histórico de comentarios (Cassandra, sin TTL), los resúmenes de `fixture2030_historico` (InfluxDB) y la integración del Hito 12 (`docs/integracion_data_mart.md`).

**¿Dónde hay caché y cómo vence?** Redis: detalle de partido con `SET … EX` (60 s). API: configuración de partición de Cassandra en memoria (Hito 12, 60 s, apagada por defecto). Las dos vencen por tiempo; no hay invalidación activa entre procesos.

**¿Cómo se evita que una consulta de alto volumen bloquee todo?** Cada fuente tiene timeout propio en el adaptador (504 si se pasa) y la API no comparte conexiones entre bases. En Cassandra, la partición `(partido, ventana, bucket)` impide que el pico de un partido caiga en una sola partición.

**¿Qué se midió y qué es proyección?** Medido: un nodo por base (latencias, throughput, caída y recuperación de Redis). Proyección: réplicas, regiones, N/R/W, 2–3 millones de usuarios. Detalle en [`limitaciones_y_evidencia.md`](limitaciones_y_evidencia.md).

## 3. Mejora transversal a partir de la evidencia (RF12)

**Observación.** En la [carga observada](../evidencia/carga_observada_20261030-212441.md) (399 req/s de lectura de comentarios):

| Dónde se mide | Latencia |
|---|---|
| Cassandra por dentro (agente JMX), p99 | 1,1 ms |
| Cassandra vista desde la API, p50 / p95 | 17 / 44 ms |
| La request completa en la API, p50 / p95 | 42 / 91 ms |
| CPU del proceso de la API | 97 % promedio, 100 % máximo |

Cassandra responde en un milisegundo; el resto del tiempo es **espera dentro del proceso de la API**, que está saturado (un solo proceso de Python, un núcleo). Confirma con métricas la hipótesis H2 que el Hito 12 dejó planteada sin poder medirla.

**Mejora propuesta (no ejecutada):** correr la API con varios procesos (`uvicorn --workers N` o varias instancias detrás de un balanceador) y **activar la caché de la configuración de partición** (`COMENTARIOS_CONFIG_CACHE_S=60`), que el Hito 12 midió que elimina el 99,98 % de esas lecturas. Sin la caché, cada proceso nuevo multiplicaría la carga sobre Cassandra (hoy 5 llamadas por GET).

**Cómo se verificaría con este monitoreo:** repetir `ejecutar_carga_observada.sh` y esperar (1) más req/s, (2) menor diferencia entre "Cassandra desde la API" y "Cassandra por dentro", (3) CPU repartida entre procesos. **Trade-off:** con varios procesos, cada uno tiene su propia caché (sin invalidación entre ellos) y las métricas de `prometheus-client` necesitan su modo multiproceso.

## 4. Costo de operar cinco productos

Cinco motores, cinco formas de respaldo, de seguridad y de actualización, y cinco exporters o sondas. Este hito lo muestra en chico: Cassandra necesitó un agente JMX, Neo4j Community no expone métricas, InfluxDB pide un token para las suyas. Se acepta porque la alternativa (una base para todo) degrada el acceso dominante de algún módulo, y porque una falla queda contenida en su módulo.
