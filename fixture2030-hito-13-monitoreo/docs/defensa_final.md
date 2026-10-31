# Defensa final ante la FIFA (RF13, RF16, §6.5)

**Pregunta central:** ¿por qué esta combinación de modelos, estructuras, distribución y observabilidad es adecuada para el Fixture 2030?

**Respuesta en una frase:** porque cada dato del Fixture tiene un acceso dominante distinto (catálogo que se lee, recorrido de eventos con un cierre que no admite dos resultados, escritura masiva en el minuto 90, sesiones que vencen, series por segundo) y cada uno quedó en el modelo que lo resuelve sin resignar ese acceso; la API los integra sin transacciones cruzadas, así que una falla queda en su módulo; y el monitoreo permite **mostrarlo con datos**, no solo afirmarlo.

Guion y tiempos: [`../defensa/guion_de_20_minutos.md`](../defensa/guion_de_20_minutos.md). Demo y plan B: [`../defensa/demo.md`](../defensa/demo.md). Detalle por base: [`decisiones_de_arquitectura.md`](decisiones_de_arquitectura.md).

## Respuestas preparadas (§6.5)

Cada respuesta dice con qué se demuestra (RF16). "Medido" = laboratorio; "diseño" = Hito 3, no medido.

| Pregunta | Respuesta corta | Cómo se demuestra |
|---|---|---|
| ¿Por qué este modelo para este dato? | Por el acceso dominante: ver la tabla por base | [`decisiones_de_arquitectura.md`](decisiones_de_arquitectura.md) §1; matriz del Hito 2 |
| ¿Qué consulta sería costosa con otra estructura? | "Últimos 50 comentarios del partido" en un documental con millones de comentarios: o un documento gigante por partido, o una colección con índice que se vuelve punto caliente en el gol. En Cassandra es leer 4 particiones acotadas y ordenadas. Y "quién asistió el gol del minuto 80" en un columnar: varias consultas y armado en la API; en el grafo, un recorrido | `GET /partidos/PAR-D16-01/comentarios` en Swagger; `esquema.cql` (clave primaria) |
| ¿Cómo se distribuyen los datos? | Comentarios por `(partido, ventana de 10 min, bucket)`; partidos y eventos juntos por partido; sesiones por id, locales a la región; estadísticas por partido + intervalo | Diseño: Hito 3 §Replicación. En el laboratorio: un nodo |
| ¿Qué pasa si se cae un nodo o una región? | Lo que es AP (comentarios, sesiones, estadísticas, eventos) sigue respondiendo desde lo local y reconcilia después; lo que es CP (cierre del partido) **espera**. Con un nodo por base, una caída = 503 en ese módulo y el resto sigue | **Medido:** prueba de falla de Redis (503 solo en sesiones, MongoDB en 200 todo el tiempo) |
| ¿Qué garantía de consistencia necesita cada módulo? | Fuerte solo en el cierre del partido y el catálogo de tipos; de sesión en equipos y usuarios; eventual en el resto | Hito 3 §CAP; `PATCH /partidos/{id}/estado` (transacción) |
| ¿Qué parte puede ser eventual? | Comentarios, estadísticas, sesiones, eventos (con orden causal) | idem |
| ¿Dónde está el cuello de botella? | Hoy, **en la API**: un proceso de Python al 97–100 % de CPU, mientras Cassandra responde en ~1 ms | **Medido:** [carga observada](../evidencia/carga_observada_20261030-212441.md); Hito 12 (H2) |
| ¿Cómo distinguen si el problema es la API o la base? | Comparando tres latencias: la request en la API, la base vista desde la API y la base por dentro, más la CPU de la API | Dashboard: filas *API* y *Comparación entre bases*; [`metricas_y_consultas.md`](metricas_y_consultas.md) §"API o base" |
| ¿Qué métrica miran primero si sube la latencia? | p95 por ruta de la API → p95 de cada base desde la API → métrica interna de esa base (Cassandra p99, tareas pendientes) | Paneles en ese orden de arriba a abajo |
| ¿Qué evidencia tienen de que la optimización funcionó? | La caché de la configuración de partición bajó **−99,98 %** esas lecturas (58.281 → 13) y −6,7 % la CPU de Cassandra. **No** afirmamos mejora de latencia: quedó dentro de la variación entre corridas | Hito 12, `hipotesis_y_optimizacion.md` |
| ¿Qué cambiarían si el tráfico se multiplica? | Primero varios procesos de la API (es el límite medido) con la caché activa; después nodos de Cassandra (la partición ya lo permite) | [`decisiones_de_arquitectura.md`](decisiones_de_arquitectura.md) §3 |
| ¿Qué se pierde o se retrasa durante una falla? | Redis: las sesiones de esa región (se vuelve a entrar). Cassandra con W=1: comentarios que tardan en verse. Neo4j: el cierre del partido espera. InfluxDB: los puntos por segundo durante la caída (el resumen por minuto se recalcula) | Prueba de falla (Redis); Hito 3 §Fallos (resto, diseño) |
| ¿Qué no pueden afirmar porque no lo midieron? | Réplicas, quórum, multirregión, 2–3 millones de usuarios, Cassandra saturada, métricas internas de Neo4j e InfluxDB | [`limitaciones_y_evidencia.md`](limitaciones_y_evidencia.md) §4 |
| ¿Qué costo agrega operar seis modelos? | Hoy son **cinco** (IRIS salió): cinco formas de respaldar, actualizar y monitorear. Lo pagamos en este hito (agente JMX, Neo4j sin métricas, token de Influx) y se acepta porque una base única degrada algún acceso y no aísla fallas | [`decisiones_de_arquitectura.md`](decisiones_de_arquitectura.md) §4 |
| ¿Por qué no usaron SQL? | El problema no es el modelo relacional en sí: es escalar escritura en picos y servir latencias bajas desde varios países con datos de forma muy distinta. El Hito 12 compara con una alternativa relacional | `fixture2030-hito12-carga/docs/comparacion_relacional.md` |
| ¿Por qué sacaron IRIS? | Partidos y tipos quedaban duplicados en dos motores y ya había un calendario inconsistente; la ventaja de objetos no se aprovecha con una API REST que valida en su capa | Reentrega del Hito 3 (aprobada) |

## Lo que la defensa no debe afirmar

- Que el sistema "soporta 100.000 req/s": se midieron ~400 req/s en una notebook.
- Que Neo4j o InfluxDB están monitoreados por dentro: solo hay sonda y latencia desde la API.
- Que la caché del Hito 12 mejoró la latencia.
- Que hay réplicas o quórum funcionando: es diseño.
