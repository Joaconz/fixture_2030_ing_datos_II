# Integridad y limitaciones (RF15, RNF4, RNF6, RNF14)

## Validación de integridad
`scripts/validar_integridad.py` corre al final de cada corrida y lee **Cassandra directo**, no la API:

| Verificación | Qué demuestra |
|---|---|
| I1 · Filas guardadas = POST confirmados con 201 | Que un 201 corresponde a una fila real, y que no se guardó nada que el cliente no haya visto confirmado |
| I2 · Sin `comentario_id` duplicados | La idempotencia del Hito 10 bajo concurrencia |
| I3 · Cada fila de la vista por usuario existe en la vista por partido | Que el LOGGED BATCH dejó las dos tablas consistentes |
| I4 · Contenido sin alterar | Que lo guardado es lo que envió k6 |
| I5 · Todo en `PAR-D16-01`, ventana 17:30 | Que no se escribió fuera del rango de la prueba |

**Resultados** (`evidencia/resultados_*/integridad.md`):

| Corrida | POST 201 (k6) | Filas en Cassandra | Duplicados | Sin su par | Alterados | Fuera de rango |
|---|---:|---:|---:|---:|---:|---:|
| Línea base `301647` | 11.732 | 11.732 | 0 | 0 | 0 | 0 |
| Optimizada `301650` | 12.402 | 12.402 | 0 | 0 | 0 | 0 |

En las dos corridas, **cada 201 tiene su fila y no hay ninguna fila sin un 201**: la caché no afectó la integridad. No hubo POST con error ni reintentos.

## Limitaciones
| Limitación | Efecto en la conclusión |
|---|---|
| Un nodo de Cassandra, una notebook, generador y API en la misma máquina | Los números valen para este ambiente (Docker con 10 CPU y ~7,7 GB; en la misma notebook había otro proyecto con contenedores en reposo); no son capacidad de producción |
| Una sola corrida por configuración | Entre pares de corridas con el mismo código vimos variaciones de ±8 % en throughput: las diferencias de latencia de ese tamaño no se consideran demostradas |
| Lazo cerrado sin pausa entre requests | Mide la capacidad máxima del ambiente, no el comportamiento con una tasa de llegada fija |
| La API corre con un solo proceso `uvicorn` | **Fue el límite medido** (95–100 % de un núcleo en las dos corridas): los números describen la capacidad de un proceso, no de Cassandra |
| Cada corrida escribe ~12.000 filas en la ventana pico | Se borran con `limpiar_datos_de_prueba.sh` antes de cada corrida, para que las dos arranquen con las mismas 64.640 filas (RNF3). Sin limpiar, la segunda corrida trabaja sobre una partición un 20 % más grande |
| La limpieza deja tombstones en la partición pico | La línea base corrió con ~51.000 y la optimizada con ~63.000 (calculado, no medido). Puede hacer más lentas las lecturas de esa ventana hasta la compactación; si influye, perjudica a la optimizada |
| No se midieron la red, el disco, las conexiones ni la latencia propia de Cassandra (solo su CPU y las lecturas de Q0) | Que el límite es la API sale de la CPU de cada proceso y contenedor (RF6); no se puede separar cuánto de la latencia pone Cassandra |
| Volumen probado: 1 partido y 20 usuarios virtuales | El escenario del TPO (2–3 M usuarios, 100.000+ req/s) no se ejecutó; requeriría varios nodos de Cassandra y varias instancias de la API detrás de un balanceador |
