# Agregaciones y resúmenes — perfil completo

- Fecha de ejecución (UTC): 2026-10-09T22:41:32+00:00
- Servidor: InfluxDB 3 Core 3.12.0 (revisión 3ba97c65f1)
- Ambiente del cliente: {'cpus_visibles': 12, 'memoria_gb_visible': 7.7, 'python': '3.12.15', 'plataforma': 'Linux-5.15.167.4-microsoft-standard-WSL2-x86_64-with-glibc2.41'}

## 1. Agregaciones según la semántica de cada medida

Partido analizado: PAR-D16-01 (ARG vs BEL).

### A1 · Posesión: último valor contra promedio (medida: porcentaje ACUMULADO)

posesion_pct ya es el acumulado desde el inicio. El valor correcto al cierre es last_value(); avg() mezcla los valores volátiles de los primeros minutos y da otro número.

```sql
SELECT equipo_id,
       last_value(posesion_pct ORDER BY time) AS posesion_final_correcta,
       round(avg(posesion_pct), 1)            AS promedio_de_acumulados_incorrecto
FROM estadisticas_equipo
WHERE partido_id = 'PAR-D16-01' AND time >= '2030-06-29T15:45:00Z' AND time < '2030-06-29T18:10:00Z'
GROUP BY equipo_id
ORDER BY equipo_id
```

Tiempo de respuesta observado: 55.2 ms

| equipo_id | posesion_final_correcta | promedio_de_acumulados_incorrecto |
|---|---|---|
| ARG | 43.4 | 44.7 |
| BEL | 56.6 | 55.3 |

### A2 · Pases: contador acumulado -> total y ritmo

Un contador acumulado se resume con max() (total) o max − min (lo ocurrido en el tramo). sum() contaría miles de veces los mismos pases.

```sql
SELECT equipo_id,
       max(pases_acum)                          AS pases_totales_correcto,
       sum(pases_acum)                          AS suma_del_acumulado_incorrecta,
       round((max(pases_acum) - min(pases_acum)) / 95.0, 2) AS pases_por_minuto_jugado
FROM estadisticas_equipo
WHERE partido_id = 'PAR-D16-01' AND time >= '2030-06-29T15:45:00Z' AND time < '2030-06-29T18:10:00Z'
GROUP BY equipo_id
ORDER BY equipo_id
```

Tiempo de respuesta observado: 21.4 ms

| equipo_id | pases_totales_correcto | suma_del_acumulado_incorrecta | pases_por_minuto_jugado |
|---|---|---|---|
| ARG | 409 | 1175882 | 4.31 |
| BEL | 519 | 1427884 | 5.46 |

### A3 · Recuperaciones: evento por segundo -> suma por tramo

recuperaciones vale 1 en el segundo en que ocurre y 0 en el resto: acá SÍ corresponde sumar.

```sql
SELECT date_bin(INTERVAL '15 minutes', time) AS tramo, equipo_id,
       sum(recuperaciones) AS recuperaciones
FROM estadisticas_equipo
WHERE partido_id = 'PAR-D16-01' AND time >= '2030-06-29T15:45:00Z' AND time < '2030-06-29T18:10:00Z'
GROUP BY tramo, equipo_id
ORDER BY tramo, equipo_id
```

Tiempo de respuesta observado: 20.6 ms

| tramo | equipo_id | recuperaciones |
|---|---|---|
| 2030-06-29T16:00:00 | ARG | 10 |
| 2030-06-29T16:00:00 | BEL | 11 |
| 2030-06-29T16:15:00 | ARG | 12 |
| 2030-06-29T16:15:00 | BEL | 11 |
| 2030-06-29T16:30:00 | ARG | 5 |
| 2030-06-29T16:30:00 | BEL | 6 |
| 2030-06-29T16:45:00 | ARG | 3 |
| 2030-06-29T16:45:00 | BEL | 2 |
| 2030-06-29T17:00:00 | ARG | 8 |
| 2030-06-29T17:00:00 | BEL | 7 |
| 2030-06-29T17:15:00 | ARG | 8 |
| 2030-06-29T17:15:00 | BEL | 8 |
| 2030-06-29T17:30:00 | ARG | 8 |
| 2030-06-29T17:30:00 | BEL | 9 |
| 2030-06-29T17:45:00 | ARG | 7 |
| 2030-06-29T17:45:00 | BEL | 7 |

### A4 · Pico de audiencia: sumar regiones por segundo y DESPUÉS tomar el máximo

El pico real es el máximo del total simultáneo. Sumar los máximos de cada región da un número más alto que nunca existió, porque cada región tiene su pico en un segundo distinto.

```sql
WITH por_segundo AS (
  SELECT time, sum(usuarios_conectados) AS total FROM audiencia_partido WHERE partido_id = 'PAR-D16-01' AND time >= '2030-06-29T15:45:00Z' AND time < '2030-06-29T18:10:00Z' GROUP BY time
), por_region AS (
  SELECT region, max(usuarios_conectados) AS pico FROM audiencia_partido WHERE partido_id = 'PAR-D16-01' AND time >= '2030-06-29T15:45:00Z' AND time < '2030-06-29T18:10:00Z' GROUP BY region
), correcto AS (SELECT max(total) AS pico_simultaneo_correcto FROM por_segundo),
   incorrecto AS (SELECT sum(pico) AS suma_de_picos_incorrecta FROM por_region)
SELECT 'PAR-D16-01' AS partido, pico_simultaneo_correcto, suma_de_picos_incorrecta
FROM correcto CROSS JOIN incorrecto
```

Tiempo de respuesta observado: 39.7 ms

| partido | pico_simultaneo_correcto | suma_de_picos_incorrecta |
|---|---|---|
| PAR-D16-01 | 2564757 | 2638593 |

### A5 · Latencia p95: no se promedian percentiles

latencia_p95_ms ya es un percentil calculado por el servicio. Para el tramo se informa el peor valor (max); el promedio escondería los minutos malos. solicitudes es un evento: se suma.

```sql
SELECT date_bin(INTERVAL '15 minutes', time) AS tramo, servicio,
       max(latencia_p95_ms)     AS p95_peor,
       round(avg(latencia_p95_ms), 2)     AS p95_promedio_enganoso,
       round(sum(solicitudes) / 900.0) AS solicitudes_por_segundo
FROM operacion_plataforma
WHERE servicio IN ('api', 'sesiones')
  AND time >= '2030-06-29T15:45:00Z'
  AND time < '2030-06-29T18:10:00Z'
GROUP BY tramo, servicio
ORDER BY tramo, servicio
```

Tiempo de respuesta observado: 20.9 ms

| tramo | servicio | p95_peor | p95_promedio_enganoso | solicitudes_por_segundo |
|---|---|---|---|---|
| 2030-06-29T15:45:00 | api | 66.05 | 50.68 | 18564.0 |
| 2030-06-29T15:45:00 | sesiones | 7.53 | 5.75 | 21614.0 |
| 2030-06-29T16:00:00 | api | 81.98 | 69.26 | 28667.0 |
| 2030-06-29T16:00:00 | sesiones | 9.36 | 7.96 | 33420.0 |
| 2030-06-29T16:15:00 | api | 75.36 | 70.57 | 28977.0 |
| 2030-06-29T16:15:00 | sesiones | 8.56 | 7.98 | 33839.0 |
| 2030-06-29T16:30:00 | api | 85.89 | 74.53 | 30683.0 |
| 2030-06-29T16:30:00 | sesiones | 9.8 | 8.46 | 35796.0 |
| 2030-06-29T16:45:00 | api | 78.48 | 62.96 | 25790.0 |
| 2030-06-29T16:45:00 | sesiones | 8.92 | 7.24 | 30179.0 |
| 2030-06-29T17:00:00 | api | 75.4 | 69.91 | 28894.0 |
| 2030-06-29T17:00:00 | sesiones | 8.61 | 8.0 | 33790.0 |
| 2030-06-29T17:15:00 | api | 76.72 | 71.61 | 29764.0 |
| 2030-06-29T17:15:00 | sesiones | 8.75 | 8.22 | 34624.0 |
| 2030-06-29T17:30:00 | api | 77.81 | 73.16 | 30081.0 |
| 2030-06-29T17:30:00 | sesiones | 8.92 | 8.32 | 35332.0 |
| 2030-06-29T17:45:00 | api | 78.69 | 66.43 | 27104.0 |
| 2030-06-29T17:45:00 | sesiones | 8.99 | 7.6 | 31678.0 |
| 2030-06-29T18:00:00 | api | 54.38 | 44.97 | 9953.0 |
| 2030-06-29T18:00:00 | sesiones | 6.11 | 5.12 | 11632.0 |

## 2. Materialización de resúmenes (vivo -> histórico)

Partidos resumidos: 112 · tiempo: 136.9 s · líneas escritas: 185,616. Cada resumen se calcula con SQL en `fixture2030_vivo` y se escribe como line protocol en `fixture2030_historico` (misma serie y timestamp en cada corrida: idempotente).

| tabla | puntos |
|---|---|
| estadisticas_equipo_1m | 21280 |
| audiencia_partido_1m | 129920 |
| operacion_plataforma_5m | 34080 |
| resumen_partido_equipo | 224 |
| resumen_partido_audiencia | 112 |

## 3. Consultas de torneo sobre la base histórica

### Top 5 partidos por pico de audiencia simultánea

| partido_id | fase | pico_usuarios | comentarios |
|---|---|---|---|
| PAR-D16-01 | DIECISEISAVOS | 2564757 | 198647 |
| PAR-D16-15 | DIECISEISAVOS | 2014657 | 139259 |
| PAR-D16-07 | DIECISEISAVOS | 2010552 | 137730 |
| PAR-D16-02 | DIECISEISAVOS | 1940979 | 151283 |
| PAR-D16-03 | DIECISEISAVOS | 1896178 | 139348 |

### Top 5 equipos por posesión media (promedio de la posesión FINAL de cada partido)

Acá sí corresponde promediar: cada partido aporta su posesión final y pesa lo mismo.

| equipo_id | partidos | posesion_media |
|---|---|---|
| JAM | 3 | 54.53 |
| CAN | 3 | 54.3 |
| ECU | 4 | 53.68 |
| FIJ | 3 | 53.6 |
| WAL | 3 | 53.43 |

