# Grafana — dashboard "Fixture 2030 — Monitoreo"

Todo se carga por *provisioning* al arrancar el contenedor; no hay que configurar nada a mano:

| Archivo | Qué hace |
|---|---|
| [`provisioning/datasources/prometheus.yml`](provisioning/datasources/prometheus.yml) | Datasource `Prometheus` (`http://prometheus:9090`, uid fijo `prometheus-fixture2030`) |
| [`provisioning/dashboards/fixture2030.yml`](provisioning/dashboards/fixture2030.yml) | Carga los `.json` de `dashboards/` en la carpeta *Fixture 2030* |
| [`dashboards/fixture2030-monitoreo.json`](dashboards/fixture2030-monitoreo.json) | El dashboard (página de inicio de Grafana) |

El dashboard no se puede editar desde la UI (`allowUiUpdates: false`): el JSON versionado es la única fuente (RNF2). Para cambiarlo: editar el JSON; Grafana lo relee en 30 s.

Acceso: http://localhost:3000 · usuario `admin` · contraseña de desarrollo `fixture2030` (se pisa con `GRAFANA_ADMIN_PASSWORD` en un `.env` no versionado). Rango por defecto: últimos 30 minutos, refresco cada 10 s.

## Qué muestra cada fila y qué decisión habilita

| Fila / panel | Qué significa | Señal desfavorable → qué se hace |
|---|---|---|
| **Estado de salud** · Estado por target (`up`) | Prometheus pudo leer cada exporter / la API | Un target CAÍDO → no hay datos de ese componente; `scripts/verificar_targets.sh` |
| Estado de salud por base | Sonda a cada base (OK / CAÍDA) | Una base CAÍDA → sus rutas dan 503; levantar el contenedor, ver `/health/dependencias` |
| Alertas activas | Reglas en pending o firing | Seguir la acción de [`docs/alertas_y_umbral.md`](../docs/alertas_y_umbral.md) |
| **API** · Requests por segundo según status | Volumen y errores de la API | Crecen los 503/504 → panel de resultados por base |
| Latencia p95 por ruta (línea roja 150 ms) | Tiempo de respuesta medido en la API | Sobre la línea → comparar con la fila de abajo para ubicar el cuello |
| Porcentaje de respuestas 5xx | Errores de servidor sobre el total | > 1 % sostenido → alerta `ApiErroresAltos` |
| **Comparación entre bases** · Latencia p95 de cada base (línea 100 ms) | Cuánto tarda cada base vista desde la API | Una base sube y las demás no → problema en esa base |
| Llamadas por segundo a cada base, por resultado | `ok`, `no_disponible`, `timeout`, `dominio:*` | Aparece `no_disponible` → esa base está caída o rechaza la conexión |
| **MongoDB** · operaciones por tipo, conexiones | Actividad del catálogo de equipos | Conexiones que crecen sin bajar → fuga de conexiones en un cliente |
| **Redis** · comandos/s, hit ratio, memoria y clientes | Uso de sesiones y caché | Hit ratio bajo con tráfico → la caché no sirve (TTL corto o claves que no se reutilizan) |
| **Cassandra** · latencia p50/p99 (línea 100 ms), peticiones/s, errores, disco por tabla, tareas pendientes | Comportamiento del módulo de comentarios | Tareas pendientes que crecen → saturación; timeouts → réplicas que no responden |
| **Host** · CPU, memoria, disco, red, carga | Recursos de la VM de Docker | CPU al 100 % durante una prueba → los números de latencia están contaminados por el propio laboratorio |
| **Prometheus** · duración del scrape, muestras/s | Salud del propio monitoreo | Un scrape que tarda segundos → el exporter está sobrecargado (p. ej. Cassandra sin filtro de MBeans) |

Unidades y períodos de cada consulta: [`docs/metricas_y_consultas.md`](../docs/metricas_y_consultas.md).
