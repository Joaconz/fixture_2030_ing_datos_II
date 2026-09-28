# Cardinalidad, carga y escalabilidad — Hito 8 · Series temporales (InfluxDB 2)

**Ingeniería de Datos II · Grupo 2** — Santiago Pazos, Valentina Frisoli, Joaquín Núñez

---

## 1. Variación de cada dimensión

| Tag | Measurement(s) | Valores distintos | ¿Multiplica series? |
|---|---|---:|---|
| `partido_id` | feed, audiencia | 112 | Sí |
| `equipo_id` | feed | 64 (2 por partido) | Sí, ×2 por partido |
| `condicion` | feed | 2 | **No**: depende de `partido_id + equipo_id` |
| `fase` | feed, audiencia | 2 | **No**: depende de `partido_id` |
| `sede_id` | feed | 16 | **No**: depende de `partido_id` |
| `region` | audiencia | 8 | Sí, ×8 por partido |
| `servicio` | operación | 5 | Sí |

Un tag que **depende funcionalmente** de otro (fase y sede dependen del partido; condición, del partido y el equipo) no crea series nuevas: solo agrega una entrada al índice con 2 o 16 valores. Se acepta ese costo porque evita cruzar con otro módulo para filtrar por fase o por estadio (P7).

## 2. Estimación y medición de la cardinalidad (RF11, RNF5)

En InfluxDB 2 una **serie** es measurement + conjunto de tags, y es lo que indexa el TSI (el índice que se mantiene en memoria y en disco). Cada field de la serie se guarda aparte en los archivos TSM, pero no agrega series al índice.

```
estadisticas_equipo   = partidos × equipos por partido = 112 × 2  =   224 series   (× 6 fields = 1.344 claves TSM)
audiencia_partido     = partidos × regiones            = 112 × 8  =   896 series   (× 3 fields = 2.688 claves TSM)
operacion_plataforma  = servicios                      =             5 series   (× 3 fields =    15 claves TSM)
                                                          TOTAL    = 1.125 series
```

**Medido:** `validacion.py` (V2) calcula la cardinalidad real con `influxdb.cardinality()` y coincide con la estimación: 224 / 896 / 5 en el perfil completo (4 / 16 / 5 en la muestra). Para comparar: el Hito 7 (Redis) maneja 2–3 millones de sesiones. 1.125 series es una cardinalidad **baja** para InfluxDB, y es a propósito: en InfluxDB 2 la memoria del índice crece con las series, no con los puntos.

> **Corrección registrada.** La primera versión de V2 esperaba "series × fields" (1.344 / 2.688 / 15). La corrida real mostró que `influxdb.cardinality()` cuenta series del índice (measurement + tags); se corrigió la expectativa, no los datos.

### Atributos que se excluyeron de los tags, y por qué

| Atributo | Valores posibles | Si fuera tag… | Decisión |
|---|---|---|---|
| `usuario_id` | 2–3 millones (Hito 1) | 112 × 8 × 3.000.000 ≈ **2.700 millones** de series: el índice no entra en memoria | **Nunca**. La actividad por usuario es del Hito 7 (Redis) o del Hito 6 (Cassandra); acá solo agregados por región |
| `comentario_id` | 1 M+ por partido | Una serie por punto: deja de ser una serie temporal | **Nunca**. El texto vive en Cassandra (Hito 6) |
| `dni` del jugador | 1.282 (≈40 por partido) | 112 × 40 = 4.480 series para el feed: manejable | **No en este hito**: ningún patrón pide estadísticas por jugador. Si el producto las pidiera, sería un measurement aparte (`estadisticas_jugador`) y con la identidad del jugador ya unificada entre MongoDB y Neo4j (corrección pendiente del Hito 5) |
| `minuto_juego` | 0–92 | ×93 series por equipo | **Field**: es un valor observado que cambia con el tiempo, no una dimensión |
| `posesion_pct`, cualquier medida | continua | Una serie por valor distinto | **Field**, siempre (el enunciado lo prohíbe expresamente) |
| texto libre (nombre del estadio, del equipo) | — | Crece con el catálogo, no se filtra | Se usa el **código** (`sede_id`, `equipo_id`); el nombre está en el Hito 5 |

## 3. Shards: cómo se reparte el tiempo en disco

Cada bucket se divide en **shards** por período de tiempo; el período lo fija InfluxDB según la retención:

| Bucket | Retención | Duración del shard | Shards medidos (V7) | Espacio en disco medido (V7) |
|---|---|---|---:|---:|
| `fixture2030_vivo` | 45 días | 1 día | **25** (del 9 de junio al 3 de julio) | **35,0 MB** |
| `fixture2030_historico` | infinita | 7 días | 5 | 6,5 MB |
| `fixture2030_prueba_retencion` | 1 hora | 1 hora | 2 | 0,0 MB |

**Consecuencias de diseño:**
- **Una consulta de un partido lee un solo shard** (un partido dura menos de un día) y, dentro de él, solo las series de ese partido gracias al índice TSI. Por eso todas las consultas en vivo acotan tiempo y partido (RNF8).
- **Una pregunta de torneo sobre el bucket vivo** recorre 25 shards y 7,8 M de puntos de audiencia. Funciona (en InfluxDB 2 no hay un límite duro de archivos por consulta), pero cuesta mucho más que leer el resumen: por eso P7 va contra el bucket histórico, y la **V8** lo verifica (mismo resultado: 112 puntos en lugar de 7.795.200).
- **La retención elimina shards enteros** cuando su fin queda más atrás que el período de retención: en el bucket vivo, el detalle de un día de partidos desaparece de una vez, 45 días después.

**Compresión observada:** los 10.094.400 puntos ocupan ~1,43 GB como line protocol y **35 MB** en el bucket vivo: el motor TSM los comprime unas **40 veces** (timestamps regulares cada 1 s, enteros que cambian poco, tags guardados una sola vez por serie). Es una medición del laboratorio: `storage_shard_disk_size` no incluye lo que todavía estuviera en el WAL.

## 4. Estrategia de carga (RF12)

| Aspecto | Decisión | Por qué |
|---|---|---|
| Generación | `generacion_puntos.py`: Python, determinista (semilla por partido), escribe `.lp.gz` por partido y measurement + `manifiesto.json` | Separa generar de cargar (RF7). El manifiesto es lo esperado contra lo que valida V1 |
| Timestamps | Calculados desde la fecha del partido del Hito 5, en **segundos** (`precision=s`) | Precisión declarada (RF6); el feed y la audiencia no tienen detalle útil por debajo del segundo |
| Formato | Line protocol, `POST /api/v2/write` | Formato nativo, sin librerías |
| Tamaño de lote | 10.000 líneas (~1,3 MB) por POST, configurable | En el rango recomendado por InfluxDB 2 (5.000–10.000 líneas) |
| Concurrencia | 4 POST en paralelo, como máximo 8 lotes en vuelo | Aprovecha los núcleos sin llenar la memoria si el servidor se atrasa |
| Orden | Cronológico dentro de cada partido (orden monótono del Hito 3); los archivos pueden llegar en cualquier orden | InfluxDB acepta puntos fuera de orden (V6) |
| Errores de datos | Una línea inválida hace que el servidor rechace el lote (HTTP 400); un 422 (puntos fuera de la retención) también detiene la carga | Ninguna pérdida silenciosa |
| Reintentos | 429, 5xx y errores de red: hasta 4, con espera exponencial (0,5 → 4 s) | Son seguros: reescribir un punto lo sobrescribe (V6) |
| Compresión | Opcional (`--gzip`) | En la misma notebook no hay red que ahorrar |
| Validación | `validacion.py` compara puntos por partido contra el manifiesto | Prueba que lo cargado es lo declarado |

### Resultado frente al objetivo de 10 M+

La carga completa **es** el objetivo: **10.094.400 puntos confirmados en 12,94 s (780.255 puntos/s), 1.127 lotes, 0 reintentos, 0 errores** (detalle en [`pruebas_y_rendimiento.md`](./pruebas_y_rendimiento.md)). En vivo, el escenario genera ~20 puntos/s (nunca hay más de 2 partidos simultáneos): el laboratorio carga unas **38.000 veces** esa tasa (780.255 ÷ 20,5), así que el cuello de botella del módulo no es la ingesta.

## 5. Límites del laboratorio

- **Un solo nodo**, cliente y servidor en la misma notebook, compitiendo por los 8 CPUs y 3,8 GB que tiene Docker.
- **InfluxDB 2 OSS**: sin réplicas ni clúster (eso es de InfluxDB Enterprise o Cloud).
- **La tasa medida es de confirmación del servidor**: el 204 llega cuando el punto está en el WAL y en el caché; la compactación a TSM ocurre después, en segundo plano.
- **Fechas en 2030**: las consultas "en vivo" usan un "ahora" simulado (minuto 90 del partido elegido), y en el bucket vivo nada vence durante la prueba (por eso existe el bucket de prueba de 1 hora).

## 6. Escalabilidad fuera del laboratorio

| Cambio | Efecto sobre el diseño |
|---|---|
| Más partidos (los 127 del TPO, con las eliminatorias completas) | Cardinalidad lineal: +10 series por partido. Sin riesgo |
| Estadísticas por jugador, 1 Hz | ≈ 40 series más por partido (4.480 en total): manejable, en un measurement aparte |
| Datos de tracking (posición de los 22 jugadores, 25 Hz) | 550 puntos por segundo por partido: ×275 el volumen del feed. Justificaría precisión de milisegundos, un nodo dedicado a la ingesta y retención de horas, no de días |
| Réplica y alta disponibilidad (Hito 3: AP, réplica conceptual) | InfluxDB 2 OSS no replica: haría falta InfluxDB Enterprise o Cloud, o un segundo nodo alimentado en paralelo (por ejemplo con Telegraf o una cola) |
| Varias fuentes escribiendo a la vez | Un intermediario (Telegraf o una cola) que acumule en lotes y reintente, en lugar de que cada fuente escriba directo |
| Observabilidad posterior (Hito 12) | `operacion_plataforma` es el antecedente; además InfluxDB 2 ya expone `/metrics` en formato Prometheus (lo usa V7) |
