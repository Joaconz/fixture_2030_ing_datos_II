# Modelo multidimensional — Hito 8 · Series temporales (InfluxDB 2)

**Ingeniería de Datos II · Grupo 2** — Santiago Pazos, Valentina Frisoli, Joaquín Núñez

## 0. Vocabulario (InfluxDB 2)

Versión observada de `influxdb:latest`: **InfluxDB v2.9.1** (28/09/2026, ver `evidencia/01_inicializacion.txt`).

| Concepto | Qué es | En este módulo |
|---|---|---|
| **Organización** | Espacio de trabajo que agrupa buckets, tokens y tasks | `fixture2030` |
| **Bucket** | Contenedor con su propia política de retención | `fixture2030_vivo`, `fixture2030_historico`, `fixture2030_prueba_retencion` |
| **Measurement** | Un fenómeno observado (equivale a una "tabla") | `estadisticas_equipo`, `audiencia_partido`, `operacion_plataforma` (+ 5 de resumen) |
| **Tag** | Dimensión: texto, **indexado** (índice TSI), parte de la identidad de la serie | `partido_id`, `equipo_id`, `condicion`, `fase`, `sede_id`, `region`, `servicio` |
| **Field** | Valor observado: número, **no indexado**, con tipo fijo (long / double) | posesión, contadores, usuarios, latencia… |
| **Timestamp** | Instante de la observación (columna `_time`) | Segundos UTC (precisión declarada: `s`) |
| **Serie** | Measurement + combinación única de valores de tags | Ej.: `estadisticas_equipo` + `PAR-D16-01` + `ARG` |
| **Shard** | Bloque de tiempo de un bucket en disco (motor TSM) | 1 día en el bucket vivo, 7 días en el histórico, 1 hora en el de prueba |

En disco, cada field de una serie se guarda por separado (clave "serie + field" en los archivos TSM), comprimido según su tipo. Las consultas se escriben en **Flux**; toda consulta acota el tiempo con `range()` y el partido con `filter()` (RNF8): así lee 1 shard y solo las series del partido.

---

## 1. Bucket `fixture2030_vivo` — detalle por segundo, retención 45 días (shards de 1 día)

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
| `posesion_pct` | field | double | **Gauge acumulado**: % de posesión desde el inicio (0–100) | `last()` (al cierre); **no** `mean()` |
| `pases_acum` | field | long | **Contador acumulado**, monótono | `max()` (total) o `spread()` = máx − mín (en el tramo); **no** `sum()` |
| `tiros_acum` | field | long | Contador acumulado | ídem |
| `goles_acum` | field | long | Contador acumulado (goles de la plantilla de eventos del Hito 5) | ídem |
| `recuperaciones` | field | long | **Evento del segundo**: 1 si el equipo recuperó la pelota en ese segundo, 0 si no | `sum()` |
| `minuto_juego` | field | long | Minuto del reloj de juego (0–47, 45–92) | contexto; no se agrega |
| `_time` | timestamp | dateTime | Segundo de la observación | `aggregateWindow()` para tramos |

**Serie** = `partido_id + equipo_id` (los demás tags dependen de esos dos). **2 series por partido**, cada una con 6 fields.

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
| `usuarios_conectados` | field | long | **Gauge**: usuarios en ese segundo | `max()` (pico), `mean()`; entre regiones: **sumar por segundo y después `max()`** |
| `comentarios` | field | long | **Evento**: comentarios publicados en ese segundo (Hito 6) | `sum()` |
| `sesiones_nuevas` | field | long | **Evento**: sesiones creadas en ese segundo (Hito 7) | `sum()` |

**Serie** = `partido_id + region`. **8 series por partido**, cada una con 3 fields.

### 1.3 `operacion_plataforma` — los servicios (P8)

**Fenómeno:** salud de cada servicio de la plataforma. **Timestamp:** fin del intervalo de 10 s.

| Columna | Rol | Tipo | Semántica | Agregación correcta |
|---|---|---|---|---|
| `servicio` | tag | string | `sesiones`, `cache` (Hito 7), `comentarios` (Hito 6), `estadisticas` (este módulo), `api` | filtro |
| `latencia_p95_ms` | field | double | **Percentil ya calculado** por el servicio en el intervalo | `max()` en el tramo; **nunca `mean()`** (promediar percentiles no da un percentil) |
| `solicitudes` | field | long | Evento: solicitudes del intervalo | `sum()` (÷ segundos = req/s) |
| `errores` | field | long | Evento: errores del intervalo | `sum()` |

**Serie** = `servicio`. **5 series** en todo el torneo.

### 1.4 Alternativas de modelado descartadas

| Alternativa | Qué pasaría | Decisión |
|---|---|---|
| **Una sola tabla** para las tres fuentes | 20 columnas (7 tags + 12 fields + `_time`), de las cuales cada fila usa entre 5 y 12. Sobre los 10.094.400 puntos, **el 63 % de las celdas quedaría vacío** (126,9 de 201,9 millones), y la identidad de la serie mezclaría dimensiones que nunca se consultan juntas (equipo, región, servicio) | Descartada: tres tablas |
| **Una tabla por medida** (`posesion`, `pases`, …) con un solo field `valor` | Cada segundo de un equipo serían 6 puntos en lugar de 1: 6 veces más timestamps y tags repetidos, y P1/P2 necesitarían 6 consultas o un cruce | Descartada: las medidas que llegan juntas van en la misma fila |
| **Posesión por segundo** (0/1: quién tiene la pelota) en lugar del % acumulado | Más fiel al dato crudo, pero cada consulta de "posesión del partido" tendría que sumar miles de segundos | Descartada: el proveedor ya entrega el acumulado; se guarda el cambio de posesión como `recuperaciones` |
| **Precisión en milisegundos o nanosegundos** | El feed y la audiencia llegan a 1 Hz: no hay dos puntos de la misma serie en el mismo segundo que distinguir | Descartada: segundos (`precision=s`). Cambiaría con datos de tracking a 25 Hz (`cardinalidad_y_escalabilidad.md` §6) |
| **Un solo bucket** con retención infinita | Los 10 M de puntos por segundo se conservarían para siempre, aunque después del torneo nadie consulta ese detalle | Descartada: la retención es por bucket en InfluxDB 2, por eso hay uno vivo (45 d) y uno histórico |
| **`fase` y `sede_id` fuera de los tags** (se obtienen del Hito 5) | Filtrar el torneo por fase o estadio obligaría a cruzar con Neo4j | Descartada: como dependen del partido no agregan series (`cardinalidad_y_escalabilidad.md` §1) |

### 1.5 Por qué tres tablas y no una

Las tres fuentes tienen **dimensiones distintas** (equipo / región / servicio), **frecuencias distintas** (1 s de juego / 1 s continuo / 10 s) y **huecos distintos** (el feed se corta en el entretiempo, la audiencia no). En una sola tabla, cada fila tendría la mayoría de las columnas vacías y la identidad de la serie mezclaría dimensiones que nunca se consultan juntas. El cruce, cuando hace falta (P5, P6), se hace en la consulta.

---

## 2. Bucket `fixture2030_historico` — resúmenes, sin vencimiento (shards de 7 días)

Las escribe `agregaciones.py` a partir del bucket vivo, con `to()` de Flux (ver [`retencion_y_granularidad.md`](./retencion_y_granularidad.md)).

| Tabla | Granularidad | Tags | Fields (tipo y cómo se calculan) | Timestamp |
|---|---|---|---|---|
| `estadisticas_equipo_1m` | 1 minuto por equipo | partido, equipo, condicion, fase | `posesion_pct` (double, `last()`), `pases_acum` / `tiros_acum` / `goles_acum` (long, `max()`), `recuperaciones` (long, `sum()`), `puntos` (long, `count()`) | inicio del minuto |
| `audiencia_partido_1m` | 1 minuto por región | partido, region, fase | `usuarios_max` (long, `max()`), `usuarios_prom` (double, `mean()`), `comentarios` / `sesiones_nuevas` (long, `sum()`) | inicio del minuto |
| `operacion_plataforma_5m` | 5 minutos por servicio | servicio | `latencia_p95_max` (double, `max()`), `solicitudes` / `errores` (long, `sum()`) | inicio del tramo |
| `resumen_partido_equipo` | 1 punto por partido y equipo | partido, equipo, condicion, fase, sede | `posesion_final` (double), `pases`, `tiros`, `goles`, `recuperaciones` (long) | inicio del partido |
| `resumen_partido_audiencia` | 1 punto por partido | partido, fase, sede | `pico_usuarios` (long: suma por segundo y después `max()`), `comentarios`, `sesiones_nuevas` (long) | inicio del partido |

El `puntos` de `estadisticas_equipo_1m` guarda cuántos segundos tuvo el minuto: permite distinguir después un minuto completo (60) de uno cortado por el entretiempo, sin volver al dato crudo.

---

## 3. Bucket `fixture2030_prueba_retencion` — retención 1 hora

Solo para **demostrar** la retención (V5 en `validacion.py`): el torneo está fechado en 2030, así que en el bucket vivo ningún punto vence durante el laboratorio. En la prueba real, InfluxDB **rechazó al escribir** el punto de hace 2 horas (HTTP 422, *"dropped 1 points outside retention policy of duration 1h0m0s"*).

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
| bucket histórico y sus 5 measurements | P7 | Consultas de torneo sin leer el dato por segundo |
| retención 45 días en el bucket vivo | P1–P6 | El detalle por segundo solo se consulta durante el torneo y la revisión posterior |

---

## 5. Coherencia con el resto del TPO

| Hito | Vínculo |
|---|---|
| **Hito 2** | N7 → series temporales; la consulta por período es la operación principal |
| **Hito 3** | N7 es **AP, eventual**: una estadística puede corregirse después (se sobrescribe el punto). **Orden monótono por partido**: cada archivo de carga es cronológico dentro de su partido. **Partición por partido + intervalo**: tag `partido_id` (índice) + shards de 1 día de InfluxDB |
| **Hito 5** | `partido_id`, `equipo_id`, `sede_id`, fechas y goles de la fase de grupos calculados con las mismas fórmulas de `carga.cypher`. Ejemplo: `PAR-D16-01` es ARG (1° del grupo A) contra BEL (2° del grupo B), igual que en el grafo. Los dieciseisavos, que el grafo deja PROGRAMADOS, se simulan como jugados (igual que el Hito 6) |
| **Hito 6** | `comentarios` de `audiencia_partido` es la tasa de escritura que recibe Cassandra; `PAR-D16-01` es el partido de audiencia MÁXIMA en ambos módulos |
| **Hito 7** | `sesiones_nuevas` es la tasa de creación de sesiones en Redis; `sesiones` y `cache` son servicios de `operacion_plataforma` |
| **Hito 4** | `equipo_id` usa el catálogo del Hito 5. La correspondencia de equipos entre MongoDB y Neo4j es una corrección pendiente del Hito 5 que se resuelve aparte: cuando se resuelva, estos códigos quedan alineados con los dos |
