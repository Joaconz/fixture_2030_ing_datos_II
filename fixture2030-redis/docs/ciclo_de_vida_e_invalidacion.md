# Ciclo de vida e invalidación — Hito 7 · Caché de Usuarios y Sesiones (Redis)

Decisión explícita de vida útil para **todo** dato temporal (RNF6). Salidas que lo demuestran: [`03_sesiones.txt`](./evidencia/03_sesiones.txt), [`04_cache.txt`](./evidencia/04_cache.txt).

## 0. Resumen de decisiones

| Dato | Vence por | Renovación | Invalidación explícita | Conservación |
|---|---|---|---|---|
| Sesión `f30:ses:*` | 30 min sin actividad · tope absoluto 12 h | Cada request autenticado (`ses_tocar`) | Logout, cerrar todas, bloqueo | No se conserva |
| Índice `f30:usr:*:sesiones` | 12 h | No | `ses_cerrar_todas` | No |
| Copia de partido | 60 s | No (se repuebla en el miss) | **Sí: al cambiar Mongo** (`cache_invalidar`) | No |
| Versión `…:ver` | 24 h | Cada invalidación | — | No |
| Copia de perfil | 900 s | No | **Sí: al cambiar Mongo** | No |
| Votación MVP **abierta** | **No vence** | — | — | **Sí, hasta cerrar** (§5) |
| Votación MVP cerrada | 24 h tras cerrar | — | — | Ver §5 |
| Tendencia por hora | 7200 s desde la primera visita del bucket | No | — | No |

## 1. Sesiones (RF3, RF4, RF5)

### 1.1 Atributos temporales (RF5)

`creada_en`, `ultima_actividad` y `expira_absoluta` (epoch en segundos, tomados con `TIME` **del servidor**, no del cliente: los relojes de los nodos de aplicación no son confiables entre sí). Además `estado` y `solicitudes` para auditar uso.

### 1.2 Regla de validez

> Una sesión es válida **si y sólo si** la clave existe **y** su `estado` es `ACTIVA`.

La primera parte la decide Redis: cuando pasan 1800 s sin renovación la clave **deja de existir** (vencimiento nativo, lazy + activo). No hay campo "vencida" que la aplicación deba comparar con el reloj.

### 1.3 Evento que renueva

Cualquier request autenticado que pase por `ses_tocar`, incluido el *heartbeat* que la app manda mientras el usuario mira un partido en vivo. Un usuario que mira un partido sin tocar la pantalla **no** está inactivo para el sistema si el heartbeat sigue llegando. Consultas que no pasan por la validación **no** renuevan.

### 1.4 Duración y justificación

| Parámetro | Valor | Justificación |
|---|---|---|
| Inactividad | **1800 s (30 min)** | Un partido tiene ~15' de previa y un entretiempo de 15': 30 min cubre una pausa larga (entretiempo + alargue de ida a buscar algo) sin obligar a reloguear, y evita mantener en memoria millones de sesiones de gente que ya cerró la app. Es un supuesto del grupo, no un dato del enunciado |
| Tope absoluto | **43200 s (12 h)** | Una jornada completa de partidos. Sin tope, un cliente con heartbeat mantendría la sesión para siempre (una credencial robada nunca caducaría). El TTL renovado se calcula como `min(1800, expira_absoluta − ahora)` |
| Consecuencia de vencer | Sesión inexistente → **login** | Coincide con el Hito 3 (N5): perder una sesión es tolerable, "se repite un login". No hay reintento silencioso |

### 1.4.1 Por qué `ses_tocar` es una función y no comandos sueltos

Con `EXISTS` → `HSET` → `EXPIRE` separados, la clave puede vencer **entre** el chequeo y el `HSET`: `HSET` la recrea como un hash parcial **sin TTL** (sesión zombie inmortal). Ejecutada como función es una unidad: o existe y se renueva, o no existe y no se toca nada. Ver [`concurrencia_y_pruebas.md`](./concurrencia_y_pruebas.md) §2.

### 1.5 Cómo se comprueba que venció o fue eliminado

`EXISTS clave` → `0`, `TTL clave` → `-2` (clave ausente; `-1` significaría "existe sin TTL"), y `ses_tocar` → `nil`. Demostrado con TTL de 3 s en [`03_sesiones.txt`](./evidencia/03_sesiones.txt) §3.6, esperando con `BLPOP` sobre una clave inexistente (una espera del servidor, no un barrido). **No hay ningún proceso que recorra sesiones** (§5.3 del enunciado).

### 1.6 Comportamiento ante una sesión inexistente

| Situación | Respuesta de la app |
|---|---|
| `ses_tocar` devuelve `nil` (no existe / venció / cerrada) | 401 y pantalla de login. **No se crea nada implícitamente** |
| `ses_tocar` devuelve `SESION_BLOQUEADA` | 403; no se renueva, la sesión vence sola |
| Redis no responde | Fail-closed para operaciones autenticadas: sin poder validar no se debe asumir sesión válida. Lecturas públicas (fixture, resultados) siguen por la fuente de verdad |

### 1.7 Cierre y invalidación explícita

| Evento | Operación |
|---|---|
| Logout | `ses_cerrar` (DEL + SREM) |
| Cambio de contraseña / baja | `ses_cerrar_todas` (usa el índice por usuario) |
| Moderación | `HSET estado BLOQUEADA` |

## 2. Caché de la ficha de partido (RF6, RF7)

**Patrón: cache-aside.** La aplicación consulta Redis; ante ausencia consulta la fuente y repuebla. Redis no conoce la fuente.

| Pregunta del enunciado (§5.4) | Respuesta |
|---|---|
| **Fuente de verdad** | MongoDB, colección de Partidos (N2, CP en el cierre según Hito 3). **Aún no implementada** (el Hito 4 sólo tiene equipos y jugadores). Redis guarda una **copia** |
| **Cache hit** | `f30:cache:partido:{id}` existe → se sirve el JSON |
| **Cache miss** | Ausente → leer Mongo → `cache_poner_si_version` con TTL 60 s → responder |
| **Cuándo se actualiza/invalida** | En cuanto el servicio de partidos **confirma** el cambio en Mongo: `cache_invalidar` (DEL + INCR de `:ver`). No se espera al TTL |
| **Permanencia máxima admisible** | 60 s **sólo** si la invalidación falla (servicio caído entre el commit de Mongo y el DEL). Con invalidación funcionando, la copia obsoleta dura ≈ 0 |
| **Clave ausente o Redis caído** | Se lee de Mongo y se responde igual. Se pierde velocidad, no disponibilidad. **No se repuebla si Redis no responde** |

### 2.1 Estrategia de coherencia (por qué TTL no alcanza)

Un TTL de 60 s significa que tras un gol el marcador viejo podría servirse hasta 60 s: inaceptable para un marcador en vivo. Por eso el TTL es sólo la **red de seguridad**; la coherencia la da la **invalidación en escritura**. Se invalida (borra) en vez de **reescribir** la copia, porque el servicio que cambia el dato no siempre conoce la forma cacheada, y borrar es idempotente.

### 2.2 La carrera que cierra la versión (`:ver`)

Invalidar con `DEL` a secas deja una ventana:

1. Un lector L hace *miss* y lee Mongo (marcador 0-0). Es lento.
2. El servicio confirma el gol (1-0) e invalida.
3. L termina y hace `SET` con 0-0. **Copia obsoleta durante todo el TTL.**

Solución: el lector anota `GET :ver` **antes** de leer Mongo y repuebla con `cache_poner_si_version(…, versión_leída)`; la función descarta la escritura si `:ver` actual > versión leída. `cache_invalidar` sube `:ver`. Demostrado en [`04_cache.txt`](./evidencia/04_cache.txt) §4.5: la escritura tardía devuelve `0` y la caché conserva 1-0.

*Límite:* `:ver` vence a las 24 h; si venciera justo mientras un lector lento sigue en vuelo, la comparación se reinicia contra 0. Es una ventana de muy baja probabilidad (lector con >24 h de retraso) y el daño está acotado por el TTL de 60 s.

### 2.3 Perfil de usuario (P7)

HASH con TTL de 900 s. El perfil cambia poco; 15 min de copia vieja no afectan la operación, pero un cambio explícito del usuario (idioma, nombre) **invalida** la copia (`DEL`) para que vea su propio cambio de inmediato: el Hito 3 exige consistencia de sesión para el propio usuario (N4).

## 3. Rankings temporales (RF9)

`f30:rank:tendencia:{yyyymmddHH}`: un ZSET por hora. `EXPIRE … NX` sólo en la primera visita del bucket → cada bucket vence **7200 s** después de nacer, sin barrido. Dos horas (no una) porque durante la hora siguiente todavía puede consultarse la anterior para mostrar "cambios respecto de la hora previa"; es un supuesto del grupo.

## 4. Votación MVP: por qué **no** tiene TTL mientras está abierta

Es el único dato del módulo que **no** es reconstruible: si se pierde un voto, no hay otra fuente que lo recupere. Por eso: (a) sin TTL, no vence por tiempo; (b) con `volatile-lru` **no es candidato a evicción** (sólo se desalojan claves con TTL); (c) si la memoria se llena sólo de claves sin TTL, las escrituras se **rechazan con OOM** en vez de perder votos en silencio. Probado en [`07_memoria.txt`](./evidencia/07_memoria.txt): tras desalojar más de 15.000 claves volátiles la votación siguió con 500 votantes y 5 candidatos.

## 5. Cierre de la votación (decisión pendiente, fuera de alcance)

Al cerrarse, el resultado **debe** pasar a una fuente de verdad (Mongo) y recién después ponerse `EXPIRE 86400` sobre las claves. Este hito no integra Mongo (el enunciado lo excluye); queda documentado como deuda: **hasta que el cierre persista el resultado, la votación es un dato que sólo vive en Redis** y depende de AOF (`everysec`: se aceptaría perder ~1 s de votos ante una caída del proceso).

## 6. Resumen de qué pasa ante una clave ausente

| Clave | Ausente significa | La app hace |
|---|---|---|
| `f30:ses:*` | Sesión vencida/cerrada/nunca existió | 401 → login |
| `f30:cache:*` | Nunca cacheada, vencida, invalidada, desalojada o Redis reiniciado sin datos | Leer la fuente y repoblar |
| `f30:voto:*` | Votación no abierta, o pérdida de datos | Tratar como votación inexistente; **no** inicializar en silencio si debería existir |
| `f30:rank:tendencia:*` | Nadie visitó nada esa hora, o ya venció | Ranking vacío (correcto) |
