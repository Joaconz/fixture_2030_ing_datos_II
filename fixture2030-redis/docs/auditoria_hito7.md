# Auditoría — Hito 7: Caché de Usuarios y Sesiones (Redis)

Auditoría posterior a la implementación, siguiendo el método de [`fixture2030-mongodb/docs/HITO4_AUDIT_SPEC.md`](../../fixture2030-mongodb/docs/HITO4_AUDIT_SPEC.md) generalizado por la skill `/auditar-hito`. Fecha: 2026-09-26.

> **Actualización 2026-10-10 — corrección del profesor.** La devolución del Hito 7 pidió reducir la sobreimplementación: *"incorporan Redis Functions y Lua para resolver varias operaciones atómicas, cuando en esta etapa alcanzaba con los mecanismos vistos en clase (INCR, ZINCRBY, MULTI/EXEC)"*. Se aplicó así:
> - Se eliminaron `funciones_f30.lua` y `carga_muestra.lua`.
> - Las sesiones se crean, renuevan y cierran con `MULTI/EXEC`, y la validación es una lectura previa (`HMGET`).
> - El voto único usa `SADD` como guarda atómica más `ZINCRBY`.
> - La tendencia usa `MULTI` con `ZINCRBY` + `EXPIRE NX`.
> - La caché es cache-aside con `SET … EX` y `DEL`, sin la clave de versión `:ver`.
> - La muestra se genera con `carga_muestra.sh` (awk → `redis-cli`), con los mismos datos: `DBSIZE = 4203` y el mismo ranking.
>
> Toda la evidencia se regeneró en una sola corrida desde un ambiente vacío.
>
> Este informe describe la **versión anterior**: donde dice `FCALL …` o "función", hoy rige lo descrito en `modelo_clave_valor.md` §4 y `concurrencia_y_pruebas.md` §2. Las cifras citadas acá (por ejemplo `DBSIZE restante: 4077`) son de aquella corrida. La decisión 3 de §3 quedó reemplazada (ver abajo).

## Resumen ejecutivo

Este es, de los módulos auditados hasta ahora, el que llegó en mejor estado: la documentación es internamente consistente, cada decisión de diseño está justificada (no solo afirmada), y — a diferencia de Hitos anteriores — el propio equipo ya había detectado y corregido antes de esta auditoría el error heredado de N2 (Partidos: IRIS, no MongoDB), incluso antes de que el documento del Hito 3 se corrigiera a sí mismo (ver `hito-3-arquitectura-distribuida.md`, línea 236).

**Corrección sobre la primera versión de este informe.** La numeración RF/RNF de la tabla siguiente se había reconstruido por concordancia de citas cruzadas dentro del propio módulo, a falta del enunciado oficial. El usuario compartió después el PDF real (`Hito 7 — Requisitos Técnicos: Caché de Usuarios y Sesiones del Fixture 2030`). Contra el texto literal: RF1, RF2, RF6–RF13 y RNF1–RNF8, RNF10 se confirman exactamente como se habían inferido. **RNF9 no era un gap** como se afirmaba en la primera versión de este informe — el enunciado real lo define como "Legibilidad: las sentencias y scripts deberán estar comentados y separados por inicio, carga, sesiones, caché, operaciones concurrentes, métricas y limpieza opcional", y el módulo lo cumple estructuralmente (ver tabla). La ausencia de la cita literal "RNF9" en el código no era el hallazgo — era una hipótesis marcada explícitamente como insegura, y resultó incorrecta. Se corrige acá en vez de dejarla como estaba, que sería peor que no haberla señalado.

También el enunciado aclara algo que la primera versión de este informe daba por sentado sin chequear: **"No se solicita presentación, defensa oral ni video. La evaluación se realizará sobre el repositorio, la documentación y la evidencia técnica"** (Restricciones, "Entrega"). Donde este informe dice que una decisión de diseño "debe poder defenderse en una evaluación oral", debe leerse como "debe estar justificada por escrito en la documentación entregada" — no hay instancia oral en este hito.

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

La numeración RF/RNF es la del enunciado oficial (PDF "Hito 7 — Requisitos Técnicos: Caché de Usuarios y Sesiones del Fixture 2030", compartido por el usuario). Coincide exactamente con la que el propio módulo ya citaba de forma consistente en sus scripts y docs.

### Requisitos funcionales

Numeración confirmada contra el texto literal del enunciado (PDF provisto por el usuario tras la primera versión de este informe).

| ID | Requisito (texto literal del enunciado) | Cómo se verificó | Resultado |
|---|---|---|---|
| RF1 | Implementar un ambiente local de Redis mediante Docker Compose y verificar la disponibilidad del servidor mediante las herramientas incluidas en el contenedor | `docker compose up -d` desde cero (imagen recién descargada) → `docker compose ps` → `healthy`; `redis-cli ping` → `PONG` | **PASS** |
| RF2 | Identificar y documentar los patrones de acceso que el módulo debe resolver antes de fijar el diseño de las claves y estructuras de datos | `patrones_de_acceso.md` precede a `modelo_clave_valor.md` (el propio README lo aclara: "este documento va antes que el modelo de claves") y cada clave de éste cita el patrón P1–P11 que la origina | **PASS** |
| RF3 | Implementar un mecanismo para crear, recuperar, actualizar y finalizar sesiones de usuarios | `FCALL ses_crear` (crear) → `HGETALL` (recuperar) → `FCALL ses_tocar` (actualizar/renovar) → `FCALL ses_cerrar`/`ses_cerrar_todas` (finalizar), las 4 operaciones ejecutadas en vivo con resultado idéntico a `03_sesiones.txt` | **PASS** |
| RF4 | Definir y aplicar una política de expiración por inactividad para las sesiones, con duración, condiciones de renovación y consecuencia de una sesión vencida justificadas | `ciclo_de_vida_e_invalidacion.md` §1.4 justifica 30 min (ventana de entretiempo) y tope 12 h (jornada de partidos), no como cifras del enunciado sino como supuesto explícito del grupo. Verificado en vivo: TTL demo de 3 s expira a `EXISTS 0`/`TTL -2`; tope de 5 s acota la renovación aunque se pida 1800 s | **PASS** |
| RF5 | Incorporar los atributos necesarios para identificar la sesión, el usuario asociado, el momento de última actividad, el estado de acceso y la información temporal pertinente | `HGETALL` sobre una sesión real devuelve `session_id`, `usuario_id`, `rol`, `region`, `dispositivo`, `estado` (ACTIVA/BLOQUEADA), `creada_en`, `ultima_actividad`, `expira_absoluta`, `solicitudes` — cubre los 5 puntos exigidos | **PASS** |
| RF6 | Implementar una estrategia para recuperar rápido al menos un dato de consulta frecuente, distinguiendo la copia en caché de su fuente de verdad | Ficha de partido (`f30:cache:partido:{id}`, fuente: IRIS/N2) y perfil de usuario (`f30:cache:usuario:{id}:perfil`, fuente: MongoDB/N4) — dos datos, no solo uno — con la fuente de verdad de cada uno documentada y sin implementar | **PASS** |
| RF7 | Implementar y documentar el flujo de cache miss y el flujo de invalidación/actualización cuando cambia la fuente de verdad | Ciclo miss→hit→invalidación (`cache_invalidar`)→miss controlado→repoblado con versión (anti "stale set"), ejecutado en vivo con resultado idéntico a `04_cache.txt`, incluyendo el escenario de carrera evitada §4.5 | **PASS** |
| RF8 | Incorporar una operación concurrente relevante (actividad, voto, contador o clasificación temporal) y garantizar que su actualización no produzca resultados inconsistentes por operaciones intercaladas | `concurrencia_paralela.sh 20`: no atómica → **20**, atómica (`FCALL voto_emitir`) → **1**. Además, vía `benchmark.sh` corregido: 100.000 incrementos concurrentes → **100.000** exacto; 100.000 votos mismo usuario → **1**; 100.000 votos aleatorios (1.000 usuarios) → **1.000 == 1.000** | **PASS** (reproducido en este sandbox, en hardware distinto al original, con el mismo resultado) |
| RF9 | Diseñar y aplicar una estrategia para recuperar una lista o ranking temporal, **si corresponde a los patrones de acceso definidos por el equipo** (prioridad Media) | El equipo declaró P10/P11 (tendencia de partidos) como patrones aplicables, así que el requisito rige. `ZREVRANGE f30:rank:tendencia:2030062916 0 4` reproduce el mismo top-5 y mismos puntajes que `05_concurrencia.txt` (determinismo confirmado: la fórmula de carga no usa aleatoriedad) | **PASS** |
| RF10 | Definir y configurar, o justificar documentalmente, el comportamiento esperado cuando la instancia alcanza su límite de memoria | `memoria_prueba.sh` ejecutado en vivo: fase 1 desaloja ~15k claves con TTL sin tocar la votación (sin TTL); fase 2 (100 KB) rechaza escritura sin TTL con `OOM command not allowed...`; votación íntegra en ambas fases | **PASS** |
| RF11 | Cargar un conjunto de datos reproducible que permita demostrar los flujos de sesión, caché, actualización, expiración, invalidación y operación concurrente | `FCALL carga_muestra 0 2000` ejecutado **3 veces seguidas** desde `DBSIZE=0`: **4203** las tres veces, sin variación. Valores del ranking MVP (ARG-10=99, FRA-7=99, ARG-9=100, BRA-11=101, FRA-10=101) idénticos a la evidencia archivada, confirmando ausencia total de aleatoriedad | **PASS** |
| RF12 | Ejecutar y registrar una prueba o medición de las operaciones principales, indicando método, entorno, resultado observado y limitaciones del laboratorio local | `benchmark.sh` corre completo sin errores; §B.0 registra método/entorno, §B.3/§B.4 el resultado, y `concurrencia_y_pruebas.md` §4.5 lista limitaciones explícitas (nodo único, clave caliente sintética, dataset chico) | **PASS**, con un bug corregido (§2) |
| RF13 | Registrar evidencia verificable de la creación del ambiente, las operaciones, los TTL observados, las métricas consultadas y los resultados de la prueba | `docs/evidencia/01_…09_.txt` existen, tienen fecha y comandos reales — confirmado que no son fabricados: se ejecutaron los mismos scripts en este sandbox y la salida estructural coincide | **PASS**, con una salvedad de higiene de evidencia (§4) |

### Requisitos no funcionales

| ID | Requisito (texto literal del enunciado) | Cómo se verificó | Resultado |
|---|---|---|---|
| RNF1 | El archivo Compose deberá utilizar `redis:latest`. No se aceptarán imágenes fijadas a versiones anteriores salvo indicación docente expresa | `docker-compose.yml` usa `image: redis:latest` sin pin de versión; `docker compose config` válido; `INFO server` → `redis_version:8.10.2`, igual al registrado en el README (§6) pese a ser una descarga nueva del tag `latest` | **PASS** |
| RNF2 | El ambiente deberá preservar los datos locales de Redis mediante un montaje en `~/docker/data/redis` | `docker volume inspect fixture2030_redis_data` → volumen **nombrado**, `driver=local`, respaldado exactamente por esa carpeta del host (excede la letra del enunciado, que solo pide un montaje: acá además es un volumen nombrado, el patrón que la materia exige en general — ver Hallazgos de Cassandra). Clave marcadora con TTL sobrevivió a `docker compose restart` **y** a `down` (sin `-v`) + `up -d`; la votación abierta y las 2 Functions (`f30`, `f30carga`) también | **PASS** |
| RNF3 | Un integrante ajeno al desarrollo deberá poder iniciar el ambiente, ejecutar los scripts de muestra y repetir las consultas siguiendo el README | Se siguió el README literal (mkdir, up -d, cargar funciones, correr scripts) en un contenedor sin ningún estado previo, sin conocimiento adicional del módulo, y funcionó igual | **PASS** |
| RNF4 | Cada clave o estructura deberá estar vinculada a una o más operaciones concretas. No se aceptará una estructura sin justificación de uso | Las 8 claves de `modelo_clave_valor.md` citan el/los patrón(es) P1–P11 que las originan; no hay ninguna clave "por las dudas" sin patrón que la respalde | **PASS** |
| RNF5 | Las claves deberán seguir una convención documentada que permita reconocer dominio, alcance y propósito sin depender de conocimiento implícito del equipo | `f30:{dominio}:{entidad}:{id}[:{subrecurso}]`, documentada con tabla de segmentos y valores posibles, aplicada sin excepciones en las 8 familias de claves | **PASS** |
| RNF6 | Todo dato temporal deberá tener una decisión explícita sobre expiración, renovación, invalidación o conservación. No se aceptará una sesión sin criterio temporal documentado | `ciclo_de_vida_e_invalidacion.md` §0 es una tabla explícita de "vence por / renovación / invalidación / conservación" para cada uno de los 8 tipos de dato del módulo, sin excepciones | **PASS** |
| RNF7 | No se deberán publicar tokens reales, contraseñas personales, credenciales de servicios externos ni información sensible en scripts, capturas o documentación | `grep` de `password/token/secret/api key/credential/contraseña` en todo el módulo: las únicas coincidencias son de negocio ("cambio de contraseña" dispara `ses_cerrar_todas`), no secretos reales. Los ids de sesión de la muestra son ficticios (`demo-ses-…`); el nodo no tiene contraseña propia pero se documenta explícitamente como config de **desarrollo**, no como el secreto que este RNF prohíbe publicar | **PASS** |
| RNF8 | No se utilizará una búsqueda global bloqueante como mecanismo normal de operación o medición. La inspección deberá respetar el volumen esperado del entorno | `grep` de `\bKEYS\b`, `FLUSHALL`, `FLUSHDB` en `scripts/`: única coincidencia es el parámetro `KEYS[]` de las Redis Functions (Lua), no el comando. Toda inspección usa `SCAN`/`DBSIZE` (ambos O(1) o por páginas acotadas) | **PASS** |
| RNF9 | Las sentencias y scripts deberán estar comentados y separados por inicio, carga, sesiones, caché, operaciones concurrentes, métricas y limpieza opcional | La primera versión de este informe marcó esto como "gap" por no encontrar la cita literal "RNF9" en el módulo — **error propio, corregido**: el requisito no pide esa cita, pide la separación y el comentario, y el módulo la tiene exactamente: `inicializacion.redis` (inicio), `carga_muestra.redis`/`.lua` (carga), `sesiones.redis` (sesiones), `cache.redis` (caché), `concurrencia.redis`/`concurrencia_paralela.sh` (operaciones concurrentes), `metricas.redis` (métricas), `limpieza.redis`/`limpieza.sh` (limpieza opcional) — los 7 apartados exigidos, cada archivo con encabezado comentado | **PASS** |
| RNF10 | Los resultados deberán incluir fecha de ejecución, versión observada de Redis, recursos del equipo cuando se midan rendimientos, y resultados interpretables | README §6 y `docs/evidencia/README.md` documentan versión, SO, hardware y fecha; cada archivo de evidencia trae su propia fecha de ejecución. Confirmado que la versión (8.10.2) sigue vigente en el tag `latest` a la fecha de esta auditoría | **PASS** |

### Estructura exigida por el enunciado (§8 y §9) — verificación adicional

El enunciado real exige, además de la tabla RF/RNF, una "estructura esperada del análisis" (§8, 11 apartados) y un layout mínimo de entregables (§9). Ambos se verificaron por separado:

| Apartado exigido (§8) | Dónde está en el repo |
|---|---|
| Problema de concurrencia | `patrones_de_acceso.md` §1 — mismo título literal |
| Patrones de acceso | `patrones_de_acceso.md` §2 |
| Modelo clave/valor | `modelo_clave_valor.md` |
| Ciclo de vida | `ciclo_de_vida_e_invalidacion.md` |
| Fuente de verdad y caché | `ciclo_de_vida_e_invalidacion.md` §2 + `patrones_de_acceso.md` §3 |
| Concurrencia | `concurrencia_y_pruebas.md` §2 — mismo título literal |
| Memoria y escalabilidad | `memoria_y_escalabilidad.md` — mismo título literal |
| Datos cargados | `concurrencia_y_pruebas.md` §1 — mismo título literal |
| Operaciones Redis | `concurrencia_y_pruebas.md` §3 — mismo título literal |
| Pruebas y evidencia | `concurrencia_y_pruebas.md` §4 — mismo título literal |
| Coherencia con el TPO | `concurrencia_y_pruebas.md` §5 — mismo título literal |

Los 11 apartados están cubiertos; varios títulos coinciden literalmente con el enunciado, lo que indica que el equipo trabajó directamente sobre este documento (o uno equivalente). El layout de §9 (`docker-compose.yml`, `scripts/{inicializacion,carga_muestra,sesiones,cache,concurrencia,metricas}.*`, `docs/{patrones_de_acceso,modelo_clave_valor,ciclo_de_vida_e_invalidacion,memoria_y_escalabilidad}.md`, `docs/evidencia/`, `README.md`) también está cubierto en su totalidad, con archivos adicionales permitidos explícitamente por el propio enunciado ("los nombres de archivos y carpetas pueden variar"). **PASS** en ambos.

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

## 3. Decisiones de diseño no tocadas (señaladas para revisión humana)

**Este hito no tiene defensa oral** — el enunciado es explícito: "No se solicita presentación, defensa oral ni video. La evaluación se realizará sobre el repositorio, la documentación y la evidencia técnica" (Restricciones, "Entrega"). Así que lo que sigue no es una lista de "cosas para poder explicar si preguntan": es una lista de decisiones que, si están mal, la evaluación las va a juzgar directamente por lo que dice la documentación entregada, no por lo que el equipo pueda aclarar de palabra después. Ninguna de estas se modificó — son decisiones de modelado o de negocio, no bugs:

1. **TTLs elegidos (30 min inactividad, 12 h tope, 60 s caché de partido, 900 s perfil, 7200 s bucket de tendencia).** Todos están rotulados honestamente como "supuesto del grupo", no como dato del enunciado (correcto: el enunciado explícitamente "no provee... la duración de sesión ni una política de memoria para copiar"). La justificación por escrito ya existe (§1.4 de `ciclo_de_vida_e_invalidacion.md`); alcanza para este hito, no hace falta tocarla.
2. **Política `volatile-lru` sobre las alternativas descartadas** (`noeviction`, `allkeys-lru/lfu`, `volatile-ttl`, `volatile-lfu`). El razonamiento en `memoria_y_escalabilidad.md` §2.1 es comparativo, no solo afirmativo — satisface RF10 ("justificar documentalmente") tal como está. No se toca.
3. ~~**Redis Functions en vez de `MULTI/EXEC`.**~~ **Reemplazada (2026-10-10)** por la corrección del profesor. La condición que motivaba las funciones se resuelve sin ellas:
   - **Voto:** la decisión la toma un comando atómico, `SADD`.
   - **Sesión:** la decide la app con una lectura previa. La ventana entre la lectura y el `MULTI` queda cubierta por la regla de validez y por el `EXPIRE` dentro de la misma transacción.

   Las ventanas que quedan están documentadas en `concurrencia_y_pruebas.md` §2.2.
4. **`ses_cerrar_todas` arma claves por concatenación de strings dentro del script.** El propio módulo ya documenta que esto es válido solo en nodo único y que Redis Cluster exigiría *hash tags*. Sigue siendo así: no se implementó Cluster en este hito (fuera de alcance declarado explícitamente por el enunciado — "no debe presentarse como... Redis Cluster"), por lo que no hay nada que corregir hoy, pero es una limitante real si el equipo llegara a escalar el diseño en otro hito.
5. **Caso abierto heredado del Hito 3** ("¿qué pasa con una sesión cuando el usuario cambia de región?"): sigue sin resolverse, tal como el propio módulo lo admite. No es un olvido de esta auditoría: es una decisión de alcance ya explicitada.
6. **Cierre de la votación MVP sin fuente de verdad asignada:** el propio módulo documenta esto como deuda pendiente de un hito de integración futuro (§5 de `ciclo_de_vida_e_invalidacion.md`). Correcto dejarlo así — no hay módulo asignado a esa necesidad en los Hitos 2/3, así que no es responsabilidad de este hito resolverlo.

## 4. Gaps de documentación / trazabilidad y evidencia

*(La primera versión de este informe listaba acá, como gap #1, que "RNF9 nunca se cita en el módulo". Con el enunciado real en mano, eso no es un gap: RNF9 es "Legibilidad" — scripts comentados y separados por etapa — y el módulo lo cumple estructuralmente sin necesidad de citar el ID. Ver la corrección en el Resumen ejecutivo y la fila RNF9 de la tabla §1. Se retira del listado en vez de dejarlo como si siguiera abierto.)*

1. **Higiene de la evidencia archivada — `02_carga_muestra.txt`.** El documento `concurrencia_y_pruebas.md` (§1) cita textualmente "El total tras la carga es `DBSIZE = 4203`" remitiendo a ese archivo. Pero `02_carga_muestra.txt` en el repo muestra **4204**, no 4203, y su paso previo ("Estado previo") ya mostraba `DBSIZE=4192` en lugar de `0`. Esta auditoría **confirmó en vivo, desde `DBSIZE=0` real, que el valor correcto y estable es 4203** (repetido 3 veces): el número que cita la documentación es el correcto: lo que está desactualizado/impreciso es el archivo de evidencia, que se capturó sobre un ambiente con 4192 claves residuales de una corrida anterior no limpiada (probablemente sesiones u otras claves de otra corrida de `correr_todo.sh` que no se resetearon con `down -v` antes de capturar esa evidencia puntual), más 1 clave suelta no perteneciente a la muestra. **No se sobrescribió el archivo** porque no es un bug del script (ya verificado: el script es determinista e idempotente) sino un problema de *cuándo* se capturó esa evidencia puntual. **Acción para el equipo:** la próxima vez que regeneren evidencia, correr `docker compose down -v && rm -rf ~/docker/data/redis && mkdir -p ~/docker/data/redis` antes de `correr_todo.sh`, para que `02_` refleje un ambiente realmente limpio y coincida con el número que ya citan correctamente en la prosa.

2. **`06_benchmark.txt` y `07_memoria.txt` quedaron generados con la versión de `benchmark.sh` que tenía el bug de §2.1.** Sus cifras de rendimiento (throughput, `p50`/`p99`, `DBSIZE restante`) no cambian de forma sustancial por el fix (el bug no afectaba el rendimiento medido, solo la limpieza posterior), pero **no se regeneraron con las cifras de este sandbox** a propósito: el propio método de medición del proyecto (documentado en `concurrencia_y_pruebas.md` §4.2) es explícito en que las cifras solo son comparables *dentro de la misma corrida, mismo equipo* ("Apple M4, Docker Desktop"), y este sandbox corre en hardware Linux x86_64 distinto. Sobreescribir esos dos archivos con números de otra máquina habría introducido una inconsistencia nueva con la tabla de "Registro del ambiente" de `docs/evidencia/README.md`. **Acción para el equipo:** correr `sh scripts/correr_todo.sh` (o al menos `benchmark.sh`) una vez más en su propia máquina de referencia para refrescar `06_` y `07_` bajo el script ya corregido, y agregar la fila correspondiente a la tabla de "Procedencia de cada archivo" de `docs/evidencia/README.md`, siguiendo el mismo patrón que ya usaron para `04_`/`09_`.

3. **Trazabilidad a Hitos 2/3 — verificada contra la fuente primaria, no solo contra el mapa canónico.** Se confirmó directamente en `hito-2-matriz-decision.md` que N5 (Sesiones) puntúa 4,35 con margen 0,35, que N2 (Partidos → IRIS) tiene margen 0,10, y que N4 (Usuarios → MongoDB) tiene margen 0,10 — los tres coinciden exactamente con lo que citan los documentos de este módulo. También se confirmó, contra `fixture2030-neo4j/queries/carga.cypher` y `fixture2030-cassandra/data/`, que el formato de los identificadores reutilizados (`PAR-A-1`…`PAR-D16-16`, `USR-0000001`…) es consistente entre los tres módulos (Cassandra usa un universo de 250.000 usuarios; la muestra de Redis usa un subconjunto de 2.000 con el mismo formato — no hay contradicción, es una muestra de laboratorio declarada como tal). No se encontró ningún caso análogo al Hallazgo H1 (Mongo/Neo4j) dentro de este módulo.

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
