# Pares de corridas sin limpieza entre línea base y optimizada

Corridas previas al par oficial, con el mismo código. Entre la línea base y la optimizada **no** se borraron los comentarios de prueba, así que la optimizada trabajó sobre ~13.000 filas más en la ventana pico. Se conservan como evidencia de la variación entre pares (ver `docs/hipotesis_y_optimizacion.md`, punto 3). Generado con `scripts/comparar.py`; los directorios fuente quedan en `anteriores/` (fuera de git).

## Par 1 · `301632` / `301635` (commit `d33f515`, muestreo de recursos cada ~5 s)
| Métrica | Línea base | Optimizada | Variación |
|---|---:|---:|---:|
| Requests totales | 64.446 | 66.500 | +3.2 % ✅ |
| Throughput (req/s) | 402,8 | 415,6 | +3.2 % ✅ |
| Requests fallidas (%) | 0,00 | 0,00 | — |
| GET p50 (ms) | 42,6 | 39,5 | -7.1 % ✅ |
| GET p95 (ms) | 72,0 | 70,4 | -2.2 % ✅ |
| GET p99 (ms) | 85,5 | 83,1 | -2.8 % ✅ |
| GET máx (ms) | 139,2 | 130,7 | -6.1 % ✅ |
| POST p50 (ms) | 45,1 | 46,7 | +3.4 % ≈ |
| POST p95 (ms) | 75,8 | 84,0 | +10.9 % ⚠️ |
| POST p99 (ms) | 90,4 | 99,6 | +10.2 % ⚠️ |
| POST 201 confirmados | 13.009 | 13.329 | +2.5 % ✅ |
| CPU Cassandra prom / máx (%) | 94,7 / 153,9 | 96,7 / 150,5 | +2.0 % ≈ |
| CPU API prom / máx (%) | 95,0 / 98,7 | 95,0 / 99,3 | -0.1 % ✅ |
| CPU generador k6 prom / máx (%) | 17,7 / 20,9 | 18,8 / 23,0 | +6.0 % ⚠️ |
| Memoria API máx (MB) | 169,0 | 171,3 | +1.4 % ≈ |
| Lecturas de `config_particion_partido` (Q0) | 64.446 | 40 | -99.9 % ✅ |
| Integridad | ✅ 13009 filas · 0 dup · 0 sin par | ✅ 13329 filas · 0 dup · 0 sin par | |

Muestras de recursos: 31 (base) / 31 (optimizada), cada 2 s.

## Par 2 · `301639` / `301642` (commit `ef271d9`)
| Métrica | Línea base | Optimizada | Variación |
|---|---:|---:|---:|
| Requests totales | 64.137 | 59.112 | -7.8 % ⚠️ |
| Throughput (req/s) | 400,9 | 369,5 | -7.8 % ⚠️ |
| Requests fallidas (%) | 0,00 | 0,00 | — |
| GET p50 (ms) | 42,3 | 44,7 | +5.7 % ⚠️ |
| GET p95 (ms) | 72,6 | 77,7 | +7.0 % ⚠️ |
| GET p99 (ms) | 86,3 | 93,2 | +7.9 % ⚠️ |
| GET máx (ms) | 137,4 | 138,6 | +0.8 % ≈ |
| POST p50 (ms) | 45,4 | 53,8 | +18.4 % ⚠️ |
| POST p95 (ms) | 76,7 | 93,8 | +22.3 % ⚠️ |
| POST p99 (ms) | 92,0 | 109,8 | +19.5 % ⚠️ |
| POST 201 confirmados | 12.939 | 11.816 | -8.7 % ⚠️ |
| CPU Cassandra prom / máx (%) | 98,5 / 163,8 | 99,2 / 197,1 | +0.7 % ≈ |
| CPU API prom / máx (%) | 94,5 / 99,5 | 93,7 / 100,2 | -0.9 % ✅ |
| CPU generador k6 prom / máx (%) | 18,1 / 21,9 | 18,1 / 21,0 | -0.1 % ✅ |
| Memoria API máx (MB) | 169,9 | 171,7 | +1.1 % ≈ |
| Lecturas de `config_particion_partido` (Q0) | 64.137 | 22 | -100.0 % ✅ |
| Integridad | ✅ 12939 filas · 0 dup · 0 sin par | ✅ 11816 filas · 0 dup · 0 sin par | |

Muestras de recursos: 80 (base) / 80 (optimizada), cada 2 s.
