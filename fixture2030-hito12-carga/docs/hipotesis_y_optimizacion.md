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
| Resultado medido | Ver la tabla de abajo y `evidencia/comparacion.md` (corridas `2049` y `2053`) |
| Decisión del equipo | **Se mantiene** la caché (60 s): elimina el 99,9 % de las lecturas de Q0 y baja la CPU de Cassandra un 10 %, con un costo bajo. **No** se presenta como mejora de latencia: en este ambiente no la hubo. El siguiente paso es atacar el límite real (H2): varias instancias o *workers* de la API |

## Resultado medido (línea base `2049` contra optimizada `2053`, mismo escenario)

| Métrica | Línea base | Optimizada | Variación |
|---|---:|---:|---:|
| **Lecturas de Q0** | **64.567** | **39** | **−99,9 %** |
| CPU de Cassandra · prom / máx | 84,2 % / 221,2 % | 76,0 % / 126,0 % | −9,8 % (prom) |
| CPU de la API · prom / máx | 93,0 % / 98,8 % | 93,2 % / 98,9 % | ≈ |
| Throughput | 403,5 req/s | 413,0 req/s | +2,3 % |
| GET p50 / p95 / p99 | 42,9 / 68,2 / 75,9 ms | 39,9 / 67,7 / 78,6 ms | −7,1 % / −0,7 % / +3,6 % |
| GET máx | 115,7 ms | 388,7 ms | un único caso aislado |
| POST p50 / p95 / p99 | 46,1 / 72,5 / 82,1 ms | 49,7 / 82,7 / 95,3 ms | +8,0 % / +14,1 % / +16,0 % |
| Errores | 0 % | 0 % | — |
| Integridad | ✅ 12.913 filas | ✅ 13.314 filas | sin duplicados ni filas sin par en ninguna |

## Interpretación

1. **H1 se confirma como mecanismo y se refuta como cuello de botella.** La caché elimina casi todas las lecturas de Q0 (de una por request a 39 en toda la corrida) y Cassandra trabaja menos. Las 39 se explican por los vencimientos de los 60 s: en cada vencimiento, las requests que llegan juntas encuentran la entrada vencida y la releen a la vez (con 20 usuarios concurrentes, ~13 por vencimiento en 3 vencimientos). Es un efecto "estampida" acotado; si molestara, se evitaría con un bloqueo por partido al refrescar. Pero la latencia de punta a punta **casi no cambia**: ahorrar una ida y vuelta a la base no acelera la respuesta cuando lo que tarda es otra cosa.
2. **H2 queda respaldada por la evidencia:** la CPU de la API está en **93 % promedio y 99 % de máximo en las dos corridas**, un único proceso de Python saturado. Con la API al límite, lo que se ahorra en Cassandra se convierte en un poco más de throughput (+2,3 %, más requests atendidas en el mismo tiempo), no en menos latencia.
3. **El empeoramiento del POST tiene una causa identificada, que impide la comparación directa (RNF3):** la corrida optimizada escribió en la **misma partición caliente**, que ya tenía las 12.913 filas de la línea base: ~64.640 → ~77.550 filas (+20 %). El POST lee por clave primaria antes de escribir, en esa partición más grande y con más datos en memoria por compactar. El GET lee las ventanas más recientes del partido, no la 17:30, por eso no se ve afectado igual.
4. **Ruido:** con una sola corrida por configuración, variaciones de este tamaño (±10 %) no alcanzan para afirmar una mejora o un empeoramiento; el GET máximo de 388,7 ms es un único valor aislado.

**Próximo paso (no ejecutado):** probar la API con varios *workers* de `uvicorn`, que es lo que ataca H2. Con la caché, cada *worker* lee Q0 una vez por minuto; sin ella, la carga sobre Cassandra crecería con cada *worker*. Ahí la caché pasa a importar de verdad.
