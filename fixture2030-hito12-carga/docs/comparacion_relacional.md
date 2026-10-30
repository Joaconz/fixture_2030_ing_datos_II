# Comparación con una estructura relacional (RF14)

> Análisis **conceptual**: no se ejecutó una base relacional. Todo número de este documento que no venga de `evidencia/` es una estimación y se marca así.

| Aspecto (§5.6) | Cassandra (implementado, Hito 6) | Alternativa relacional (PostgreSQL, conceptual) |
|---|---|---|
| Unidad de información | Fila en la partición `(partido_id, ventana, bucket)`, ordenada por `creado_en DESC` | Fila de la tabla `comentarios` |
| Estructura | 2 tablas desnormalizadas (por partido y por usuario) escritas en un LOGGED BATCH; Q0 para la configuración | `comentarios(id PK, partido_id FK, usuario_id FK, creado_en, contenido, estado)` + `partidos` + `usuarios`; índices `(partido_id, creado_en DESC)` y `(usuario_id, creado_en DESC)` |
| Lectura "últimos 50" | Q0 + 4 lecturas en paralelo de la ventana más reciente y mezcla en la API | `SELECT … WHERE partido_id = ? ORDER BY creado_en DESC LIMIT 50`: una sola consulta por índice, **más simple** |
| Escritura | Lectura por PK (idempotencia) + batch en 2 tablas | `INSERT … ON CONFLICT (id) DO NOTHING`: idempotencia y consistencia **en una transacción** |
| Garantías | Consistencia configurable (ONE en el laboratorio); las dos tablas quedan consistentes por el LOGGED BATCH, sin aislamiento de transacción | ACID: la fila y sus índices se actualizan juntos; aislamiento por transacción |
| Crecimiento del volumen | Lineal agregando nodos; las particiones están acotadas por ventana y bucket (≈ 16.000 filas máximo en el pico) | El índice `(partido_id, creado_en)` crece con todo el torneo; con un solo nodo, el pico de un partido se concentra en la misma página del índice (clave caliente) |
| Crecimiento de la concurrencia | Escrituras repartidas en 4 buckets por partido y entre nodos, sin bloqueos | Escrituras concurrentes en la misma tabla e índice: contención en la página caliente y un solo nodo de escritura (réplicas solo de lectura) |
| Más simple en | Escalar la escritura masiva del pico | Leer, paginar, filtrar por moderación (un `WHERE`, sin filtrar en la aplicación) e idempotencia |
| Más complejo en | Paginación entre buckets, desnormalización, la API mezcla resultados | Escalar la escritura más allá de un nodo (particionado o sharding manual) |

## Cuándo conviene cada una (condicionado al caso)
- **Cassandra conviene** cuando la escritura masiva y concentrada es la que manda: el pico de 300.000 comentarios de `PAR-D16-01`, con varios partidos simultáneos y la necesidad de seguir escribiendo aunque se caiga un nodo (AP del Hito 3).
- **La relacional conviene** con un volumen que entra en un nodo, cuando se necesitan consultas variadas sobre los comentarios (búsquedas, moderación por estado, reportes) o garantías transaccionales entre el comentario y otras entidades.

## Qué no se pudo medir
El rendimiento real de PostgreSQL con este escenario, el comportamiento de Cassandra con varios nodos y réplicas, y la contención de la página caliente del índice relacional bajo 20 o más escritores. La conclusión queda condicionada al acceso (clave caliente, 80/20), al volumen probado y a esta notebook.
