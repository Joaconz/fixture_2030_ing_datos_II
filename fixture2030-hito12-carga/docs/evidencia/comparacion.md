# Comparación línea base vs. optimizada

Generado por `scripts/comparar.py` a partir de los archivos de cada corrida (sin cifras a mano).

| Métrica | Línea base | Optimizada | Variación |
|---|---:|---:|---:|
| Requests totales | 58.281 | 62.557 | +7.3 % ✅ |
| Throughput (req/s) | 364,3 | 391,0 | +7.3 % ✅ |
| Requests fallidas (%) | 0,00 | 0,00 | — |
| GET p50 (ms) | 46,3 | 41,6 | -10.1 % ✅ |
| GET p95 (ms) | 82,4 | 72,6 | -11.9 % ✅ |
| GET p99 (ms) | 100,6 | 87,9 | -12.6 % ✅ |
| GET máx (ms) | 367,7 | 217,8 | -40.8 % ✅ |
| POST p50 (ms) | 50,3 | 50,3 | +0.0 % ≈ |
| POST p95 (ms) | 87,4 | 86,6 | -1.0 % ✅ |
| POST p99 (ms) | 109,4 | 102,7 | -6.1 % ✅ |
| POST 201 confirmados | 11.732 | 12.402 | +5.7 % ✅ |
| CPU Cassandra prom / máx (%) | 104,3 / 192,6 | 97,3 / 201,4 | -6.7 % ✅ |
| CPU API prom / máx (%) | 95,0 / 99,5 | 94,6 / 100,6 | -0.4 % ✅ |
| CPU generador k6 prom / máx (%) | 18,0 / 21,1 | 18,0 / 26,6 | -0.1 % ✅ |
| Memoria API máx (MB) | 162,9 | 166,7 | +2.3 % ≈ |
| Lecturas de `config_particion_partido` (Q0) | 58.281 | 13 | -100.0 % ✅ |
| Integridad | ✅ 11732 filas · 0 dup · 0 sin par | ✅ 12402 filas · 0 dup · 0 sin par | |

Muestras de recursos: 79 (base) / 80 (optimizada), cada 2 s.

✅ mejora · ⚠️ empeora 5 % o más · ≈ variación menor al 5 % (dentro del ruido de una sola corrida).
