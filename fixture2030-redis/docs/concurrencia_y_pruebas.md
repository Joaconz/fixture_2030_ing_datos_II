# Concurrencia, datos, pruebas y coherencia — Hito 7 · Redis

Cubre los apartados de §8 del enunciado que no están en los otros documentos: **Concurrencia**, **Datos cargados**, **Operaciones Redis**, **Pruebas y evidencia** y **Coherencia con el TPO**.

---

## 1. Datos cargados (RF11)

Generados por [`scripts/carga_muestra.sh`](../scripts/carga_muestra.sh): un `awk` arma los comandos (`HSET`, `EXPIRE`, `SADD`, `ZADD`, `ZINCRBY`) y los envía a `redis-cli`. Al final ejecuta [`carga_muestra.redis`](../scripts/carga_muestra.redis), que verifica lo cargado. **Determinista**: sin azar; todo sale de fórmulas sobre el índice, y los timestamps parten de un instante fijo de demostración (2030-06-29 16:00 UTC). Repetir la carga deja las mismas claves y los mismos valores. Solo cambian los TTL restantes, que Redis cuenta desde el momento de la carga.

| Dato | Cantidad | Distribución |
|---|---|---|
| Usuarios `USR-0000001…0002000` | 2.000 | ids del Hito 6 |
| Sesiones `f30:ses:demo-ses-*` | 2.200 | 1 por usuario; **2** cada 10º usuario (web + móvil) |
| Estado | ~3 % `BLOQUEADA` (usuarios múltiplo de 33), resto `ACTIVA` | |
| Rol | 1 de cada 200 `MODERADOR`, resto `HINCHA` | |
| Región | AM / EU / AF, rotación por índice (regiones del Hito 3) | ≈ 1/3 cada una |
| Dispositivo | web / android / ios, rotación | ≈ 1/3 cada uno |
| Actividad | `ultima_actividad` escalonada entre 0 y 30 min atrás → **TTL restantes repartidos** | |
| Ranking de tendencia | 112 partidos (los `PAR-*` de los Hitos 5 y 6) en `f30:rank:tendencia:2030062916` | visitas decrecientes con el índice; `PAR-D16-01` = 250.000 (audiencia máxima, coherente con el Hito 6) |
| Votación MVP de `PAR-D16-01` | 500 votos, 5 candidatos | ≈ 100 c/u (99–101 en la corrida registrada) |
| Caché | **vacía a propósito** | los flujos miss→hit se ven desde cero |

El total tras la carga es `DBSIZE = 4203` ([`02_carga_muestra.txt`](./evidencia/02_carga_muestra.txt)): 2.200 sesiones + 2.000 índices de usuario + 1 ranking + 2 de votación.

Los documentos de origen de la caché (la ficha de partido, que vendría de IRIS, y el perfil, de MongoDB) se escriben a mano en [`cache.redis`](../scripts/cache.redis): el enunciado excluye la integración física con los otros servicios.

Aparte de esta muestra hay un **dataset de volumen de 100.000 usuarios simultáneos** (sesión, índice y perfil de cada uno), que se carga, se mide y se borra con sus propios scripts sin tocar la muestra: ver §6.

---

## 2. Concurrencia (RF8)

### 2.1 Operaciones y riesgo que evitan

| Operación | Riesgo si se hace con comandos sueltos | Protección |
|---|---|---|
| **Voto MVP único** | *Check-then-act*: con `SISMEMBER` y después `SADD`, dos requests del mismo usuario ven "no votó" y ambos suman | `SADD` hace el chequeo y el registro en **un solo comando**: devuelve 1 solo al primero. La app suma con `ZINCRBY` solo si recibió 1 |
| **Crear sesión** | Caída entre el `HSET` y el `EXPIRE`: sesión sin TTL (eterna) o fuera del índice del usuario | `MULTI/EXEC` con `HSET` + `EXPIRE` + `SADD` + `EXPIRE` |
| **Renovar sesión** | Caída a mitad: actividad registrada sin renovar el TTL, o contador sin la actividad | `MULTI/EXEC` con `HSET` + `HINCRBY` + `EXPIRE`. La validación previa la hace la app con `HMGET` |
| **Cerrar sesión** | Sesión borrada que sigue en el índice, o al revés | `MULTI/EXEC` con `SREM` + `DEL` |
| **Contar visitas de tendencia** | Ninguno en el `ZINCRBY` (un comando nativo ya es atómico). El riesgo es `ZINCRBY` y `EXPIRE` separados: bucket sin TTL si cae el proceso | `MULTI/EXEC` con `ZINCRBY` + `EXPIRE … NX` |
| **Contador de solicitudes de la sesión** | Leer, sumar en la app y escribir pierde incrementos | `HINCRBY`: el incremento ocurre en el servidor |

### 2.2 Por qué es atómico, y qué no garantiza

Redis ejecuta los comandos en **un único hilo**, uno por vez. Hay dos niveles de atomicidad:

- **Un comando** (`SADD`, `ZINCRBY`, `HINCRBY`, `INCR`, `DEL`) se ejecuta entero. Por eso `SADD` alcanza como guarda del voto: no hay forma de que dos clientes reciban 1 para el mismo usuario.
- **`MULTI/EXEC`** encola comandos y los ejecuta seguidos, sin comandos de otro cliente en el medio. Las respuestas llegan juntas al `EXEC`. No hay *rollback* ni condiciones adentro: lo que hay que decidir (¿existe la sesión? ¿está bloqueada? ¿cuánto TTL le queda?) se decide **antes**, con una lectura.

Lo que queda fuera de esa garantía está documentado, no escondido:

| Ventana | Qué puede pasar | Por qué se acepta |
|---|---|---|
| Entre la validación (`HMGET`) y la renovación (`MULTI`) | La sesión vence en el medio y el `HSET` crea un hash parcial | Tiene TTL (el `EXPIRE` va en el mismo `MULTI`) y no tiene `usuario_id`, así que la regla de validez lo trata como inexistente. Demostrado en `03_` §3.4 bis |
| Entre `SADD` (devolvió 1) y `ZINCRBY` del voto | Si el proceso de la app cae justo ahí, el votante queda registrado y su voto no se cuenta | Nunca hay voto **doble**. La pérdida se detecta con el invariante `SCARD votantes == suma de puntajes`, que `concurrencia.redis` §5.4 verifica |
| Repoblado de la caché después de una invalidación (lector lento) | Copia obsoleta hasta que vence el TTL | Acotado a 60 s ([`ciclo_de_vida_e_invalidacion.md`](./ciclo_de_vida_e_invalidacion.md) §2.2) |

### 2.3 Evidencia

**(a) El riesgo existe y la guarda lo evita.** Ver [`05_concurrencia.txt`](./evidencia/05_concurrencia.txt) y [`concurrencia_paralela.sh`](../scripts/concurrencia_paralela.sh): 20 procesos `redis-cli` simultáneos votan **con el mismo usuario**.

| Variante | Puntaje de `ARG-10` | Correcto |
|---|---|---|
| A) `SISMEMBER` → pausa 0,2 s → `SADD` → `ZINCRBY` (no atómica) | **20** | 1 |
| B) `SADD` (guarda) → pausa 0,2 s → `ZINCRBY` solo si `SADD` devolvió 1 | **1** | 1 |

La pausa de 0,2 s en (A) solo **agranda la ventana** de la carrera para que se vea siempre; sin ella la carrera existe igual, pero es más rara. (B) tiene la misma pausa y da 1: la decisión ya la tomó `SADD`. El experimento demuestra que la carrera es posible, **no** su probabilidad en producción.

**(b) Corrección bajo carga.** Ver [`06_benchmark.txt`](./evidencia/06_benchmark.txt) §B.3: 50 clientes, 100.000 requests.

| Prueba | Esperado | Obtenido |
|---|---|---|
| 100.000 `ZINCRBY` concurrentes sobre la misma clave | puntaje exacto 100.000 | **100.000** |
| 100.000 `HINCRBY` concurrentes sobre el contador de una sesión | +100.000 exacto | **+100.000** |
| 100.000 `SADD` con usuarios al azar (rango 1.000) | usuarios distintos, sin duplicados | **1.000** |

---

## 3. Operaciones Redis: qué hace cada script

| Script | Sección del enunciado | Propósito | Salida |
|---|---|---|---|
| [`inicializacion.redis`](../scripts/inicializacion.redis) | inicio | PING, versión, nodo único, política de memoria y persistencia | `01_` |
| [`carga_muestra.sh`](../scripts/carga_muestra.sh) + [`carga_muestra.redis`](../scripts/carga_muestra.redis) | carga | Genera el dataset y lo verifica | `02_` |
| [`sesiones.redis`](../scripts/sesiones.redis) | sesiones | Crear, leer, renovar (con `MULTI/EXEC`), bloquear, vencer, tope absoluto, cerrar | `03_` |
| [`cache.redis`](../scripts/cache.redis) | caché | miss → hit → invalidación → miss, lector lento, TTL, perfil | `04_` |
| [`concurrencia.redis`](../scripts/concurrencia.redis) + [`concurrencia_paralela.sh`](../scripts/concurrencia_paralela.sh) | operaciones concurrentes | Voto, ranking, tendencia; prueba con clientes paralelos | `05_` |
| [`benchmark.sh`](../scripts/benchmark.sh) | métricas | Rendimiento y corrección con `redis-benchmark`; método de hit ratio | `06_` |
| [`memoria_prueba.sh`](../scripts/memoria_prueba.sh) | métricas | TTL vs evicción | `07_` |
| [`metricas.redis`](../scripts/metricas.redis) | métricas | INFO, TTL, MEMORY USAGE, SLOWLOG, SCAN acotado | `08_` |
| [`correr_todo.sh`](../scripts/correr_todo.sh) | — | Ejecuta todo, prueba el reinicio | `09_` |
| [`limpieza.redis`](../scripts/limpieza.redis) / [`limpieza.sh`](../scripts/limpieza.sh) | limpieza opcional | Borrado de demos / por prefijo con `SCAN` + `UNLINK` | — |
| [`carga_volumen.sh`](../scripts/carga_volumen.sh) | carga de volumen | 100.000 usuarios con sesión, índice y perfil, por pipeline (§6) | `10_` |
| [`limpieza_volumen.sh`](../scripts/limpieza_volumen.sh) | limpieza de volumen | Borra sólo el volumen, por prefijo con `SCAN` + `UNLINK` | `10_`, `11_` |
| [`rendimiento_volumen.sh`](../scripts/rendimiento_volumen.sh) | rendimiento con volumen | Memoria, latencia, `redis-benchmark`, transacciones con 50 clientes, expiración activa (§6) | `11_` |
| [`correr_volumen.sh`](../scripts/correr_volumen.sh) | — | Ejecuta la carga tres veces, las pruebas, y limpia el volumen | `10_`, `11_` |

`redis-cli` no admite comentarios: los `.redis` se ejecutan filtrándolos con `grep -v '^#'` (ver README).

### 3.1 Catálogo de operaciones de ejemplo

Las 27 operaciones que muestran los `.redis` del módulo, todas sobre las claves de [`modelo_clave_valor.md`](./modelo_clave_valor.md). La columna "Dónde" es el marcador `== N.M ==` del script; la salida real está en el archivo de evidencia con el mismo número.

| # | Operación | Comandos | Dónde |
|---|---|---|---|
| 1 | Verificar disponibilidad | `PING` | `inicializacion.redis` 1.1 |
| 2 | Confirmar nodo único y configuración efectiva | `ROLE`, `CONFIG GET maxmemory-policy` / `appendonly` | `inicializacion.redis` 1.3–1.4 |
| 3 | Crear sesión (P1) | `MULTI` · `HSET` 10 campos · `EXPIRE 1800` · `SADD` al índice · `EXPIRE 43200` · `EXEC` | `sesiones.redis` 3.1 |
| 4 | Recuperar la sesión completa y su vigencia | `HGETALL`, `TTL` | `sesiones.redis` 3.2 |
| 5 | Validar sesión (P2) | `HMGET usuario_id estado expira_absoluta` | `sesiones.redis` 3.3 (a) |
| 6 | Renovar sesión (P2) | `MULTI` · `HSET ultima_actividad` · `HINCRBY solicitudes 1` · `EXPIRE 1800` · `EXEC` | `sesiones.redis` 3.3 (b) |
| 7 | Detectar sesión inexistente (401) | `HMGET` (todo vacío), `EXISTS` | `sesiones.redis` 3.4 |
| 8 | Bloquear una sesión sin cambiar su TTL | `HSET estado BLOQUEADA` | `sesiones.redis` 3.5 |
| 9 | Vencimiento por inactividad | `EXPIRE` corto, espera, `EXISTS` 0 y `TTL` -2 | `sesiones.redis` 3.6 |
| 10 | Renovación acotada por el tope absoluto | `EXPIRE` con `min(1800, expira_absoluta − ahora)` | `sesiones.redis` 3.7 |
| 11 | Listar las sesiones de un usuario | `SMEMBERS f30:usr:{id}:sesiones` | `sesiones.redis` 3.8 |
| 12 | Cerrar sesión (P3) | `MULTI` · `SREM` del índice · `DEL` · `EXEC` | `sesiones.redis` 3.8 |
| 13 | Cerrar todas las sesiones de un usuario (P3) | `SMEMBERS` y después `MULTI` · `DEL` de cada sesión · `DEL` del índice · `EXEC` | `sesiones.redis` 3.9 |
| 14 | Leer la copia de un partido (miss / hit) | `GET` | `cache.redis` 4.1–4.2 |
| 15 | Repoblar la caché con TTL (P5) | `SET … EX 60` | `cache.redis` 4.1, 4.4 |
| 16 | Invalidar la copia al cambiar la fuente (P6) | `DEL` | `cache.redis` 4.3 |
| 17 | Cachear el perfil con sus preferencias (P7) | `MULTI` · `HSET nombre idioma region` · `EXPIRE 900` · `EXEC` | `cache.redis` 4.7 |
| 18 | Leer el perfil cacheado | `HGETALL`, `TTL` | `cache.redis` 4.7 |
| 19 | Voto MVP único (P8) | `SADD` como guarda y, si devolvió 1, `ZINCRBY` | `concurrencia.redis` 5.1–5.3 |
| 20 | Verificar el invariante de la votación | `ZRANGE … WITHSCORES`, `SCARD` | `concurrencia.redis` 5.4 |
| 21 | Top 3 de la votación (P9) | `ZREVRANGE … 0 2 WITHSCORES` | `concurrencia.redis` 5.5 |
| 22 | Top 5 de partidos en tendencia (P11) | `ZREVRANGE … 0 4 WITHSCORES` | `concurrencia.redis` 5.6 |
| 23 | Posición y visitas de un partido | `ZREVRANK`, `ZSCORE` | `concurrencia.redis` 5.6 |
| 24 | Registrar una visita en el bucket de la hora (P10) | `MULTI` · `ZINCRBY` · `EXPIRE 7200 NX` · `EXEC` | `concurrencia.redis` 5.7 |
| 25 | Inspeccionar claves por prefijo sin bloquear | `SCAN 0 MATCH f30:ses:* COUNT 20` | `metricas.redis` 7.6 |
| 26 | Costo y codificación de una clave | `MEMORY USAGE`, `OBJECT ENCODING` | `metricas.redis` 7.7–7.8 |
| 27 | Vencidas por TTL vs desalojadas, comandos lentos y latencia | `INFO stats` / `keyspace`, `SLOWLOG GET`, `LATENCY LATEST` | `metricas.redis` 7.2–7.3, 7.9–7.10 |

Con volumen (§6), las operaciones 3, 5, 6 y 12 se ejecutan sobre las 100.000 sesiones, y 17 sobre los 100.000 perfiles.

---

## 4. Pruebas y evidencia (RF12, RF13)

### 4.1 Método y entorno (RNF10)

| | |
|---|---|
| Fecha de la corrida | 2026-10-10 (UTC 00:09) |
| Redis | **8.10.2**, imagen `redis:latest` |
| Host | Notebook con Windows 11, 12 CPUs; Docker Desktop (WSL2) con 12 CPUs y ~7,7 GB visibles para contenedores |
| Herramienta | `redis-benchmark` dentro del contenedor, **50 clientes, 100.000 requests por prueba, sin pipeline** |
| Configuración | `volatile-lru`, 256 MB, AOF `everysec` |

### 4.2 Resultados ([`06_benchmark.txt`](./evidencia/06_benchmark.txt))

| Operación | Req/s | p50 (ms) | p99 (ms) |
|---|---|---|---|
| `SET` (línea base, una clave) | 107.643 | 0,407 | 0,879 |
| `GET` (línea base, una clave) | 185.185 | 0,135 | 0,511 |
| `HGETALL` de una sesión (10 campos) | 139.276 | 0,183 | 0,647 |
| `HINCRBY` del contador de una sesión (parte de la renovación) | 97.752 | 0,415 | 0,943 |
| `EXPIRE` de una sesión (parte de la renovación) | 109.529 | 0,399 | 0,807 |
| `ZINCRBY` de tendencia (**una sola clave** con 50 clientes) | 102.987 | 0,431 | 0,951 |
| `SADD` de la guarda del voto (usuarios al azar) | 167.504 | 0,143 | 0,791 |

**Interpretación.** Todas las operaciones del módulo quedan en el orden de 10⁵ req/s en este equipo. `redis-benchmark` mide un comando por vez: la renovación de una sesión son tres comandos en un `MULTI/EXEC` (`HSET` + `HINCRBY` + `EXPIRE`), así que se mide por partes y no como transacción. Estas cifras **no** dicen cuánto soportaría la plataforma real: sirven para comparar operaciones entre sí *en este equipo y esta corrida*.

**Variabilidad.** Es **una** corrida por prueba, sin intervalo de confianza. La corrida anterior del módulo (25/09/2026, en otro equipo: Apple M4 con macOS) midió `SET` a 323.625 req/s; esta, a 107.643. La diferencia es de hardware y de virtualización, no del módulo: no se deben comparar cifras entre equipos ni leer como reales diferencias de ±30 % entre operaciones.

### 4.3 Hit ratio: qué se midió y qué no

[`06_benchmark.txt`](./evidencia/06_benchmark.txt) §B.4 valida el **método** (`CONFIG RESETSTAT` → carga → `keyspace_hits/misses`). Se precargaron 56 de 112 claves y se pidieron 100.000 al azar: hit ratio observado **50,0 %**, coincidente con el ~50 % esperado por construcción. **No es un hit ratio de producción ni una promesa**: la relación real depende del tráfico, que no se midió (restricción de rendimiento del enunciado).

### 4.4 TTL observados

| Prueba | TTL observado | Archivo |
|---|---|---|
| Sesión nueva | 1800 | `03_` §3.2 |
| Sesión renovada | 1800 | `03_` §3.3 |
| Sesión con TTL de demo 3 s, tras esperar 4 s | `EXISTS 0`, `TTL -2` | `03_` §3.6 |
| Sesión con tope absoluto 5 s, renovada 1 s después | TTL 4 = `min(1800, 4)` (acotado) | `03_` §3.7 |
| Hash parcial creado por la carrera validar/renovar | 1800 (no queda eterno) | `03_` §3.4 bis |
| Copia de partido | 60 | `04_` §4.2 |
| Copia con TTL de demo 2 s, tras esperar 3 s | ausente | `04_` §4.6 |
| Votación abierta | `-1` (sin TTL, a propósito) | `08_` §7.7 |
| Ranking de tendencia | ≈ 7200 | `05_` §5.7 |

### 4.5 Limitaciones del laboratorio

- **Nodo único**, cliente y servidor en la **misma VM** de Docker Desktop: comparten CPU; sin latencia de red real.
- `redis-benchmark` genera carga sintética con **una** clave caliente en varias pruebas (peor caso de contención, poco realista); los ids `__rand_int__` no coinciden con el formato de los ids de la muestra, por lo que las pruebas de sesión de `benchmark.sh` usan una clave fija. Las pruebas de volumen (§6) sí eligen sesiones al azar entre 100.000.
- Dataset chico (~4.200 claves, ~3 MB): todo cabe en la caché del procesador. Con 100.000 usuarios (~300.000 claves, ~60 MB) se midió en §6; no se prueba el comportamiento con 3 M de sesiones.
- **No** se mide ni se simula el caso Redis caído (documentado en [`ciclo_de_vida_e_invalidacion.md`](./ciclo_de_vida_e_invalidacion.md) §2 como comportamiento esperado, no probado).
- No hay integración con ninguna fuente de verdad (IRIS para Partidos, MongoDB para Usuarios): el flujo miss/invalidación se demuestra con el documento de origen escrito a mano.
- Las estadísticas de `INFO` de [`08_metricas.txt`](./evidencia/08_metricas.txt) acumulan lo ocurrido desde el último `CONFIG RESETSTAT` (que `benchmark.sh` ejecuta en §B.4): `keyspace_hits/misses` reflejan el hit ratio sintético, no tráfico real.

---

## 5. Coherencia con el TPO y los hitos anteriores

| Requisito / hito | Cómo lo respeta este módulo |
|---|---|
| **Hito 1 — escenario** (2–3 M usuarios simultáneos, >100.000 req/s, respuesta ≤ 100 ms) | La operación más frecuente (validar sesión) es una lectura (`HMGET`) más una renovación (`MULTI/EXEC` de tres comandos) en memoria; cada comando queda por debajo de 0,5 ms p50 en el laboratorio. No es una demostración de capacidad de producción (§4.5) |
| **Hito 2 — modelo por necesidad** | Sesiones (N5) → clave/valor, como se decidió |
| **Hito 3 — N5 AP, eventual, TTL, local por región** | Sesión local sin réplica cross-región; vigencia por TTL; pérdida = relogin. Se **mantiene** la exclusión de réplica entre regiones ([`memoria_y_escalabilidad.md`](./memoria_y_escalabilidad.md) §5). El caso abierto del Hito 3 ("¿qué pasa con la sesión si el usuario cambia de región?") **sigue sin resolverse**: no se aborda en este hito |
| **Hito 2 — N2 Partidos y N4 Usuarios** | La matriz asigna **Partidos (N2) a Objetos (IRIS, 4,25)**, 0,10 sobre Documental (4,15), y **Usuarios (N4) a Documental (MongoDB, 4,10)**, 0,10 sobre Columnar (4,00). Ambas quedaron marcadas como decisiones frágiles (margen menor a 0,20). Son las fuentes de verdad de las copias de este módulo. **Ninguna está implementada todavía** |
| **Hito 3 — N2 y N4** | Mantiene N4 en MongoDB, pero **lista N2 como Documental (MongoDB) "por 0,20 sobre IRIS"** y márgenes de 0,20, lo que **contradice la matriz del Hito 2** (IRIS por 0,10; N4 también por 0,10). Además el argumento de topología de N4 ("Equipos, Jugadores y Partidos ya requieren un núcleo con escritura coordinada en el mismo motor documental") parte de esa premisa. Este módulo sigue la matriz del Hito 2. La discrepancia es del Hito 3 y **no se corrigió acá**; el diseño de la caché no depende del motor de origen y no cambia si se resuelve en un sentido u otro |
| **Hito 4 — MongoDB** | Implementa sólo `equipos` y `jugadores`; no hay colección de partidos ni de usuarios, así que la fuente de las copias es **prevista**, no existente. Los `PAR-…` de la muestra vienen del Hito 5 (Neo4j) y los `USR-…` del Hito 6 (Cassandra) |
| **Hito 5 — Neo4j** | Mismos `partido_id` (`PAR-…`) para el ranking de tendencia: 112 partidos (fase de grupos y dieciseisavos; el Hito 2 estima 127 en todo el torneo). Sin integración por código |
| **Hito 6 — Cassandra** | Mismos `partido_id` y `usuario_id` (`USR-…`). El **Hito 6 (Comentarios)** anticipaba "Q0: se cachea la configuración del partido"; queda como caso de uso futuro de esta caché, sin implementar |

---

## 6. Volumen: 100.000 usuarios simultáneos (RF11, RF12)

La guía del TPO pide, para Redis, un dataset de **100.000+ usuarios simultáneos** y pruebas de rendimiento. La muestra de §1 tiene 2.000. Este apartado agrega el volumen **sin estructuras nuevas**: cada usuario tiene las mismas claves que ya usa el módulo.

### 6.1 Qué se carga ([`carga_volumen.sh`](../scripts/carga_volumen.sh))

| Clave (por usuario) | Estructura | Contenido | TTL |
|---|---|---|---|
| `f30:ses:vol-ses-{12 dígitos}` | HASH | los mismos 10 campos que la muestra (`session_id`, `usuario_id`, `rol`, `region`, `dispositivo`, `estado`, `creada_en`, `ultima_actividad`, `expira_absoluta`, `solicitudes`) | 1201–1800 s (actividad escalonada entre 0 y 10 min atrás) |
| `f30:usr:{usuario_id}:sesiones` | SET | el `session_id` del usuario | 43200 s (tope de sesión) |
| `f30:cache:usuario:{usuario_id}:perfil` | HASH | `nombre`, `idioma` (es/en/pt/fr/ar), `region` (AM/EU/AF): las **preferencias** del usuario | 900 s |

- **Usuarios** `USR-1000000…USR-1099999` y sesiones `vol-ses-000000000000…000000099999`. No se cruzan con la muestra (`USR-0000001…0002000`, `demo-ses-…`). Los 12 dígitos son el formato que `redis-benchmark` usa en `__rand_int__`: así las pruebas eligen sesiones reales al azar.
- **Una sesión `ACTIVA` por usuario**, 1 de cada 200 `MODERADOR`, regiones y dispositivos en rotación. Ninguna sesión vence durante las pruebas (TTL mínimo 1201 s).
- **Preferencias:** el TPO menciona usuarios, sesiones y preferencias. Las preferencias (idioma, región) viven en la copia del perfil que ya existía (P7, fuente MongoDB N4): no se creó otra clave.

**Cómo se carga.** Un `awk` genera el protocolo de Redis (RESP) y `redis-cli --pipe` lo envía sin esperar cada respuesta. Cada usuario se crea **igual que en la aplicación**: crear sesión (P1: `HSET` + `EXPIRE` + `SADD` + `EXPIRE` en `MULTI/EXEC`) y cachear perfil (P7: `HSET` + `EXPIRE` en `MULTI/EXEC`). Sin Lua. Son 11 comandos por usuario, 1.100.000 en total.

**Determinista e idempotente.** Sin azar: todo sale del índice del usuario y del instante fijo de la muestra (2030-06-29 16:00 UTC). Repetir la carga, con o sin limpieza previa, deja los mismos conteos y los mismos valores; sólo cambia el TTL restante. Se comprueba con una **huella**: el md5 de `HGETALL`/`SMEMBERS` de 1 de cada 100 usuarios.

**Limpieza propia** ([`limpieza_volumen.sh`](../scripts/limpieza_volumen.sh)): `SCAN` por patrón (`f30:ses:vol-ses-*`, `f30:usr:USR-1??????:sesiones`, `f30:cache:usuario:USR-1??????:perfil`) + `UNLINK` en lotes de 500. Nunca `KEYS` ni `FLUSHALL` (RNF8). Los conteos de verificación también usan `SCAN` (`redis-cli --scan`), que recorre por cursor sin bloquear.

### 6.2 Cómo se corre

```bash
cd fixture2030-redis
docker compose up -d --wait
sh scripts/correr_volumen.sh          # ~2 min; escribe docs/evidencia/10_ y 11_
```

Por partes (dentro del contenedor):

```bash
docker compose exec -T redis sh /scripts/carga_volumen.sh            # 100.000 usuarios (otro número: como argumento)
docker compose exec -T redis sh /scripts/rendimiento_volumen.sh      # pruebas (modifica el volumen)
docker compose exec -T redis sh /scripts/limpieza_volumen.sh         # borra sólo el volumen
```

### 6.3 Carga: tres corridas iguales ([`10_carga_volumen.txt`](./evidencia/10_carga_volumen.txt))

Corrida del 2026-11-11, commit `1464124`, Redis 8.10.2, ambiente nuevo (volumen de Docker vacío). Primero se cargó la muestra (`DBSIZE = 4203`).

| Corrida | Estado previo | Tiempo de carga | Usuarios / sesiones / perfiles | Errores | Huella |
|---|---|---|---|---|---|
| 1 | volumen vacío | 2,77 s (36.140 usuarios/s, ~398.000 comandos/s) | 100.000 / 100.000 / 100.000 | 0 | `171a025c…` |
| 2 | vacío otra vez (`limpieza_volumen.sh`) | 2,54 s | 100.000 / 100.000 / 100.000 | 0 | `171a025c…` |
| 3 | encima de la corrida 2, sin limpiar | 2,18 s | 100.000 / 100.000 / 100.000 | 0 | `171a025c…` |

- `INFO keyspace` tras la carga: `keys=304202, expires=304200`. Las únicas dos claves sin TTL son las de la votación abierta de la muestra: **todas las claves del volumen tienen TTL**.
- La muestra quedó igual (md5 de una sesión, un índice y la votación, antes y después; votantes 500, candidatos 5, partidos en tendencia 112).
- `evicted_keys = 0`: la carga entra en los 256 MB sin desalojar nada.

### 6.4 Rendimiento ([`11_rendimiento_volumen.txt`](./evidencia/11_rendimiento_volumen.txt))

Misma corrida, con los 100.000 usuarios cargados. Cliente y servidor dentro del mismo contenedor.

**Memoria** (detalle en [`memoria_y_escalabilidad.md`](./memoria_y_escalabilidad.md) §4.1): `used_memory` 63 MB en total; 584 B por usuario según la diferencia de `used_memory` en la carga, 467 B según `MEMORY USAGE` de sus tres claves.

**Latencia vista por un cliente** (`redis-cli --latency`, ms):

| Situación | p50 | p99 | máx. |
|---|---|---|---|
| En reposo, 5 s | 0,19 | 0,89 | 1,34 |
| Mientras 200 clientes validan sesiones al azar (3 s) | 1,44 | 3,72 | 4,62 |

**`redis-benchmark`**, 200 clientes (`--threads 4`), sesiones al azar entre las 100.000 (`-r 100000`), sin pipeline:

| Operación | Requests | Req/s | p50 (ms) | p99 (ms) | máx. (ms) |
|---|---|---|---|---|---|
| Validar: `HMGET usuario_id estado expira_absoluta` | 1.000.000 | 114.234 | 1,50 | 3,82 | 13,6 |
| Renovar, parte 1: `HSET ultima_actividad` | 300.000 | 92.194 | 1,82 | 4,53 | 11,0 |
| Renovar, parte 2: `HINCRBY solicitudes 1` | 300.000 | 79.893 | 2,01 | 6,94 | 57,4 |
| Renovar, parte 3: `EXPIRE 1800` | 300.000 | 99.800 | 1,74 | 4,74 | 20,9 |

**Transacciones completas** (`MULTI/EXEC`, como las ejecuta la app): 50 clientes `redis-cli --pipe` a la vez, cada uno con 2.000 usuarios distintos. Cada fase recorre los 100.000 usuarios y se verifica después:

| Fase | Tiempo | Operaciones/s | Comandos/s | Errores | Verificación |
|---|---|---|---|---|---|
| Validar (`HMGET`) | 0,14 s | 724.638 | 724.638 | 0 | 100.000 respuestas |
| Renovar (`MULTI` `HSET` `HINCRBY` `EXPIRE` `EXEC`) | 0,73 s | 136.799 | 683.995 | 0 | `ultima_actividad` nueva en **100.000 de 100.000** sesiones |
| Cerrar (`MULTI` `SREM` `DEL` `EXEC`) | 0,49 s | 204.082 | 816.327 | 0 | 0 sesiones y 0 índices (el SET vacío desaparece solo) |
| Crear (`MULTI` `HSET` `EXPIRE` `SADD` `EXPIRE` `EXEC`) | 1,36 s | 73.314 | 439.883 | 0 | 100.000 sesiones e índices, y la **misma huella** que la carga |

**Expiración activa.** Las 100.000 sesiones pasan a TTL 5 s y nadie las lee (sólo se consultan `DBSIZE` e `INFO`, que no tocan claves). Redis las borra solo con su ciclo de expiración activa: empieza a los ~6 s y termina a los 21 s (unos 15 s, ≈ 6.700 claves/s con `hz 10`). `DBSIZE` bajó de 304.200 a 204.115 y `expired_keys` subió 100.085 (las 100.000 más 85 sesiones de la muestra que vencieron solas en esos segundos). Después, un `SCAN` no encontró ninguna sesión del volumen. Los índices y perfiles siguieron (TTL de 12 h y 900 s).

**Durante todas las pruebas:** `evicted_keys = 0`, ningún evento en `LATENCY LATEST` (umbral 50 ms) y ningún comando en `SLOWLOG` (umbral 10 ms).

### 6.5 Cómo leer estas cifras

- **`redis-benchmark` mide un comando por request.** Con 200 clientes, la latencia incluye la espera en la cola del servidor: por eso p50 sube de 0,19 ms en reposo a ~1,5 ms. Los máximos aislados (57 ms en `HINCRBY`) son picos de una sola corrida, sin repetición; no aparecieron en el `SLOWLOG`, así que lo más probable es que sean espera del cliente o de la VM y no ejecución lenta, pero no se verificó.
- **Las transacciones van por pipeline:** cada cliente envía sus 2.000 transacciones sin esperar cada respuesta. Las cifras de la tabla son de **rendimiento total**, no latencia por request. Muestran que las operaciones reales (con `MULTI/EXEC`) sobre 100.000 usuarios distintos terminan sin errores y con el resultado exacto.
- **Laboratorio:** nodo único, cliente y servidor en la misma VM de Docker Desktop (comparten CPU), sin red real, una corrida por prueba. 100.000 usuarios no son los 2–3 M del escenario del Hito 1: la proyección está en [`memoria_y_escalabilidad.md`](./memoria_y_escalabilidad.md) §4.1.
- **`correr_todo.sh` sigue andando con este agregado:** se volvió a correr el 2026-11-11 sobre el mismo ambiente y terminó sin errores las 9 etapas. La evidencia `01_`–`09_` del 2026-10-10 no se reemplazó (no cambió ningún script de esas etapas).
