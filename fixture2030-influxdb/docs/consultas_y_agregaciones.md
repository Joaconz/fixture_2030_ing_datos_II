# Consultas y agregaciones: resultados e interpretación — Hito 8 · InfluxDB 2

**Ingeniería de Datos II · Grupo 2** — Santiago Pazos, Valentina Frisoli, Joaquín Núñez

> Apartado "Consultas y agregaciones" del enunciado (§8): operaciones implementadas, resultados obtenidos, interpretación y límites. Todas las consultas están en Flux, en `scripts/consultas_temporales.py` y `scripts/agregaciones.py`. Los resultados y tiempos son de la corrida real del **28/09/2026** sobre InfluxDB v2.9.1 con el **perfil completo** cargado (10.094.400 puntos); la salida completa está en `docs/evidencia/consultas_PAR-D16-01_*.md` y `agregaciones_*.md`.

Partido analizado: **PAR-D16-01**, ARG (1° del grupo A) contra BEL (2° del grupo B), 29/06/2030 16:00 UTC, estadio Centenario (`URU-CEN`). Goles simulados de BEL a los 7' y a los 33'. "Ahora" simulado: minuto 90.

---

## 1. Consultas (`consultas_temporales.py`)

Cada consulta se ejecutó 10 veces: la 1ª se informa aparte (caché fría); p50 y p95 son de las 9 restantes.

| # | Qué hace (Flux) | Resultado | Interpretación | 1ª / p50 / p95 (ms) |
|---|---|---|---|---|
| **P1** | Puntos crudos de los últimos 2 min: `range()` de 2 min + `filter()` + `pivot()` | 10 filas: BEL 57,3 % de posesión, 508 pases, 7 tiros, 2 goles; ARG 42,7 %, 389 pases, 7 tiros, 0 goles | La lectura de la pantalla del partido: una fila por equipo y segundo | 12,1 / 5,6 / 9,4 |
| **P2** | Último valor de cada contador por equipo: `last()` + `pivot()` | BEL 2 – ARG 0 | El marcador sale de la serie misma, sin guardar un "estado actual" aparte | 5,1 / 4,4 / 4,6 |
| **P3** | Audiencia de AR y ES cada 5 min: `aggregateWindow()` con `max`, `mean` y `sum` | 58 filas (29 tramos × 2 regiones). AR pasa de ~295 mil usuarios (previa) a ~525 mil al inicio del partido; ES tiene cerca de la mitad | AR tiene triple cuota porque juega Argentina. Los comentarios de AR saltan de 1.530 a 3.486 en el tramo del primer gol | 194,8 / 190,0 / 212,5 |
| **P4** | Local contra visitante por cuarto de hora: `last()`, `spread()` y `sum()` por tramo | 8 tramos. Posesión de ARG al cierre de cada tramo entre 38,4 % y 48,0 % | El tramo de las 16:45 es casi todo entretiempo (3 y 13 pases). El de las 17:15 muestra el dominio de BEL: 106 pases contra 40 | 230,9 / 228,4 / 241,9 |
| **P5** | Goles del feed contra comentarios por minuto (dos measurements, `union()` + `pivot()`) | Minuto del gol: 1.372 → 2.057 → **6.278** → 5.752 comentarios, y vuelve a ~1.400 a los 5 minutos | La audiencia reacciona durante ~5 minutos después de cada gol: es la señal que el Hito 6 necesita para reforzar la moderación | 12,4 / 11,0 / 16,0 |
| **P6** | Puntos por minuto de cada fuente entre los minutos 44 y 65: `count()` con `createEmpty: true` | Audiencia: 480 por minuto siempre (8 regiones × 60 s). Feed: 120 hasta las 16:46 y **0** desde las 16:47 | El hueco del feed es el entretiempo, no una falla: la audiencia sigue llegando. Si el feed diera 0 con el partido en juego, sería una alerta | 11,9 / 12,7 / 18,3 |

**Por qué P3 y P4 tardan entre 15 y 40 veces más que el resto:** son las únicas que recorren **el partido completo** (145 minutos) y combinan varias agregaciones por ventana con `union()` y `pivot()`. P3 lee 2 regiones × 8.700 segundos × 2 fields; P4, 2 equipos × 5.700 segundos × 3 fields. P1, P2, P5 y P6 leen ventanas de 2 a 21 minutos. Todas quedan muy por debajo de los 100 ms del Hito 1 salvo P3 y P4, que no son consultas de la pantalla en vivo sino de análisis (patrones de frecuencia media).

## 2. Agregaciones (`agregaciones.py`): la función depende de la semántica

| # | Medida | Correcto | Incorrecto | Diferencia | Qué muestra |
|---|---|---|---|---|---|
| **A1** | Posesión (gauge acumulado) | `last()`: ARG **43,4 %**, BEL **56,6 %** | `mean()`: ARG 44,7 %, BEL 55,3 % | 1,3 puntos porcentuales | El promedio mezcla los valores inestables del arranque; la posesión del partido es el último valor |
| **A2** | Pases (contador acumulado) | `max()`: ARG **409**, BEL **519** | `sum()`: ARG 1.175.882, BEL 1.427.884 | ×2.875 | Sumar un acumulado cuenta cada pase miles de veces |
| **A3** | Recuperaciones (evento por segundo) | `sum()` por cuarto de hora: entre 5 y 12 por equipo en los tramos de juego, 2–3 en el del entretiempo | — | — | Acá sí corresponde sumar: cada 1 es un evento |
| **A4** | Usuarios conectados (gauge por región) | Suma por segundo y después `max()`: **2.564.757** | Suma de los picos de cada región: 2.638.593 | +73.836 (+2,9 %) | Cada región tiene su pico en otro momento (AR baja con los goles de BEL, el resto sube). El "pico" incorrecto nunca ocurrió |
| **A5** | Latencia p95 de `api` (percentil) | `max()` por tramo: **81,98 ms** (16:00–16:15) | `mean()`: 69,26 ms | −12,7 ms (−15 %) | Promediar percentiles esconde los peores minutos. Con el objetivo de 100 ms del Hito 1, la diferencia importa |

## 3. Consultas de torneo sobre el bucket histórico

| Consulta | Resultado | Interpretación |
|---|---|---|
| Top partidos por pico de audiencia | Encabeza PAR-D16-01 con 2.564.757 usuarios simultáneos | El partido de audiencia MÁXIMA del Hito 6 es también el de mayor pico acá |
| Top equipos por posesión media | Promedio de la posesión **final** de cada partido, con `reduce()` | Cada partido pesa lo mismo, que es lo que se quiere comparar |
| **V8** (en `validacion.py`): total de comentarios del torneo | Mismo total en el bucket vivo (7.795.200 puntos de audiencia) y en el histórico (112 puntos) | La base del argumento de la política de granularidad: la respuesta se conserva y el costo baja varios órdenes |

## 4. Límites

- Todas las consultas en vivo acotan **partido y tiempo** (RNF8): leen un shard y solo las series del partido.
- Los valores son de datos sintéticos: validan la semántica de cada agregación y el diseño, no son conclusiones deportivas.
- Los tiempos son de una notebook con cliente y servidor juntos; incluyen el viaje HTTP y la serialización a CSV de la respuesta.
