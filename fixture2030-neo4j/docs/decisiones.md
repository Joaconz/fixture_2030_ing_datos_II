# Decisiones técnicas — Hito 5 · Módulo de Grafos del Fixture 2030

**Asignatura:** Ingeniería de Datos II · **Grupo 2**
**Integrantes:** Santiago Pazos, Valentina Frisoli, Joaquín Núñez
**Motor:** Neo4j (`neo4j:latest`, Community Edition) · Docker Compose

---

## 1. Problema relacional

El módulo documental del Hito 4 responde muy bien a preguntas *sobre una entidad*: quién es este jugador, qué equipos hay en el grupo A, cuántos delanteros tiene Brasil. Todas se resuelven con un `find` y un índice, y para eso el modelo documental es la elección correcta.

Lo que el Hito 4 **no** puede responder sin reimplementar el recorrido en la aplicación son las preguntas *sobre las conexiones entre entidades*. Las que motivan este hito:

| # | Pregunta del Fixture 2030 | Por qué no alcanza el documento |
|---|---|---|
| P1 | ¿Cuál fue la cadena de pases y asistencias que terminó en el gol del minuto 13? | Los eventos son documentos independientes. La jugada no está en ningún documento: está *entre* los documentos. |
| P2 | ¿En qué estadios, y en qué fechas, juega un futbolista determinado? | Exige tres saltos (jugador → equipo → partidos → sedes) y por lo tanto tres consultas encadenadas o dos `$lookup`. |
| P3 | ¿Qué equipos comparten rival con Argentina sin haberla enfrentado? | Conexión de segundo grado. Requiere dos rondas de `$lookup` y deduplicar en la aplicación. |
| P4 | ¿Qué separa a dos selecciones que nunca se enfrentaron? | Es un problema de camino más corto. No hay consulta documental que lo exprese. |
| P5 | ¿Qué jugador interviene en más jugadas de gol aunque no las convierta? | Es centralidad en una red, no un contador. El goleador aparece en la tabla; el que arma la jugada, no. |
| P6 | ¿Es cierto que ningún evento precede a su causa? | El invariante de consistencia causal del Hito 3 es una propiedad de las relaciones. Sin relaciones, no es verificable. |

El patrón común: **la información valiosa no está en los nodos, está en las aristas.** Cuando el dato que importa es la conexión, guardarla como un campo de referencia obliga a que la lógica de recorrido viva en el código de la aplicación, donde no está indexada, no está validada y no se puede consultar.

Este módulo **no reemplaza** al del Hito 4. Equipos y jugadores siguen siendo del módulo documental — se leen enteros, cambian poco y se filtran por atributo. Acá se los replica solo como puntos de anclaje del recorrido, con la misma identidad, para poder navegar desde y hacia ellos.

---

## 2. Modelo propuesto

Siete etiquetas y nueve tipos de relación. El detalle completo (atributos, tipos, cardinalidades e índices) está en [`modelo_grafo.md`](./modelo_grafo.md); acá va el resumen y la lógica.

**Nodos.** `:Equipo`, `:Jugador`, `:Partido`, `:Sede`, `:Evento`, `:Grupo`, `:TipoEvento`.

**Relaciones y direcciones.**

```
(:Jugador)-[:JUEGA_EN {dorsal, desde, rol}]->(:Equipo)-[:PERTENECE_A]->(:Grupo)
(:Equipo)-[:PARTICIPA_EN {condicion}]->(:Partido)-[:SE_JUEGA_EN]->(:Sede)
(:Partido)-[:CORRESPONDE_A]->(:Grupo)
(:Evento)-[:OCURRE_EN]->(:Partido)
(:Evento)-[:ES_DE_TIPO]->(:TipoEvento)
(:Evento)-[:PROTAGONIZADO_POR]->(:Jugador)
(:Evento)-[:SIGUIENTE_EVENTO]->(:Evento)     ← orden total, dentro del partido
(:Evento)-[:CAUSA_DE]->(:Evento)             ← orden causal, dentro del partido
```

**Criterio de dirección.** Cada relación apunta desde lo que varía hacia lo que es estable: el jugador cambia de equipo, no el equipo de jugador; el partido se asigna a una sede que ya existía; el evento pertenece a un partido. Ese criterio también hace que las direcciones coincidan con el sentido de las referencias del Hito 4 (`jugadores.equipoId → equipos._id`), lo que mantiene la lectura del modelo coherente entre módulos.

**Qué es nodo y qué es relación.** La regla aplicada: es nodo lo que tiene identidad propia y puede ser origen o destino de un recorrido; es propiedad de relación lo que solo describe el vínculo. Por eso `dorsal` y `rol` viven en `JUEGA_EN` (son atributos del vínculo de un jugador con *ese* equipo, no de la persona) y `condicion` vive en `PARTICIPA_EN`.

---

## 3. Decisiones de diseño

### 3.1 Vínculo con los Hitos 1 a 4

| Hito | Qué aportó | Cómo se respeta acá |
|---|---|---|
| **Hito 1/2** | N3 "Eventos" se asignó al modelo de **grafo**; N1 "Equipos y jugadores" al **documental** | El módulo se limita a eventos y programación. Equipos y jugadores se replican como anclas, no se migran. |
| **Hito 2 (N8)** | Los tipos de evento se asignaron a un motor de **objetos**, con prioridad CP | `:TipoEvento` es una **réplica local de solo lectura**, no la fuente autoritativa. |
| **Hito 3** | Eventos = **AP**, consistencia **causal**, partición **por partido**, réplica **multi-región asíncrona** | Ver §3.2, §3.3 y §3.4 — es el eje de este hito. |
| **Hito 4** | **Clave natural** en vez de ObjectId, para permitir cargas idempotentes por upsert | Se reutilizan las mismas claves (`equipos._id` = código FIFA, `jugadores.dni`) y la misma estrategia de idempotencia, ahora con `MERGE`. |
| **Hito 4** | Índices puntuales, solo donde hay una consulta que los justifique | Mismo criterio: 9 índices, cada uno atado a una consulta concreta (§6). |

### 3.2 Cómo este modelo respeta ser un sistema **AP**

El Hito 3 definió Eventos en vivo (N3) como **AP**: ante una partición de red se sacrifica consistencia y se sigue respondiendo. Un modelo de datos no "es" AP por sí solo — el motor lo es —, pero sí puede **hacerlo posible o imposible**. Tres decisiones del modelo son las que lo hacen posible:

**(a) Ninguna escritura necesita leer estado global.** Insertar un evento requiere conocer únicamente su partido y el último número de secuencia *de ese partido*. No hay contador global, no hay `sequence` compartido, no hay ID autoincremental de torneo. Una región aislada puede seguir aceptando eventos de los partidos que se están jugando en ella sin coordinar con nadie. Si el `eventoId` fuera un correlativo global, cada escritura exigiría consenso y el sistema sería **CP por diseño del identificador**, sin importar cómo esté configurado el motor.

**(b) No hay restricciones de unicidad que crucen regiones.** Las siete restricciones son sobre claves que se generan localmente (el `eventoId` lleva el `partidoId` adelante). Una restricción global como "solo puede haber un gol por minuto en el torneo" obligaría a validación distribuida en cada escritura y volvería a romper la disponibilidad.

**(c) Ningún valor derivado se actualiza con incrementos.** El marcador se **recalcula** contando eventos `GOL` (`carga.cypher`, paso 12), no se incrementa. Un `SET p.golesLocal = p.golesLocal + 1` es una operación no idempotente y no conmutativa: al reconciliar réplicas después de una partición, aplicar dos veces el mismo evento daría un resultado incorrecto. Un `SET` a un valor **calculado a partir del conjunto de eventos presentes** converge al mismo resultado sin importar el orden ni la cantidad de veces que se aplique. Eso es lo que hace que la convergencia eventual sea segura.

**Lo que se paga.** El módulo asume que puede haber un intervalo en el que una región no ve todavía un evento ocurrido en otra. La consulta 3.2 de `consultas_grafo.cypher` da la medida de por qué es tolerable: los recorridos frecuentes no cruzan la frontera del partido, así que un evento no propagado degrada un solo timeline, no el resto del torneo.

### 3.3 Cómo se materializa la **consistencia causal**

El Hito 3 la definió como: *"eventual con orden causal — un gol antes que su asistencia; el evento aparece con demora, no al revés"*. Traducirla al modelo exigió separar dos cosas que suelen confundirse:

| | Orden total | Orden causal |
|---|---|---|
| Relación | `SIGUIENTE_EVENTO` | `CAUSA_DE` |
| Qué afirma | "pasó justo después" | "pasó **por causa de**" |
| Se puede reordenar al reconciliar | **sí** — es presentación | **no** — invertirlo es una inconsistencia real |
| Estructura | cadena lineal | grafo dirigido acíclico |

La consistencia causal **solo obliga sobre `CAUSA_DE`**. La sustitución del minuto 62 es posterior al gol del minuto 13, pero no es su consecuencia: si al reconciliar réplicas llega primero, no se violó nada. En cambio, si la asistencia del minuto 13 llegara después del gol que la causó, sí. Modelar las dos relaciones por separado es lo que permite decir exactamente **qué se puede reordenar y qué no**, en lugar de tratar todo el timeline como una única secuencia rígida (lo que sería consistencia fuerte disfrazada, es decir CP).

El mecanismo concreto es el **reloj lógico por partición**: `Evento.secuencia` es un contador monótono local al partido, no un timestamp de reloj de pared. Un sistema AP no puede asumir relojes sincronizados entre regiones; sí puede garantizar un contador monótono dentro de una partición escrita en una sola región de ingesta. Ese contador es lo que ordena la reconciliación.

Y el invariante es **verificable, no declarativo**: la consulta 2.2 de `consultas_grafo.cypher` recorre todas las aristas `CAUSA_DE` y cuenta cuántas violan el orden o cruzan de partición. Debe devolver `0` en ambas columnas. Una afirmación del Hito 3 se convirtió en una aserción ejecutable sobre los datos reales.

### 3.4 Cómo se materializa la **partición por partido**

El Hito 3 definió: *"partición por partido; los eventos de un mismo partido conviven"*. En este modelo eso aparece en cuatro lugares, no solo en un comentario:

1. **En el identificador.** `eventoId = 'PAR-A-2-EV-05'` lleva la clave de partición adelante. El ID es autodescriptivo respecto de dónde vive el dato.
2. **En una propiedad indexada.** `Evento.partidoId` existe además de la relación `OCURRE_EN`. Es la única denormalización deliberada del modelo, y su razón es precisa: la clave de partición tiene que ser **filtrable sin recorrer una arista**, porque en un despliegue real es lo que decide a qué nodo del clúster va la operación — una decisión que se toma *antes* de tocar el grafo.
3. **En el índice compuesto** `(partidoId, secuencia)`, que es el índice central del módulo: acota la lectura del timeline a una sola partición y la devuelve ya ordenada.
4. **En el alcance de las relaciones de orden.** Ni `SIGUIENTE_EVENTO` ni `CAUSA_DE` cruzan de partido — por construcción en la carga (pasos 10 y 11) y auditado en la consulta 2.2. Ninguna cadena causal necesita datos de otra partición, así que **ninguna consulta caliente requiere coordinación entre particiones**.

El punto 4 es el que valida la decisión del Hito 3, y la consulta 3.2 lo muestra empíricamente: durante la fase de grupos, el grafo de rivalidades son **16 componentes conexas aisladas**. La estructura real del torneo ya está particionada; el criterio del Hito 3 no impone una frontera artificial, reconoce una que existe. Si los recorridos frecuentes cruzaran partidos habitualmente, particionar por partido sería una mala decisión — y este modelo permitiría detectarlo.

**Réplica multi-región.** `Sede.region` y `Evento.regionOrigen` (AMERICAS / EUROPA / AFRICA) registran dónde se ingesta cada partición. No es decorativo: con réplica asíncrona multi-región, saber en qué región se originó un evento es lo que permite razonar sobre el *replication lag* que el Hito 3 propuso medir como métrica de los subsistemas AP.

### 3.5 Alternativas consideradas y descartadas

| Decisión | Alternativas | Elección | Por qué |
|---|---|---|---|
| Identidad de jugador | (a) ObjectId de Mongo · (b) `dni` · (c) UUID nuevo | **(b) `dni`** | Es la clave natural que el Hito 4 ya definió con índice único. (a) ataría el grafo a un detalle interno del otro motor, justo lo que la restricción de "no integrar por código" pide evitar. (c) rompería RF5. |
| Condición local/visitante | (a) dos tipos `ES_LOCAL`/`ES_VISITANTE` · (b) un tipo con propiedad · (c) dos propiedades en `:Partido` | **(b)** | (a) obliga a escribir la unión en toda consulta que no distingue condición. (c) haría del partido un documento y perdería la navegabilidad. Costo asumido: la cardinalidad "1 local + 1 visitante" hay que auditarla (consulta 6.4). |
| Orden de eventos | (a) solo `secuencia` como propiedad · (b) solo `SIGUIENTE_EVENTO` · (c) ambas + `CAUSA_DE` | **(c)** | (a) no permite recorrer la jugada. (b) confunde sucesión con causalidad y no distingue qué se puede reordenar. (c) es lo que hace verificable el invariante del Hito 3. |
| Grupo | (a) propiedad `grupo` en `:Equipo` · (b) nodo `:Grupo` | **(b)** | En Mongo la pregunta es "equipos del grupo A" (filtro); en el grafo es "qué separa a estos equipos" (recorrido), y ahí el grupo es un punto de paso. |
| Estadísticas de jugador | (a) replicar `estadisticas` del Hito 4 · (b) derivarlas del grafo | **(b)** | (a) importaría una limitación que el propio Hito 4 documentó (el contador se desincroniza). (b) las hace imposibles de desincronizar y es el argumento concreto de por qué N3 conviene como grafo. |
| Carga | (a) `CREATE` + limpiar antes · (b) `LOAD CSV` · (c) `MERGE` con datos generados | **(c)** | (a) no es idempotente. (b) agrega un artefacto externo sin aportar nada al modelo. (c) es la traducción directa del `bulkWrite` con upsert del Hito 4. |

---

## 4. Datos cargados

### 4.1 Origen

| Entidad | Origen | Coherencia con el Hito 4 |
|---|---|---|
| 64 equipos | Códigos FIFA reales, confederación real, entrenadores reales | `equipoId` = `equipos._id`; enum de confederación idéntico; grupos `A`–`P` (patrón `^[A-P]$`) |
| 1.282 jugadores | Sintéticos, generados con fórmulas deterministas | `dni` con patrón `^[0-9]{7,8}$`; enum de `posicion` idéntico; dorsal 1–99; plantel de 18 a 22 (dentro del rango 15–26 declarado en el Hito 4) |
| 16 sedes | Estadios reales de la candidatura conjunta 2030 (España, Portugal, Marruecos + los tres partidos del centenario en Uruguay, Argentina y Paraguay) | — |
| 112 partidos | Generados: 96 de grupos (16 × 6 cruces) + 16 dieciseisavos | — |
| 1.152 eventos | Generados con 3 guiones deterministas por partido | — |
| 12 tipos de evento | Catálogo N8 replicado | — |

Los jugadores son sintéticos por la misma razón que en el Hito 4: se necesita volumen (>1.000) y no hay una fuente de planteles reales de 2030. Está declarado, igual que allá.

### 4.2 Controles de coherencia

**Determinismo total.** Ni un solo valor usa `rand()`, `randomUUID()`, `timestamp()` ni `datetime()` "de ahora". Todo deriva de fórmulas sobre el índice de la entidad. Es la condición para que la carga sea idempotente de verdad y no solo "sin errores".

**Idempotencia (RNF4).** Todo se escribe con `MERGE` sobre clave natural, con `ON CREATE SET` / `ON MATCH SET`. La verificación es directa: correr `carga.cypher` dos veces y comparar los conteos del paso 14. Deben ser idénticos. Los `MERGE` de relación incluyen la propiedad discriminante en el patrón (`MERGE (e)-[:PARTICIPA_EN {condicion:'LOCAL'}]->(p)`), que es lo que evita que una segunda corrida agregue una arista paralela.

**Valores derivados y no cargados.** El marcador se calcula contando eventos. Los clasificados a dieciseisavos se calculan recorriendo la tabla de posiciones, con desempate final por `equipoId` para que el resultado sea determinista incluso ante empates.

### 4.3 Limitaciones declaradas

- Los planteles y los eventos son sintéticos; no representan datos reales.
- El sorteo de grupos es determinista (`índice % 16`), no el sorteo real: puede haber dos equipos de la misma confederación en un grupo.
- Todos los partidos de grupos siguen uno de tres guiones de eventos. Alcanza para validar los recorridos, pero la distribución de goles no es realista.
- Solo se cargan dieciseisavos, no la eliminatoria completa. Se cargan porque sin ellos el grafo queda desconectado entre grupos y las consultas de camino no tendrían nada que mostrar.
- Community Edition no soporta restricciones de existencia; se sustituyen por auditoría (§6).

---

## 5. Consultas

| Archivo · bloque | Propósito | Saltos | Qué evidencia |
|---|---|---|---|
| `crud` 1.1–1.4 | Alta de partido, jugador y cadena causal completa | — | RF7 (create) |
| `crud` 2.1–2.4 | Lectura puntual, por patrón con filtro y paginación, timeline, tabla de posiciones agregada | 1–3 | RF7 (read) |
| `crud` 3.1–3.4 | Update de nodo, de relación, reasignación estructural de jugador, update masivo acotado | 1–2 | RF7 (update) |
| `crud` 4.1–4.5 | Verificación previa, borrado de relación, de nodo por clave, de subgrafo por partición, verificación posterior | 1–2 | RF7 (delete) + nota del enunciado sobre borrados precisos |
| `consultas` 1.1 | Agenda de un jugador: en qué estadios juega | **3** | **RF8** |
| `consultas` 1.2 | Rivales de mis rivales (segundo grado) | **4** | **RF8** |
| `consultas` 1.3 | Distribución de confederaciones por región de sede | **3** | RF8 |
| `consultas` 2.1 | **Cadena causal completa que llevó a cada gol** | **variable (1–5)** | **Análisis relacional del Hito 3** |
| `consultas` 2.2 | Validación del invariante causal (esperado: 0 y 0) | 1 | Verifica la consistencia causal |
| `consultas` 2.3 | Goleadores y asistidores derivados del grafo | 2 | Contraste con la denormalización del Hito 4 |
| `consultas` 3.1 | Camino más corto entre dos selecciones | variable | **RF9 (camino)** |
| `consultas` 3.2 | Conectividad: cuántos equipos son alcanzables | variable | **RF9 (conectividad)** |
| `consultas` 4.1 | Centralidad de grado en la red de causalidad | variable | **RF9 (centralidad)** |
| `consultas` 4.2 | Centralidad de sedes | 2 | RF9 |
| `consultas` 5.1–5.2 | Cruces de una jornada; conflictos de programación | 2–3 | Programación del fixture |
| `consultas` 6.1–6.7 | Auditoría de integridad (6 chequeos, todos esperan 0) + conteos finales | 1–2 | RNF7, RF11 |

Las capturas de resultados van en `docs/evidencia/`.

---

## 6. Integridad y rendimiento

### 6.1 Integridad

**Lo que garantiza el motor:** 7 restricciones de unicidad, una por entidad, todas sobre clave natural. Impiden duplicados aun con escrituras concurrentes.

**Lo que el motor no puede garantizar en Community Edition:** las restricciones de existencia y de tipo, que son el equivalente de los `$jsonSchema` con `validationLevel: strict` del Hito 4. Quedan escritas y comentadas en `estructura.cypher`.

**Cómo se cubre esa brecha:** con el bloque 6 de `consultas_grafo.cypher`, seis auditorías que deben devolver `0`:

| Chequeo | Qué detecta |
|---|---|
| 6.1 Eventos huérfanos | Un evento sin partición asignada |
| 6.2 Tipos desconocidos | Un evento cuyo tipo no existe en el catálogo N8 |
| 6.3 Jugadores sin equipo | Equivalente al control del Hito 4: "el 100% de los jugadores vinculado a un equipo válido" |
| 6.4 Partidos mal formados | Un partido sin exactamente un local y un visitante (la cardinalidad que el modelo no puede imponer) |
| 6.5 Cadenas rotas | Un evento sin sucesor que no sea el `FIN_PARTIDO` |
| 6.6 Marcador inconsistente | El marcador almacenado no coincide con el conteo de goles del grafo |

Es una degradación consciente: se cambia validación *en escritura* por auditoría *verificable y repetible*. En un despliegue real, además, buena parte de la validación en escritura se pierde igual por ser un sistema AP — la reconciliación ocurre después del hecho.

**Sobre las eliminaciones.** El enunciado advierte que un borrado sin patrón acotado puede destruir el subgrafo. La regla adoptada: toda escritura destructiva filtra por clave natural o por clave de partición, y va precedida de su consulta de verificación (`crud.cypher` 4.1). Los anti-patrones están documentados y comentados en el bloque 5 de ese archivo. Nótese que la partición del Hito 3 también acota el **radio de daño**: borrar por `partidoId` no puede propagarse al resto del torneo.

### 6.2 Rendimiento

**Criterio de indexado**, heredado del Hito 4: no se indexa ningún campo sin una consulta concreta que lo justifique, porque cada índice cuesta escritura y almacenamiento. Nueve índices, cada uno atado a un patrón de acceso (tabla completa en `modelo_grafo.md` §4.2).

**El índice que más importa** es el compuesto `(:Evento) ON (partidoId, secuencia)`. El acceso dominante durante el torneo es el timeline de un partido en orden; con este índice la lectura queda acotada a una partición y llega ya ordenada, sin *sort* en memoria. Es también el índice que hace que el particionamiento del Hito 3 sea operativo y no solo conceptual.

**Recorridos frecuentes y su costo.**

| Recorrido | Estrategia |
|---|---|
| Timeline de un partido | Index seek sobre el compuesto — el más barato |
| Plantel de un equipo | Seek por `equipoId` + expansión de `JUEGA_EN` (~20 aristas) |
| Cadena causal de un gol | Seek + expansión de `CAUSA_DE`, acotada a 5 saltos. **El límite superior en el patrón de longitud variable es obligatorio**: sin él, un ciclo accidental haría explotar la búsqueda |
| Rivales de segundo grado | Expansión de grado 4, acotada por la componente del grupo (4 equipos, 6 partidos) |
| Camino más corto entre equipos | `shortestPath` con cota superior explícita, por la misma razón |

**Verificación del plan.** El equivalente en Neo4j del `explain("executionStats")` del Hito 4 es `PROFILE`. Anteponer `PROFILE` a cualquier consulta muestra `db hits` y filas por operador; lo que hay que buscar es `NodeIndexSeek` en lugar de `NodeByLabelScan` (equivalente de `IXSCAN` vs `COLLSCAN`). La comparación antes/después de crear el índice compuesto va en `docs/evidencia/`.

**Escala.** Con ~2.650 nodes y ~6.600 aristas, el subgrafo entra entero en la *page cache* de 512 MB configurada. El rendimiento acá no prueba nada sobre producción; lo que sí es extrapolable es la **forma** de los recorridos: todos acotados a una partición o a una componente pequeña, ninguno recorriendo el grafo completo.

---

## 7. Análisis relacional

Se seleccionaron dos análisis. El primero es el que da sentido al hito; el segundo es el que valida una decisión del Hito 3.

### 7.1 Centralidad de grado en la red de causalidad

**Consulta:** `consultas_grafo.cypher` 4.1.
**Objetivo:** identificar a los jugadores más determinantes, definiendo "determinante" como *aparecer en más cadenas causales que terminan en gol*, no como *convertir*.

**Cómo se calcula:** para cada jugador se cuentan los goles distintos alcanzables desde algún evento suyo por `CAUSA_DE*1..4`. Es centralidad de grado sobre el subgrafo de causalidad, calculada en Cypher puro para no depender de la versión de GDS que traiga `latest`.

**Qué información aporta que no se ve de otro modo:** el perfil del jugador con **centralidad alta y goles cero** — el mediocampista que inicia las jugadas pero no las termina. En la tabla de goleadores del módulo documental ese jugador no existe: `estadisticas.goles = 0`. Acá aparece arriba, porque el dato que lo revela no es un atributo suyo, es su **posición en la red de jugadas**. Es el ejemplo más claro de la afirmación del enunciado: hay información que solo se obtiene recorriendo relaciones.

**Interpretación en el Fixture 2030:** insumo directo para scouting y para el relato en vivo de la plataforma ("el 60% de los goles de este equipo pasan por el mismo jugador"), una afirmación que no se puede sostener con contadores.

### 7.2 Conectividad del fixture y validación de la partición del Hito 3

**Consultas:** `consultas_grafo.cypher` 3.1, 3.2 y 3.3.
**Objetivo:** medir la estructura de componentes del grafo de rivalidades.

**Resultado:** con solo la fase de grupos, desde cualquier equipo se alcanzan exactamente 3 equipos: los de su propio grupo. **El fixture de grupos no es un grafo conexo: son 16 componentes aisladas de 4 nodos.** Al agregar los dieciseisavos, las componentes se unen y el camino más corto entre equipos de grupos distintos pasa a existir y a ser medible.

**Interpretación en el Fixture 2030 — y por qué importa para la arquitectura:** ese resultado es la **validación empírica de la partición por partido** definida en el Hito 3. La estructura real del torneo ya está fragmentada; la decisión de particionar no impone una frontera artificial, reconoce una que existe en el dominio. Ningún recorrido frecuente (plantel, timeline, jugada del gol, tabla de un grupo) cruza esa frontera, así que ninguna consulta caliente exige coordinación entre particiones — que es exactamente la condición que hace viable un diseño AP sin degradar la experiencia.

Y funciona también como **advertencia**: si en una revisión futura apareciera una consulta frecuente que sí cruza particiones, esta misma medición la haría visible y obligaría a revisar el criterio del Hito 3. El análisis no solo confirma la decisión: da la herramienta para saber cuándo dejaría de ser correcta.

---

## 8. Preguntas abiertas

1. **El catálogo de tipos de evento** está replicado localmente por razones de disponibilidad, pero el Hito 3 lo definió CP en su motor autoritativo. Falta definir el mecanismo y la frecuencia de propagación, y qué hace este módulo si recibe un evento con un tipo que su copia todavía no conoce.
2. **`Evento.partidoId` está denormalizado** respecto de `OCURRE_EN`. Está justificado (§3.4), pero es la única redundancia del modelo y debe auditarse: si divergieran, la propiedad y la arista dirían cosas distintas sobre la partición.
3. **La cardinalidad "1 local + 1 visitante"** no la impone el motor. En Community solo se audita. Es el precio de haber elegido un tipo de relación con propiedad discriminante.
4. **El límite de saltos** en los recorridos de longitud variable (`*1..5`, `*1..4`) está fijado por la profundidad de los guiones de eventos actuales. Con jugadas más largas habría que revisarlo, y conviene medirlo antes de subirlo.
