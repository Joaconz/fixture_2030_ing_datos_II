# Grafana — los cinco dashboards del Fixture 2030

Todo se carga por *provisioning* al arrancar el contenedor; no hay que configurar nada a mano:

| Archivo | Qué hace |
|---|---|
| [`provisioning/datasources/prometheus.yml`](provisioning/datasources/prometheus.yml) | Datasource `Prometheus` (`http://prometheus:9090`, uid fijo `prometheus-fixture2030`) |
| [`provisioning/dashboards/fixture2030.yml`](provisioning/dashboards/fixture2030.yml) | Carga todos los `.json` de `dashboards/` en la carpeta *Fixture 2030* |
| [`dashboards/fixture2030-monitoreo.json`](dashboards/fixture2030-monitoreo.json) | **1. Resumen y SLAs** (página de inicio de Grafana) |
| [`dashboards/fixture2030-api.json`](dashboards/fixture2030-api.json) | **2. API integrada** |
| [`dashboards/fixture2030-comparacion-bases.json`](dashboards/fixture2030-comparacion-bases.json) | **3. Comparación entre bases** |
| [`dashboards/fixture2030-bases.json`](dashboards/fixture2030-bases.json) | **4. Bases por dentro** |
| [`dashboards/fixture2030-infraestructura.json`](dashboards/fixture2030-infraestructura.json) | **5. Infraestructura** |

Los dashboards no se pueden editar desde la UI (`allowUiUpdates: false`): los JSON versionados son la única fuente (RNF2). Para cambiar uno: editar su JSON; Grafana lo relee en 30 s.

**UIDs estables.** Cada dashboard tiene un uid fijo, que es su URL: `/d/fixture2030-monitoreo`, `/d/fixture2030-api`, `/d/fixture2030-comparacion-bases`, `/d/fixture2030-bases`, `/d/fixture2030-infraestructura`. El *1* conserva el archivo y el uid del dashboard único anterior, así siguen funcionando la página de inicio (`GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH` en `docker-compose.yml`) y los links ya guardados en `evidencia/`.

**Navegación.** Arriba de cada dashboard hay un link por cada dashboard con la etiqueta `fixture2030` (aparecen ordenados por título, de ahí el número). El link conserva el rango de tiempo, así que se puede bajar de *1* a *2*, *3* o *4* mirando el mismo intervalo. Algunos paneles del *1* tienen además un link al dashboard que da el detalle.

Acceso: http://localhost:3000 · usuario `admin` · contraseña de desarrollo `fixture2030` (se pisa con `GRAFANA_ADMIN_PASSWORD` en un `.env` no versionado). Rango por defecto: últimos 30 minutos, refresco cada 10 s.

## 1. Resumen y SLAs

¿Está todo arriba, hay alertas y se cumplen los SLAs del enunciado? Es lo primero que se mira.

| Panel | Qué significa | Señal desfavorable → qué se hace |
|---|---|---|
| Estado de salud por base | Sonda a cada base (OK / CAÍDA) | Una base CAÍDA → sus rutas dan 503; levantar el contenedor, ver `/health/dependencias` |
| Targets arriba · Estado por target (`up`) | Prometheus pudo leer cada exporter / la API | Un target CAÍDO → no hay datos de ese componente; `scripts/verificar_targets.sh` |
| Alertas activas | Reglas en pending o firing | Seguir la acción de [`docs/alertas_y_umbral.md`](../docs/alertas_y_umbral.md) |
| p95 de la API (SLA < 100 ms) | Latencia de toda la API, últimos 5 minutos. Verde < 100 ms, rojo desde 100 ms | Rojo → *2. API integrada* para ver qué ruta, *3* para ver si es una base |
| Requests en < 100 ms (SLA 99,99 %) | Disponibilidad efectiva del Hito 3: proporción de requests dentro del objetivo de latencia | Debajo de 99,99 % → hay una cola de requests lentas aunque el p95 esté bien |
| API sin 5xx (SLA 99,99 %) | Disponibilidad de la API vista por el usuario, sobre todo el rango elegido | Debajo de 99,99 % → *3*, panel de resultados por base |
| Disponibilidad de cada base (SLA 99,99 %) | Porcentaje de sondas exitosas de cada base, sobre todo el rango elegido | Debajo de 99,99 % → la base estuvo caída parte del rango; ver la alerta `BaseNoResponde` |
| Latencia p95 de la API frente al SLA de 100 ms | Evolución del p95 con la línea del SLA | Cruza la línea y se queda → a los 150 ms sostenidos salta `ApiLatenciaAlta` |

Los SLAs salen del enunciado (latencia por debajo de 100 ms, Hito 2) y de la métrica de disponibilidad efectiva del Hito 3 (objetivo 99,99 %). En el laboratorio se miden sobre un solo nodo por base y desde una sola notebook ([`docs/limitaciones_y_evidencia.md`](../docs/limitaciones_y_evidencia.md)): validan que el sistema *se puede* medir contra el SLA, no que el despliegue real lo cumpla.

## 2. API integrada

| Panel | Qué significa | Señal desfavorable → qué se hace |
|---|---|---|
| Requests por segundo según status | Volumen y errores de la API | Crecen los 503/504 → *3*, panel de resultados por base |
| Latencia p95 por ruta (línea roja 150 ms) | Tiempo de respuesta medido en la API | Sobre la línea → *3* para ubicar el cuello |
| Porcentaje de respuestas 5xx | Errores de servidor sobre el total | > 1 % sostenido → alerta `ApiErroresAltos` |

## 3. Comparación entre bases

| Panel | Qué significa | Señal desfavorable → qué se hace |
|---|---|---|
| Latencia p95 de cada base (línea 100 ms) | Cuánto tarda cada base vista desde la API | Una base sube y las demás no → problema en esa base (confirmar en *4*) |
| Llamadas por segundo a cada base, por resultado | `ok`, `no_disponible`, `timeout`, `dominio:*` | Aparece `no_disponible` → esa base está caída o rechaza la conexión |

## 4. Bases por dentro

| Fila / panel | Qué significa | Señal desfavorable → qué se hace |
|---|---|---|
| **MongoDB** · operaciones por tipo, conexiones | Actividad del catálogo de equipos | Conexiones que crecen sin bajar → fuga de conexiones en un cliente |
| **Redis** · comandos/s, hit ratio, memoria y clientes | Uso de sesiones y caché | Hit ratio bajo con tráfico → la caché no sirve (TTL corto o claves que no se reutilizan) |
| **Cassandra** · latencia p50/p99 (línea 100 ms), peticiones/s, errores, disco por tabla, tareas pendientes | Comportamiento del módulo de comentarios | Tareas pendientes que crecen → saturación; timeouts → réplicas que no responden |

La fila de Cassandra necesita el agente JMX ([`../../fixture2030-cassandra/docker-compose.monitoreo.yml`](../../fixture2030-cassandra/docker-compose.monitoreo.yml)); sin él queda vacía y el target `cassandra` aparece CAÍDO en el *1*.

## 5. Infraestructura

| Fila / panel | Qué significa | Señal desfavorable → qué se hace |
|---|---|---|
| **Host** · CPU, memoria, disco, red, carga | Recursos de la VM de Docker | CPU al 100 % durante una prueba → los números de latencia están contaminados por el propio laboratorio |
| **Prometheus** · duración del scrape, muestras/s | Salud del propio monitoreo | Un scrape que tarda segundos → el exporter está sobrecargado (p. ej. Cassandra sin filtro de MBeans) |

Unidades y períodos de cada consulta, y en qué dashboard está: [`docs/metricas_y_consultas.md`](../docs/metricas_y_consultas.md).
