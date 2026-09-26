# Concurrencia, datos, pruebas y coherencia — Hito 7 · Redis

Cubre los apartados de §8 del enunciado que no están en los otros documentos: **Concurrencia**, **Datos cargados**, **Operaciones Redis**, **Pruebas y evidencia** y **Coherencia con el TPO**.

---

## 1. Datos cargados (RF11)

Generados por [`scripts/carga_muestra.lua`](../scripts/carga_muestra.lua) (función `carga_muestra`), invocada desde [`carga_muestra.redis`](../scripts/carga_muestra.redis). **Determinista**: sin `math.random` ni reloj para decidir valores; todo sale de fórmulas sobre el índice. Repetir la carga deja las mismas claves (sólo cambian timestamps y TTL restantes, que dependen del reloj del servidor).

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

---

## 2. Concurrencia (RF8)

### 2.1 Operaciones y riesgo que evitan

| Operación | Riesgo si se hace con comandos sueltos | Protección |
|---|---|---|
| **Voto MVP único** (`voto_emitir`) | *Check-then-act*: dos requests del mismo usuario ven "no votó" y ambos suman. O caída entre `SADD` y `ZINCRBY`: votante registrado sin voto contado | Función Redis: `SADD` + `ZINCRBY` como unidad |
| **Renovar sesión** (`ses_tocar`) | La clave vence entre el chequeo y el `HSET` → hash parcial **sin TTL** (zombie) | Función Redis |
| **Repoblar caché tras invalidar** (`cache_poner_si_version`) | Un lector lento escribe una copia obsoleta después de la invalidación | Versión + función Redis |
| **Contar visitas** (`tendencia_registrar`) | Ninguno en el `ZINCRBY` (un comando nativo ya es atómico); el riesgo es `ZINCRBY` + `EXPIRE` separados: bucket sin TTL si cae el proceso | Función: los dos juntos |

### 2.2 Por qué es atómico

Redis ejecuta los comandos en **un único hilo**, uno por vez; una **función** (`FCALL`) o un `EVAL` se ejecuta completa antes de que se atienda otro cliente: nadie ve un estado intermedio. Se eligió función y no `MULTI/EXEC` porque `MULTI/EXEC` no permite **decidir** con lo leído dentro de la transacción (no hay `if`), y `WATCH` obligaría a reintentos del lado cliente. Las funciones se guardan en el AOF/RDB: sobreviven al reinicio ([`09_persistencia.txt`](./evidencia/09_persistencia.txt)). Las funciones no usan el reloj del cliente: leen `TIME` del servidor.

Consecuencia a tener en cuenta: **una función lenta bloquea a todos**. Las de `f30` son O(1) o O(sesiones del usuario); `ses_cerrar_todas` es O(n) en las sesiones de **un** usuario (unidades, no millones).

### 2.3 Evidencia

**(a) El riesgo existe** — [`05_concurrencia.txt`](./evidencia/05_concurrencia.txt), [`concurrencia_paralela.sh`](../scripts/concurrencia_paralela.sh): 20 procesos `redis-cli` simultáneos votando **con el mismo usuario**.

| Variante | Puntaje de `ARG-10` | Correcto |
|---|---|---|
| A) `SISMEMBER` → pausa 0,2 s → `SADD` → `ZINCRBY` (no atómica) | **20** | 1 |
| B) `FCALL voto_emitir` | **1** | 1 |

La pausa de 0,2 s en (A) sólo **agranda la ventana** de la carrera para que se vea siempre; sin ella la carrera existe igual pero es más rara. Este experimento demuestra que la carrera es posible, **no** su probabilidad en producción.

**(b) Corrección bajo carga** — [`06_benchmark.txt`](./evidencia/06_benchmark.txt) §B.3, 50 clientes, 100.000 requests:

| Prueba | Esperado | Obtenido |
|---|---|---|
| 100.000 `tendencia_registrar` concurrentes sobre la misma clave | puntaje exacto 100.000 | **100.000** |
| 100.000 votos del mismo usuario | puntaje 1 | **1** |
| 100.000 votos con usuarios al azar (rango 1.000) | votantes distintos == puntaje | **1.000 == 1.000** |

---

## 3. Operaciones Redis: qué hace cada script

| Script | Sección del enunciado | Propósito | Salida |
|---|---|---|---|
| [`funciones_f30.lua`](../scripts/funciones_f30.lua) | — | Librería `f30`: 8 funciones atómicas | — |
| [`carga_muestra.lua`](../scripts/carga_muestra.lua) | — | Librería `f30carga`: generador determinista | — |
| [`inicializacion.redis`](../scripts/inicializacion.redis) | inicio | PING, versión, nodo único, política de memoria, funciones | `01_` |
| [`carga_muestra.redis`](../scripts/carga_muestra.redis) | carga | Genera y verifica el dataset | `02_` |
| [`sesiones.redis`](../scripts/sesiones.redis) | sesiones | Crear, leer, renovar, bloquear, vencer, tope absoluto, cerrar | `03_` |
| [`cache.redis`](../scripts/cache.redis) | caché | miss → hit → invalidación → miss, carrera evitada, TTL, perfil | `04_` |
| [`concurrencia.redis`](../scripts/concurrencia.redis) + [`concurrencia_paralela.sh`](../scripts/concurrencia_paralela.sh) | operaciones concurrentes | Voto, ranking, tendencia; prueba con clientes paralelos | `05_` |
| [`benchmark.sh`](../scripts/benchmark.sh) | métricas | Rendimiento y corrección con `redis-benchmark`; método de hit ratio | `06_` |
| [`memoria_prueba.sh`](../scripts/memoria_prueba.sh) | métricas | TTL vs evicción | `07_` |
| [`metricas.redis`](../scripts/metricas.redis) | métricas | INFO, TTL, MEMORY USAGE, SLOWLOG, SCAN acotado | `08_` |
| [`correr_todo.sh`](../scripts/correr_todo.sh) | — | Ejecuta todo, prueba el reinicio | `09_` |
| [`limpieza.redis`](../scripts/limpieza.redis) / [`limpieza.sh`](../scripts/limpieza.sh) | limpieza opcional | Borrado de demos / por prefijo con `SCAN` + `UNLINK` | — |

`redis-cli` no admite comentarios: los `.redis` se ejecutan filtrándolos con `grep -v '^#'` (ver README).

---

## 4. Pruebas y evidencia (RF12, RF13)

### 4.1 Método y entorno (RNF10)

| | |
|---|---|
| Fecha de la corrida | 2026-09-25 (UTC 23:58) |
| Redis | **8.10.2**, imagen `redis:latest` |
| Host | Apple M4, 10 CPUs, 24 GB RAM; Docker Desktop con 10 CPUs y ~7,75 GB visibles para contenedores |
| Herramienta | `redis-benchmark` dentro del contenedor, **50 clientes, 100.000 requests por prueba, sin pipeline** |
| Configuración | `volatile-lru`, 256 MB, AOF `everysec` |

### 4.2 Resultados ([`06_benchmark.txt`](./evidencia/06_benchmark.txt))

| Operación | Req/s | p50 (ms) | p99 (ms) |
|---|---|---|---|
| `SET` (línea base, una clave) | 323.625 | 0,119 | 0,263 |
| `GET` (línea base, una clave) | 317.460 | 0,087 | 0,111 |
| `HGETALL` de una sesión (9 campos) | 181.488 | 0,111 | 0,615 |
| `FCALL ses_tocar` (validar + renovar, **una sola clave** con 50 clientes) | 138.889 | 0,319 | 0,879 |
| `FCALL tendencia_registrar` (una sola clave) | 121.507 | 0,303 | 0,919 |
| `FCALL voto_emitir` (usuarios al azar) | 328.947 | 0,087 | 0,255 |

**Interpretación.** Renovar una sesión con la función es ~2× más lento que un `HGETALL` (varios comandos por dentro) pero sigue en el orden de 10⁵ req/s en este equipo. Estas cifras **no** dicen cuánto soportaría la plataforma real: sirven para comparar operaciones entre sí *en este equipo y esta corrida*.

**Variabilidad.** Es **una** corrida por prueba, sin intervalo de confianza. En una ejecución previa (no archivada) `tendencia_registrar` midió casi el doble que acá (~239.000 vs ~122.000 req/s), lo que da una idea del ruido: no se deben leer diferencias de ±30 % entre operaciones como reales.

### 4.3 Hit ratio: qué se midió y qué no

[`06_benchmark.txt`](./evidencia/06_benchmark.txt) §B.4 valida el **método** (`CONFIG RESETSTAT` → carga → `keyspace_hits/misses`). Se precargaron 56 de 112 claves y se pidieron 100.000 al azar: hit ratio observado **50,2 %**, coincidente con el ~50 % esperado por construcción. **No es un hit ratio de producción ni una promesa**: la relación real depende del tráfico, que no se midió (restricción de rendimiento del enunciado).

### 4.4 TTL observados

| Prueba | TTL observado | Archivo |
|---|---|---|
| Sesión nueva | 1800 | `03_` §3.2 |
| Sesión renovada | 1800 | `03_` §3.3 |
| Sesión con TTL de demo 3 s, tras esperar 4 s | `EXISTS 0`, `TTL -2` | `03_` §3.6 |
| Sesión con tope absoluto 5 s, pidiendo renovar 1800 | TTL 5 (acotado) | `03_` §3.7 |
| Copia de partido | 60 | `04_` §4.2 |
| Copia con TTL de demo 2 s, tras esperar 3 s | ausente | `04_` §4.6 |
| Votación abierta | `-1` (sin TTL, a propósito) | `08_` §7.7 |
| Ranking de tendencia | ≈ 7200 | `05_` §5.7 |

### 4.5 Limitaciones del laboratorio

- **Nodo único**, cliente y servidor en la **misma VM** de Docker Desktop: comparten CPU; sin latencia de red real.
- `redis-benchmark` genera carga sintética con **una** clave caliente en varias pruebas (peor caso de contención, poco realista); los ids `__rand_int__` no coinciden con el formato de los ids de la muestra, por lo que las pruebas de sesión usan una clave fija.
- Dataset chico (~4.200 claves, ~3 MB): todo cabe en la caché del procesador; no se prueba el comportamiento con 3 M de sesiones.
- **No** se mide ni se simula el caso Redis caído (documentado en [`ciclo_de_vida_e_invalidacion.md`](./ciclo_de_vida_e_invalidacion.md) §2 como comportamiento esperado, no probado).
- No hay integración con ninguna fuente de verdad (IRIS para Partidos, MongoDB para Usuarios): el flujo miss/invalidación se demuestra con el documento de origen escrito a mano.
- Las estadísticas de `INFO` de [`08_metricas.txt`](./evidencia/08_metricas.txt) acumulan lo ocurrido desde el último `CONFIG RESETSTAT` (que `benchmark.sh` ejecuta en §B.4): `keyspace_hits/misses` reflejan el hit ratio sintético, no tráfico real.

---

## 5. Coherencia con el TPO y los hitos anteriores

| Requisito / hito | Cómo lo respeta este módulo |
|---|---|
| **Hito 1 — escenario** (2–3 M usuarios simultáneos, >100.000 req/s, respuesta ≤ 100 ms) | La operación más frecuente (validar sesión) es una lectura+renovación en memoria de ~0,3 ms p50 en el laboratorio. No es una demostración de capacidad de producción (§4.5) |
| **Hito 2 — modelo por necesidad** | Sesiones (N5) → clave/valor, como se decidió |
| **Hito 3 — N5 AP, eventual, TTL, local por región** | Sesión local sin réplica cross-región; vigencia por TTL; pérdida = relogin. Se **mantiene** la exclusión de réplica entre regiones ([`memoria_y_escalabilidad.md`](./memoria_y_escalabilidad.md) §5). El caso abierto del Hito 3 ("¿qué pasa con la sesión si el usuario cambia de región?") **sigue sin resolverse**: no se aborda en este hito |
| **Hito 2 — N2 Partidos y N4 Usuarios** | La matriz asigna **Partidos (N2) a Objetos (IRIS, 4,25)**, 0,10 sobre Documental (4,15), y **Usuarios (N4) a Documental (MongoDB, 4,10)**, 0,10 sobre Columnar (4,00). Ambas quedaron marcadas como decisiones frágiles (margen menor a 0,20). Son las fuentes de verdad de las copias de este módulo. **Ninguna está implementada todavía** |
| **Hito 3 — N2 y N4** | Mantiene N4 en MongoDB, pero **lista N2 como Documental (MongoDB) "por 0,20 sobre IRIS"** y márgenes de 0,20, lo que **contradice la matriz del Hito 2** (IRIS por 0,10; N4 también por 0,10). Además el argumento de topología de N4 ("Equipos, Jugadores y Partidos ya requieren un núcleo con escritura coordinada en el mismo motor documental") parte de esa premisa. Este módulo sigue la matriz del Hito 2. La discrepancia es del Hito 3 y **no se corrigió acá**; el diseño de la caché no depende del motor de origen y no cambia si se resuelve en un sentido u otro |
| **Hito 4 — MongoDB** | Implementa sólo `equipos` y `jugadores`; no hay colección de partidos ni de usuarios, así que la fuente de las copias es **prevista**, no existente. Los `PAR-…` de la muestra vienen del Hito 5 (Neo4j) y los `USR-…` del Hito 6 (Cassandra) |
| **Hito 5 — Neo4j** | Mismos `partido_id` (`PAR-…`) para el ranking de tendencia: 112 partidos (fase de grupos y dieciseisavos; el Hito 2 estima 127 en todo el torneo). Sin integración por código |
| **Hito 6 — Cassandra** | Mismos `partido_id` y `usuario_id` (`USR-…`). El **Hito 6 (Comentarios)** anticipaba "Q0: se cachea la configuración del partido"; queda como caso de uso futuro de esta caché, sin implementar |
