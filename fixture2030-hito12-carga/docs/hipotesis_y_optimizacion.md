# Hipótesis y optimización (RF7, RF8, RF11)

## Hipótesis del cuello de botella

**Observación en el código (antes de medir):** el servicio de comentarios del Hito 10 lee la **configuración de partición del partido** (Q0: buckets, ancho de ventana e inicio, tabla `config_particion_partido`) **en cada request**, tanto en el GET como en el POST. Esa configuración se fija antes del partido (Hito 6) y no cambia durante él.

- En el **GET**, Q0 es una ida y vuelta a Cassandra **en serie** antes de las lecturas en paralelo de los buckets.
- En el **POST**, son tres operaciones en serie: Q0 → lectura por clave primaria (idempotencia) → LOGGED BATCH. Q0 es la primera.

**Hipótesis H1:** con la clave caliente (todas las requests al mismo partido), Q0 suma una ida y vuelta repetida que no aporta nada; reutilizarla debería **bajar la latencia de las dos operaciones** (en torno a una ida y vuelta a Cassandra) y **bajar la carga de Cassandra**, sin afectar la integridad.

**Cómo se prueba la relación con la evidencia:**
1. `lecturas_q0.txt`: con H1, las lecturas de `config_particion_partido` durante la línea base deberían acercarse a la cantidad de requests, y en la optimizada caer a ~1 por proceso.
2. La latencia p50 y p95 de GET y POST debería bajar; si no baja, Q0 no era el cuello de botella (ver hipótesis alternativa).
3. `recursos.csv`: si la API está cerca del 100 % de un núcleo, el límite es el proceso de Python y no Cassandra.

**Hipótesis alternativa H2:** el límite es la **API** (un único proceso `uvicorn` de Python), no Cassandra. Si la CPU de la API se satura mientras Cassandra tiene margen, la caché solo ayuda en la medida en que reduce el trabajo del driver en la API.

## Optimización implementada

| Campo (§5.5) | Detalle |
|---|---|
| Problema o hipótesis | H1: Q0 se lee en cada request aunque no cambia durante el partido |
| Cambio | Caché en memoria del proceso de la configuración por partido, con vencimiento (`COMENTARIOS_CONFIG_CACHE_S`, 60 s en la prueba). Solo se guardan configuraciones existentes: un partido inexistente sigue dando 404 sin cachearse |
| Archivos | `fixture2030-hito10-api/app/services/comentarios.py`, `app/config/settings.py`, `.env.example`, `tests/unit/test_cache_config_comentarios.py` (3 pruebas; suite completa: 210 en verde) |
| Activación | Variable de entorno; por defecto **0** = comportamiento del Hito 10. Las dos corridas usan el mismo código |
| Costo o riesgo (trade-off, RF11) | **Frescura:** si se cambiara la configuración de un partido en curso (por ejemplo, más buckets por un pico imprevisto), la API seguiría usando la anterior hasta 60 s, y en ese lapso podría leer o escribir en el bucket viejo. **Memoria:** una entrada pequeña por partido (≤ 112). **Varios procesos:** cada proceso de la API tiene su propia copia: no hay invalidación entre procesos |
| Prueba ejecutada después | Mismo escenario (`ejecutar_prueba_optimizada.sh`) |
| Resultado medido | Ver la tabla de abajo y `evidencia/comparacion.md` (corridas `301647` y `301650`, commit `ef271d9`) |
| Decisión del equipo | **Se mantiene** la caché (60 s): elimina prácticamente todas las lecturas de Q0 y baja algo la CPU de Cassandra, con un costo bajo. **No** se presenta como mejora de latencia demostrada: la diferencia medida es del mismo tamaño que la variación entre pares de corridas (ver punto 3). El siguiente paso es atacar el límite real (H2): varias instancias o *workers* de la API |

## Resultado medido (línea base `301647` contra optimizada `301650`, mismo escenario)

Las dos corridas arrancaron con la ventana pico en las **64.640 filas** del Hito 6: antes de cada una se borraron los comentarios de prueba anteriores (ver README, orden de ejecución).

| Métrica | Línea base | Optimizada | Variación |
|---|---:|---:|---:|
| **Lecturas de Q0** | **58.281** | **13** | **−99,98 %** |
| CPU de Cassandra · prom / máx | 104,3 % / 192,6 % | 97,3 % / 201,4 % | −6,7 % (prom) |
| CPU de la API · prom / máx | 95,0 % / 99,5 % | 94,6 % / 100,6 % | ≈ |
| CPU del generador k6 · prom / máx | 18,0 % / 21,1 % | 18,0 % / 26,6 % | ≈ |
| Throughput | 364,3 req/s | 391,0 req/s | +7,3 % |
| GET p50 / p95 / p99 | 46,3 / 82,4 / 100,6 ms | 41,6 / 72,6 / 87,9 ms | −10,1 % / −11,9 % / −12,6 % |
| POST p50 / p95 / p99 | 50,3 / 87,4 / 109,4 ms | 50,3 / 86,6 / 102,7 ms | 0 % / −1,0 % / −6,1 % |
| Errores | 0 % | 0 % | — |
| Integridad | ✅ 11.732 filas | ✅ 12.402 filas | sin duplicados ni filas sin par en ninguna |

## Interpretación

1. **H1 se confirma como mecanismo.** La caché elimina casi todas las lecturas de Q0 (de una por request a 13 en toda la corrida) y la CPU de Cassandra baja un 6,7 % en promedio. Las 13 se explican por los vencimientos de los 60 s: la corrida dura ~160 s, así que la entrada vence 2 veces, y en cada vencimiento las requests que llegan juntas la encuentran vencida y la releen a la vez (efecto "estampida" acotado; si molestara, se evitaría con un bloqueo por partido al refrescar).
2. **H2 queda respaldada por la evidencia:** la CPU de la API está en **~95 % promedio y ~100 % de máximo en las dos corridas**, un único proceso de Python saturado. Cassandra usa ~1 de los 10 núcleos disponibles y el generador k6 un 18 %: ninguno de los dos es el límite.
3. **La mejora de latencia y throughput de este par no alcanza para afirmarla.** Antes de este par corrimos dos pares sin limpiar entre corridas (con la optimizada escribiendo sobre ~13.000 filas más). El throughput de la optimizada dio **+3,2 %** en uno y **−7,8 %** en el otro (`evidencia/pares_sin_limpieza.md`). Una diferencia de ±8 % aparece entre pares con el mismo código, y este par da +7,3 % y −10 % en el GET p50: está dentro de esa variación. Lo coherente con H2 es que ahorrar una ida y vuelta a Cassandra casi no cambia la respuesta cuando lo que tarda es la CPU de la API.
4. **Diferencia de condiciones declarada (RNF3):** la limpieza borra por clave y deja *tombstones* (marcas de borrado) en la ventana pico. La línea base corrió con ~51.000 y la optimizada con ~63.000. Si eso influye, juega **en contra** de la optimizada.

**Próximo paso (no ejecutado):** probar la API con varios *workers* de `uvicorn`, que es lo que ataca H2. Con la caché, cada *worker* lee Q0 una vez por minuto; sin ella, la carga sobre Cassandra crecería con cada *worker*. Ahí la caché pasa a importar de verdad.
