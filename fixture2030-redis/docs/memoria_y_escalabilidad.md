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
| Efecto en caché | Copia vieja sale a los 60 s / 900 s | Se pierde una copia útil → *miss* y recarga desde Mongo |
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

Resultados observados (corrida del 2026-09-25, Redis 8.10.2; [`07_memoria.txt`](./evidencia/07_memoria.txt)):

| Fase | Observación |
|---|---|
| Fase 1 (tope ≈ 11 MB) | `used_memory` 10,1 MB (bajo el tope); `evicted_keys` = 15.851; `expired_keys` = 0 → **la pérdida fue por presión, no por tiempo** |
| Votación abierta tras la fase 1 | 500 votantes y 5 candidatos: intacta (sin TTL) |
| Muestra de 10 sesiones | 0 sobrevivieron. Esto **no** contradice LRU: se desalojó cerca de dos tercios de las claves con TTL (DBSIZE pasó de 24.253 esperadas a 7.258) y las sesiones se habían cargado **antes** que los rellenos, o sea que eran las más antiguas para LRU. La prueba **no** pretende demostrar que una sesión reciente sobrevive |
| Fase 2 (tope 100 KB) | Una escritura **sin TTL** fue rechazada con `OOM command not allowed when used memory > 'maxmemory'` (a la 2.ª escritura); `evicted_keys` 21.316 |
| Votación tras la fase 2 | Sigue intacta y **legible** |

**Lectura importante:** la evicción no fue instantánea: la primera escritura tras bajar el tope todavía fue aceptada; lo más probable es que Redis limite el tiempo de evicción por comando (las métricas muestran `total_eviction_exceeded_time` > 0), pero la causa exacta no se verificó. No se debe asumir que `maxmemory` es un techo duro al byte.

## 4. Consumo observado (base para dimensionar)

De [`08_metricas.txt`](./evidencia/08_metricas.txt) y [`02_carga_muestra.txt`](./evidencia/02_carga_muestra.txt), con la muestra cargada:

| Elemento | Bytes (`MEMORY USAGE`) |
|---|---|
| Una sesión (HASH, 9 campos, `listpack`) | 255 |
| ZSET de tendencia (112 partidos) | 1.501 |
| SET de 500 votantes (`hashtable`) | 18.705 |

Con **255 B por sesión** (dato medido; excluye el ítem del índice por usuario y la sobrecarga de la clave en el diccionario), 3 millones de sesiones darían ~0,7 GB **por extrapolación lineal**, un orden de magnitud a validar con una prueba de carga real, no una cifra comprometida. El `mem_fragmentation_ratio` (12,57) de la muestra **no** es representativo: con menos de 4 MB de datos, el RSS del proceso está dominado por el arranque, no por la fragmentación de los datos.

## 5. Límites del nodo local y pasos futuros de escala

**El laboratorio es un nodo único, sin réplicas, sin Sentinel, sin Cluster.** No es alta disponibilidad: si el contenedor cae, no hay reemplazo automático (el `restart: unless-stopped` lo vuelve a levantar, con los datos del AOF).

| Aspecto | Laboratorio (este hito) | Despliegue con réplicas / Sentinel | Redis Cluster |
|---|---|---|---|
| Nodos | 1 | 1 primario + N réplicas + ≥3 Sentinels | ≥3 primarios (+ réplicas) |
| Falla del primario | Caída hasta que reinicia | Sentinel promueve una réplica | El clúster promueve una réplica del shard |
| Escala de lectura | No | Sí (leer de réplicas, con lag) | Sí |
| Escala de memoria/escritura | Límite = RAM del contenedor | No (un solo primario escribe) | Sí: 16.384 *hash slots* repartidos |
| Réplica asíncrona | — | Sí: una escritura confirmada puede perderse en un failover (coherente con "AP eventual" de N5) | Ídem |
| Impacto en este diseño | — | Ninguno en el modelo | Las funciones que arman claves (`ses_cerrar_todas`) y las multi-clave (`voto_emitir`, `ses_crear`, `cache_*`) exigen que sus claves caigan en el **mismo slot**: hay que usar *hash tags* (`f30:{USR-1}:ses:…`, `f30:{PAR-D16-01}:cache:…`) |

Pasos de escala coherentes con el Hito 3 (sesiones **locales por región, sin réplica cross-región**):

1. **Separar instancias por rol**: sesiones (`volatile-lru`, AOF) y caché (`allkeys-lfu`, sin persistencia) tienen requisitos opuestos y hoy comparten política.
2. **Primario + réplica + Sentinel por región** para sesiones.
3. **Cluster** cuando la memoria de sesiones supere un nodo, con *hash tags* por usuario/partido.
4. Persistencia distinta por rol: la caché no necesita AOF (se reconstruye); las sesiones aceptan perder ~1 s.
5. Cerrar el flujo de la votación hacia la fuente de verdad (ciclo de vida §5).
