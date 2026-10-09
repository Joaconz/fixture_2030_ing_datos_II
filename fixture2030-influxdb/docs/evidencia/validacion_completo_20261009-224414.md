# Validación — perfil completo

- Fecha de ejecución (UTC): 2026-10-09T22:44:01+00:00
- Servidor: InfluxDB 3 Core 3.12.0 (revisión 3ba97c65f1)
- Ambiente del cliente: {'cpus_visibles': 12, 'memoria_gb_visible': 7.7, 'python': '3.12.15', 'plataforma': 'Linux-5.15.167.4-microsoft-standard-WSL2-x86_64-with-glibc2.41'}

## Resumen

| Verificación | Resultado | Detalle |
|---|:-:|---|
| V1 puntos estadisticas_equipo | ✅ | 1,276,800 cargados / 1,276,800 esperados |
| V1 puntos audiencia_partido | ✅ | 7,795,200 cargados / 7,795,200 esperados |
| V1 puntos operacion_plataforma | ✅ | 1,022,400 cargados / 1,022,400 esperados |
| V2 series estadisticas_equipo | ✅ | 224 medidas / 224 esperadas; partido_id + equipo_id solo ya da 224 |
| V2 series audiencia_partido | ✅ | 896 medidas / 896 esperadas; partido_id + region solo ya da 896 |
| V2 series operacion_plataforma | ✅ | 5 medidas / 5 esperadas; servicio solo ya da 5 |
| V3 tipos de fields y tags | ✅ | todos consistentes |
| V4 retención configurada | ✅ | fixture2030_vivo=45 d, fixture2030_historico=infinita, fixture2030_prueba_retencion=1 h |
| V5 la retención de 1 h no conserva el punto de hace 2 h | ✅ | escritura HTTP 204 (sin cuerpo); valores visibles en orden temporal: [3, 20] |
| V6 dato tardío aceptado y ordenado por tiempo | ✅ | el punto de hace 30 min llegó último y se devuelve primero |
| V6 dato repetido: misma serie + timestamp se sobrescribe | ✅ | escritura HTTP 204; queda un único punto con valor 20 (última escritura) |
| V8 la pregunta de torneo da igual en el histórico | ✅ | vivo: 9,847,799 en 4309.0 ms · histórico: 9,847,799 en 41.2 ms (mismo resultado leyendo 112 puntos en lugar de 7,795,200) |

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

## V2 · Cardinalidad (combinaciones distintas de tags)

La columna `clave_de_serie` sale de `system.tables`: son los tags que identifican cada serie, en el orden en que InfluxDB 3 ordena los datos dentro de cada archivo.

| tabla | clave_de_serie | series_esperadas | series_medidas | identidad | combinaciones_identidad | fields_por_fila |
|---|---|---|---|---|---|---|
| estadisticas_equipo | partido_id, equipo_id, condicion, fase, sede_id | 224 | 224 | partido_id + equipo_id | 224 | 6 |
| audiencia_partido | partido_id, region, fase | 896 | 896 | partido_id + region | 896 | 3 |
| operacion_plataforma | servicio | 5 | 5 | servicio | 5 | 3 |

## V3 · Tipos (system.influxdb_schema)

| tabla | field | esperado | observado | tags_son_tag |
|---|---|---|---|---|
| estadisticas_equipo | posesion_pct | float | float | ✅ |
| estadisticas_equipo | pases_acum | integer | integer | ✅ |
| estadisticas_equipo | tiros_acum | integer | integer | ✅ |
| estadisticas_equipo | goles_acum | integer | integer | ✅ |
| estadisticas_equipo | recuperaciones | integer | integer | ✅ |
| estadisticas_equipo | minuto_juego | integer | integer | ✅ |
| audiencia_partido | usuarios_conectados | integer | integer | ✅ |
| audiencia_partido | comentarios | integer | integer | ✅ |
| audiencia_partido | sesiones_nuevas | integer | integer | ✅ |
| operacion_plataforma | latencia_p95_ms | float | float | ✅ |
| operacion_plataforma | solicitudes | integer | integer | ✅ |
| operacion_plataforma | errores | integer | integer | ✅ |

## V4 · Retención por base (system.databases)

| base | retencion_esperada | retencion_real |
|---|---|---|
| fixture2030_vivo | 45 d | 45 d |
| fixture2030_historico | infinita | infinita |
| fixture2030_prueba_retencion | 1 h | 1 h |

## V5–V6 · Retención real, dato tardío y dato repetido

Se escribieron, en este orden: valor=1 (hace 2 h), valor=2 (hace 10 min), valor=3 (hace 30 min) y luego valor=20 con el MISMO timestamp que valor=2.

Respuesta del servidor a la primera escritura: HTTP 204 (sin cuerpo)

| time | valor |
|---|---|
| 2026-10-09T22:14:06 | 3 |
| 2026-10-09T22:34:06 | 20 |

## V7 · Archivos Parquet y espacio (system.parquet_files)

InfluxDB 3 confirma cada escritura cuando está en el WAL; los puntos pasan a archivos Parquet (uno por tabla y por tramo de 10 minutos de datos) cuando el servidor hace un snapshot del WAL. Lo que todavía no tiene archivo se sigue consultando desde memoria.

_(sin filas)_

## V8 · Pregunta de torneo: vivo contra histórico

vivo: 9,847,799 en 4309.0 ms · histórico: 9,847,799 en 41.2 ms (mismo resultado leyendo 112 puntos en lugar de 7,795,200)

