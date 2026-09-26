# Hito 1: Análisis de Requisitos

**Ingeniería de Datos II — Trabajo Práctico Obligatorio**
**Plataforma Fixture Mundial 2030**

**Alumnos:** Santiago Pazos, Joaquín Núñez y Valentina Frisoli
**Profesor:** Joaquín Salas
**Fecha:** 7 de agosto de 2026

> Basado en el PDF entregado (`Grupo_N2_Hito_1_Analisis.pdf`), con la corrección del profesor ya aplicada — ver [`correcciones-profesor.md`](./correcciones-profesor.md) por el texto original de la corrección, y "Historial de revisión" al final de este documento por el detalle de qué cambió.

---

## Sección 1: Identificación de datos

Se identificaron nueve entidades. El punto central del análisis es que el sistema presenta una asimetría marcada: los datos propios del torneo son de volumen reducido y prácticamente fijos, mientras que los datos generados por los usuarios crecen en órdenes de magnitud superiores durante los partidos.

| Entidad | Volumen | Vel. crecimiento | Patrón de acceso | Operación típica |
|---|---|---|---|---|
| Equipo | 64 | Fijo | Lectura frecuente, escritura ocasional | Obtener el plantel de Argentina |
| Jugador | 1.500+ | Fijo | Lectura frecuente, escritura ocasional | Buscar delanteros con más de 10 goles |
| Partido | 127 | Fijo | Lectura frecuente, escritura al cierre | Actualizar el resultado final |
| Evento | 1.000+ por partido (~127.000 total) | Acotado al partido | Escritura de bajo volumen (~0,2/seg), alta densidad de relaciones | Registrar un gol con jugador y asistencia |
| Usuario | 2–3 M | Constante | Lectura en cada request, escritura ocasional | Actualizar preferencias de idioma |
| Sesión | 2–3 M simultáneas | Picos durante partidos | Lectura intensiva, escritura al inicio/cierre | Verificar validez de un token |
| Comentario | 1 M+ por partido | Escritura masiva en picos | Escritura masiva, lectura moderada | Publicar un comentario en el minuto 90 |
| Estadística | 10 M+ puntos/partido | Tiempo real | Ingesta continua, lectura por ventanas | Consultar posesión del minuto 1 al 45 |
| Auditoría | ~260 TB en el torneo | Constante | Escritura continua, lectura ocasional | Consultar quién modificó un resultado |

**Nota sobre el volumen de Auditoría.** La consigna menciona petabytes para el histórico del sistema completo. Estimado sobre la auditoría en particular: 100.000 operaciones por segundo × ~1 KB por registro ≈ 100 MB/seg, es decir unos 8,6 TB diarios y ~260 TB durante el mes de torneo. Se adopta esa estimación por ser verificable a partir de los requisitos de rendimiento.

## Sección 2: Análisis de problemas SQL

### Equipos y Jugadores

En un modelo relacional serían dos tablas vinculadas por clave foránea, con un JOIN para reconstruir el plantel completo. A esta escala —64 y 1.500 registros— no existe ningún problema de rendimiento: cualquier motor relacional resuelve estas consultas sin dificultad.

La limitación es de otra naturaleza. El esquema fijo obliga a que todos los jugadores compartan las mismas columnas, cuando un arquero y un delantero tienen estadísticas relevantes distintas (atajadas frente a goles y asistencias). Modelarlo en SQL implica columnas nulas para la mayoría de las filas, o tablas adicionales por posición. Cada incorporación de una métrica nueva requiere un `ALTER TABLE` en producción, operación riesgosa sobre un sistema en vivo.

### Partidos y Eventos

Los eventos se modelarían como una tabla con claves foráneas a jugador, equipo y partido. La escritura no representa un problema: mil eventos distribuidos en noventa minutos equivalen a aproximadamente 0,2 inserciones por segundo, carga que ningún motor considera significativa.

El costo aparece en la lectura. Las consultas de interés recorren cadenas de relaciones de profundidad variable: identificar qué jugadores asistieron goles a un delantero determinado en partidos donde el rival terminó con un jugador expulsado exige encadenar JOINs sobre las mismas tablas de forma repetida. Cada nivel de profundidad agrega un JOIN adicional, y la profundidad no siempre se conoce al escribir la consulta: el costo de la consulta crece con cada salto de la cadena, por la forma en que se accede al dato, no por su volumen.

### Usuarios y Sesiones

Cada request de cada uno de los 2–3 millones de usuarios activos requiere verificar un token de sesión. En SQL esto implica una consulta indexada con acceso a disco más el overhead transaccional correspondiente, multiplicado por millones de operaciones por segundo.

Conviene precisar un punto: el problema no es que las lecturas bloqueen a las escrituras, sino el volumen sostenido de operaciones: aun resolviéndose cada verificación de sesión en pocos milisegundos, la latencia acumulada de millones de verificaciones simultáneas compromete el objetivo de 100 ms bajo carga concurrente. Agregar réplicas de lectura alivia las consultas pero no las escrituras de creación y cierre de sesión.

### Comentarios

Una tabla con claves foráneas a partido y usuario. El problema es el pico concurrente: durante un partido de alta audiencia, las escrituras simultáneas saturan la capacidad de un servidor único, generando encolamiento creciente y degradación de la latencia.

La respuesta natural sería distribuir la carga entre varios servidores, pero las claves foráneas hacia partidos y usuarios lo dificultan: garantizar integridad referencial exige que las filas relacionadas sean accesibles desde el nodo que valida la restricción, lo que introduce coordinación entre nodos en cada escritura.

### Estadísticas

Se modelarían con una columna por métrica o mediante el patrón EAV (*Entity-Attribute-Value*). La primera opción impide agregar métricas nuevas sin modificar el esquema; la segunda resulta lenta para agregaciones, ya que reconstruir una métrica exige recorrer múltiples filas por punto de dato.

Con 10 millones de puntos por partido, las consultas de agregación por período —el promedio de posesión entre los minutos 1 y 45— requieren recorrer volúmenes muy grandes de filas. SQL no incorpora primitivas de ventana temporal ni compresión específica para series de datos, funciones que deberían implementarse en la aplicación.

### Auditoría

Una tabla append-only funciona correctamente en principio: el patrón de escritura es simple y no hay actualizaciones. El problema es el volumen acumulado, que excede la capacidad de almacenamiento de un servidor único. Sin particionamiento, las consultas sobre el histórico se vuelven inviables, y el particionamiento manual en SQL implica trabajo operativo continuo.

### Problema transversal: distribución geográfica

Con sedes en seis países de tres continentes, los datos deben servirse cerca del usuario. Existen soluciones SQL distribuidas —replicación lógica en PostgreSQL, CockroachDB, Spanner—, de modo que sería incorrecto afirmar que SQL no puede distribuirse.

El problema real es el costo de mantener consistencia fuerte al hacerlo: una escritura que necesita confirmación de nodos ubicados en otros continentes agrega una latencia de coordinación que compite directamente con el objetivo de 100 ms para el 95% de las consultas. El sistema debe decidir, para cada tipo de dato, si esa garantía justifica su costo — es decir, si necesita ACID o si le alcanza con BASE.

## Sección 3: Propuesta de modelos NoSQL

### Equipos y Jugadores → Documental (MongoDB)

Un documento contiene el equipo completo con su plantel embebido, de modo que obtener toda la información de una selección es una sola lectura sin JOINs. El esquema flexible permite que arqueros y delanteros tengan atributos distintos sin columnas nulas ni migraciones.

*Alternativas descartadas:* Cassandra, cuya arquitectura orientada a escritura masiva es innecesaria para datos estáticos de bajo volumen; Redis, que no permite consultas por atributos —buscar delanteros con más de diez goles requeriría recorrer todas las claves.

### Partidos → Relacional (PostgreSQL), con proyección en Neo4j

Es la única entidad que se mantiene en un motor relacional. El resultado oficial requiere que el cierre de un partido sea atómico —resultado, clasificado y tabla de posiciones se actualizan en conjunto o no se actualizan— y no admite una ventana durante la cual distintos usuarios vean marcadores contradictorios.

*Alternativa descartada:* solo Neo4j, que no ofrece la garantía de consistencia inmediata que exige un resultado oficial.

> **Nota de trazabilidad (no está en el PDF original):** esta decisión se revisó en el Hito 2 — ver [`../hito-2-matriz-decision/hito-2-matriz-decision.md`](../hito-2-matriz-decision/hito-2-matriz-decision.md), sección "Revisión de una decisión del Hito 1". Partidos terminó en **Objetos (IRIS)**, no en un relacional ni en MongoDB.

### Eventos → Grafo (Neo4j)

Cada evento es en sí mismo una relación entre entidades: ANOTA vincula jugador con partido, ASISTE vincula jugador con jugador. Un grafo las modela de forma nativa, y recorrerlas es una operación directa en lugar de una cadena de JOINs anidados. La justificación no es el volumen —que es bajo— sino la densidad relacional del dato.

*Alternativas descartadas:* MongoDB, donde los arrays anidados permiten almacenar las relaciones pero limitan su consulta en profundidad; Cassandra, sin soporte nativo para recorrido de relaciones.

### Usuarios → Documental (MongoDB) con caché en Redis

El perfil de usuario es dato persistente: preferencias, idioma y configuración no pueden perderse ante una caída. Al mismo tiempo se lee en cada request. La combinación resuelve ambos requisitos: MongoDB garantiza durabilidad y esquema flexible, y Redis absorbe el volumen de lecturas.

*Alternativas descartadas:* solo Redis, que expone los perfiles a pérdida ante una caída del nodo; PostgreSQL, que no aporta ventajas sobre MongoDB para un dato sin relaciones complejas.

### Sesiones → Clave-valor (Redis)

Una sesión es exactamente un par clave-valor con vencimiento. Redis opera en memoria con latencia inferior al milisegundo, la velocidad que exige verificar un token en cada request de 2 a 3 millones de usuarios. La pérdida de sesiones ante una caída es aceptable: el usuario vuelve a autenticarse, así que no hace falta la consistencia fuerte de otros modelos — es un caso BASE.

*Alternativas descartadas:* MongoDB, con latencia excesiva para verificar el token en cada request; Cassandra, innecesariamente compleja para acceso por clave única.

### Comentarios → Columnar (Cassandra)

Cualquier nodo puede aceptar escrituras, sin punto único de fallo, y la escala horizontal es lineal: es la propiedad de escalabilidad que este volumen de escritura necesita, muy por encima de lo que sostiene un servidor único.

Sobre el riesgo de concentración: repartir la carga por un único criterio de acceso (el partido) arriesga concentrar el millón de comentarios de la final en una sola porción del sistema, mientras el resto permanece ocioso. Cómo particionar en concreto para evitarlo es una decisión de diseño distribuido que corresponde al hito de arquitectura, no a esta etapa; alcanza con señalar acá que el modelo columnar admite resolverlo sin cambiar de motor.

*Alternativas descartadas:* MongoDB, no optimizado para escritura masiva a esta escala; InfluxDB, apropiado para datos numéricos temporales pero no para texto.

### Auditoría → Columnar (Cassandra)

Escritura append-only continua distribuida entre nodos, con durabilidad garantizada y escala horizontal. Se particiona por ventana temporal combinada con el identificador de la entidad afectada, dado que la auditoría registra operaciones del sistema en general y no de un partido en particular.

*Alternativas descartadas:* particionar por `partido_id`, inaplicable porque la mayoría de las operaciones auditadas no pertenecen a ningún partido; PostgreSQL, cuyo volumen acumulado excede la capacidad de un servidor único.

### Entidades complejas → Objetos (IRIS)

Los eventos presentan subtipos con atributos y reglas propias: Gol, Tarjeta y Cambio comparten estructura común pero difieren en sus campos específicos. El modelo de objetos representa esa jerarquía de forma directa: una estructura común con partes específicas por tipo, sin las columnas vacías que exigiría forzarlo en un esquema fijo.

Se propone una división de responsabilidades: IRIS mantiene la definición de los tipos de evento y sus reglas de validación, mientras que Neo4j almacena las instancias y sus relaciones. IRIS modela el esquema del dominio; Neo4j, lo ocurrido durante los partidos.

*Alternativas descartadas:* MongoDB, que puede simular herencia mediante un campo discriminador pero pierde el tipado y la lógica encapsulada; Neo4j, que modela las relaciones pero no la jerarquía de tipos.

### Estadísticas en vivo → Series temporales (InfluxDB)

El timestamp es la dimensión principal del dato. InfluxDB está optimizada para la ingesta continua de volúmenes altos de puntos y para las consultas por ventana temporal, que es exactamente el acceso dominante de este dato — la posesión entre el minuto 1 y el 45. Sostiene los más de 10 millones de puntos por partido sin la reconstrucción fila por fila que exigiría un modelo genérico.

*Alternativas descartadas:* Cassandra, que puede almacenar series temporales pero carece de funciones de agregación temporal; MongoDB, no optimizado para consultas de ventana sobre millones de puntos.

## Sección 4: Conclusión

Una arquitectura exclusivamente relacional no resulta adecuada para el Fixture 2030 por tres razones. Primero, escalabilidad: el escalado vertical tiene un techo físico que no absorbe 2–3 millones de usuarios simultáneos ni 100.000 requests por segundo, mientras que el escalado horizontal sobre hardware convencional permite crecer de forma incremental. Segundo, rendimiento bajo carga: la reconstrucción de entidades mediante JOINs y el overhead transaccional por request generan latencia incompatible con el umbral de 100 ms. Tercero, distribución geográfica: mantener consistencia fuerte entre seis países exige coordinación entre nodos remotos cuya latencia compite con ese mismo umbral.

La solución propuesta es una arquitectura políglota, que asigna a cada subsistema el modelo de datos correspondiente a la naturaleza de su acceso. El sistema adopta mayoritariamente el paradigma BASE (*Basically Available, Soft state, Eventually consistent*), priorizando disponibilidad y rendimiento sobre consistencia inmediata —decisión válida para una plataforma de entretenimiento en vivo.

### El caso híbrido: el resultado oficial de los partidos

El resultado oficial de un partido no admite consistencia eventual: si distintas réplicas se actualizan a distinto ritmo, dos usuarios pueden ver marcadores contradictorios al mismo tiempo. Por eso la entidad Partidos vive en SQL, y ningún resultado se considera oficial hasta que la transacción confirma. Una vez confirmada, el cambio se propaga a Neo4j, que responde las consultas de relaciones que en SQL serían JOINs anidados.

El costo de esta duplicación es que el grafo puede quedar desactualizado si la propagación falla, y no se corrige solo: el sistema necesita reintentos o un proceso de reconciliación periódica.

### Matriz de decisión (Hito 1)

| Modelo | Tecnología | Entidades | Criterio determinante |
|---|---|---|---|
| Relacional | PostgreSQL | Partidos | Atomicidad y consistencia inmediata |
| Documental | MongoDB | Equipos, Jugadores, Usuarios | Esquema flexible, lectura sin JOINs |
| Grafo | Neo4j | Eventos y relaciones | Densidad relacional del dato |
| Clave-valor | Redis | Sesiones, caché de perfiles | Latencia mínima y TTL nativo |
| Columnar | Cassandra | Comentarios, Auditoría | Escritura masiva distribuida |
| Objetos | IRIS | Jerarquía de tipos de evento | Herencia y composición nativas |
| Series temporales | InfluxDB | Estadísticas en vivo | Timestamp como dimensión principal |

**Próximos pasos (según el Hito 1):** Clase 2, refinamiento de la matriz de decisión. Clase 3, implementación en MongoDB. Clase 4, implementación en Neo4j.

---

## Historial de revisión

**26/09/2026 — corrección de alcance (ver [`correcciones-profesor.md`](./correcciones-profesor.md)).** El profesor marcó que el documento adelantaba mecanismos internos no vistos hasta la Clase 1 (MVCC, CTEs recursivas, consenso multi-región, arquitectura peer-to-peer, diseño de clave de partición compuesta, TTL, downsampling, herencia de objetos en IRIS) y pedía justificar solo con volumen, velocidad, acceso, esquema, escalabilidad y ACID/BASE. Se reescribieron los pasajes de la Sección 2 (Usuarios y Sesiones, Partidos y Eventos, distribución geográfica) y la Sección 3 (Comentarios, Sesiones, Estadísticas en vivo, Entidades complejas) para justificar con esas seis dimensiones únicamente, sin nombrar el mecanismo interno de ningún motor ni proponer un diseño de partición concreto. **No cambió ninguna entidad, modelo elegido, alternativa descartada ni la matriz de decisión** — es una corrección de nivel de detalle, no de arquitectura.
