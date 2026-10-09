# Cardinalidad, carga y escalabilidad — Hito 8 · Series temporales (InfluxDB 3 Core)

**Ingeniería de Datos II · Grupo 2** — Santiago Pazos, Valentina Frisoli, Joaquín Núñez

---

## 1. Variación de cada dimensión

| Tag | Tabla(s) | Valores distintos | ¿Multiplica series? |
|---|---|---:|---|
| `partido_id` | feed, audiencia | 112 | Sí |
| `equipo_id` | feed | 64 (2 por partido) | Sí, ×2 por partido |
| `condicion` | feed | 2 | **No**: depende de `partido_id + equipo_id` |
| `fase` | feed, audiencia | 2 | **No**: depende de `partido_id` |
| `sede_id` | feed | 16 | **No**: depende de `partido_id` |
| `region` | audiencia | 8 | Sí, ×8 por partido |
| `servicio` | operación | 5 | Sí |

Un tag que **depende funcionalmente** de otro (fase y sede dependen del partido; condición, del partido y el equipo) no crea series nuevas: es una columna más de la clave de serie con 2 o 16 valores. Se acepta ese costo porque evita cruzar con otro módulo para filtrar por fase o por estadio (P7).

## 2. Estimación y medición de la cardinalidad (RF11, RNF5)

En InfluxDB 3 una **serie** es la tabla + una combinación de valores de sus tags. Los tags de cada tabla forman su **clave de serie** (`system.tables.series_key_columns`): dentro de cada archivo, los datos se ordenan por esa clave y por tiempo, y la deduplicación (un punto repetido reemplaza al anterior) se hace sobre clave de serie + `time`. Cada tag se guarda como columna de texto con codificación de diccionario (`Dictionary(Int32, Utf8)`, observado en `information_schema.columns`): cuantos más valores distintos tiene un tag, más grande es el diccionario, peor la compresión y más grupos tiene que armar cada `GROUP BY` y cada deduplicación. Por eso la cardinalidad sigue siendo una decisión de diseño, aunque la versión 3 no tenga el índice de series en memoria de la versión 2.

```
estadisticas_equipo   = partidos × equipos por partido = 112 × 2  =   224 series   (6 fields por fila)
audiencia_partido     = partidos × regiones            = 112 × 8  =   896 series   (3 fields por fila)
operacion_plataforma  = servicios                      =             5 series   (3 fields por fila)
                                                          TOTAL    = 1.125 series
```

**Medido:** `validacion.py` (V2) cuenta las combinaciones distintas de tags que aparecen en los datos y coinciden con la estimación: **224 / 896 / 5** en el perfil completo (4 / 16 / 5 en la muestra). Además verifica que la identidad mínima (`partido_id + equipo_id`, `partido_id + region`) da el mismo número: `condicion`, `fase` y `sede_id` no agregan series. Para comparar: el Hito 7 (Redis) maneja 2–3 millones de sesiones. 1.125 series es una cardinalidad **baja**, y es a propósito.

### Atributos que se excluyeron de los tags, y por qué

| Atributo | Valores posibles | Si fuera tag… | Decisión |
|---|---|---|---|
| `usuario_id` | 2–3 millones (Hito 1) | 112 × 8 × 3.000.000 ≈ **2.700 millones** de series: cada fila tendría su propia serie y nada se podría agrupar ni comprimir | **Nunca**. La actividad por usuario es del Hito 7 (Redis) o del Hito 6 (Cassandra); acá solo agregados por región |
| `comentario_id` | 1 M+ por partido | Una serie por punto: deja de ser una serie temporal | **Nunca**. El texto vive en Cassandra (Hito 6) |
| `dni` del jugador | 1.282 (≈40 por partido) | 112 × 40 = 4.480 series para el feed: manejable | **No en este hito**: ningún patrón pide estadísticas por jugador. Si el producto las pidiera, sería una tabla aparte (`estadisticas_jugador`) y con la identidad del jugador ya unificada entre MongoDB y Neo4j (corrección pendiente del Hito 5) |
| `minuto_juego` | 0–92 | ×93 series por equipo | **Field**: es un valor observado que cambia con el tiempo, no una dimensión |
| `posesion_pct`, cualquier medida | continua | Una serie por valor distinto | **Field**, siempre (el enunciado lo prohíbe expresamente) |
| texto libre (nombre del estadio, del equipo) | — | Crece con el catálogo, no se filtra | Se usa el **código** (`sede_id`, `equipo_id`); el nombre está en el Hito 5 |

## 3. Cómo se guardan los datos: WAL, memoria y archivos Parquet

| Etapa | Qué pasa | Medido en el laboratorio |
|---|---|---|
| **Escritura** | El servidor junta las escrituras y las vuelca al **WAL** en disco cada 1 s (`--wal-flush-interval`). Recién ahí responde 204: un punto confirmado ya está en disco | Cada POST tarda ~1 s (p50 1,15 s en la carga completa), sea cual sea su tamaño |
| **Buffer consultable** | Lo que está en el WAL también queda en memoria y se puede consultar enseguida | Pico de **1,55 GiB** de memoria del contenedor durante la carga de los 10 M de puntos (`docker stats`) |
| **Snapshot a Parquet** | Cada 600 archivos de WAL (`--wal-snapshot-size`), el servidor pasa los datos a archivos **Parquet** (columnares, comprimidos) por tabla y por tramo de 10 minutos de datos, y libera memoria | La carga completa generó **226 archivos de WAL**: no alcanzó para un snapshot. `system.parquet_files` quedó vacío (V7) y los datos ocupan **645 MB** de WAL en `~/docker/data/influxdb` |
| **Reinicio** | Al arrancar, el servidor vuelve a leer el WAL que todavía no pasó a Parquet | Con los 10 M de puntos: **9,0 s** de lectura del WAL y *healthy* en **19 s**; mismos conteos antes y después (`02_persistencia.txt`) |

**Consecuencias de diseño:**
- **Una consulta de un partido lee solo su tramo de tiempo** (un partido dura menos de 3 horas) y, dentro de él, solo las filas del partido. Por eso todas las consultas en vivo acotan tiempo y partido (RNF8): P1–P6 responden entre 8 y 22 ms con los 10 M de puntos cargados.
- **Una pregunta de torneo sobre la base viva** recorre los 7,8 M de puntos de audiencia: tardó **4.309 ms** (V8). La misma pregunta sobre la base histórica lee 112 puntos y tardó **41 ms**: unas 100 veces menos. Por eso P7 va contra la base histórica.
- **En operación real el patrón de escritura es otro**: durante un partido llega un poco de datos por segundo, el WAL se vuelca cada segundo y a los ~10 minutos hay un snapshot a Parquet. Una consulta de todo el torneo sobre la base viva leería entonces cientos de archivos Parquet. InfluxDB 3 Core tiene un tope configurable de archivos por consulta (`--query-file-limit`). Es un motivo más para responder las preguntas de torneo desde la base histórica. Ese comportamiento no se midió en el laboratorio, porque la carga fue una ráfaga de 55 s.

## 4. Estrategia de carga (RF12)

| Aspecto | Decisión | Por qué |
|---|---|---|
| Generación | `generacion_puntos.py`: Python, determinista (semilla por partido), escribe `.lp.gz` por partido y tabla + `manifiesto.json` | Separa generar de cargar (RF7). El manifiesto es lo esperado contra lo que valida V1 |
| Timestamps | Calculados desde la fecha del partido del Hito 5, en **segundos** (`precision=second`) | Precisión declarada (RF6); el feed y la audiencia no tienen detalle útil por debajo del segundo |
| Formato | Line protocol, `POST /api/v3/write_lp` | Formato nativo de InfluxDB 3, sin librerías |
| Tamaño de lote | **50.000 líneas (~7 MB) por POST**, configurable | Debajo de los 10 MB que recomienda InfluxDB 3. Como cada POST espera el volcado del WAL (~1 s), conviene mandar más líneas por viaje: con 10.000 líneas y 4 hilos la muestra cargó a 40.495 puntos/s; con 50.000, a 98.001 (barrido en `evidencia/barrido/`) |
| Concurrencia | **8 POST en paralelo**, como máximo 16 lotes en vuelo | Mientras un lote espera el WAL, los otros se siguen enviando. El tope de lotes en vuelo evita llenar la memoria si el servidor se atrasa |
| Orden | Cronológico dentro de cada partido (orden monótono del Hito 3); los archivos pueden llegar en cualquier orden | InfluxDB acepta puntos fuera de orden (V6) |
| Errores de datos | `accept_partial=false`: una línea inválida (sintaxis o tipo distinto al de la columna) hace que el servidor rechace **el lote entero** (HTTP 400) y la carga se detiene | Sin ese parámetro, InfluxDB 3 escribe las líneas válidas y descarta las otras (verificado en el laboratorio): habría pérdidas parciales difíciles de rastrear |
| Puntos fuera de la retención | InfluxDB 3 los **descarta en silencio** (HTTP 204, V5) | La carga no puede detectarlo: lo detecta la validación (V1, puntos cargados contra el manifiesto) |
| Reintentos | 429, 5xx y errores de red: hasta 4, con espera exponencial (0,5 → 4 s) | Son seguros: reescribir un punto lo sobrescribe (V6) |
| Compresión | Opcional (`--gzip`, soportado por el servidor) | En la misma notebook no hay red que ahorrar |
| Validación | `validacion.py` compara puntos por partido contra el manifiesto | Prueba que lo cargado es lo declarado |

### Resultado frente al objetivo de 10 M+

La carga completa **es** el objetivo: **10.094.400 puntos confirmados en 55,24 s (182.726 puntos/s), 361 lotes, 0 reintentos, 0 errores** (detalle en [`pruebas_y_rendimiento.md`](./pruebas_y_rendimiento.md)). En vivo, el escenario genera ~20 puntos/s, porque nunca hay más de 2 partidos simultáneos. El laboratorio carga unas **9.000 veces** esa tasa (182.726 ÷ 20,5), así que el cuello de botella del módulo no es la ingesta.

## 5. Límites del laboratorio

- **Un solo nodo**, con cliente y servidor en la misma notebook compartiendo los 12 CPUs y 7,7 GB que tiene Docker.
- **InfluxDB 3 Core** es nodo único: no tiene réplicas ni clúster. Eso es de InfluxDB 3 Enterprise o de Cloud.
- **La tasa medida es de confirmación del servidor**: el 204 llega cuando el punto está en el WAL en disco. El pasaje a Parquet no ocurrió durante la prueba (§3).
- **Fechas en 2030**: las consultas "en vivo" usan un "ahora" simulado (minuto 90 del partido elegido), y en la base viva nada vence durante la prueba. Por eso existe la base de prueba de 1 hora.

## 6. Escalabilidad fuera del laboratorio

| Cambio | Efecto sobre el diseño |
|---|---|
| Más partidos (los 127 del TPO, con las eliminatorias completas) | Cardinalidad lineal: +10 series por partido. Sin riesgo |
| Estadísticas por jugador, 1 Hz | ≈ 40 series más por partido (4.480 en total): manejable, en una tabla aparte |
| Datos de tracking (posición de los 22 jugadores, 25 Hz) | 550 puntos por segundo por partido: ×275 el volumen del feed. Justificaría precisión de milisegundos, un nodo dedicado a la ingesta y retención de horas, no de días |
| Réplica y alta disponibilidad (Hito 3: AP, réplica conceptual) | InfluxDB 3 Core no replica: haría falta InfluxDB 3 Enterprise (varios nodos sobre el mismo almacenamiento de objetos) o un segundo nodo alimentado en paralelo (por ejemplo con Telegraf o una cola) |
| Varias fuentes escribiendo a la vez | Un intermediario (Telegraf o una cola) que acumule en lotes y reintente, en lugar de que cada fuente escriba directo. Cada POST cuesta ~1 s de espera del WAL: escribir punto por punto desde cada fuente sería ineficiente |
| Almacenamiento | `--object-store=file` guarda todo en el disco del nodo. En producción, InfluxDB 3 puede usar almacenamiento de objetos (S3 o equivalente) para los archivos Parquet |
| Observabilidad posterior (Hito 12) | `operacion_plataforma` es el antecedente. Además, InfluxDB 3 expone `/metrics` en formato Prometheus (con token) y la tabla `system.queries` con las consultas ejecutadas |
