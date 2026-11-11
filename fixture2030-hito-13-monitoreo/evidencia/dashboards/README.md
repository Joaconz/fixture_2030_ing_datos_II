# Capturas de los cinco dashboards (10/11/2026)

| Captura | Dashboard |
|---|---|
| [`1_resumen_y_slas.png`](1_resumen_y_slas.png) | 1. Resumen y SLAs |
| [`2_api_integrada.png`](2_api_integrada.png) | 2. API integrada |
| [`3_comparacion_entre_bases.png`](3_comparacion_entre_bases.png) | 3. Comparación entre bases |
| [`4_bases_por_dentro.png`](4_bases_por_dentro.png) | 4. Bases por dentro |
| [`5_infraestructura.png`](5_infraestructura.png) | 5. Infraestructura |

`falla_redis_durante.jpg` y `falla_redis_despues.jpg` son del dashboard único anterior (30/10/2026); ver [`../../docs/limitaciones_y_evidencia.md`](../../docs/limitaciones_y_evidencia.md).

## Cómo se generaron

- Stack del módulo levantado con `docker compose` (mismo `docker-compose.yml`, con un override local no versionado que solo cambia nombres de contenedor y puertos para convivir con otro stack en la misma notebook).
- Las cinco bases arriba (contenedores de cada módulo) y la API del Hito 10 escuchando en `:8000`.
- Tráfico: solo `GET`, 4 clientes en paralelo durante 10 minutos (21:06:19–21:16:19 UTC) sobre equipos, jugadores, partidos, eventos, comentarios, estadísticas y una sesión inexistente (404, que igual consulta Redis). Resultado: 17.061 requests, 14.936 × 200, 2.123 × 404, 2 × 500.
- Capturas con el endpoint `/render` de Grafana sobre la ventana fija 21:06:30–21:16:15 UTC (los horarios de las capturas están en UTC).

## Qué se verificó por la API de Grafana

- `GET /api/search`: los cinco dashboards existen en la carpeta *Fixture 2030*, provisionados desde archivo, con los uids `fixture2030-monitoreo`, `fixture2030-api`, `fixture2030-comparacion-bases`, `fixture2030-bases` y `fixture2030-infraestructura`. `GET /api/dashboards/home` abre *1. Resumen y SLAs*.
- Log de Grafana: `finished to provision dashboards`, sin errores de provisioning.
- Cada consulta de cada panel (39 en total) ejecutada por `POST /api/ds/query` sobre esa ventana: **0 errores**, 31 con datos y 8 vacías.
- Los cinco JSON pasan `python -m json.tool`; dentro de cada uno, ids de panel únicos, sin paneles superpuestos en la grilla y todas las consultas contra el datasource `prometheus-fixture2030`.

## Paneles sin datos y por qué

| Dashboard | Paneles | Motivo |
|---|---|---|
| 4. Bases por dentro | Toda la fila **Cassandra** (5 paneles, 8 consultas): latencia p99/p50, peticiones/s, errores, espacio en disco por tabla, tareas pendientes | El Cassandra de la notebook corría con el compose normal, **sin** el agente JMX (`docker-compose.monitoreo.yml`), así que no hay nada escuchando en `:7070`. Por eso el target `cassandra` figura CAÍDO en el *1* y la alerta `TargetSinScrape` está en firing. No se recreó el contenedor para no cortar a otros trabajos que lo estaban usando. La sonda de Cassandra (`probe_success`) y su latencia desde la API sí tienen datos. |

Todos los demás paneles tienen datos.

## Lectura de los SLAs en esta corrida

| Panel | Valor | Contra el objetivo |
|---|---|---|
| p95 de la API | 98 ms | Dentro de < 100 ms, por poco |
| Requests en < 100 ms | 95,5 % | **No cumple** 99,99 %: la ruta de comentarios tiene un p95 de ~250 ms con la notebook cargada |
| API sin 5xx | 99,99 % | En el límite (2 errores 500 sobre 17.061 requests) |
| Disponibilidad de cada base | 100 % las cinco | Cumple en la ventana |

Son valores de un solo nodo por base en una notebook que en ese momento corría además otros stacks de Docker (la carga del host llegó a 120 en los minutos anteriores, ver *5. Infraestructura*). Lo que demuestran es que los SLAs se pueden medir y que el umbral cambia de color cuando no se cumplen, no el rendimiento de producción. En una ventana anterior que incluía unos minutos en que Docker Desktop dejó de responder, la disponibilidad de las cinco bases bajó a 92–94 % y los cuatro paneles de SLA quedaron en rojo.
