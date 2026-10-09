# Modelo multidimensional — Hito 8 · Series temporales (InfluxDB 3 Core)

**Ingeniería de Datos II · Grupo 2** — Santiago Pazos, Valentina Frisoli, Joaquín Núñez

## 0. Vocabulario (InfluxDB 3 Core)

Versión observada de `influxdb:3-core`: **InfluxDB 3 Core 3.12.0** (09/10/2026, ver `evidencia/01_inicializacion.txt`).

| Concepto | Qué es | En este módulo |
|---|---|---|
| **Base de datos** | Contenedor lógico de tablas. El **período de retención se fija al crearla** y en Core no se puede cambiar después | `fixture2030_vivo`, `fixture2030_historico`, `fixture2030_prueba_retencion` |
| **Tabla** | Un fenómeno observado (cumple el papel de la *measurement* de versiones anteriores). Se crea sola con la primera escritura (esquema al escribir) | `estadisticas_equipo`, `audiencia_partido`, `operacion_plataforma` (+ 5 de resumen) |
| **Tag** | Dimensión de texto que forma parte de la **clave de serie** de la tabla y se usa para filtrar | `partido_id`, `equipo_id`, `condicion`, `fase`, `sede_id`, `region`, `servicio` |
| **Field** | Valor observado, con tipo fijo por columna (`integer` / `float`) | posesión, contadores, usuarios, latencia… |
| **Timestamp** | Columna `time` de cada fila | Segundos UTC (precisión declarada: `precision=second`) |
| **Serie** | Tabla + combinación única de valores de tags | Ej.: `estadisticas_equipo` + `PAR-D16-01` + `ARG` |
| **Clave de serie** | Lista ordenada de los tags de la tabla (`system.tables.series_key_columns`). Dentro de cada archivo los datos se ordenan por esa clave y por tiempo | `partido_id, equipo_id, condicion, fase, sede_id` |
| **WAL y archivos Parquet** | Cada escritura se confirma al volcarse al WAL (cada 1 s). Después, el servidor pasa los datos a archivos Parquet (columnares, comprimidos) por tabla y por tramo de 10 minutos | Ver `cardinalidad_y_escalabilidad.md` §3 |

Una fila de InfluxDB 3 es un **punto completo**: la tabla guarda una columna por tag, una por field y la columna `time`. Las consultas se escriben en **SQL**; toda consulta acota el tiempo (`WHERE time >= … AND time < …`) y el partido (`WHERE partido_id = …`) (RNF8): así se descartan los datos de otros tramos de tiempo y de otras series.

---

## 1. Base `fixture2030_vivo` — detalle por segundo, retención 45 días

### 1.1 `estadisticas_equipo` — el juego (P1, P2, P4, P5, P6)

**Fenómeno:** estado estadístico de cada equipo en cada segundo de juego, según el proveedor de datos deportivos.
**Timestamp:** hora UTC del proveedor, truncada al segundo. No hay puntos durante el entretiempo (47'–62' de reloj).

| Columna | Rol | Tipo | Semántica | Agregación correcta |
|---|---|---|---|---|
| `partido_id` | tag | string | Partido del Hito 5 (`PAR-A-1` … `PAR-D16-16`) | filtro |
| `equipo_id` | tag | string | Código FIFA del catálogo del Hito 5 | filtro / agrupación |
| `condicion` | tag | string | `LOCAL` / `VISITANTE` | comparación (P4) |
| `fase` | tag | string | `GRUPOS` / `DIECISEISAVOS` (depende del partido) | filtro |
| `sede_id` | tag | string | Estadio del Hito 5 (depende del partido) | filtro |
| `posesion_pct` | field | float | **Gauge acumulado**: % de posesión desde el inicio (0–100) | `last_value(… ORDER BY time)` (al cierre); **no** `avg()` |
| `pases_acum` | field | integer | **Contador acumulado**, monótono | `max()` (total) o `max() − min()` (en el tramo); **no** `sum()` |
| `tiros_acum` | field | integer | Contador acumulado | ídem |
| `goles_acum` | field | integer | Contador acumulado (goles de la plantilla de eventos del Hito 5) | ídem |
| `recuperaciones` | field | integer | **Evento del segundo**: 1 si el equipo recuperó la pelota en ese segundo, 0 si no | `sum()` |
| `minuto_juego` | field | integer | Minuto del reloj de juego (0–47, 45–92) | contexto; no se agrega |
| `time` | timestamp | timestamp | Segundo de la observación | `date_bin()` para tramos |

**Serie** = `partido_id + equipo_id` (los demás tags dependen de esos dos). **2 series por partido**, cada fila con 6 fields.

```
estadisticas_equipo,partido_id=PAR-D16-01,equipo_id=BEL,condicion=VISITANTE,fase=DIECISEISAVOS,sede_id=URU-CEN posesion_pct=57.3,pases_acum=508i,tiros_acum=7i,goles_acum=2i,recuperaciones=0i,minuto_juego=90i 1908985649
```

### 1.2 `audiencia_partido` — la plataforma (P3, P5, P6)

**Fenómeno:** actividad de los usuarios de la plataforma que siguen un partido, por región.
**Timestamp:** hora UTC del servidor que agrega la métrica, al segundo. Continúa en el entretiempo.

| Columna | Rol | Tipo | Semántica | Agregación correcta |
|---|---|---|---|---|
| `partido_id` | tag | string | Partido | filtro |
| `region` | tag | string | `AR`, `UY`, `PY`, `ES`, `PT`, `MA` (anfitriones), `RESTO_AMERICAS`, `RESTO_MUNDO` | filtro / agrupación |
| `fase` | tag | string | Depende del partido | filtro |
| `usuarios_conectados` | field | integer | **Gauge**: usuarios en ese segundo | `max()` (pico), `avg()`; entre regiones: **sumar por segundo y después `max()`** |
| `comentarios` | field | integer | **Evento**: comentarios publicados en ese segundo (Hito 6) | `sum()` |
| `sesiones_nuevas` | field | integer | **Evento**: sesiones creadas en ese segundo (Hito 7) | `sum()` |

**Serie** = `partido_id + region`. **8 series por partido**, cada fila con 3 fields.

### 1.3 `operacion_plataforma` — los servicios (P8)

**Fenómeno:** salud de cada servicio de la plataforma. **Timestamp:** fin del intervalo de 10 s.

| Columna | Rol | Tipo | Semántica | Agregación correcta |
|---|---|---|---|---|
| `servicio` | tag | string | `sesiones`, `cache` (Hito 7), `comentarios` (Hito 6), `estadisticas` (este módulo), `api` | filtro |
| `latencia_p95_ms` | field | float | **Percentil ya calculado** por el servicio en el intervalo | `max()` en el tramo; **nunca `avg()`** (promediar percentiles no da un percentil) |
| `solicitudes` | field | integer | Evento: solicitudes del intervalo | `sum()` (÷ segundos = req/s) |
| `errores` | field | integer | Evento: errores del intervalo | `sum()` |

**Serie** = `servicio`. **5 series** en todo el torneo.

### 1.4 Alternativas de modelado descartadas

| Alternativa | Qué pasaría | Decisión |
|---|---|---|
| **Una sola tabla** para las tres fuentes | 20 columnas (7 tags + 12 fields + `time`), de las cuales cada fila usa entre 5 y 12. Sobre los 10.094.400 puntos, **el 63 % de las celdas quedaría vacío** (126,9 de 201,9 millones), y la clave de serie mezclaría dimensiones que nunca se consultan juntas (equipo, región, servicio) | Descartada: tres tablas |
| **Una tabla por medida** (`posesion`, `pases`, …) con un solo field `valor` | Cada segundo de un equipo serían 6 filas en lugar de 1: 6 veces más timestamps y tags repetidos, y P1/P2 necesitarían 6 consultas o un cruce | Descartada: las medidas que llegan juntas van en la misma fila |
| **Posesión por segundo** (0/1: quién tiene la pelota) en lugar del % acumulado | Más fiel al dato crudo, pero cada consulta de "posesión del partido" tendría que sumar miles de segundos | Descartada: el proveedor ya entrega el acumulado; se guarda el cambio de posesión como `recuperaciones` |
| **Precisión en milisegundos o nanosegundos** | El feed y la audiencia llegan a 1 Hz: no hay dos puntos de la misma serie en el mismo segundo que distinguir | Descartada: segundos (`precision=second`). Cambiaría con datos de tracking a 25 Hz (`cardinalidad_y_escalabilidad.md` §6) |
| **Una sola base** con retención infinita | Los 10 M de puntos por segundo se conservarían para siempre, aunque después del torneo nadie consulta ese detalle | Descartada: en InfluxDB 3 Core la retención es **por base** y se fija al crearla; por eso hay una viva (45 d) y una histórica (sin vencimiento) |
| **`fase` y `sede_id` fuera de los tags** (se obtienen del Hito 5) | Filtrar el torneo por fase o estadio obligaría a cruzar con Neo4j | Descartada: como dependen del partido no agregan series (`cardinalidad_y_escalabilidad.md` §1) |

### 1.5 Por qué tres tablas y no una

Las tres fuentes tienen **dimensiones distintas** (equipo / región / servicio), **frecuencias distintas** (1 s de juego / 1 s continuo / 10 s) y **huecos distintos** (el feed se corta en el entretiempo, la audiencia no). En una sola tabla, cada fila tendría la mayoría de las columnas vacías y la clave de serie mezclaría dimensiones que nunca se consultan juntas. El cruce, cuando hace falta (P5, P6), se hace en la consulta con un `JOIN` por minuto.

---

## 2. Base `fixture2030_historico` — resúmenes, sin vencimiento

Las escribe `agregaciones.py` a partir de la base viva: una consulta SQL calcula cada resumen y el resultado se vuelve a escribir como line protocol (ver [`retencion_y_granularidad.md`](./retencion_y_granularidad.md) §4).

| Tabla | Granularidad | Tags | Fields (tipo y cómo se calculan) | Timestamp |
|---|---|---|---|---|
| `estadisticas_equipo_1m` | 1 minuto por equipo | partido, equipo, condicion, fase | `posesion_pct` (float, `last_value()`), `pases_acum` / `tiros_acum` / `goles_acum` (integer, `max()`), `recuperaciones` (integer, `sum()`), `puntos` (integer, `count()`) | inicio del minuto |
| `audiencia_partido_1m` | 1 minuto por región | partido, region, fase | `usuarios_max` (integer, `max()`), `usuarios_prom` (float, `avg()`), `comentarios` / `sesiones_nuevas` (integer, `sum()`) | inicio del minuto |
| `operacion_plataforma_5m` | 5 minutos por servicio | servicio | `latencia_p95_max` (float, `max()`), `solicitudes` / `errores` (integer, `sum()`) | inicio del tramo |
| `resumen_partido_equipo` | 1 punto por partido y equipo | partido, equipo, condicion, fase, sede | `posesion_final` (float), `pases`, `tiros`, `goles`, `recuperaciones` (integer) | inicio del partido |
| `resumen_partido_audiencia` | 1 punto por partido | partido, fase, sede | `pico_usuarios` (integer: suma por segundo y después `max()`), `comentarios`, `sesiones_nuevas` (integer) | inicio del partido |

El `puntos` de `estadisticas_equipo_1m` guarda cuántos segundos tuvo el minuto: permite distinguir después un minuto completo (60) de uno cortado por el entretiempo, sin volver al dato crudo.

---

## 3. Base `fixture2030_prueba_retencion` — retención 1 hora

Solo para **demostrar** la retención (V5 en `validacion.py`): el torneo está fechado en 2030, así que en la base viva ningún punto vence durante el laboratorio. En la prueba real, InfluxDB 3 **aceptó la escritura del punto de hace 2 horas (HTTP 204) pero no lo conservó**: el punto no aparece en ninguna consulta. La retención no avisa con un error; por eso la validación cuenta lo cargado contra el manifiesto (V1).

---

## 4. Relación de cada elemento con los patrones (RNF4)

| Elemento | Patrones | Por qué existe |
|---|---|---|
| tag `partido_id` | P1–P7 | Todas las consultas en vivo son de un partido |
| tag `equipo_id` | P2, P4, P7 | Estado y comparación por equipo |
| tag `condicion` | P4 | Comparar local contra visitante sin conocer los códigos |
| tags `fase`, `sede_id` | P7 | Filtrar el torneo por fase o estadio sin cruzar con otro módulo |
| tag `region` | P3 | Audiencia por país anfitrión |
| tag `servicio` | P8 | Salud por servicio |
| fields de `estadisticas_equipo` | P1, P2, P4, P5 | Las tres naturalezas del RF5: gauge acumulado, contador acumulado y evento |
| fields de `audiencia_partido` | P3, P5, P6 | Gauge (usuarios) y eventos (comentarios, sesiones) |
| fields de `operacion_plataforma` | P8 | Percentil precalculado y eventos |
| base histórica y sus 5 tablas | P7 | Consultas de torneo sin leer el dato por segundo |
| retención 45 días en la base viva | P1–P6 | El detalle por segundo solo se consulta durante el torneo y la revisión posterior |

---

## 5. Coherencia con el resto del TPO

| Hito | Vínculo |
|---|---|
| **Hito 2** | N7 → series temporales; la consulta por período es la operación principal |
| **Hito 3** | N7 es **AP, eventual**: una estadística puede corregirse después (se sobrescribe el punto). **Orden monótono por partido**: cada archivo de carga es cronológico dentro de su partido. **Partición por partido + intervalo**: tag `partido_id` (primera columna de la clave de serie) + archivos Parquet por tramo de tiempo |
| **Hito 5** | `partido_id`, `equipo_id`, `sede_id`, fechas y goles de la fase de grupos calculados con las mismas fórmulas de `carga.cypher`. Ejemplo: `PAR-D16-01` es ARG (1° del grupo A) contra BEL (2° del grupo B), igual que en el grafo. Los dieciseisavos, que el grafo deja PROGRAMADOS, se simulan como jugados (igual que el Hito 6) |
| **Hito 6** | `comentarios` de `audiencia_partido` es la tasa de escritura que recibe Cassandra; `PAR-D16-01` es el partido de audiencia MÁXIMA en ambos módulos |
| **Hito 7** | `sesiones_nuevas` es la tasa de creación de sesiones en Redis; `sesiones` y `cache` son servicios de `operacion_plataforma` |
| **Hito 4** | `equipo_id` usa el catálogo del Hito 5. La correspondencia de equipos entre MongoDB y Neo4j es una corrección pendiente del Hito 5 que se resuelve aparte: cuando se resuelva, estos códigos quedan alineados con los dos |
