# Memoria y escalabilidad — Hito 7 · Caché de Usuarios y Sesiones (Redis)

Evidencia: [`07_memoria.txt`](./evidencia/07_memoria.txt), [`08_metricas.txt`](./evidencia/08_metricas.txt). Configuración: [`config/redis.conf`](../config/redis.conf).

## 1. TTL y evicción resuelven problemas distintos

| | **TTL (vencimiento)** | **Evicción (presión de memoria)** |
|---|---|---|
| Pregunta que responde | ¿Hasta cuándo es **válido** el dato? | ¿Qué se sacrifica cuando el servidor **no puede aceptar más**? |
| Quién lo decide | El diseño (política de negocio) | `maxmemory` + `maxmemory-policy` |
| Es predecible | Sí: se sabe cuándo | No: depende de la carga del momento |
| Contador que lo muestra | `expired_keys` | `evicted_keys` |
| Efecto en sesiones | Usuario inactivo pierde la sesión a los 30 min (esperado) | Un usuario **activo** podría perder la sesión antes de tiempo → login inesperado |
| Efecto en caché | Copia vieja sale a los 60 s / 900 s | Se pierde una copia útil → *miss* y recarga desde la fuente de verdad |
| Efecto en datos temporales sin TTL (votación) | Ninguno (no tienen) | **Con `volatile-lru` no se desalojan**: si hay presión, las escrituras fallan (OOM) |

Una clave puede desaparecer **antes** de su TTL por presión de memoria. Ninguna parte del diseño debe asumir que "tiene TTL de 30 min, entonces existirá 30 min".

## 2. Política elegida (RF10)

```
maxmemory 256mb
maxmemory-policy volatile-lru
maxmemory-samples 10
```

| Decisión | Justificación |
|---|---|
| `maxmemory 256mb` | Sin límite, Redis crece hasta agotar la RAM del contenedor y el kernel mata el proceso (peor que una evicción controlada). 256 MB sobra para el laboratorio: la muestra completa usa ~3 MB (`used_memory` en [`07_memoria.txt`](./evidencia/07_memoria.txt)) |
| `volatile-lru` | Sólo desaloja claves **con TTL**. Todo lo que tiene TTL en este módulo es **reconstruible** (sesión → relogin, aceptado por el Hito 3; caché → *miss*). Lo que no tiene TTL (votación abierta) **no** es candidato. Se prefiere "los menos usados recientemente": una sesión inactiva es mejor víctima que una activa |
| `maxmemory-samples 10` | Redis aproxima LRU muestreando; 10 muestras mejora la fidelidad respecto del default (5) a costo de CPU despreciable |

### 2.1 Alternativas descartadas

| Política | Por qué no |
|---|---|
| `noeviction` | Ante presión rechazaría **todas** las escrituras, incluido login y renovación de sesión: caída total del acceso, para proteger datos que son reconstruibles |
| `allkeys-lru` / `allkeys-lfu` | Podría desalojar la votación abierta, único dato no reconstruible |
| `volatile-ttl` | Desaloja lo que **vence antes**, y el orden lo fijan los TTL configurados, no el uso: la copia de un partido en vivo (la más leída) tiene el TTL más corto (60 s) y sería siempre la primera víctima |
| `volatile-lfu` | Alternativa razonable para la caché, pero una sesión recién creada tiene frecuencia baja y sería víctima aunque esté activa; LRU premia el uso reciente, que es lo que importa para sesiones |

## 3. Prueba controlada (RF10)

Método, [`scripts/memoria_prueba.sh`](../scripts/memoria_prueba.sh): se baja `maxmemory` a uso + 8 MB y se escriben 20.000 claves de 1 KB con TTL (`redis-benchmark`); luego, fase 2, se baja a 100 KB (menos que el piso de un Redis vacío).

Resultados observados (corrida del 2026-10-10, Redis 8.10.2; [`07_memoria.txt`](./evidencia/07_memoria.txt)):

| Fase | Observación |
|---|---|
| Fase 1 (tope ≈ 11 MB) | `used_memory` 10,1 MB (bajo el tope); `evicted_keys` = 15.652; `expired_keys` = 11 antes y después del relleno (sin cambios) → **la pérdida fue por presión, no por tiempo** |
| Votación abierta tras la fase 1 | 500 votantes y 5 candidatos: intacta (sin TTL) |
| Muestra de 10 sesiones | 1 sobrevivió: `demo-ses-0000001-1`, la única que se leyó justo antes del relleno. Las otras 9 se habían usado por última vez en la carga, **antes** que los rellenos, o sea que eran las más antiguas para LRU. Se desalojaron cerca de dos tercios de las claves con TTL (DBSIZE pasó de 24.155 esperadas a 7.364). Es coherente con LRU, pero una sola corrida no prueba que una sesión reciente siempre sobreviva: LRU es aproximado (muestrea) |
| Fase 2 (tope 100 KB) | Una escritura **sin TTL** fue rechazada con `OOM command not allowed when used memory > 'maxmemory'` (a la 2.ª escritura); `evicted_keys` 20.990 |
| Votación tras la fase 2 | Sigue intacta y **legible** |

**Lectura importante:** la evicción no fue instantánea: la primera escritura tras bajar el tope todavía fue aceptada; lo más probable es que Redis limite el tiempo de evicción por comando (las métricas muestran `total_eviction_exceeded_time` > 0), pero la causa exacta no se verificó. No se debe asumir que `maxmemory` es un techo duro al byte.

## 4. Consumo observado (base para dimensionar)

De [`08_metricas.txt`](./evidencia/08_metricas.txt) y [`02_carga_muestra.txt`](./evidencia/02_carga_muestra.txt), con la muestra cargada:

| Elemento | Bytes (`MEMORY USAGE`) |
|---|---|
| Una sesión (HASH, 10 campos, `listpack`) | 255 |
| ZSET de tendencia (112 partidos) | 1.501 |
| SET de 500 votantes (`hashtable`) | 18.705 |

Con **255 B por sesión** (dato medido; excluye el ítem del índice por usuario y la sobrecarga de la clave en el diccionario), 3 millones de sesiones darían ~0,7 GB **por extrapolación lineal**. Esa cifra se queda corta: con 100.000 usuarios cargados (§4.1) el costo real por usuario es de 584 B. El `mem_fragmentation_ratio` (13,73) de la muestra **no** es representativo: con menos de 4 MB de datos, el RSS del proceso está dominado por el arranque, no por la fragmentación de los datos.

### 4.1 Medido con 100.000 usuarios simultáneos

Evidencia: [`10_carga_volumen.txt`](./evidencia/10_carga_volumen.txt) y [`11_rendimiento_volumen.txt`](./evidencia/11_rendimiento_volumen.txt) (2026-11-11, Redis 8.10.2). Cada usuario tiene sesión, índice y perfil con sus preferencias: [`concurrencia_y_pruebas.md`](./concurrencia_y_pruebas.md) §6.

| Medida | Valor |
|---|---|
| `used_memory` con 100.000 usuarios + la muestra | 63 MB (de 256 MB de `maxmemory`) |
| `used_memory_dataset` | 37,7 MB |
| `used_memory_rss` / `mem_fragmentation_ratio` | 85,6 MB / 1,35 |
| `evicted_keys` durante la carga y las pruebas | **0** |
| Costo por usuario: diferencia de `used_memory` antes y después de cargar | **584 B** |
| Costo por usuario: suma de `MEMORY USAGE` de sus tres claves (promedio de 1.000 usuarios) | 467 B |

| Clave | Estructura (`OBJECT ENCODING`) | `MEMORY USAGE` promedio |
|---|---|---|
| Sesión `f30:ses:…` (10 campos) | HASH (`listpack`) | 262 B |
| Índice `f30:usr:…:sesiones` (1 sesión) | SET (`listpack`) | 84 B |
| Perfil `f30:cache:usuario:…:perfil` (3 campos) | HASH (`listpack`) | 121 B |

**Por qué 584 y no 467.** `MEMORY USAGE` mide el valor y la clave, pero no la entrada en el diccionario principal ni la de la tabla de vencimientos (las tres claves tienen TTL). Esa diferencia (~117 B por usuario, ~39 B por clave) es parte del costo real: para dimensionar se usa 584 B.

**Proyección lineal** (no medida; orden de magnitud):

| Usuarios con sesión y perfil | Memoria de datos | Comentario |
|---|---|---|
| 100.000 | ~56 MB (58,4 millones de bytes) | medido |
| ~400.000–450.000 | ~256 MB | llena el `maxmemory` del laboratorio: desde ahí `volatile-lru` empieza a desalojar sesiones y perfiles (§1) |
| 2–3 millones (escenario del Hito 1) | ~1,1–1,6 GB | más fragmentación (×1,35 observado); entra en un nodo con varios GB, o se reparte en un Cluster por región (§5) |

(MB y GB en potencias de 2, como `used_memory_human`.)

**Expiración activa con volumen.** Cuando 100.000 sesiones vencieron sin que nadie las leyera, Redis las borró solo en unos 15 s (≈ 6.700 claves/s, `hz 10`): la memoria de las sesiones inactivas se libera sin barridos ni procesos externos. Mientras el ciclo activo no llega a una clave vencida, cualquier lectura ya la ve como inexistente (expiración pasiva), así que la validez de la sesión nunca depende de esa demora.

## 5. Límites del nodo local y pasos futuros de escala

**El laboratorio es un nodo único, sin réplicas, sin Sentinel, sin Cluster.** No es alta disponibilidad: si el contenedor cae, no hay reemplazo automático (el `restart: unless-stopped` lo vuelve a levantar, con los datos del AOF).

| Aspecto | Laboratorio (este hito) | Despliegue con réplicas / Sentinel | Redis Cluster |
|---|---|---|---|
| Nodos | 1 | 1 primario + N réplicas + ≥3 Sentinels | ≥3 primarios (+ réplicas) |
| Falla del primario | Caída hasta que reinicia | Sentinel promueve una réplica | El clúster promueve una réplica del shard |
| Escala de lectura | No | Sí (leer de réplicas, con lag) | Sí |
| Escala de memoria/escritura | Límite = RAM del contenedor | No (un solo primario escribe) | Sí: 16.384 *hash slots* repartidos |
| Réplica asíncrona | — | Sí: una escritura confirmada puede perderse en un failover (coherente con "AP eventual" de N5) | Ídem |
| Impacto en este diseño | — | Ninguno en el modelo | Cada `MULTI/EXEC` con varias claves (crear y cerrar sesión: la sesión y el índice del usuario; cerrar todas) exige que esas claves caigan en el **mismo slot**: hay que usar *hash tags* (`f30:{USR-1}:ses:…`, `f30:{USR-1}:sesiones`). El voto usa dos claves en comandos separados (`SADD`, `ZINCRBY`), así que no lo necesita |

Pasos de escala coherentes con el Hito 3 (sesiones **locales por región, sin réplica cross-región**):

1. **Separar instancias por rol**: sesiones (`volatile-lru`, AOF) y caché (`allkeys-lfu`, sin persistencia) tienen requisitos opuestos y hoy comparten política.
2. **Primario + réplica + Sentinel por región** para sesiones.
3. **Cluster** cuando la memoria de sesiones supere un nodo, con *hash tags* por usuario/partido.
4. Persistencia distinta por rol: la caché no necesita AOF (se reconstruye); las sesiones aceptan perder ~1 s.
5. Cerrar el flujo de la votación hacia la fuente de verdad (ciclo de vida §5).
