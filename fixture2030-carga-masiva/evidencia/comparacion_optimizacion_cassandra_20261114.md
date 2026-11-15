# Comparación de corridas

| Corrida | Modo | Commit | Parámetros |
|---|---|---|---|
| `20261114-195607_secuencial_c128-r1` | secuencial | `88bebf9` | Cassandra conc. 128, Influx lote 50.000 / hilos 8 |
| `20261114-200712_secuencial_c128-r2` | secuencial | `88bebf9` | Cassandra conc. 128, Influx lote 50.000 / hilos 8 |
| `20261114-201841_secuencial_c128-r3` | secuencial | `88bebf9` | Cassandra conc. 128, Influx lote 50.000 / hilos 8 |
| `20261114-200008_secuencial_c256-r1` | secuencial | `88bebf9` | Cassandra conc. 256, Influx lote 50.000 / hilos 8 |
| `20261114-201122_secuencial_c256-r2` | secuencial | `88bebf9` | Cassandra conc. 256, Influx lote 50.000 / hilos 8 |
| `20261114-202237_secuencial_c256-r3` | secuencial | `88bebf9` | Cassandra conc. 256, Influx lote 50.000 / hilos 8 |
| `20261114-200328_secuencial_c512-r1` | secuencial | `88bebf9` | Cassandra conc. 512, Influx lote 50.000 / hilos 8 |
| `20261114-201439_secuencial_c512-r2` | secuencial | `88bebf9` | Cassandra conc. 512, Influx lote 50.000 / hilos 8 |
| `20261114-202633_secuencial_c512-r3` | secuencial | `88bebf9` | Cassandra conc. 512, Influx lote 50.000 / hilos 8 |

## Tiempo de reloj y recursos

| Métrica | 20261114-195607_secuencial_c128-r1 | 20261114-200712_secuencial_c128-r2 | 20261114-201841_secuencial_c128-r3 | 20261114-200008_secuencial_c256-r1 | 20261114-201122_secuencial_c256-r2 | 20261114-202237_secuencial_c256-r3 | 20261114-200328_secuencial_c512-r1 | 20261114-201439_secuencial_c512-r2 | 20261114-202633_secuencial_c512-r3 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Reloj hasta la última carga (s) | 220,5 | 230,7 | 214,8 | 182,4 | 179,3 | 214,5 | 203,5 | 219,6 | 225,1 |
| Reloj total con verificación y apagado (s) | 235,9 | 246,4 | 231,5 | 196,5 | 193,5 | 231,4 | 220,2 | 237,9 | 241,0 |
| Suma de las cargas (s) | 158,3 | 168,8 | 153,2 | 120,7 | 117,6 | 153,1 | 142,0 | 157,9 | 163,7 |
| Suma arranque + preparación + carga (s) | 220,5 | 230,7 | 214,8 | 182,4 | 179,2 | 214,5 | 203,6 | 219,5 | 225,0 |
| Última carga en terminar | cassandra | cassandra | cassandra | cassandra | cassandra | cassandra | cassandra | cassandra | cassandra |
| Presupuesto de memoria (MiB) | – | – | – | – | – | – | – | – | – |
| Máx. bases simultáneas | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| Pico RAM de la prueba (MiB) | 2.174 | 2.159 | 2.056 | 2.057 | 2.166 | 2.168 | 2.170 | 2.169 | 2.167 |
| Pico RAM de toda la VM (MiB) | 5.734 | 5.680 | 5.464 | 5.620 | 5.586 | 5.573 | 5.694 | 5.582 | 5.574 |
| Pico CPU de la prueba (%) | 503,2 | 468,3 | 650,9 | 577,1 | 569,3 | 620,3 | 650,3 | 620,0 | 507,3 |
| RAM libre mínima del host (MiB) | – | – | – | – | – | – | – | – | – |
| Chequeos de integridad OK | 4/4 | 4/4 | 4/4 | 4/4 | 4/4 | 4/4 | 4/4 | 4/4 | 4/4 |

## Fase: arranque (segundos)

| Base | 20261114-195607_secuencial_c128-r1 | 20261114-200712_secuencial_c128-r2 | 20261114-201841_secuencial_c128-r3 | 20261114-200008_secuencial_c256-r1 | 20261114-201122_secuencial_c256-r2 | 20261114-202237_secuencial_c256-r3 | 20261114-200328_secuencial_c512-r1 | 20261114-201439_secuencial_c512-r2 | 20261114-202633_secuencial_c512-r3 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| cassandra | 58,8 | 58,2 | 58,2 | 58,2 | 58,2 | 58,2 | 58,2 | 58,2 | 58,2 |

## Fase: preparacion (segundos)

| Base | 20261114-195607_secuencial_c128-r1 | 20261114-200712_secuencial_c128-r2 | 20261114-201841_secuencial_c128-r3 | 20261114-200008_secuencial_c256-r1 | 20261114-201122_secuencial_c256-r2 | 20261114-202237_secuencial_c256-r3 | 20261114-200328_secuencial_c512-r1 | 20261114-201439_secuencial_c512-r2 | 20261114-202633_secuencial_c512-r3 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| cassandra | 3,4 | 3,7 | 3,4 | 3,5 | 3,4 | 3,2 | 3,4 | 3,4 | 3,1 |

## Fase: carga (segundos)

| Base | 20261114-195607_secuencial_c128-r1 | 20261114-200712_secuencial_c128-r2 | 20261114-201841_secuencial_c128-r3 | 20261114-200008_secuencial_c256-r1 | 20261114-201122_secuencial_c256-r2 | 20261114-202237_secuencial_c256-r3 | 20261114-200328_secuencial_c512-r1 | 20261114-201439_secuencial_c512-r2 | 20261114-202633_secuencial_c512-r3 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| cassandra | 158,3 | 168,8 | 153,2 | 120,7 | 117,6 | 153,1 | 142,0 | 157,9 | 163,7 |

## Fase: verificacion (segundos)

| Base | 20261114-195607_secuencial_c128-r1 | 20261114-200712_secuencial_c128-r2 | 20261114-201841_secuencial_c128-r3 | 20261114-200008_secuencial_c256-r1 | 20261114-201122_secuencial_c256-r2 | 20261114-202237_secuencial_c256-r3 | 20261114-200328_secuencial_c512-r1 | 20261114-201439_secuencial_c512-r2 | 20261114-202633_secuencial_c512-r3 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| cassandra | 8,7 | 9,1 | 10,2 | 7,4 | 7,6 | 10,4 | 10,1 | 11,7 | 9,4 |

## Throughput de la carga

| Base | 20261114-195607_secuencial_c128-r1 | 20261114-200712_secuencial_c128-r2 | 20261114-201841_secuencial_c128-r3 | 20261114-200008_secuencial_c256-r1 | 20261114-201122_secuencial_c256-r2 | 20261114-202237_secuencial_c256-r3 | 20261114-200328_secuencial_c512-r1 | 20261114-201439_secuencial_c512-r2 | 20261114-202633_secuencial_c512-r3 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| cassandra | 6.632,5 comentarios/s | 6.221,3 comentarios/s | 6.854,7 comentarios/s | 8.700,2 comentarios/s | 8.926,4 comentarios/s | 6.859,4 comentarios/s | 7.396,9 comentarios/s | 6.648,4 comentarios/s | 6.413,7 comentarios/s |

## Tasa medida por el propio cargador

| Base | 20261114-195607_secuencial_c128-r1 | 20261114-200712_secuencial_c128-r2 | 20261114-201841_secuencial_c128-r3 | 20261114-200008_secuencial_c256-r1 | 20261114-201122_secuencial_c256-r2 | 20261114-202237_secuencial_c256-r3 | 20261114-200328_secuencial_c512-r1 | 20261114-201439_secuencial_c512-r2 | 20261114-202633_secuencial_c512-r3 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| cassandra | 14,576 escrituras/s (medida por carga_masiva.py) | 13,659 escrituras/s (medida por carga_masiva.py) | 15,058 escrituras/s (medida por carga_masiva.py) | 19,326 escrituras/s (medida por carga_masiva.py) | 19,866 escrituras/s (medida por carga_masiva.py) | 15,199 escrituras/s (medida por carga_masiva.py) | 16,284 escrituras/s (medida por carga_masiva.py) | 14,635 escrituras/s (medida por carga_masiva.py) | 14,069 escrituras/s (medida por carga_masiva.py) |
| influxdb | – | – | – | – | – | – | – | – | – |
