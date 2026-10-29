# Línea base (RF4, RF5, RF6)

Corrida con la API del Hito 10 **sin modificar su comportamiento** (`COMENTARIOS_CONFIG_CACHE_S=0`).

| Qué se conserva (§5.4) | Dónde |
|---|---|
| Commit, fecha, versiones de Cassandra y k6, recursos de Docker | `evidencia/resultados_linea_base/ambiente.md` |
| Configuración de la API y del escenario | `ambiente.md` + `config/configuracion-ejemplo.env` |
| Latencias (mín, p50, p95, p99, máx) por operación, throughput, errores | `k6_resumen.json` y `k6_salida.txt` |
| CPU y memoria de Cassandra y de la API (cada 2 s) | `recursos.csv` |
| Lecturas de la tabla de configuración durante la corrida | `lecturas_q0.txt` |
| Registros enviados, confirmados y guardados | `integridad.md` |

## Resultados (corrida `2049`, 29/10/2026 20:49 UTC)

| Métrica | Valor | Método |
|---|---|---|
| Requests | **64.567** (≈ 160 s) | k6, `http_reqs` |
| Throughput | **403,5 req/s** | k6, `http_reqs` / duración |
| Requests fallidas | **0,00 %** | k6, `http_req_failed` |
| GET últimos 50 · p50 / p95 / p99 / máx | **42,9 / 68,2 / 75,9 / 115,7 ms** | k6, `lat_get_comentarios` |
| POST comentario · p50 / p95 / p99 | **46,1 / 72,5 / 82,1 ms** | k6, `lat_post_comentario` |
| POST confirmados (201) | **12.913** (20,0 % de las requests) | k6, contador propio |
| CPU de la API · promedio / máx | **93,0 % / 98,8 %** de un núcleo | `ps` cada 2 s (49 muestras) |
| CPU de Cassandra · promedio / máx | **84,2 % / 221,2 %** | `docker stats` cada 2 s |
| Memoria de la API · máx | 124,3 MB | `ps` (RSS) |
| **Lecturas de `config_particion_partido` (Q0)** | **64.567: exactamente una por request** | `nodetool tablestats` antes y después |
| Integridad | ✅ 12.913 filas · 0 duplicados · 0 sin par · 0 alterados | `validar_integridad.py` (Cassandra directo) |

Fuentes: `evidencia/resultados_linea_base/` (`k6_salida.txt`, `k6_resumen.json`, `recursos.csv`, `lecturas_q0.txt`, `integridad.md`, `ambiente.md`).

## Observaciones sobre la estabilidad
- **Estable:** 0 errores y 0 timeouts; el p99 (75,9 ms) queda cerca del p95 (68,2 ms), sin colas largas. El máximo (115,7 ms) es un caso aislado.
- **Coherencia de las cifras:** con 20 usuarios en lazo cerrado y ~44 ms por request, la tasa esperada es 20 / 0,044 ≈ 455 req/s; la medida (403,5) es algo menor por el tiempo del propio generador y de red. El generador no fue el límite: hubo 0 requests sin respuesta y la CPU de la API estuvo saturada antes.
- **Dónde está el límite:** la **API usa ~93 % de un núcleo** en promedio y llega al 98,8 %, mientras Cassandra trabaja holgada (84 % de 8 núcleos disponibles, con picos de 221 %). Ver `hipotesis_y_optimizacion.md`.
- **Hipótesis H1, primera parte, confirmada:** las lecturas de Q0 coinciden **exactamente** con las requests (64.567 = 64.567): la configuración del partido se lee de Cassandra en cada request.
