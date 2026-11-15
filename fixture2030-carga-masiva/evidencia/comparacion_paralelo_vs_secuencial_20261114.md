# Comparación de corridas

| Corrida | Modo | Commit | Parámetros |
|---|---|---|---|
| `20261114-194204_paralelo` | paralelo | `62d5a41` | Cassandra conc. 128, Influx lote 50.000 / hilos 8 |
| `20261114-194926_secuencial` | secuencial | `62d5a41 + cambios sin commitear` | Cassandra conc. 128, Influx lote 50.000 / hilos 8 |

## Tiempo de reloj y recursos

| Métrica | 20261114-194204_paralelo | 20261114-194926_secuencial |
|---|---:|---:|
| Reloj hasta la última carga (s) | 382,6 | 324,5 |
| Reloj total con verificación y apagado (s) | 402,7 | 340,7 |
| Suma de las cargas (s) | 247,0 | 188,3 |
| Suma arranque + preparación + carga (s) | 379,7 | 284,7 |
| Última carga en terminar | cassandra | redis |
| Presupuesto de memoria (MiB) | 2.571 | – |
| Máx. bases simultáneas | 2 | 1 |
| Pico RAM de la prueba (MiB) | 2.359 | 2.365 |
| Pico RAM de toda la VM (MiB) | 5.910 | 5.944 |
| Pico CPU de la prueba (%) | 518,7 | 584,8 |
| RAM libre mínima del host (MiB) | – | – |
| Chequeos de integridad OK | 25/26 | 25/26 |

## Fase: arranque (segundos)

| Base | 20261114-194204_paralelo | 20261114-194926_secuencial |
|---|---:|---:|
| mongodb | 6,4 | 5,8 |
| neo4j | 15,4 | 7,7 |
| cassandra | 58,8 | 58,2 |
| influxdb | 22,5 | 8,2 |
| redis | 5,9 | 5,8 |

## Fase: preparacion (segundos)

| Base | 20261114-194204_paralelo | 20261114-194926_secuencial |
|---|---:|---:|
| mongodb | 12,0 | 1,2 |
| neo4j | 2,0 | 1,7 |
| cassandra | 5,2 | 3,5 |
| influxdb | 4,5 | 4,3 |
| redis | 0,0 | 0,0 |

## Fase: carga (segundos)

| Base | 20261114-194204_paralelo | 20261114-194926_secuencial |
|---|---:|---:|
| mongodb | 1,5 | 0,5 |
| neo4j | 7,5 | 5,5 |
| cassandra | 188,1 | 133,7 |
| influxdb | 46,3 | 46,4 |
| redis | 3,6 | 2,2 |

## Fase: verificacion (segundos)

| Base | 20261114-194204_paralelo | 20261114-194926_secuencial |
|---|---:|---:|
| mongodb | 1,2 | 0,5 |
| neo4j | 0,6 | 0,4 |
| cassandra | 13,4 | 21,4 |
| influxdb | 3,5 | 3,5 |
| redis | 23,8 | 15,4 |

## Throughput de la carga

| Base | 20261114-194204_paralelo | 20261114-194926_secuencial |
|---|---:|---:|
| mongodb | 1.187,7 documentos/s | 3.483,0 documentos/s |
| neo4j | 1.842,9 nodos+relaciones/s | 2.507,4 nodos+relaciones/s |
| cassandra | 5.581,1 comentarios/s | 7.856,2 comentarios/s |
| influxdb | 218.245,3 puntos/s | 217.457,4 puntos/s |
| redis | 27.878,1 usuarios/s | 44.753,7 usuarios/s |

## Tasa medida por el propio cargador

| Base | 20261114-194204_paralelo | 20261114-194926_secuencial |
|---|---:|---:|
| cassandra | 12,124 escrituras/s (medida por carga_masiva.py) | 17,317 escrituras/s (medida por carga_masiva.py) |
| influxdb | 221,934.5 puntos/s (medida por carga_lotes.py) | 220,931.0 puntos/s (medida por carga_lotes.py) |
