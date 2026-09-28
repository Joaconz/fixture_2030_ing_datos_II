# Agregaciones y resúmenes — perfil muestra

- Fecha de ejecución (UTC): 2026-09-28T19:11:50+00:00
- Servidor: InfluxDB v2.9.1 (commit d4fa1941fd)
- Ambiente del cliente: {'cpus_visibles': 8, 'memoria_gb_visible': 3.8, 'python': '3.12.14', 'plataforma': 'Linux-7.0.12-linuxkit-aarch64-with-glibc2.41'}

## 1. Agregaciones según la semántica de cada medida

Partido analizado: PAR-D16-01 (ARG vs BEL).

### A1 · Posesión: último valor contra promedio (medida: porcentaje ACUMULADO)

posesion_pct ya es el acumulado desde el inicio. El valor correcto al cierre es last(); mean() mezcla los valores volátiles de los primeros minutos y da otro número.

```flux
datos = from(bucket: "fixture2030_vivo")
  |> range(start: 2030-06-29T15:45:00Z, stop: 2030-06-29T18:10:00Z)
  |> filter(fn: (r) => r._measurement == "estadisticas_equipo" and r.partido_id == "PAR-D16-01")
  |> filter(fn: (r) => r._field == "posesion_pct")
correcto = datos |> last() |> set(key: "_field", value: "posesion_final_correcta")
incorrecto = datos |> mean() |> set(key: "_field", value: "promedio_de_acumulados_incorrecto")
union(tables: [correcto, incorrecto])
  |> keep(columns: ["equipo_id", "_field", "_value"])
  |> group(columns: ["equipo_id"])
  |> pivot(rowKey: ["equipo_id"], columnKey: ["_field"], valueColumn: "_value")
  |> group()
  |> sort(columns: ["equipo_id"])
```

Tiempo de respuesta observado: 21.1 ms

| equipo_id | posesion_final_correcta | promedio_de_acumulados_incorrecto |
|---|---|---|
| ARG | 43.4 | 44.71510526315791 |
| BEL | 56.6 | 55.28489473684211 |

### A2 · Pases: contador acumulado -> total y ritmo

Un contador acumulado se resume con max() (total) o spread() (lo ocurrido en el tramo). sum() contaría miles de veces los mismos pases.

```flux
datos = from(bucket: "fixture2030_vivo")
  |> range(start: 2030-06-29T15:45:00Z, stop: 2030-06-29T18:10:00Z)
  |> filter(fn: (r) => r._measurement == "estadisticas_equipo" and r.partido_id == "PAR-D16-01")
  |> filter(fn: (r) => r._field == "pases_acum")
correcto = datos |> max() |> toFloat() |> set(key: "_field", value: "pases_totales_correcto")
incorrecto = datos |> sum() |> toFloat() |> set(key: "_field", value: "suma_del_acumulado_incorrecta")
ritmo = datos |> spread() |> toFloat() |> map(fn: (r) => ({r with _value: r._value / 95.0}))
  |> set(key: "_field", value: "pases_por_minuto_jugado")
union(tables: [correcto, incorrecto, ritmo])
  |> keep(columns: ["equipo_id", "_field", "_value"])
  |> group(columns: ["equipo_id"])
  |> pivot(rowKey: ["equipo_id"], columnKey: ["_field"], valueColumn: "_value")
  |> group()
  |> sort(columns: ["equipo_id"])
```

Tiempo de respuesta observado: 16.6 ms

| equipo_id | pases_por_minuto_jugado | pases_totales_correcto | suma_del_acumulado_incorrecta |
|---|---|---|---|
| ARG | 4.3052631578947365 | 409 | 1175882 |
| BEL | 5.463157894736842 | 519 | 1427884 |

### A3 · Recuperaciones: evento por segundo -> suma por tramo

recuperaciones vale 1 en el segundo en que ocurre y 0 en el resto: acá SÍ corresponde sumar.

```flux
from(bucket: "fixture2030_vivo")
  |> range(start: 2030-06-29T15:45:00Z, stop: 2030-06-29T18:10:00Z)
  |> filter(fn: (r) => r._measurement == "estadisticas_equipo" and r.partido_id == "PAR-D16-01")
  |> filter(fn: (r) => r._field == "recuperaciones")
  |> aggregateWindow(every: 15m, fn: sum, timeSrc: "_start", createEmpty: false)
  |> group()
  |> keep(columns: ["_time", "equipo_id", "_value"])
  |> rename(columns: {_value: "recuperaciones"})
  |> sort(columns: ["_time", "equipo_id"])
```

Tiempo de respuesta observado: 7.0 ms

| _time | recuperaciones | equipo_id |
|---|---|---|
| 2030-06-29T16:00:00Z | 10 | ARG |
| 2030-06-29T16:00:00Z | 11 | BEL |
| 2030-06-29T16:15:00Z | 12 | ARG |
| 2030-06-29T16:15:00Z | 11 | BEL |
| 2030-06-29T16:30:00Z | 5 | ARG |
| 2030-06-29T16:30:00Z | 6 | BEL |
| 2030-06-29T16:45:00Z | 3 | ARG |
| 2030-06-29T16:45:00Z | 2 | BEL |
| 2030-06-29T17:00:00Z | 8 | ARG |
| 2030-06-29T17:00:00Z | 7 | BEL |
| 2030-06-29T17:15:00Z | 8 | ARG |
| 2030-06-29T17:15:00Z | 8 | BEL |
| 2030-06-29T17:30:00Z | 8 | ARG |
| 2030-06-29T17:30:00Z | 9 | BEL |
| 2030-06-29T17:45:00Z | 7 | ARG |
| 2030-06-29T17:45:00Z | 7 | BEL |

### A4 · Pico de audiencia: sumar regiones por segundo y DESPUÉS tomar el máximo

El pico real es el máximo del total simultáneo. Sumar los máximos de cada región da un número más alto que nunca existió, porque cada región tiene su pico en un segundo distinto.

```flux
datos = from(bucket: "fixture2030_vivo")
  |> range(start: 2030-06-29T15:45:00Z, stop: 2030-06-29T18:10:00Z)
  |> filter(fn: (r) => r._measurement == "audiencia_partido" and r.partido_id == "PAR-D16-01")
  |> filter(fn: (r) => r._field == "usuarios_conectados")
correcto = datos
  |> group(columns: ["_time"]) |> sum() |> group() |> max()
  |> map(fn: (r) => ({partido: "PAR-D16-01", _field: "pico_simultaneo_correcto", _value: r._value}))
incorrecto = datos
  |> max() |> group() |> sum()
  |> map(fn: (r) => ({partido: "PAR-D16-01", _field: "suma_de_picos_incorrecta", _value: r._value}))
union(tables: [correcto, incorrecto])
  |> group()
  |> pivot(rowKey: ["partido"], columnKey: ["_field"], valueColumn: "_value")
```

Tiempo de respuesta observado: 2298.4 ms

| partido | suma_de_picos_incorrecta | pico_simultaneo_correcto |
|---|---|---|
| PAR-D16-01 | 2638593 | 2564757 |

### A5 · Latencia p95: no se promedian percentiles

latencia_p95_ms ya es un percentil calculado por el servicio. Para el tramo se informa el peor valor (max); el promedio escondería los minutos malos. solicitudes es un evento: se suma.

```flux
datos = from(bucket: "fixture2030_vivo")
  |> range(start: 2030-06-29T15:45:00Z, stop: 2030-06-29T18:10:00Z)
  |> filter(fn: (r) => r._measurement == "operacion_plataforma" and (r.servicio == "api" or r.servicio == "sesiones"))
peor = datos |> filter(fn: (r) => r._field == "latencia_p95_ms")
  |> aggregateWindow(every: 15m, fn: max, timeSrc: "_start", createEmpty: false)
  |> set(key: "_field", value: "p95_peor")
prom = datos |> filter(fn: (r) => r._field == "latencia_p95_ms")
  |> aggregateWindow(every: 15m, fn: mean, timeSrc: "_start", createEmpty: false)
  |> set(key: "_field", value: "p95_promedio_enganoso")
rps = datos |> filter(fn: (r) => r._field == "solicitudes")
  |> aggregateWindow(every: 15m, fn: sum, timeSrc: "_start", createEmpty: false)
  |> toFloat() |> map(fn: (r) => ({r with _value: r._value / 900.0}))
  |> set(key: "_field", value: "solicitudes_por_segundo")
union(tables: [peor, prom, rps])
  |> keep(columns: ["_time", "servicio", "_field", "_value"])
  |> group(columns: ["servicio"])
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> group()
  |> sort(columns: ["_time", "servicio"])
```

Tiempo de respuesta observado: 36.2 ms

| _time | servicio | p95_peor | p95_promedio_enganoso | solicitudes_por_segundo |
|---|---|---|---|---|
| 2030-06-29T15:45:00Z | api | 66.05 | 50.67977777777778 | 18563.98888888889 |
| 2030-06-29T15:45:00Z | sesiones | 7.53 | 5.753 | 21614.325555555555 |
| 2030-06-29T16:00:00Z | api | 81.98 | 69.26066666666668 | 28666.646666666667 |
| 2030-06-29T16:00:00Z | sesiones | 9.36 | 7.958444444444446 | 33420.19 |
| 2030-06-29T16:15:00Z | api | 75.36 | 70.56833333333336 | 28977.105555555554 |
| 2030-06-29T16:15:00Z | sesiones | 8.56 | 7.979222222222218 | 33838.57111111111 |
| 2030-06-29T16:30:00Z | api | 85.89 | 74.52988888888889 | 30683.094444444443 |
| 2030-06-29T16:30:00Z | sesiones | 9.8 | 8.459555555555559 | 35796.04777777778 |
| 2030-06-29T16:45:00Z | api | 78.48 | 62.960333333333345 | 25789.66888888889 |
| 2030-06-29T16:45:00Z | sesiones | 8.92 | 7.244666666666666 | 30179.126666666667 |
| 2030-06-29T17:00:00Z | api | 75.4 | 69.90588888888887 | 28893.751111111113 |
| 2030-06-29T17:00:00Z | sesiones | 8.61 | 8.001444444444441 | 33789.85 |
| 2030-06-29T17:15:00Z | api | 76.72 | 71.606 | 29763.674444444445 |
| 2030-06-29T17:15:00Z | sesiones | 8.75 | 8.219444444444445 | 34624.16111111111 |
| 2030-06-29T17:30:00Z | api | 77.81 | 73.15944444444447 | 30080.595555555556 |
| 2030-06-29T17:30:00Z | sesiones | 8.92 | 8.317888888888886 | 35332.09111111111 |
| 2030-06-29T17:45:00Z | api | 78.69 | 66.43222222222222 | 27103.78 |
| 2030-06-29T17:45:00Z | sesiones | 8.99 | 7.596444444444443 | 31678.07888888889 |
| 2030-06-29T18:00:00Z | api | 54.38 | 44.96866666666667 | 9952.933333333332 |
| 2030-06-29T18:00:00Z | sesiones | 6.11 | 5.117333333333334 | 11632.431111111111 |

## 2. Materialización de resúmenes (vivo -> histórico)

Partidos resumidos: 2 · tiempo: 5.7 s. Cada tramo se borra con `/api/v2/delete` y se reescribe con `to()` de Flux (reemplazo explícito: idempotente).

| puntos | measurement |
|---|---|
| 2320 | audiencia_partido_1m |
| 380 | estadisticas_equipo_1m |
| 480 | operacion_plataforma_5m |
| 2 | resumen_partido_audiencia |
| 4 | resumen_partido_equipo |

Task nativa `fixture2030_resumen_1m` (producción, cada 1 h sobre la última hora): actualizada (id 116659ba283b0000, cada 1 h, estado activo)

```flux
option task = {name: "fixture2030_resumen_1m", every: 1h, offset: 5m}

from(bucket: "fixture2030_vivo")
  |> range(start: -task.every, stop: now())
  |> filter(fn: (r) => r._measurement == "estadisticas_equipo")
  |> filter(fn: (r) => r._field == "posesion_pct")
  |> aggregateWindow(every: 1m, fn: last, timeSrc: "_start", createEmpty: false)
  |> set(key: "_measurement", value: "estadisticas_equipo_1m")
  |> to(bucket: "fixture2030_historico", org: "fixture2030")
  |> yield(name: "r0")
from(bucket: "fixture2030_vivo")
  |> range(start: -task.every, stop: now())
  |> filter(fn: (r) => r._measurement == "estadisticas_equipo")
  |> filter(fn: (r) => r._field == "pases_acum")
  |> aggregateWindow(every: 1m, fn: max, timeSrc: "_start", createEmpty: false)
  |> set(key: "_measurement", value: "estadisticas_equipo_1m")
  |> to(bucket: "fixture2030_historico", org: "fixture2030")
  |> yield(name: "r1")
from(bucket: "fixture2030_vivo")
  |> range(start: -task.every, stop: now())
  |> filter(fn: (r) => r._measurement == "estadisticas_equipo")
  |> filter(fn: (r) => r._field == "tiros_acum")
  |> aggregateWindow(every: 1m, fn: max, timeSrc: "_start", createEmpty: false)
  |> set(key: "_measurement", value: "estadisticas_equipo_1m")
  |> to(bucket: "fixture2030_historico", org: "fixture2030")
  |> yield(name: "r2")
from(bucket: "fixture2030_vivo")
  |> range(start: -task.every, stop: now())
  |> filter(fn: (r) => r._measurement == "estadisticas_equipo")
  |> filter(fn: (r) => r._field == "goles_acum")
  |> aggregateWindow(every: 1m, fn: max, timeSrc: "_start", createEmpty: false)
  |> set(key: "_measurement", value: "estadisticas_equipo_1m")
  |> to(bucket: "fixture2030_historico", org: "fixture2030")
  |> yield(name: "r3")
from(bucket: "fixture2030_vivo")
  |> range(start: -task.every, stop: now())
  |> filter(fn: (r) => r._measurement == "estadisticas_equipo")
  |> filter(fn: (r) => r._field == "recuperaciones")
  |> aggregateWindow(every: 1m, fn: sum, timeSrc: "_start", createEmpty: false)
  |> set(key: "_measurement", value: "estadisticas_equipo_1m")
  |> to(bucket: "fixture2030_historico", org: "fixture2030")
  |> yield(name: "r4")
from(bucket: "fixture2030_vivo")
  |> range(start: -task.every, stop: now())
  |> filter(fn: (r) => r._measurement == "estadisticas_equipo")
  |> filter(fn: (r) => r._field == "posesion_pct")
  |> aggregateWindow(every: 1m, fn: count, timeSrc: "_start", createEmpty: false)
  |> set(key: "_measurement", value: "estadisticas_equipo_1m")
  |> set(key: "_field", value: "puntos")
  |> to(bucket: "fixture2030_historico", org: "fixture2030")
  |> yield(name: "r5")
from(bucket: "fixture2030_vivo")
  |> range(start: -task.every, stop: now())
  |> filter(fn: (r) => r._measurement == "audiencia_partido")
  |> filter(fn: (r) => r._field == "usuarios_conectados")
  |> aggregateWindow(every: 1m, fn: max, timeSrc: "_start", createEmpty: false)
  |> set(key: "_measurement", value: "audiencia_partido_1m")
  |> set(key: "_field", value: "usuarios_max")
  |> to(bucket: "fixture2030_historico", org: "fixture2030")
  |> yield(name: "r6")
from(bucket: "fixture2030_vivo")
  |> range(start: -task.every, stop: now())
  |> filter(fn: (r) => r._measurement == "audiencia_partido")
  |> filter(fn: (r) => r._field == "usuarios_conectados")
  |> aggregateWindow(every: 1m, fn: mean, timeSrc: "_start", createEmpty: false)
  |> set(key: "_measurement", value: "audiencia_partido_1m")
  |> set(key: "_field", value: "usuarios_prom")
  |> to(bucket: "fixture2030_historico", org: "fixture2030")
  |> yield(name: "r7")
from(bucket: "fixture2030_vivo")
  |> range(start: -task.every, stop: now())
  |> filter(fn: (r) => r._measurement == "audiencia_partido")
  |> filter(fn: (r) => r._field == "comentarios")
  |> aggregateWindow(every: 1m, fn: sum, timeSrc: "_start", createEmpty: false)
  |> set(key: "_measurement", value: "audiencia_partido_1m")
  |> to(bucket: "fixture2030_historico", org: "fixture2030")
  |> yield(name: "r8")
from(bucket: "fixture2030_vivo")
  |> range(start: -task.every, stop: now())
  |> filter(fn: (r) => r._measurement == "audiencia_partido")
  |> filter(fn: (r) => r._field == "sesiones_nuevas")
  |> aggregateWindow(every: 1m, fn: sum, timeSrc: "_start", createEmpty: false)
  |> set(key: "_measurement", value: "audiencia_partido_1m")
  |> to(bucket: "fixture2030_historico", org: "fixture2030")
  |> yield(name: "r9")
```

## 3. Consultas de torneo sobre el bucket histórico

### Top 5 partidos por pico de audiencia simultánea

| fase | partido_id | pico_usuarios | comentarios |
|---|---|---|---|
| DIECISEISAVOS | PAR-D16-01 | 2564757 | 198647 |
| GRUPOS | PAR-A-1 | 1504582 | 102119 |

### Top 5 equipos por posesión media (promedio de la posesión FINAL de cada partido)

Acá sí corresponde promediar: cada partido aporta su posesión final y pesa lo mismo.

| equipo_id | partidos | posesion_media |
|---|---|---|
| BEL | 1 | 56.6 |
| NED | 1 | 48.5 |
| ARG | 2 | 47.45 |

