# Consultas y agregaciones: resultados e interpretación — Hito 8 · InfluxDB 3 Core

**Ingeniería de Datos II · Grupo 2** — Santiago Pazos, Valentina Frisoli, Joaquín Núñez

> Apartado "Consultas y agregaciones" del enunciado (§8): operaciones implementadas, resultados obtenidos, interpretación y límites. Todas las consultas están en **SQL**, en `scripts/consultas_temporales.py` y `scripts/agregaciones.py` (`POST /api/v3/query_sql`). Los resultados y tiempos son de la corrida real del **09/10/2026** sobre InfluxDB 3 Core 3.12.0 con el **perfil completo** cargado (10.094.400 puntos). La salida completa, con el SQL de cada consulta, está en `docs/evidencia/consultas_PAR-D16-01_*.md` y `agregaciones_*.md`.

Partido analizado: **PAR-D16-01**, ARG (1° del grupo A) contra BEL (2° del grupo B), 29/06/2030 16:00 UTC, estadio Centenario (`URU-CEN`). Goles simulados de BEL a los 7' y a los 33'. "Ahora" simulado: minuto 90.

---

## 1. Consultas (`consultas_temporales.py`)

Cada consulta se ejecutó 10 veces: la 1ª se informa aparte (caché fría); p50 y p95 son de las 9 restantes.

| # | Qué hace (SQL) | Resultado | Interpretación | 1ª / p50 / p95 (ms) |
|---|---|---|---|---|
| **P1** | Puntos crudos de los últimos 2 min: `WHERE partido_id = … AND time >= … AND time < …` + `ORDER BY time DESC LIMIT 10` | 10 filas: BEL 57,3 % de posesión, 508 pases, 7 tiros, 2 goles; ARG 42,7 %, 389 pases, 7 tiros, 0 goles | La lectura de la pantalla del partido: una fila por equipo y segundo, con todos los fields del punto | 9,6 / 8,2 / 9,7 |
| **P2** | Último valor de cada contador por equipo: `last_value(… ORDER BY time)` + `GROUP BY equipo_id`, y `max(time)` | BEL 2 – ARG 0; último punto 17:47:29 | El marcador sale de la serie misma, sin guardar un "estado actual" aparte. `max(time)` dice cuán fresco es el dato | 21,8 / 20,3 / 21,8 |
| **P3** | Audiencia de AR y ES cada 5 min: `date_bin(INTERVAL '5 minutes', time)` con `max`, `avg` y `sum` | 58 filas (29 tramos × 2 regiones). AR pasa de ~295 mil usuarios (previa) a ~523 mil al inicio del partido; ES tiene cerca de la mitad | AR tiene triple cuota porque juega Argentina. Los comentarios de AR saltan de 1.530 a 3.486 en el tramo del primer gol | 22,5 / 22,1 / 23,1 |
| **P4** | Local contra visitante por cuarto de hora: `last_value()`, `max() − min()` y `sum()` con `FILTER (WHERE condicion = …)` | 8 tramos. Posesión de ARG al cierre de cada tramo entre 38,4 % y 48,0 % | El tramo de las 16:45 es casi todo entretiempo (3 y 13 pases). El de las 17:15 muestra el dominio de BEL: 106 pases contra 40 | 16,3 / 16,2 / 18,2 |
| **P5** | Goles del feed contra comentarios por minuto: dos tablas unidas con `FULL OUTER JOIN` sobre `date_bin()` | Minuto del gol: 1.372 → 2.057 → **6.278** → 5.752 comentarios, y vuelve a ~1.400 a los 5 minutos | La audiencia reacciona durante ~5 minutos después de cada gol: es la señal que el Hito 6 necesita para reforzar la moderación | 18,5 / 14,6 / 15,3 |
| **P6** | Puntos por minuto de cada fuente entre los minutos 44 y 65: `date_bin_gapfill()` + `count()` | Audiencia: 480 por minuto siempre (8 regiones × 60 s). Feed: 120 hasta las 16:46 y **0** desde las 16:47 | El hueco del feed es el entretiempo, no una falla: la audiencia sigue llegando. Si el feed diera 0 con el partido en juego, sería una alerta | 15,1 / 14,6 / 17,1 |

**Lectura de los tiempos:** las seis quedan entre 8 y 22 ms, muy por debajo de los 100 ms del Hito 1, porque todas acotan partido y tiempo. P1 es la más rápida (lee 2 minutos y corta en 10 filas). P2 y P3 son las más lentas: recorren el partido completo (hasta 145 minutos) para calcular el último valor o las ventanas. Los datos estaban todavía en el buffer en memoria del servidor (no se había hecho el snapshot a Parquet, ver `cardinalidad_y_escalabilidad.md` §3). Con los datos en Parquet, la 1ª ejecución debería tardar más.

## 2. Agregaciones (`agregaciones.py`): la función depende de la semántica

| # | Medida | Correcto | Incorrecto | Diferencia | Qué muestra |
|---|---|---|---|---|---|
| **A1** | Posesión (gauge acumulado) | `last_value()`: ARG **43,4 %**, BEL **56,6 %** | `avg()`: ARG 44,7 %, BEL 55,3 % | 1,3 puntos porcentuales | El promedio mezcla los valores inestables del arranque; la posesión del partido es el último valor |
| **A2** | Pases (contador acumulado) | `max()`: ARG **409**, BEL **519** | `sum()`: ARG 1.175.882, BEL 1.427.884 | ×2.875 | Sumar un acumulado cuenta cada pase miles de veces |
| **A3** | Recuperaciones (evento por segundo) | `sum()` por cuarto de hora: entre 5 y 12 por equipo en los tramos de juego, 2–3 en el del entretiempo | — | — | Acá sí corresponde sumar: cada 1 es un evento |
| **A4** | Usuarios conectados (gauge por región) | Suma por segundo y después `max()`: **2.564.757** | Suma de los picos de cada región: 2.638.593 | +73.836 (+2,9 %) | Cada región tiene su pico en otro momento (AR baja con los goles de BEL, el resto sube). El "pico" incorrecto nunca ocurrió |
| **A5** | Latencia p95 de `api` (percentil) | `max()` por tramo: **81,98 ms** (16:00–16:15) | `avg()`: 69,26 ms | −12,7 ms (−15 %) | Promediar percentiles esconde los peores minutos. Con el objetivo de 100 ms del Hito 1, la diferencia importa |

Los valores son **idénticos** a los de la versión anterior del módulo (Flux sobre InfluxDB 2), con los mismos datos generados: la migración cambió el lenguaje de consulta, no la semántica de las agregaciones.

## 3. Consultas de torneo sobre la base histórica

| Consulta | Resultado | Interpretación |
|---|---|---|
| Top partidos por pico de audiencia | Encabeza PAR-D16-01 con 2.564.757 usuarios simultáneos; lo siguen cuatro dieciseisavos con 1,9–2,0 M | El partido de audiencia MÁXIMA del Hito 6 es también el de mayor pico acá |
| Top equipos por posesión media | `avg(posesion_final)` por equipo: JAM 54,53 %, CAN 54,30 %, ECU 53,68 % | Promedio de la posesión **final** de cada partido: cada partido pesa lo mismo, que es lo que se quiere comparar |
| **V8** (en `validacion.py`): total de comentarios del torneo | **9.847.799** en las dos bases: 4.309 ms en la viva (7.795.200 puntos de audiencia) y 41 ms en la histórica (112 puntos) | La base del argumento de la política de granularidad: la respuesta se conserva y el costo baja unas 100 veces |

## 4. Límites

- Todas las consultas en vivo acotan **partido y tiempo** (RNF8).
- Los valores son de datos sintéticos: validan la semántica de cada agregación y el diseño, no son conclusiones deportivas.
- Los tiempos son de una notebook con cliente y servidor juntos; incluyen el viaje HTTP y la serialización a JSON de la respuesta.
- En las respuestas JSON de InfluxDB 3, una columna con valor `NULL` **no aparece** en la fila (por ejemplo, los goles de P5 antes del inicio del partido). Los scripts la leen como vacía.
