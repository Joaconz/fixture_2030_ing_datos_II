# Validación — perfil completo

- Fecha de ejecución (UTC): 2026-09-28T19:14:40+00:00
- Servidor: InfluxDB v2.9.1 (commit d4fa1941fd)
- Ambiente del cliente: {'cpus_visibles': 8, 'memoria_gb_visible': 3.8, 'python': '3.12.14', 'plataforma': 'Linux-7.0.12-linuxkit-aarch64-with-glibc2.41'}

## Resumen

| Verificación | Resultado | Detalle |
|---|:-:|---|
| V1 puntos estadisticas_equipo | ✅ | 1,276,800 cargados / 1,276,800 esperados |
| V1 puntos audiencia_partido | ✅ | 7,795,200 cargados / 7,795,200 esperados |
| V1 puntos operacion_plataforma | ✅ | 1,022,400 cargados / 1,022,400 esperados |
| V2 series estadisticas_equipo | ✅ | 224 medidas / 224 esperadas (combinaciones de tags) |
| V2 series audiencia_partido | ✅ | 896 medidas / 896 esperadas (combinaciones de tags) |
| V2 series operacion_plataforma | ✅ | 5 medidas / 5 esperadas (combinaciones de tags) |
| V3 tipos de fields y tags | ✅ | todos consistentes |
| V4 retención configurada | ✅ | fixture2030_vivo=45 d, fixture2030_historico=infinita, fixture2030_prueba_retencion=1 h |
| V5 la retención de 1 h no admite el punto de hace 2 h | ✅ | escritura HTTP 422 {"code":"unprocessable entity","message":"failure writing points to database: partial write: dropped 1 points outside retention policy of duration 1h0m0s - olde; valores visibles en orden temporal: [3, 20] |
| V6 dato tardío aceptado y ordenado por tiempo | ✅ | el punto de hace 30 min llegó último y se devuelve primero |
| V6 dato repetido: misma serie + timestamp se sobrescribe | ✅ | escritura HTTP 204; queda un único punto con valor 20 (última escritura) |
| V8 la pregunta de torneo da igual en el histórico | ❌ | vivo: 9,847,799 en 98.2 ms · histórico: 300,766 en 3.7 ms (mismo resultado leyendo 112 puntos en lugar de 7,795,200) |

## V1 · Puntos por partido (cargados / esperados)

Partidos con diferencias: 0

| partido_id | feed | audiencia | ok |
|---|---|---|---|
| PAR-A-1 | 11400/11400 | 69600/69600 | ✅ |
| PAR-A-2 | 11400/11400 | 69600/69600 | ✅ |
| PAR-E-1 | 11400/11400 | 69600/69600 | ✅ |
| PAR-E-2 | 11400/11400 | 69600/69600 | ✅ |
| PAR-I-1 | 11400/11400 | 69600/69600 | ✅ |
| PAR-I-2 | 11400/11400 | 69600/69600 | ✅ |
| PAR-M-1 | 11400/11400 | 69600/69600 | ✅ |
| PAR-M-2 | 11400/11400 | 69600/69600 | ✅ |
| PAR-B-1 | 11400/11400 | 69600/69600 | ✅ |
| PAR-B-2 | 11400/11400 | 69600/69600 | ✅ |
| PAR-F-1 | 11400/11400 | 69600/69600 | ✅ |
| PAR-F-2 | 11400/11400 | 69600/69600 | ✅ |
| PAR-J-1 | 11400/11400 | 69600/69600 | ✅ |
| PAR-J-2 | 11400/11400 | 69600/69600 | ✅ |
| PAR-N-1 | 11400/11400 | 69600/69600 | ✅ |
| PAR-N-2 | 11400/11400 | 69600/69600 | ✅ |
| PAR-C-1 | 11400/11400 | 69600/69600 | ✅ |
| PAR-C-2 | 11400/11400 | 69600/69600 | ✅ |
| PAR-G-1 | 11400/11400 | 69600/69600 | ✅ |
| PAR-G-2 | 11400/11400 | 69600/69600 | ✅ |

_… 92 filas más_

## V2 · Cardinalidad (influxdb.cardinality)

| measurement | series_esperadas | series_medidas | fields_por_serie | claves_tsm_serie_x_field |
|---|---|---|---|---|
| estadisticas_equipo | 224 | 224 | 6 | 1344 |
| audiencia_partido | 896 | 896 | 3 | 2688 |
| operacion_plataforma | 5 | 5 | 3 | 15 |

## V3 · Tipos (anotación #datatype)

| measurement | field | esperado | observado | tags_string |
|---|---|---|---|---|
| estadisticas_equipo | posesion_pct | double | double | ✅ |
| estadisticas_equipo | pases_acum | long | long | ✅ |
| estadisticas_equipo | tiros_acum | long | long | ✅ |
| estadisticas_equipo | goles_acum | long | long | ✅ |
| estadisticas_equipo | recuperaciones | long | long | ✅ |
| estadisticas_equipo | minuto_juego | long | long | ✅ |
| audiencia_partido | usuarios_conectados | long | long | ✅ |
| audiencia_partido | comentarios | long | long | ✅ |
| audiencia_partido | sesiones_nuevas | long | long | ✅ |
| operacion_plataforma | latencia_p95_ms | double | double | ✅ |
| operacion_plataforma | solicitudes | long | long | ✅ |
| operacion_plataforma | errores | long | long | ✅ |

## V4 · Retención por bucket (API /api/v2/buckets)

| bucket | retencion_esperada | retencion_real | shard_group |
|---|---|---|---|
| fixture2030_vivo | 45 d | 45 d | 1 d |
| fixture2030_historico | infinita | infinita | 7 d |
| fixture2030_prueba_retencion | 1 h | 1 h | 1 h |

## V5–V6 · Retención real, dato tardío y dato repetido

Se escribieron, en este orden: valor=1 (hace 2 h), valor=2 (hace 10 min), valor=3 (hace 30 min) y luego valor=20 con el MISMO timestamp que valor=2.

Respuesta del servidor a la primera escritura: HTTP 422 {"code":"unprocessable entity","message":"failure writing points to database: partial write: dropped 1 points outside retention policy of duration 1h0m0s - olde

| _time | _value |
|---|---|
| 2026-09-28T18:44:42Z | 3 |
| 2026-09-28T19:04:42Z | 20 |

## V7 · Shards y espacio en disco (/metrics: storage_shard_disk_size)

Cada bucket se divide en shards por período de tiempo (1 día para una retención de 45 días; 7 días para retención infinita). Lo recién escrito puede estar todavía en el caché/WAL.

| bucket | shards | mb_en_disco |
|---|---|---|
| fixture2030_historico | 2 | 0.6 |
| fixture2030_prueba_retencion | 2 | 0.0 |
| fixture2030_vivo | 25 | 28.8 |

## V8 · Pregunta de torneo: vivo contra histórico

vivo: 9,847,799 en 98.2 ms · histórico: 300,766 en 3.7 ms (mismo resultado leyendo 112 puntos en lugar de 7,795,200)

