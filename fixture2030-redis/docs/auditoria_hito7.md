# Auditoría — Hito 7: Caché de Usuarios y Sesiones (Redis)

Auditoría posterior a la implementación, siguiendo el método de [`fixture2030-mongodb/docs/HITO4_AUDIT_SPEC.md`](../../fixture2030-mongodb/docs/HITO4_AUDIT_SPEC.md) generalizado por la skill `/auditar-hito`. Fecha: 2026-09-26.

## Resumen ejecutivo

Este es, de los módulos auditados hasta ahora, el que llegó en mejor estado: la documentación es internamente consistente, cada decisión de diseño está justificada (no solo afirmada), y — a diferencia de Hitos anteriores — el propio equipo ya había detectado y corregido antes de esta auditoría el error heredado de N2 (Partidos: IRIS, no MongoDB), incluso antes de que el documento del Hito 3 se corrigiera a sí mismo (ver `hito-3-arquitectura-distribuida.md`, línea 236).

**Esta auditoría no se limitó a releer documentación.** El entorno del sandbox tenía Docker disponible (el daemon no estaba levantado por defecto; se inició para esta sesión), así que se pudo:

- Levantar el ambiente **desde cero real** (`docker compose up -d` tras un `docker pull redis:latest` limpio, sin ningún estado previo).
- Cargar la muestra **tres veces seguidas** y confirmar el conteo exacto documentado (`DBSIZE = 4203`) en las tres.
- Ejecutar **todos** los scripts `.redis` y `.sh` del módulo contra un Redis real y comparar la salida, línea por línea, contra la evidencia archivada.
- Reproducir el escenario de carrera de concurrencia (20 clientes, mismo usuario) y la prueba de 100.000 operaciones concurrentes.
- Forzar la prueba de presión de memoria (evicción vs. TTL) y el rechazo por OOM.
- Verificar persistencia real con `docker compose restart` **y** `down` (sin `-v`) + `up`, con una clave marcadora propia.
- Encontrar y corregir un bug real y reproducirlo con y sin el fix (§2).
- Verificar contra el texto primario del Hito 2 (no contra una cita de segundo nivel) los puntajes y márgenes de N2, N4 y N5, y contra el código real de Neo4j/Cassandra el formato de los identificadores `PAR-*`/`USR-*` que este módulo dice reutilizar.

## 1. Tabla de requisitos

La numeración RF/RNF es la que ya usa el propio módulo (citada de forma consistente en sus scripts y docs); no hay un enunciado literal en el repo, así que se reconstruyó por concordancia de citas cruzadas. Donde esa reconstrucción es ambigua, se marca explícitamente.

### Requisitos funcionales

| ID | Requisito (inferido de las citas del módulo) | Cómo se verificó | Resultado |
|---|---|---|---|
| RF1 | Entorno reproducible con Docker Compose, servidor disponible | `docker compose up -d` desde cero (imagen recién descargada) → `docker compose ps` → `healthy`; `redis-cli ping` → `PONG` | **PASS** |
| RF2 | Documentar patrones de acceso antes de fijar el modelo de claves | `patrones_de_acceso.md` precede a `modelo_clave_valor.md` y cada clave de éste cita el patrón P1–P11 que la origina | **PASS** (interpretación razonable; no hay enunciado literal para confirmar la redacción exacta — **No verificable al 100 % — falta insumo** del texto original) |
| RF3–RF5 | CRUD de sesión: crear, leer todos los atributos, TTL deslizante | `FCALL ses_crear` → `HGETALL` devuelve 9 campos + TTL 1800; `FCALL ses_tocar` renueva y devuelve `{usuario, region, rol, solicitudes, ttl}` | **PASS** (ejecutado en vivo, salida idéntica a `03_sesiones.txt`) |
| RF6–RF7 | Caché cache-aside con invalidación en escritura, no solo TTL | Ciclo miss→hit→invalidación (`cache_invalidar`)→miss controlado→repoblado con versión, ejecutado en vivo | **PASS** (salida idéntica a `04_cache.txt`, incluyendo el escenario de carrera evitada §4.5) |
| RF8 | Operaciones concurrentes atómicas (voto único, renovar sesión) | `concurrencia_paralela.sh 20`: no atómica → **20**, atómica (`FCALL voto_emitir`) → **1**. Además, vía `benchmark.sh` corregido: 100.000 incrementos concurrentes → **100.000** exacto; 100.000 votos mismo usuario → **1**; 100.000 votos aleatorios (1.000 usuarios) → **1.000 == 1.000** | **PASS** (reproducido en este sandbox, en hardware distinto al original, con el mismo resultado) |
| RF9 | Ranking de tendencia por hora, top-N sin ordenar en la app | `ZREVRANGE f30:rank:tendencia:2030062916 0 4` reproduce el mismo top-5 y mismos puntajes que `05_concurrencia.txt` (determinismo confirmado: la fórmula de carga no usa aleatoriedad) | **PASS** |
| RF10 | Política de memoria explícita y probada (`volatile-lru`, techo) | `memoria_prueba.sh` ejecutado en vivo: fase 1 desaloja ~15k claves con TTL sin tocar la votación (sin TTL); fase 2 (100 KB) rechaza escritura sin TTL con `OOM command not allowed...`; votación íntegra en ambas fases | **PASS** |
| RF11 | Carga de muestra determinista, sin duplicados al repetir | `FCALL carga_muestra 0 2000` ejecutado **3 veces seguidas** desde `DBSIZE=0`: **4203** las tres veces, sin variación. Valores del ranking MVP (ARG-10=99, FRA-7=99, ARG-9=100, BRA-11=101, FRA-10=101) idénticos a la evidencia archivada, confirmando ausencia total de aleatoriedad | **PASS** |
| RF12 | Medición de rendimiento con herramienta estándar (`redis-benchmark`) | `benchmark.sh` corre completo sin errores; §B.3 y §B.4 con resultados exactos como arriba | **PASS**, con un bug corregido (§2) |
| RF13 | Evidencia real archivada (no solo prosa) | `docs/evidencia/01_…09_.txt` existen, tienen fecha y comandos reales — confirmado que no son fabricados: se ejecutaron los mismos scripts en este sandbox y la salida estructural coincide | **PASS**, con una salvedad de higiene de evidencia (§4) |

### Requisitos no funcionales

| ID | Requisito | Cómo se verificó | Resultado |
|---|---|---|---|
| RNF1 | Imagen oficial `redis:latest`, versión registrada | `docker compose config` válido; `INFO server` → `redis_version:8.10.2`, igual al registrado en el README (§6) pese a ser una descarga nueva del tag `latest` | **PASS** |
| RNF2 | Persistencia real en volumen **nombrado** (no bind mount simple) | `docker volume inspect fixture2030_redis_data` → volumen nombrado, `driver=local`, respaldado por carpeta de host. Clave marcadora con TTL sobrevivió a `docker compose restart` **y** a `down` (sin `-v`) + `up -d`; la votación abierta y las 2 Functions (`f30`, `f30carga`) también | **PASS** |
| RNF3 | Reproducible desde cero siguiendo solo el README | Se siguió el README literal (mkdir, up -d, cargar funciones, correr scripts) en un contenedor sin ningún estado previo, sin conocimiento adicional, y funcionó igual | **PASS** |
| RNF4 | Cada clave trazable a un patrón de acceso declarado | Las 8 claves de `modelo_clave_valor.md` citan P1–P11; no hay ninguna clave "por las dudas" sin patrón que la respalde | **PASS** |
| RNF5 | Convención de nombres de claves consistente | `f30:{dominio}:{entidad}:{id}[:{subrecurso}]` aplicada sin excepciones en las 8 familias de claves | **PASS** |
| RNF6 | Mantenibilidad: decisiones separadas por archivo, no un script monolítico | 5 documentos de diseño con responsabilidad única + scripts separados por etapa | **PASS** |
| RNF7 | Sin rutas absolutas hardcodeadas / sin credenciales en un nodo de desarrollo | `grep` de rutas tipo `/Users/`, `/home/usuario` en todo `fixture2030-redis/` (excluida `docs/evidencia/`, que es *salida* real, no código): **0 coincidencias** en scripts/config. Nodo sin contraseña, publicado solo en `127.0.0.1` — documentado como decisión de laboratorio, no de producción | **PASS** |
| RNF8 | Sin `KEYS`/`FLUSHALL` como operación normal | `grep` de `\bKEYS\b`, `FLUSHALL`, `FLUSHDB` en `scripts/`: única coincidencia es el parámetro `KEYS[]` de las Redis Functions (Lua), no el comando. Toda inspección usa `SCAN`/`DBSIZE` | **PASS** |
| RNF9 | *(sin cita en ningún archivo del módulo)* | Se buscó `RNF9` en todo el módulo (docs, scripts, config): cero apariciones, a diferencia de RNF1–RNF8 y RNF10 que sí tienen cada uno varias citas cruzadas | **No verificable — falta insumo**: sugiere un requisito del enunciado original que este módulo nunca citó ni marcó explícitamente como fuera de alcance. Puede ser análogo al "RNF8 Tiempo" del Hito 4 (no verificable técnicamente, se omite a propósito) — pero eso debería decirlo el equipo, no asumirlo esta auditoría |
| RNF10 | Registrar la versión real de `latest` usada, con entorno de prueba | README §6 y `docs/evidencia/README.md` documentan versión, SO, hardware y fecha. Confirmado que la versión (8.10.2) sigue vigente en el tag `latest` a la fecha de esta auditoría | **PASS** |

## 2. Cambios aplicados automáticamente

### 2.1 Bug de limpieza en `scripts/benchmark.sh` (§B.4/§B.5) — corregido

**El problema:** el paso §B.4 crea 56 claves de prueba con el nombre `f30:cache:bench:%012d` (TTL 600 s) para medir el hit ratio de la caché. El paso §B.5 las limpia llamando a `limpieza.sh f30:bench:`, que hace `SCAN --pattern 'f30:bench:*'`. Ese patrón **no coincide** con `f30:cache:bench:*` (el prefijo real empieza con `f30:cache:`, no con `f30:bench:`), así que la limpieza no borraba nada de lo que decía limpiar.

**Cómo se confirmó (no se asumió):**
```
$ docker compose exec redis redis-cli EVAL "for i=0,55 do redis.call('SET', string.format('f30:cache:bench:%012d', i), 'x', 'EX', 600) end" 0
$ docker compose exec -T redis sh /scripts/limpieza.sh f30:bench:
Borrando claves con prefijo 'f30:bench:' (SCAN + UNLINK)...
DBSIZE restante: 4239        # sin cambios: 0 claves borradas
$ docker compose exec redis redis-cli --scan --pattern 'f30:cache:bench:*' | wc -l
56                            # las 56 claves seguían ahí
```

**Por qué no era catastrófico pero sí un bug real:** las claves tienen `EX 600`, así que se autolimpian en 10 minutos, y en la ejecución archivada probablemente ya estaban desalojadas por la prueba de memoria que corre justo después en `correr_todo.sh` (que desaloja cualquier clave con TTL bajo presión). Pero si alguien corre `benchmark.sh` **solo** (como lista el README §4, paso "6. medición"), quedan 56 claves de prueba viviendo 10 minutos de más, y el mensaje "Limpieza de claves de la medición" es falso para ese subconjunto.

**Corrección aplicada:** se renombraron las claves de `f30:cache:bench:%012d` a `f30:bench:cache:%012d` (dos líneas en `benchmark.sh`, §B.4), manteniéndolas bajo el mismo prefijo `f30:bench:` que ya usan el resto de las claves de medición del archivo (`f30:bench:tend`, `f30:bench:vA:*`, `f30:bench:vB:*`) y que la limpieza de §B.5 sí cubre.

**Verificado que el fix funciona, en el pipeline completo, no solo aislado:**
```
$ sh scripts/benchmark.sh        # corrida completa, con el fix
...
== B.5 Limpieza de claves de la medición (SCAN + UNLINK) ==
Borrando claves con prefijo 'f30:bench:' (SCAN + UNLINK)...
DBSIZE restante: 4077
$ docker compose exec redis redis-cli --scan --pattern 'f30:bench:*' | wc -l
0                             # ahora sí, cero remanentes
```

**Por qué esto entra en "se corrige directamente":** es un error mecánico dentro de un solo script (un prefijo mal tipeado), no toca ninguna decisión de modelado ni de otro módulo — misma categoría que "la carga genera duplicados al re-ejecutarse" del criterio del Hito 4.

### 2.2 Nada más se modificó

El resto del módulo pasó la verificación en vivo sin necesidad de cambios: la carga es determinista e idempotente (confirmado con 3 corridas reales, no solo lectura del código), la invalidación de caché evita la carrera del lector lento tal como se documenta, la política de memoria se comporta exactamente como se describe, y la persistencia sobrevive tanto a un `restart` como a un `down`+`up` reales.

## 3. Decisiones de diseño no tocadas (señaladas para revisión humana / defensa oral)

Ninguna de estas se modificó — son decisiones de modelado o de negocio que el grupo tiene que poder defender, no bugs:

1. **TTLs elegidos (30 min inactividad, 12 h tope, 60 s caché de partido, 900 s perfil, 7200 s bucket de tendencia).** Todos están rotulados honestamente como "supuesto del grupo", no como dato del enunciado. Es la decisión correcta documentarlo así, pero el grupo debe poder justificar cada número si se lo preguntan (por qué 30 y no 20 o 45, por qué 60 s y no 30 s para un marcador en vivo).
2. **Política `volatile-lru` sobre las alternativas descartadas** (`noeviction`, `allkeys-lru/lfu`, `volatile-ttl`, `volatile-lfu`). El razonamiento en `memoria_y_escalabilidad.md` §2.1 es sólido y comparativo, no solo afirmativo — se deja como está, pero es una decisión de arquitectura que amerita poder explicarse en la defensa.
3. **Redis Functions en vez de `MULTI/EXEC`.** Justificado por la necesidad de lógica condicional dentro de la transacción, que `MULTI/EXEC` no permite. Correcto, no se toca.
4. **`ses_cerrar_todas` arma claves por concatenación de strings dentro del script.** El propio módulo ya documenta que esto es válido solo en nodo único y que Redis Cluster exigiría *hash tags*. Sigue siendo así: no se implementó Cluster en este hito (fuera de alcance declarado), por lo que no hay nada que corregir hoy, pero es una limitante real a mencionar si se pregunta por escalar el diseño.
5. **Caso abierto heredado del Hito 3** ("¿qué pasa con una sesión cuando el usuario cambia de región?"): sigue sin resolverse, tal como el propio módulo lo admite. No es un olvido de esta auditoría: es una decisión de alcance ya explicitada.
6. **Cierre de la votación MVP sin fuente de verdad asignada:** el propio módulo documenta esto como deuda pendiente de un hito de integración futuro (§5 de `ciclo_de_vida_e_invalidacion.md`). Correcto dejarlo así — no hay módulo asignado a esa necesidad en los Hitos 2/3, así que no es responsabilidad de este hito resolverlo.

## 4. Gaps de documentación / trazabilidad y evidencia

1. **`RNF9` nunca se cita en el módulo** (ver tabla §1). No se puede saber, sin el enunciado original, si es un requisito no aplicable a este hito (como el "RNF8 Tiempo" del Hito 4, que se omite a propósito) o algo que se pasó por alto. **Acción para el equipo:** revisar el enunciado original del Hito 7 y, si RNF9 aplica, documentarlo explícitamente (aunque sea para decir por qué no corresponde); si no aplica, dejar una línea aclarándolo, igual que se hizo con el RNF8 del Hito 4.

2. **Higiene de la evidencia archivada — `02_carga_muestra.txt`.** El documento `concurrencia_y_pruebas.md` (§1) cita textualmente "El total tras la carga es `DBSIZE = 4203`" remitiendo a ese archivo. Pero `02_carga_muestra.txt` en el repo muestra **4204**, no 4203, y su paso previo ("Estado previo") ya mostraba `DBSIZE=4192` en lugar de `0`. Esta auditoría **confirmó en vivo, desde `DBSIZE=0` real, que el valor correcto y estable es 4203** (repetido 3 veces): el número que cita la documentación es el correcto: lo que está desactualizado/impreciso es el archivo de evidencia, que se capturó sobre un ambiente con 4192 claves residuales de una corrida anterior no limpiada (probablemente sesiones u otras claves de otra corrida de `correr_todo.sh` que no se resetearon con `down -v` antes de capturar esa evidencia puntual), más 1 clave suelta no perteneciente a la muestra. **No se sobrescribió el archivo** porque no es un bug del script (ya verificado: el script es determinista e idempotente) sino un problema de *cuándo* se capturó esa evidencia puntual. **Acción para el equipo:** la próxima vez que regeneren evidencia, correr `docker compose down -v && rm -rf ~/docker/data/redis && mkdir -p ~/docker/data/redis` antes de `correr_todo.sh`, para que `02_` refleje un ambiente realmente limpio y coincida con el número que ya citan correctamente en la prosa.

3. **`06_benchmark.txt` y `07_memoria.txt` quedaron generados con la versión de `benchmark.sh` que tenía el bug de §2.1.** Sus cifras de rendimiento (throughput, `p50`/`p99`, `DBSIZE restante`) no cambian de forma sustancial por el fix (el bug no afectaba el rendimiento medido, solo la limpieza posterior), pero **no se regeneraron con las cifras de este sandbox** a propósito: el propio método de medición del proyecto (documentado en `concurrencia_y_pruebas.md` §4.2) es explícito en que las cifras solo son comparables *dentro de la misma corrida, mismo equipo* ("Apple M4, Docker Desktop"), y este sandbox corre en hardware Linux x86_64 distinto. Sobreescribir esos dos archivos con números de otra máquina habría introducido una inconsistencia nueva con la tabla de "Registro del ambiente" de `docs/evidencia/README.md`. **Acción para el equipo:** correr `sh scripts/correr_todo.sh` (o al menos `benchmark.sh`) una vez más en su propia máquina de referencia para refrescar `06_` y `07_` bajo el script ya corregido, y agregar la fila correspondiente a la tabla de "Procedencia de cada archivo" de `docs/evidencia/README.md`, siguiendo el mismo patrón que ya usaron para `04_`/`09_`.

4. **Trazabilidad a Hitos 2/3 — verificada contra la fuente primaria, no solo contra el mapa canónico.** Se confirmó directamente en `hito-2-matriz-decision.md` que N5 (Sesiones) puntúa 4,35 con margen 0,35, que N2 (Partidos → IRIS) tiene margen 0,10, y que N4 (Usuarios → MongoDB) tiene margen 0,10 — los tres coinciden exactamente con lo que citan los documentos de este módulo. También se confirmó, contra `fixture2030-neo4j/queries/carga.cypher` y `fixture2030-cassandra/data/`, que el formato de los identificadores reutilizados (`PAR-A-1`…`PAR-D16-16`, `USR-0000001`…) es consistente entre los tres módulos (Cassandra usa un universo de 250.000 usuarios; la muestra de Redis usa un subconjunto de 2.000 con el mismo formato — no hay contradicción, es una muestra de laboratorio declarada como tal). No se encontró ningún caso análogo al Hallazgo H1 (Mongo/Neo4j) dentro de este módulo.

## 5. Comandos ejecutados para esta auditoría (referencia)

Todos corridos contra un contenedor Redis real (`redis:8.10.2`, imagen `redis:latest` recién descargada), en este entorno de sandbox, no simulados:

```
docker compose config
docker compose up -d                                    # desde volumen/red inexistentes
docker compose exec redis redis-cli ping
FUNCTION LOAD REPLACE (funciones_f30.lua, carga_muestra.lua)
FCALL carga_muestra 0 2000   × 3                         # idempotencia real
sesiones.redis / cache.redis / concurrencia.redis        # ejecutados completos
concurrencia_paralela.sh 20
memoria_prueba.sh
metricas.redis / inicializacion.redis
verificar_persistencia.sh                                # incluye restart y down/up reales
benchmark.sh                                             # antes y después del fix de §2.1
```
