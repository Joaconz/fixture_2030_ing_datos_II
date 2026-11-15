# Distribución de los datos y escalabilidad

Cómo quedan repartidos los datos en cada base después de la carga completa, y qué implica para escalar. Los números salen de `scripts/distribucion.py`, que corre en la fase de verificación de cada base. Están en la sección *Distribución* de cada `reporte.md` y completos en `reporte.json` → `distribucion`. Los datos de los cinco cargadores son **deterministas**, así que la distribución es idéntica en todas las corridas. Las cifras de este documento son las de la corrida definitiva (README).

## MongoDB — equipos y jugadores

| Medida | Valor |
|---|---|
| Jugadores por equipo | 26 en los 64 equipos (mín = máx = 26) |
| Por confederación | UEFA 520 (20 equipos) · CAF, AFC, CONMEBOL y CONCACAF 260 (10 c/u) · OFC 104 (4) |
| Por posición | Mediocampista 437 · Delantero 419 · Arquero 418 · Defensor 390 |
| Tamaño | `jugadores`: 1.664 docs, 368 KB de datos, **221 B/doc**, 4 índices · `equipos`: 64 docs, 14 KB, 226 B/doc, 2 índices |

**Qué implica**

- El reparto por equipo es perfectamente uniforme: el plantel fijo de 26 es justamente lo que pidió la corrección del Hito 4. Si se fragmentara (sharding) por `equipoId` con clave *hashed*, cada fragmento recibiría la misma cantidad de jugadores. Por **confederación** con rangos, en cambio, UEFA tendría el 31 % de los jugadores en un solo fragmento: no sirve como clave de fragmentación.
- Hoy no hace falta fragmentar: menos de 400 KB entran completos en la caché de WiredTiger. El crecimiento esperable (más torneos, estadísticas por jugador) es por cantidad de documentos, no por tamaño de cada uno. Primero alcanza con réplicas (Hito 9) y recién con varios órdenes de magnitud más tendría sentido fragmentar por `equipoId` hashed.

## Neo4j — partidos, eventos y relaciones

| Medida | Valor |
|---|---|
| Nodos | 3.089: Evento 1.572 · Jugador 1.282 · Partido 127 · Equipo 64 · Grupo 16 · Sede 16 · TipoEvento 12 |
| Relaciones | 10.647. Las del enunciado: PARTICIPA 1.248, ANOTA 220, ASISTE 220, RECIBE_TARJETA 136, REEMPLAZA 136 |
| Eventos por fase | Grupos 96 partidos / 1.152 · Dieciseisavos 16 / 220 · Octavos 8 / 116 · Cuartos 4 / 52 · Semifinales 2 / 32 · Final 1 / 0 (PROGRAMADO) |

| Grado por etiqueta | mín | p50 | p99 | máx | prom |
|---|---:|---:|---:|---:|---:|
| Evento | 4 | 6 | 7 | 7 | 5,7 |
| Partido | 3 | 30 | 37 | 37 | 28,8 |
| Equipo | 22 | 25 | 31 | 31 | 25,0 |
| Jugador | 1 | 1 | 21 | 29 | 4,0 |
| TipoEvento | 0 | 126 | 294 | 294 | 131,0 |

**Qué implica**

- Los nodos de negocio tienen grado **acotado y parejo**: un evento tiene 4 a 7 relaciones, y un partido unas 30, porque ahí cuelgan sus eventos. Los recorridos típicos (eventos de un partido, cadena SIGUIENTE_EVENTO, goles de un jugador) tocan pocas decenas de nodos.
- Los **Jugador** están sesgados: la mitad tiene grado 1 (solo JUEGA_EN, nunca protagonizó un evento) y unos pocos llegan a 29. Es la distribución real de un torneo (pocos goleadores) y no complica nada a esta escala.
- Los **TipoEvento** son *supernodos*: PASE ya tiene 294 relaciones y crece linealmente con los eventos. Con un torneo completo, con decenas de eventos por minuto, llegarían a decenas o cientos de miles. Las consultas no deben **empezar** el recorrido en un TipoEvento (por ejemplo, "todos los GOL"); conviene filtrar por la propiedad del evento o arrancar desde el partido, que es lo que ya hacen las consultas del módulo.
- Escala vertical: Neo4j Community es una sola instancia, y el grafo entero entra holgado en los 512 MB de *page cache* del compose. Escalar lecturas requeriría réplicas (Enterprise). No hay particionamiento horizontal del grafo en esta edición.

## Cassandra — comentarios

| Medida | `comentarios_por_partido` | `comentarios_por_usuario` |
|---|---|---|
| Filas | 1.050.000 | 1.050.000 |
| Particiones | **1.725** (`partido_id`, ventana de 10 min, bucket) | **360.052** (`usuario_id`, mes) |
| Filas por partición (recorrido completo) | mín 49 · p50 258 · p90 1.052 · p99 5.883 · **máx 16.161** | mín 1 · p50 2 · p90 6 · p99 11 · máx 192 |
| Tamaño de partición (`tablestats`, compactada) | media 84 KB · **máx 2,3 MB** | media 364 B · máx 20 KB |
| Espacio en disco | 74 MB | 61 MB |

Las particiones más grandes son las cuatro de `PAR-D16-01` (audiencia MÁXIMA, 300.000 comentarios) en la ventana 17:30, una por bucket, con 16.159 a 16.161 filas cada una. Por partido, el reparto está muy concentrado: 96 partidos tienen ~4.688 comentarios, 15 tienen 20.000 y uno tiene 300.000 (**32 veces el promedio**). `tablehistograms` muestra latencias de escritura p50 29 µs, p99 2,8 ms y máx 316 ms (pausas puntuales de *flush* o compactación).

**Qué implica**

- **El diseño de buckets hace su trabajo.** El partido más comentado es 32 veces el promedio, pero su partición más grande queda en 16.161 filas y 2,3 MB, por debajo del techo de diseño del módulo (20.000 filas, ~7 MB) y muy lejos de los ~100 MB a partir de los cuales Cassandra empieza a sufrir. Sin la ventana de 10 minutos ni los 4 buckets, `PAR-D16-01` sería una sola partición de 300.000 filas.
- **Con más nodos, el punto caliente es temporal.** Durante la ventana pico de `PAR-D16-01`, las escrituras van a solo 4 particiones, o sea, a lo sumo 4 réplicas primarias aunque el clúster tenga más nodos. Si el clúster crece, el número de buckets de los partidos de audiencia MÁXIMA (`config_particion_partido.buckets`) es la perilla para repartir ese pico.
- `comentarios_por_usuario` está en el extremo opuesto: muchísimas particiones chicas (mediana 2 filas). Se reparte de forma uniforme por el *partitioner* Murmur3, pero cada partición tiene un costo fijo (índice, *bloom filter*). Es el precio de poder leer el historial de un usuario con una sola consulta.
- Con un solo nodo y RF = 1 todo vive en la misma máquina. La distribución de tokens se vería recién con más nodos (Hito 9). Lo que este análisis asegura es que ninguna partición va a ser un cuello de botella cuando se repartan.

## Redis — sesiones y caché

| Medida | Valor |
|---|---|
| Claves | 304.174 (100.000 usuarios del volumen + la muestra de 2.000) |
| Por tipo (`--memkeys`) | hash 202.174 (38,7 MB) · set 102.001 (8,6 MB) · zset 2 |
| Por prefijo | `f30:ses` 102.171 · `f30:usr:…:sesiones` 102.000 · `f30:cache:usuario:…:perfil` 100.000 · `f30:voto` 2 · `f30:rank` 1 |
| Memoria | `used_memory` 61 MB de `maxmemory` 256 MB · fragmentación 1,46 · `evicted_keys` 0 |
| Bytes por clave (`MEMORY USAGE`) | sesión (hash) 262 · índice de sesiones (set) 84 · perfil en caché (hash) 121 |
| Con TTL | 304.172 de 304.174 |

**Qué implica**

- Cada usuario simultáneo cuesta unos **470 B en datos** (262 + 84 + 121) y unos ~610 B contando la sobrecarga del diccionario: 61 MB / 100.000. Con el `maxmemory` de 256 MB del módulo entrarían del orden de **400.000 usuarios simultáneos** antes de que `volatile-lru` empiece a desalojar. Como todas las claves tienen TTL, desalojaría sesiones y perfiles en caché: es degradación, no pérdida de datos durables.
- Las claves se reparten de forma **uniforme**: una por usuario o sesión, sin claves gigantes. En Redis Cluster se distribuirían parejas entre los *hash slots*. Las excepciones son el ranking de tendencia (`f30:rank:tendencia:*`, un solo ZSET) y la votación: claves **calientes** que en un clúster caen en un solo nodo, por lo que la escalabilidad de ese patrón pasa por réplicas de lectura, no por más fragmentos.

## InfluxDB — estadísticas en vivo

| Medida | Valor |
|---|---|
| Puntos | 10.094.400 = manifiesto: `audiencia_partido` 7.795.200 · `estadisticas_equipo` 1.276.800 · `operacion_plataforma` 1.022.400 |
| Series (combinaciones de tags) | `estadisticas_equipo` **224** (112 partidos × 2 equipos) · `audiencia_partido` **896** (112 × 8 regiones) · `operacion_plataforma` **5** (servicios) |
| Puntos por partido | `estadisticas_equipo` 11.400 en cada uno de los 112 · `audiencia_partido` 69.600 en cada uno (máx/prom = 1,0) |
| Partidos por audiencia | NORMAL 96 · ALTA 15 · MÁXIMA 1 |
| Disco | 602 MB: **975 archivos Parquet** + 53 de WAL (con el snapshot forzado a 512 MB) |

**Qué implica**

- Al revés que Cassandra, **el volumen por partido es idéntico**. Una serie temporal tiene un punto por segundo de reloj, sea cual sea la audiencia: la audiencia cambia el *valor* (usuarios conectados), no la cantidad de puntos. El crecimiento es lineal en partidos × regiones × segundos y predecible de antemano.
- La **cardinalidad es baja**: 1.125 series en total. Lo que más la haría crecer es agregar tags de alta cardinalidad (`usuario_id`, `comentario_id`), que el modelo del Hito 8 evita a propósito. Agregar regiones o partidos la hace crecer en forma lineal y controlada.
- El límite práctico que apareció es otro: **la cantidad de archivos**. Con la memoria de escritura acotada (necesario para que no se pase de su `mem_limit`, ver [`orquestacion.md`](orquestacion.md) §5), InfluxDB 3 Core vuelca más seguido y deja ~1.000 archivos Parquet. Core **no compacta** y tiene un tope de archivos por consulta (`--query-file-limit`, sin valor por defecto en la ayuda): el `count(*)` de `audiencia_partido` sobre todo el torneo falló con "Query would scan 432 Parquet files, exceeding the file limit". Por eso la validación y este análisis consultan por día. Para el producto, esto significa que las consultas sobre todo el torneo (los resúmenes) deben ir a la base `fixture2030_historico` del Hito 8, de baja resolución, o acotarse por tiempo. Consultar el detalle por segundo de un mes entero no escala en Core sin compactación (que es de Enterprise).
