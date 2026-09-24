# Decisiones de particionamiento — Hito 6 · Módulo de Comentarios (Cassandra)

**Ingeniería de Datos II · Grupo 2** — Santiago Pazos, Valentina Frisoli, Joaquín Núñez
**Motor:** Apache Cassandra (`cassandra:latest`) · Docker Compose · nodo único de laboratorio

---

## 1. Vínculo con los hitos anteriores

| Hito | Qué definió | Cómo se respeta acá |
|---|---|---|
| **Hito 1** | Más de 1.000.000 de comentarios por partido popular; escrituras masivas concentradas en 90 minutos | Carga de 1.050.000 comentarios con picos reales de concentración (§3) |
| **Hito 2** | Comentarios (N6) → modelo **columnar**, por escalabilidad (30 %) y consistencia al 5 % | El diseño prioriza repartir escritura; la consistencia es eventual |
| **Hito 3** | N6 es **AP**, eventual; **N=3, R=1, W=1**; partición **"identificador de partido + ventana temporal"** para evitar el hotspot del minuto 90 | La clave `(partido_id, ventana, bucket)` es esa partición, más el bucket (§2) |
| **Hito 3** | Pregunta abierta: *"¿La ventana alcanza para distribuir el pico de un partido de máxima audiencia? No lo medimos."* | **Se midió**: sin bucket, la ventana pico del partido máximo tiene 64.640 filas; con 4 buckets, 16.161 (§3) |
| **Hito 4** | Claves naturales para cargas idempotentes por *upsert* | `comentario_id` determinista; reejecutar la carga no duplica (§6) |
| **Hito 5** | Identidad de partidos `PAR-A-1` … `PAR-D16-16` y sus fechas; "ningún valor derivado se actualiza con incrementos" | Mismos 112 partidos, mismas fechas; los contadores se tratan aparte y no se cargan (§6) |

---

## 2. Por qué la clave de partición no es solo `partido_id`

Es la primera opción que aparece, y falla por dos razones independientes:

1. **Tamaño.** La final tendría 1.000.000 de filas × ~300 bytes ≈ **300 MB en una sola partición**. Cassandra lee, compacta y repara por partición; la guía práctica es mantenerlas por debajo de ~100 MB y ~100.000 filas. A 300 MB cada lectura de "los últimos 50" arrastra índices de partición enormes y la compactación de esa partición bloquea recursos del nodo.
2. **Hotspot de escritura.** Con N=3, una partición vive en exactamente **3 réplicas**. Toda la escritura de la final iría a esos 3 nodos, sin importar cuántos nodos tenga el clúster. Agregar nodos no ayudaría: es el caso que la pregunta guía 6 describe como "un único punto lógico".

### Alternativas evaluadas

| Clave de partición | Tamaño máx. de partición (lab) | Reparte el pico | Q1 "últimos 50" | Decisión |
|---|---|---|---|---|
| `partido_id` | 300.000 filas (~90 MB); 1 M en producción | No | 1 partición | **Descartada** — tamaño y hotspot |
| `(partido_id, minuto)` | ~15.700 filas | Parcial: el minuto pico sigue en 3 réplicas | 1 partición, pero se vacía cada minuto: la app lee 2–3 minutos por pedido | Descartada — demasiadas particiones chicas y lecturas multi-partición constantes |
| `(partido_id, ventana 10')` — *la del Hito 3* | **64.640 filas** (~19 MB) | No: la ventana del minuto 90 cae entera en 3 réplicas | 1 partición | Descartada **tras medirla**: el tamaño es aceptable, pero el pico de escritura sigue concentrado |
| `(partido_id, ventana 10', bucket)` | **16.161 filas** (~5 MB) | **Sí**: 4 particiones → hasta 4 conjuntos de réplicas distintos | `buckets` particiones en paralelo | **Elegida** |
| `comentario_id` (o un UUID) | 1 fila | Perfectamente | Imposible sin recorrer todo el clúster | Descartada — reparte todo y no sirve para ninguna consulta |

La última fila es el recordatorio de que **la mejor distribución no es la mejor clave**: la clave tiene que repartir la escritura *y* mantener juntas las filas que se leen juntas.

---

## 3. Dimensionamiento: ventana y buckets

### 3.1 Ventana de 10 minutos

- **Más corta (1 minuto):** particiones que se llenan y se abandonan enseguida; Q1 tendría que leer varias particiones casi siempre.
- **Más larga (1 hora):** la ventana del cierre del partido absorbería casi la mitad de los comentarios.
- **10 minutos:** un partido completo son **15 ventanas**. Q1 lee la ventana actual y, solo si trae menos de 50 filas, la anterior: nunca más de 2.

### 3.2 Regla de buckets

```
pico_por_ventana = volumen_esperado_del_partido × 0,20
buckets          = menor potencia de 2  ≥  pico_por_ventana / 20.000
```

- **20 %**: fracción del partido en la ventana más cargada (supuesto; medido en el dataset: **21,5 %**).
- **20.000 filas** ≈ 6 MB por partición: techo de diseño, holgado respecto de la guía de ~100 MB.
- **Potencia de 2**: para poder duplicar buckets sin redistribuir el `crc32`.
- **El bucket se calcula con `crc32(comentario_id) % buckets`**: determinista (idempotencia) y uniforme.

| Partido | Volumen | Pico estimado por ventana | Buckets | Filas por partición en el pico |
|---|---:|---:|---:|---:|
| Normal (96 partidos, lab) | ~4.690 | ~940 | **1** | 610 (medido) |
| Alta audiencia (15 partidos, lab) | 20.000 | 4.000 | **1** | 4.786 (medido, máx.) |
| Audiencia máxima (1 partido, lab) | 300.000 | 60.000 | **4** | **16.161** (medido) |
| Final real (producción, Hito 1) | 1.000.000 | 200.000 | **16** | ~12.500 |

### 3.3 Distribución resultante de la carga masiva (1.050.000 comentarios)

Calculada sobre las claves reales que genera `scripts/generador.py` (es determinista: el resultado es el mismo en cualquier máquina). El script de carga la vuelve a reportar en cada corrida.

| Métrica | Filas por partición |
|---|---:|
| Particiones de `comentarios_por_partido` | 1.725 |
| Mínimo | 49 |
| Mediana (p50) | 258 |
| p90 | 1.051 |
| p99 | 5.883 |
| **Máximo** | **16.161** |

Los 4 buckets de la ventana pico del partido de audiencia máxima quedaron con **16.161 / 16.160 / 16.160 / 16.159** filas: el `crc32` reparte de forma prácticamente perfecta.

### 3.4 Vista por usuario

`(usuario_id, mes)` acota la partición de un usuario a un mes. En el dataset (distribución sesgada: pocos usuarios muy activos) hay 360.052 particiones; la mediana es 2 filas y el máximo, del usuario más activo, es de 192 filas en el mes. Si apareciera un autor automatizado (bot), su partición crecería sin techo dentro del mes: es un riesgo registrado y se controla desde moderación, no desde el modelo.

---

## 4. Regla operativa: los buckets se fijan antes y solo pueden crecer

`buckets` se lee de `config_particion_partido`, que se completa **antes** del partido con la audiencia estimada.

- **¿Y si un partido resulta inesperadamente masivo?** Se sube `buckets` (por ejemplo de 1 a 4) mientras el partido está en juego. Las ventanas nuevas ya se escriben repartidas. Las ventanas viejas tienen todo en el bucket 0, y leerlas pidiendo los buckets 0 a 3 simplemente devuelve vacío en 1, 2 y 3: **leer de más no rompe nada**.
- **Por qué nunca se baja.** Si se bajara de 4 a 1, las lecturas de ventanas viejas dejarían de consultar los buckets 1 a 3 y esos comentarios "desaparecerían" de la vista. Por eso la regla es monótona.
- **Costo aceptado.** La lectura Q1 de un partido de 4 buckets son 4 consultas en paralelo que la aplicación mezcla. Es el precio de repartir la escritura, y se paga solo en los partidos que lo necesitan.

---

## 5. Duplicación controlada

| | |
|---|---|
| Qué se duplica | Cada comentario se escribe en `comentarios_por_partido` y en `comentarios_por_usuario` |
| Por qué | Q5 (historial de un usuario) necesita otra clave de partición. Sin la segunda tabla, la única forma es `ALLOW FILTERING` sobre todo el keyspace |
| Qué se copia | Solo lo que muestra el historial, más un **puntero** `(partido_id, ventana, bucket)` a la fila original |
| Cómo se mantiene coherente | La aplicación escribe las dos filas en un **LOGGED BATCH**: si una se aplica, la otra también termina aplicándose (batchlog). Mismo criterio en edición, moderación y borrado |
| Costo | El doble de escrituras por comentario, y un batchlog por comentario en la aplicación. La carga masiva no usa batch porque es idempotente: si algo falla, se reejecuta (ver `rendimiento.md`) |
| Riesgo residual | Si se modera con `IF EXISTS` (LWT), esa escritura no puede ir en el batch; hay una ventana en la que la vista por usuario muestra el estado anterior. Tolerable: es eventual, como todo N6 |

---

## 6. TTL, borrado, contadores y tombstones

| Decisión | Elección | Razón |
|---|---|---|
| TTL en comentarios | **No** | Los comentarios alimentan el histórico (N9) y los reportes posteriores. Un TTL generaría un tombstone por comentario al vencer: 1.050.000 tombstones que las lecturas tendrían que saltear hasta la compactación |
| Borrado por el autor | **Borrado lógico**: `estado = 'ELIMINADO'`, `contenido = null` | Genera un tombstone de **celda**, no de **fila**. Las lecturas de la ventana siguen devolviendo la fila y la aplicación la muestra como "comentario eliminado" |
| Borrado físico (`DELETE`) | Solo por **clave primaria completa**, fila a fila | Para pedidos de baja de datos personales o limpieza de pruebas. Nunca por partición ni por rango en la operación normal: un tombstone de rango sobre una ventana caliente degrada todas las lecturas de esa ventana |
| Métricas de interacción | Tabla de **contadores** aparte | Cassandra exige separar contadores. Los contadores **no son idempotentes** (reaplicar +1 vuelve a sumar) ni admiten TTL, así que no se incluyen en ninguna carga: solo se ejercitan en `crud.cql`, con +1 y -1 |
| Columnas sin valor | **No se escriben** (se omiten del `INSERT`; en el driver, `UNSET_VALUE`) | En Cassandra escribir `null` no es "no escribir": crea un tombstone de celda. Con `responde_a` y `motivo_moderacion` vacíos en ~90 % de las filas, bindear `None` habría generado ~1,9 millones de tombstones en la carga masiva |
| Moderación | `UPDATE ... IF EXISTS` (LWT) | Evita resucitar una fila fantasma al moderar un comentario ya borrado. Es ~4 veces más caro que una escritura común; se acepta porque la moderación es de baja frecuencia. **No** se usa en la escritura del comentario |

**Si en el futuro se quisiera retención limitada** (por ejemplo, borrar comentarios a los 2 años), la forma correcta sería `default_time_to_live` en la tabla más `TimeWindowCompactionStrategy` por ventana de días: los datos vencen por ventanas completas y la compactación descarta SSTables enteras en lugar de procesar tombstones uno por uno. Hoy no se aplica porque la tabla recibe actualizaciones de moderación, que TWCS no tolera bien.

---

## 7. Estructura secundaria elegida (RF10)

| Consulta | Estructura | Por qué esa y no otra |
|---|---|---|
| Q5 historial por usuario | **Tabla adicional** `comentarios_por_usuario` | La consulta no trae `partido_id`: un índice secundario sobre `usuario_id` igual consultaría todos los nodos del clúster en cada pedido |
| Q4 pendientes de un partido | **Índice SAI** sobre `estado_moderacion` | La consulta sí trae la partición completa: el índice se evalúa dentro de una partición. Una tabla con el estado en la clave obligaría a borrar e insertar en cada acción de moderación |

**Descartado:** vista materializada (`MATERIALIZED VIEW`) para Q5. Hace la duplicación automática, pero las vistas materializadas están marcadas como experimentales y deshabilitadas por defecto en las versiones actuales de Cassandra, por problemas conocidos de consistencia entre la tabla base y la vista. La duplicación explícita con batch es más predecible y se puede verificar.

**Pendiente si el producto lo pide:** "pendientes de moderación de todo el torneo" → tabla `moderacion_pendiente_por_dia` con clave `((dia, bucket), creado_en)`, escrita al crear un comentario pendiente y borrada al resolverlo.

---

## 8. Respuestas a las preguntas guía

| # | Respuesta corta | Dónde se desarrolla |
|---|---|---|
| 1 | Q1, Q2 y Q3 se responden con 1 partición (partido normal) o `buckets` particiones (partido masivo), siempre de la ventana actual y a lo sumo la anterior | §3.1, `consultas.cql` Q1 |
| 2 | `(partido_id, ventana, bucket)`. Riesgo: si la audiencia se subestima, la ventana pico queda en pocos buckets | §2, §4 |
| 3 | `creado_en DESC, comentario_id ASC`: lectura del más nuevo al más viejo, sin ordenar | `modelo_tabular.md` §2.1 |
| 4 | Porque `usuario_id` no está en la clave de la tabla principal | §5, §7 |
| 5 | ~16.000 filas y ~5 MB por partición en el lab; techo de diseño 20.000 filas / ~6 MB; ~260 escrituras/s en el minuto pico del partido máximo | §3, `patrones_de_acceso.md` §1 |
| 6 | Bucket por `crc32(comentario_id)`: la ventana pico se reparte en 4 (lab) o 16 (final real) particiones | §3.2 |
| 7 | Nada expira. El borrado es lógico (tombstone de celda); `DELETE` solo por clave completa | §6 |
| 8 | Q5 justifica la tabla adicional; Q4 justifica el índice SAI | §7 |
| 9 | Lab: 1 nodo, RF=1, sin tolerancia a fallas. Producción: `NetworkTopologyStrategy` con RF=3 por región y W=1 | `modelo_tabular.md` §1 |
| 10 | Tasa sostenida de escritura sin errores + tamaño de particiones con `nodetool tablehistograms` + traza de una lectura de una sola partición | `rendimiento.md` |
| 11 | Hardware, versión de Cassandra, concurrencia, que cliente y servidor comparten la notebook, RF=1 y consistencia ONE | `rendimiento.md` §2 |
| 12 | Las consultas analíticas históricas no tienen partición conocida. Correspondería copiar los datos a un motor analítico o procesarlos por lotes, no agregar `ALLOW FILTERING` a este módulo; las series de actividad por minuto son del módulo de series temporales (N7) | §8 de este documento |

---

## 9. Supuestos que sostienen el diseño y cómo se invalidarían

| Supuesto | Si resultara falso |
|---|---|
| La ventana pico concentra ~20 % del partido | Con 30 % o más, un partido "alta" de 20.000 comentarios necesitaría 2 buckets. Se corrige subiendo `buckets` (§4) |
| La audiencia de cada partido se puede estimar antes | Un partido sorpresa arranca con 1 bucket. Mitigación: subir `buckets` en vivo |
| El orden por `creado_en` del servidor alcanza | Comentarios escritos desde regiones con relojes desfasados pueden aparecer levemente desordenados. Es consistente con el Hito 3 (eventual, sin orden causal para comentarios) |
| Un usuario no escribe miles de comentarios por mes | Un bot haría crecer su partición de historial. Se controla desde moderación |
