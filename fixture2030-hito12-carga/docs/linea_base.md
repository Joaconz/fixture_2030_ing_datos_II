# Línea base (RF4, RF5, RF6)

Corrida con la API del Hito 10 **sin modificar su comportamiento** (`COMENTARIOS_CONFIG_CACHE_S=0`).

| Qué se conserva (§5.4) | Dónde |
|---|---|
| Commit, fecha, versiones de Cassandra y k6, recursos de Docker | `evidencia/resultados_linea_base/ambiente.md` |
| Configuración de la API y del escenario | `ambiente.md` + `config/configuracion-ejemplo.env` |
| Latencias (mín, p50, p95, p99, máx) por operación, throughput, errores | `k6_resumen.json` y `k6_salida.txt` |
| CPU y memoria de Cassandra, de la API y del generador k6 (cada 2 s) | `recursos.csv` |
| Lecturas de la tabla de configuración durante la corrida | `lecturas_q0.txt` |
| Registros enviados, confirmados y guardados | `integridad.md` |

## Resultados (corrida `301647`, 30/10/2026 16:47 UTC, commit `ef271d9`)

Antes de la corrida se borraron los comentarios de corridas anteriores (`limpiar_datos_de_prueba.sh`): la ventana pico arrancó con las **64.640 filas** del Hito 6, igual que la optimizada.

| Métrica | Valor | Método |
|---|---|---|
| Requests | **58.281** (≈ 160 s) | k6, `http_reqs` |
| Throughput | **364,3 req/s** | k6, `http_reqs` / duración |
| Requests fallidas | **0,00 %** | k6, `http_req_failed` |
| GET últimos 50 · p50 / p95 / p99 / máx | **46,3 / 82,4 / 100,6 / 367,7 ms** | k6, `lat_get_comentarios` |
| POST comentario · p50 / p95 / p99 | **50,3 / 87,4 / 109,4 ms** | k6, `lat_post_comentario` |
| POST confirmados (201) | **11.732** (20,1 % de las requests) | k6, contador propio |
| CPU de la API · promedio / máx | **95,0 % / 99,5 %** de un núcleo | `ps` cada 2 s (79 muestras) |
| CPU de Cassandra · promedio / máx | **104,3 % / 192,6 %** (de 10 núcleos) | `docker stats` cada 2 s |
| CPU del generador k6 · promedio / máx | **18,0 % / 21,1 %** | `docker stats` cada 2 s |
| Memoria de la API · máx | 162,9 MB | `ps` (RSS) |
| **Lecturas de `config_particion_partido` (Q0)** | **58.281: exactamente una por request** | `nodetool tablestats` antes y después |
| Integridad | ✅ 11.732 filas · 0 duplicados · 0 sin par · 0 alterados | `validar_integridad.py` (Cassandra directo) |

Fuentes: `evidencia/resultados_linea_base/` (`k6_salida.txt`, `k6_resumen.json`, `recursos.csv`, `lecturas_q0.txt`, `integridad.md`, `ambiente.md`).

## Observaciones sobre la estabilidad
- **Estable:** 0 errores y 0 timeouts; el p99 (100,6 ms) queda cerca del p95 (82,4 ms), sin colas largas. El máximo (367,7 ms) es un caso aislado.
- **Coherencia de las cifras:** con 20 usuarios en lazo cerrado y ~48 ms por request, la tasa esperada es 20 / 0,048 ≈ 415 req/s; la medida (364,3) es algo menor por el tiempo del propio generador y de red.
- **El generador no fue el límite:** k6 usó 18 % de CPU en promedio (21 % de máximo) y hubo 0 requests sin respuesta.
- **Dónde está el límite:** la **API usa ~95 % de un núcleo** en promedio y llega al 99,5 %, mientras Cassandra trabaja holgada (~1 núcleo de los 10 disponibles, con picos de ~2). Ver `hipotesis_y_optimizacion.md`.
- **Hipótesis H1, primera parte, confirmada:** las lecturas de Q0 coinciden **exactamente** con las requests (58.281 = 58.281): la configuración del partido se lee de Cassandra en cada request.
