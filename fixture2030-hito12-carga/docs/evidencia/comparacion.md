# Comparación línea base vs. optimizada

Generado por `scripts/comparar.py` a partir de los archivos de cada corrida (sin cifras a mano).

| Métrica | Línea base | Optimizada | Variación |
|---|---:|---:|---:|
| Requests totales | 64.567 | 66.084 | +2.3 % ✅ |
| Throughput (req/s) | 403,5 | 413,0 | +2.3 % ✅ |
| Requests fallidas (%) | 0,00 | 0,00 | — |
| GET p50 (ms) | 42,9 | 39,9 | -7.1 % ✅ |
| GET p95 (ms) | 68,2 | 67,7 | -0.7 % ✅ |
| GET p99 (ms) | 75,9 | 78,6 | +3.6 % ≈ |
| GET máx (ms) | 115,7 | 388,7 | +236.0 % ⚠️ |
| POST p50 (ms) | 46,1 | 49,7 | +8.0 % ⚠️ |
| POST p95 (ms) | 72,5 | 82,7 | +14.1 % ⚠️ |
| POST p99 (ms) | 82,1 | 95,3 | +16.0 % ⚠️ |
| POST 201 confirmados | 12.913 | 13.314 | +3.1 % ✅ |
| CPU Cassandra prom / máx (%) | 84,2 / 221,2 | 76,0 / 126,0 | -9.8 % ✅ |
| CPU API prom / máx (%) | 93,0 / 98,8 | 93,2 / 98,9 | +0.1 % ≈ |
| Memoria API máx (MB) | 124,3 | 129,6 | +4.3 % ≈ |
| Lecturas de `config_particion_partido` (Q0) | 64.567 | 39 | -99.9 % ✅ |
| Integridad | ✅ 12913 filas · 0 dup · 0 sin par | ✅ 13314 filas · 0 dup · 0 sin par | |

Muestras de recursos: 49 (base) / 49 (optimizada), cada 2 s.

✅ mejora · ⚠️ empeora 5 % o más · ≈ variación menor al 5 % (dentro del ruido de una sola corrida).
