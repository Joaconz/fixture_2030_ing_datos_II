# Rendimiento y distribución — Hito 6 · Módulo de Comentarios (Cassandra)

**Ingeniería de Datos II · Grupo 2** — Santiago Pazos, Valentina Frisoli, Joaquín Núñez

> **Regla del enunciado:** no se declara ninguna tasa sin método, entorno y resultado observado. Las cifras de la sección 4 salen del archivo que genera `carga_masiva.py` en `docs/evidencia/` en cada corrida; **no se completan a mano**.

---

## 1. Método

| Aspecto | Decisión | Por qué |
|---|---|---|
| Herramienta | `scripts/carga_masiva.py` con el driver oficial de Python (`cassandra-driver`), corriendo en un contenedor del mismo compose | Reproducible sin instalar nada en la notebook (RNF3) |
| Tipo de escritura | `INSERT` con **sentencias preparadas**, ejecutadas en paralelo (`execute_concurrent`) | Es como escribe una aplicación real. Preparar la sentencia evita que Cassandra la parsee en cada escritura |
| Consistencia | `ONE` (W=1) | La del Hito 3 para comentarios |
| Concurrencia | 128 escrituras en vuelo (parámetro `--concurrencia`) | Suficiente para saturar un nodo local; se puede variar para buscar el punto óptimo |
| Qué se cronometra | **Solo** el tiempo de escritura, en lotes de 10.000 comentarios. La generación de datos en Python se mide aparte | Para no atribuirle a Cassandra el costo del generador |
| Unidad | **Escrituras por segundo** = filas escritas por segundo. Cada comentario son 2 escrituras (vista por partido + vista por usuario) | Es la unidad del objetivo del enunciado (10.000 escrituras/s) |
| Por qué sin batch | La carga es idempotente: si una escritura falla, se reejecuta y converge. El batch lo usa la aplicación, no la carga | Medir el batchlog no es medir la escritura (ver `decisiones_de_particionamiento.md` §5) |
| Volumen | 1.050.000 comentarios → 2.100.000 escrituras | Supera el millón exigido por RF11 |

### Comandos

```bash
# Prueba corta (100.000 comentarios, ~200.000 escrituras) para calentar y verificar
docker compose --profile carga run --rm cargador --limite 100000

# Carga completa y medición oficial
docker compose --profile carga run --rm cargador

# Variante: solo la tabla principal (1 escritura por comentario)
docker compose --profile carga run --rm cargador --solo-principal

# Barrido de concurrencia (opcional, para encontrar el punto de saturación)
docker compose --profile carga run --rm cargador --limite 200000 --concurrencia 32
docker compose --profile carga run --rm cargador --limite 200000 --concurrencia 256
```

Como la carga es idempotente, correr cualquiera de estas en cualquier orden deja el mismo estado final.

---

## 2. Ambiente de prueba

| Dato | Valor |
|---|---|
| Fecha de la prueba | 2026-09-24 (20:28 UTC corrida corta · 20:31 UTC carga completa) |
| Versión de Cassandra (`SHOW VERSION`) | 5.0.9 (cqlsh 6.2.0, CQL spec 3.4.7, protocolo nativo v5) |
| Notebook | MacBook Air, disco SSD |
| Recursos visibles para los contenedores | 8 CPUs · 3,8 GB de RAM (asignación de Docker Desktop; la compartían Cassandra y el cargador) |
| Sistema operativo | macOS con Docker Desktop (virtualización de Linux) |
| Heap de Cassandra | 1 GB (fijado en `docker-compose.yml`) |
| Nodos / RF / consistencia | 1 / 1 / ONE |
| Cliente | `cassandra-driver` en contenedor `python:3.11-slim`, misma notebook, concurrencia 128 |

**Condiciones que hay que registrar para que otro pueda interpretar el número (pregunta guía 11):**

- El **cliente y el servidor corren en la misma notebook** y compiten por la CPU. En un clúster real el generador de carga corre en otras máquinas.
- Con **RF=1** cada escritura se hace una sola vez. Con RF=3 cada escritura del cliente son 3 escrituras en el clúster, repartidas en 3 nodos.
- El heap está limitado a 1 GB para que entre en una notebook: con más heap, menos pausas de *garbage collection*.
- Docker Desktop en macOS y Windows agrega una capa de virtualización al disco; en Linux nativo la tasa suele ser mayor.

---

## 3. Qué se espera observar y por qué

Estas son **hipótesis** a contrastar con la medición, no resultados:

1. **La tasa sube con la concurrencia hasta un techo** y después se estanca o baja. El techo lo pone la CPU compartida, no el disco: Cassandra escribe primero en el commit log (secuencial) y en memoria (memtable).
2. **La tasa por lote es estable durante toda la carga.** Si cayera fuerte en algún tramo, lo más probable es un *flush* de memtable o una compactación; se puede ver en `docker compose logs cassandra`.
3. **El partido de audiencia máxima no debería escribir más lento que los demás.** Si la partición única fuera un problema en un solo nodo, se notaría ahí. (En un nodo único el bucket no reparte entre máquinas: su efecto de distribución solo se vería con varios nodos; lo que sí se ve en el lab es el **tamaño** de las particiones, sección 5.)
4. **`--solo-principal` debería dar una tasa de escrituras parecida** a la carga dual: el costo por escritura es el mismo; lo que cambia es cuántas escrituras cuesta cada comentario.

---

## 4. Resultados obtenidos

Salida de `carga_masiva.py` (archivos `carga_masiva_<fecha>.md/.json` en `docs/evidencia/`):

| Corrida | Comentarios | Escrituras OK | Errores | Tiempo de escritura | **Escrituras/s** | Tasa por lote mín / mediana / máx |
|---|---:|---:|---:|---:|---:|---|
| Prueba corta (`--limite 100000`) | 100.000 | 200.000 | 0 | 10,91 s | **18.336** | 13.442 / 19.348 / 21.332 |
| Carga completa | 1.050.000 | 2.100.000 | 0 | 118,15 s | **17.774** | 11.606 / 18.340 / 21.958 |
| `--solo-principal` | — | — | — | — | — | No se ejecutó (opcional) |

**¿Se alcanzó el objetivo de 10.000 escrituras/s?** **Sí.** La carga completa sostuvo 17.774 escrituras/s (≈ 8.887 comentarios/s, porque cada comentario son 2 escrituras). Además, **ningún lote** de 10.000 comentarios bajó del objetivo: el más lento dio 11.606 escrituras/s.

### 4.1 Contraste con las hipótesis de la sección 3

| Hipótesis | Resultado | Lectura |
|---|---|---|
| 1. La tasa sube con la concurrencia hasta un techo | **No verificada**: solo se midió con concurrencia 128 | Queda como mejora: el barrido de concurrencia de la sección 1 |
| 2. La tasa por lote es estable | **Se cumple con una caída acotada**: mediana 18.340, mínimo 11.606 (−37 %) | La caída es la esperable de un *flush* de memtable o una compactación durante la carga. El máximo de latencia de escritura del histograma (263 ms, sección 5.2) apunta en la misma dirección: pausas puntuales, no una degradación sostenida |
| 3. El partido de audiencia máxima no escribe más lento | **Se cumple**: la tasa de la carga completa (que incluye los 300.000 comentarios de `PAR-D16-01`) es prácticamente igual a la de la prueba corta (que solo tiene partidos normales): 17.774 contra 18.336 escrituras/s, un 3 % menos | El tamaño de partición no penalizó la escritura. En Cassandra escribir es agregar al commit log y a la memtable, sin leer la partición existente |
| 4. `--solo-principal` da una tasa de escrituras parecida | No verificada | No se ejecutó |

### 4.2 Cómo interpretar el número

- La cifra es **del laboratorio**, no una promesa de producción. Con **RF=1** cada escritura del cliente es una sola escritura en disco; con RF=3 (Hito 3) serían 3, repartidas en 3 nodos.
- **Cliente y servidor compartían la notebook** (8 CPUs y 3,8 GB para ambos). El número real de Cassandra sola es, como mínimo, este.
- **Escala del escenario.** El minuto pico del partido de audiencia máxima genera ~15.700 comentarios (≈ 260/s, ≈ 520 escrituras/s con la doble vista). Un solo nodo de laboratorio absorbió **34 veces** esa tasa. El techo real del Fixture 2030 son los 100.000+ solicitudes/s de toda la plataforma: eso se alcanza escalando horizontalmente (más nodos), que es por lo que se eligió el modelo columnar en el Hito 2.

### 4.3 Mejoras posibles

| Mejora | Efecto esperado |
|---|---|
| Barrido de concurrencia (32 / 128 / 256) | Encontrar el punto de saturación y validar la hipótesis 1 |
| Correr el cargador en otra máquina | Libera CPU del nodo; la tasa medida sería la de Cassandra sola |
| Subir el heap a 2–4 GB | Menos flushes y pausas de GC; debería subir el mínimo por lote |
| Varios procesos cargadores en paralelo | El driver de Python está limitado por el GIL en un solo proceso |
| Clúster de 3+ nodos | La escritura escala horizontalmente |

---

## 5. Tamaño y distribución de particiones

### 5.1 Lo que calcula el generador (determinista, igual en cualquier máquina)

| Métrica | `comentarios_por_partido` | `comentarios_por_usuario` |
|---|---:|---:|
| Particiones | 1.725 | 360.052 |
| Mínimo | 49 | 1 |
| Mediana | 258 | 2 |
| p90 | 1.051 | 6 |
| p99 | 5.883 | 11 |
| Máximo | **16.161** | 192 |

Ventana pico del partido de audiencia máxima, por bucket: **16.161 / 16.160 / 16.160 / 16.159**.

### 5.2 Lo que hay que verificar en Cassandra después de la carga

```bash
# Forzar que las memtables se escriban a disco (si no, las estadísticas no las ven)
docker compose exec cassandra nodetool flush fixture2030_comentarios

# Percentiles de tamaño de partición (bytes) y de celdas por partición
docker compose exec cassandra nodetool tablehistograms fixture2030_comentarios comentarios_por_partido

# Tamaño máximo y medio de partición, espacio en disco, cantidad estimada de particiones
docker compose exec cassandra nodetool tablestats fixture2030_comentarios.comentarios_por_partido

# Conteo por bucket de la ventana pico (debe coincidir con 5.1)
docker compose exec cassandra cqlsh -e "PAGING OFF; SELECT bucket, count(*) FROM fixture2030_comentarios.comentarios_por_partido WHERE partido_id='PAR-D16-01' AND ventana='2030-06-29 17:30:00.000+0000' AND bucket IN (0,1,2,3) GROUP BY partido_id, ventana, bucket;"
```

Salida guardada en `docs/evidencia/07_particiones.txt` y `08_consultas_con_volumen.txt`:

| Verificación | Valor esperado | Valor observado |
|---|---|---|
| `Number of partitions (estimate)` | ~1.725 | **1.725** — coincide exacto |
| Conteo por bucket de la ventana pico (Q7) | ~16.160 cada uno | **16.161 / 16.160 / 16.160 / 16.159** — coincide exacto |
| `Compacted partition maximum bytes` | 5–10 MB estimado | **2.346.799 bytes ≈ 2,3 MB** |
| `Compacted partition mean bytes` | — | 84.246 bytes ≈ 82 KB |
| p99 de `Partition Size` (`tablehistograms`) | Muy por debajo del máximo | **785.939 bytes ≈ 0,77 MB** (≈ 1/3 del máximo) |
| Celdas en la partición más grande | — | 152.321 (≈ 9,4 celdas por fila × 16.161 filas) |
| Espacio total de la tabla | — | 74.007.277 bytes ≈ 71 MB para 1.050.000 comentarios |
| Latencia de escritura local p50 / p99 / máx | — | 10 µs / 446 µs / 263 ms |
| Latencia de lectura local p50 / p99 | — | 86 µs / 179 µs |

**Sobre el tamaño de la partición máxima.** El valor observado (2,3 MB) es **menor** que el estimado (5–10 MB) porque la estimación usaba ~300 bytes por fila sin comprimir, y Cassandra comprime las SSTables por defecto (LZ4). En disco quedaron ≈ 145 bytes por fila. El diseño tenía margen de sobra: la partición más grande está unas **40 veces por debajo** de la guía práctica de ~100 MB.

> Los percentiles de `tablehistograms` son aproximados: Cassandra agrupa los valores en rangos, por eso no coinciden al byte con los de `tablestats`.

---

## 6. Qué se concluye con esta evidencia (pregunta guía 10)

La solución se comportó como se esperaba si se cumplen las tres cosas a la vez:

1. **Escritura sostenida sin errores** durante los 2.100.000 inserts, con una tasa por lote estable.
2. **Ninguna partición supera el techo de diseño** (20.000 filas / ~6 MB), incluida la ventana pico del partido de audiencia máxima.
3. **La lectura caliente (Q1) toca una sola partición**, verificado con `TRACING ON` en `consultas.cql`.

La primera valida la elección del motor; la segunda valida la clave de partición; la tercera valida que la clave sirve para la consulta que la motivó.