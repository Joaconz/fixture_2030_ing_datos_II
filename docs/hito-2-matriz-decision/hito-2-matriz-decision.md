# Hito 2: Matriz de Decisión Tecnológica

**Plataforma Fixture Mundial 2030 — Ingeniería de Datos II**

**Alumnos:** Santiago Pazos, Joaquín Núñez y Valentina Frisoli · **Profesor:** Joaquín Salas · **Fecha:** 14 de agosto de 2026

**Anexo:** `Grupo_N_Hito_2_Matriz_Decision_Fixture2030.xlsx` (matriz completa con fórmulas — no está en este repositorio)

> Transcripción fiel del PDF entregado (`Grupo_N2_Hito_2_Matriz_Decision_Fixture2030.pdf`). Es un documento histórico: registra lo que se entregó y evaluó en su momento. Las correcciones del profesor están en [`correcciones-profesor.md`](./correcciones-profesor.md), no se editan acá.
>
> **Este documento es la fuente canónica de la matriz Hito 2.** Ante cualquier discrepancia con la transcripción que hace el Hito 3 de esta misma matriz, gana este documento — el Hito 3 tuvo un caso así (N2 Partidos) y ya está corregido, ver "Historial de revisión" en [`../hito-3-arquitectura-distribuida/hito-3-arquitectura-distribuida.md`](../hito-3-arquitectura-distribuida/hito-3-arquitectura-distribuida.md).

---

## 1. Síntesis del diagnóstico inicial

El Hito 1 identificó nueve entidades y una asimetría que condiciona toda la selección tecnológica: los datos del torneo son de volumen reducido y prácticamente fijos, mientras que los que generan los usuarios crecen varios órdenes de magnitud durante los partidos. 64 equipos y 1.500 jugadores conviven con 2 a 3 millones de sesiones simultáneas y un millón de comentarios por partido de alta audiencia. De ahí que no exista un criterio único de selección para toda la plataforma: lo que restringe un extremo es irrelevante en el otro.

Los límites del modelo relacional tampoco son los mismos en todos los casos. En equipos y jugadores el problema es el esquema: los atributos que importan cambian según la posición, y una estructura fija obliga a dejar columnas vacías o a rehacerla cada vez que aparece una métrica nueva. En eventos el problema es el acceso: las consultas encadenan vínculos entre entidades y la cantidad de saltos no siempre se conoce al escribirlas. En sesiones y comentarios el problema es la escala: 2 a 3 millones de verificaciones y más de un millón de escrituras por partido superan lo que sostiene un servidor único. Tres problemas distintos, tres criterios de selección distintos: por eso la matriz pondera cada necesidad por separado.

Las restricciones transversales del escenario actúan sobre todas las necesidades, aunque no con la misma intensidad: 2 a 3 millones de usuarios simultáneos, más de 100.000 solicitudes por segundo en picos, latencia por debajo de 100 ms para el 95% de las consultas críticas, 99,99% de disponibilidad y operación en seis países. La distribución geográfica es la que más pesa sobre la decisión, porque sostener garantías fuertes de consistencia entre regiones tiene un costo de tiempo que compite con ese mismo objetivo de 100 ms. La pregunta para cada subsistema, entonces, es si necesita ACID o si le alcanza con BASE.

### Necesidades priorizadas

| Necesidad | Volumen | Acceso dominante | Restricción que condiciona la elección |
|---|---|---|---|
| N1 Equipos y jugadores | 64 / 1.500+ | Lectura frecuente | Los atributos varían según la posición del jugador |
| N2 Partidos | 127 | Escritura al cierre | El resultado oficial exige ACID, no tolera BASE |
| N3 Eventos | ~127.000 | Recorrido de vínculos | El dato es la vinculación entre entidades |
| N4 Usuarios | 2–3 M | Lectura en cada solicitud | Padrón creciente servido desde seis países |
| N5 Sesiones | 2–3 M simultáneas | Acceso por clave | Velocidad de respuesta frente al objetivo de 100 ms |
| N6 Comentarios | 1 M+ por partido | Escritura masiva | Carga concentrada en 90 minutos |
| N7 Estadísticas en vivo | 10 M+ puntos/partido | Consulta por período | El momento de generación es la dimensión principal |
| N8 Entidades complejas | Catálogo acotado | Recuperación integral | Tipos con estructura en parte común y reglas propias |
| N9 Auditoría e históricos | ~260 TB / torneo | Escritura continua | Volumen por encima de un servidor único |

Evaluamos nueve necesidades y no los siete grupos mínimos, porque el diagnóstico separa dos pares con comportamientos opuestos. Partidos y Eventos comparten dominio pero no acceso: uno se lee y se escribe como entidad completa, el otro se recorre siguiendo vínculos. Usuarios y Sesiones tampoco son lo mismo, el perfil es dato persistente que no puede perderse y la sesión es dato transitorio cuya pérdida es aceptable. Evaluarlos juntos forzaría una decisión única sobre necesidades que la matriz resuelve distinto.

> **Revisión de una decisión del Hito 1.** En el Hito 1 asignamos Partidos a un motor relacional, con el argumento de que solo un relacional garantiza atomicidad y consistencia inmediata. La Clase 2 mostró que la premisa era falsa: varios de los modelos NoSQL estudiados ofrecen garantías ACID. El requisito sigue en pie, el resultado oficial no admite que dos usuarios vean marcadores distintos, pero no obliga a usar un relacional. Partidos se re-evalúa acá entre los seis modelos, y el resultado cambió respecto de lo que suponíamos. Dejamos constancia para que la trazabilidad entre hitos sea verificable.

## 2. Criterios y método de evaluación

Definimos seis criterios, uno por cada dimensión de análisis trabajada en clase, para que la comparación sea homogénea entre necesidades y ninguna dimensión quede afuera. El alcance de la evaluación se limita a esas dimensiones: comparamos modelos por cómo tratan el dato, no por sus mecanismos internos ni por decisiones de implementación, que corresponden a los hitos siguientes.

| Criterio | Qué mide | Tipo |
|---|---|---|
| 1. Esquema | Estructura del dato y cuánto varía entre instancias | De ajuste |
| 2. Acceso | Operación dominante: lectura integral, búsqueda por atributo, acceso por clave, recorrido de vínculos o consulta por período | De ajuste |
| 3. Volumen | Cantidad de datos que el modelo debe sostener | Del modelo |
| 4. Velocidad | Rapidez de respuesta de una operación y ritmo de generación que admite | Del modelo |
| 5. Escalabilidad | Capacidad de crecer repartiendo la carga entre varios servidores | Del modelo |
| 6. Consistencia | Garantías que ofrece el modelo entre los extremos ACID y BASE | Del modelo |

Los dos primeros son criterios **de ajuste**: se puntúan distinto en cada necesidad, porque miden el encaje entre un modelo y un dato concreto. El modelo documental representa un plantel con un 5 y una red de eventos con un 3, siendo el mismo modelo. Los cuatro restantes son **propiedades del modelo** y llevan la misma puntuación en toda la matriz. Esa separación evita el error más común del método: mover las puntuaciones hasta que den el resultado que uno ya quería.

Volumen y escalabilidad quedan separados a propósito, porque suelen confundirse: el volumen es cuánto dato hay que sostener, la escalabilidad es cómo se reparte ese crecimiento entre servidores. Las estadísticas en vivo tienen volumen enorme y crecimiento previsible; los comentarios tienen menos volumen total pero una concentración que obliga a repartir. Si un modelo sacara siempre lo mismo en ambos criterios, uno de los dos sobraría.

### Alternativas comparadas

La comparación se hace entre los seis modelos de la Clase 2, no entre productos. Cada columna de la matriz identifica un modelo y consigna su tecnología de referencia únicamente para dejar claro a qué se alude, pero ninguna puntuación se justifica por características de un producto en particular.

| Modelo | Tecnología de referencia | Rasgo que lo distingue en esta comparación |
|---|---|---|
| Documental | MongoDB | Estructura variable entre instancias y lectura integral de una entidad |
| Grafo | Neo4j | El vínculo entre entidades es parte del dato y se recorre |
| Clave-valor | Redis | Acceso directo por clave, con la mayor velocidad de respuesta |
| Columnar | Cassandra | Escritura repartida entre servidores y crecimiento sostenido |
| Objetos | InterSystems IRIS | Entidades con partes y reglas propias, con garantías ACID |
| Series temporales | InfluxDB | Datos generados de forma continua y consultados por período |

### Escala de valoración y ponderación

Las puntuaciones van de 1 a 5. Un **5** significa que el modelo está pensado para ese caso; **4**, que lo resuelve bien con alguna limitación menor; **3**, que lo resuelve pero exige trabajo adicional en la aplicación; **2**, que lo soporta forzándolo, con costo evidente; y **1**, que no corresponde a ese caso. Cada nivel lleva descripción explícita para que los tres integrantes puntúen igual y otro grupo pueda reconstruir el razonamiento.

Los pesos suman 100% *dentro de cada necesidad*, no en el total de la matriz. Un peso único para toda la plataforma sería un error de método: la velocidad es determinante en Sesiones, donde cada solicitud de 2 a 3 millones de usuarios verifica un identificador contra un objetivo de 100 ms, y es marginal en Auditoría, que se escribe de forma continua y se lee rara vez. Con un peso común habría que compensar esa diferencia forzando las puntuaciones, y el resultado saldría bien por las razones equivocadas.

Para que los pesos no queden a ojo, adoptamos una escala cerrada de seis niveles: **determinante 30%**, si el modelo falla ahí la necesidad no se cumple; **alto 25%**, impacta directo en un requisito del escenario; **medio-alto 20%**; **medio 15%**, relevante pero no decide; **medio-bajo 10%**; y **bajo 5%**, se considera y nada más. Cada asignación cita un dato del Hito 1, así la ponderación es trazable y no una preferencia nuestra. Las justificaciones individuales están en la planilla anexa.

### Verificaciones aplicadas

Antes de aceptar los resultados pasamos la matriz por tres controles. El primero, la **suma de pesos**, verificada por fórmula en cada necesidad. El segundo, el **control de margen**: toda decisión en la que el primero y el segundo quedan a menos de 0,20 puntos se marca como frágil y exige un argumento adicional, porque a esa distancia el resultado depende de una sola celda. El tercero, el **control de resultado preconcebido**: asignamos los pesos antes de puntuar, y si ninguna decisión hubiera diferido del Hito 1 habría tocado revisarlos por sospecha de ajuste retroactivo. Dos decisiones difirieron.

## 3. Matriz de decisión

La matriz completa va en la planilla anexa: seis criterios con su peso y su justificación, la puntuación de los seis modelos en cada una de las nueve necesidades, y el resultado ponderado calculado por fórmula. Acá consolidamos los resultados; la celda destacada marca el modelo seleccionado.

| Necesidad | Documental | Grafo | Clave-valor | Columnar | Objetos | Temporal | Criterio determinante | Margen |
|---|---|---|---|---|---|---|---|---|
| N1 Equipos y jugadores | **4,40** | 3,40 | 2,10 | 2,75 | 4,00 | 2,30 | Esquema (30%) | 0,40 |
| N2 Partidos | 4,15 | 3,45 | 3,20 | 3,20 | **4,25** | 2,65 | Consistencia (30%) | **0,10** |
| N3 Eventos | 3,05 | **4,25** | 2,10 | 2,50 | 3,75 | 2,30 | Esquema (30%) | 0,50 |
| N4 Usuarios | **4,10** | 2,80 | 3,45 | 4,00 | 3,70 | 2,85 | Escalabilidad (25%) | **0,10** |
| N5 Sesiones | 3,30 | 2,30 | **4,35** | 4,00 | 3,25 | 3,05 | Velocidad (30%) | 0,35 |
| N6 Comentarios | 3,65 | 2,00 | 3,00 | **4,70** | 2,95 | 3,85 | Escalabilidad (30%) | 0,85 |
| N7 Estadísticas en vivo | 3,10 | 1,70 | 2,45 | 3,95 | 3,20 | **4,75** | Esquema (30%) | 0,80 |
| N8 Entidades complejas | 3,60 | 2,95 | 2,25 | 2,35 | **4,60** | 2,15 | Esquema (30%) | 1,00 |
| N9 Auditoría e históricos | 3,70 | 2,25 | 2,30 | **4,50** | 3,35 | 4,00 | Volumen (30%) | 0,50 |

**Nota para lectura automática (validar-hito / auditar-hito):** la fila **N2 Partidos** gana **Objetos (IRIS) con 4,25**, por 0,10 sobre Documental (4,15). La fila **N4 Usuarios** gana **Documental (MongoDB) con 4,10**, por 0,10 sobre Columnar (4,00). Cualquier documento posterior que afirme un ganador distinto para N2 o N4, o un margen distinto de 0,10 para cualquiera de las dos, contradice esta tabla — que es la fuente.

Como muestra del detalle que hay en la planilla, va la primera necesidad desagregada.

| N1 — Equipos y jugadores | Peso | Documental | Grafo | Clave-valor | Columnar | Objetos | Temporal |
|---|---|---|---|---|---|---|---|
| 1. Esquema | 30% | 5 | 3 | 1 | 2 | 4 | 1 |
| 2. Acceso | 25% | 5 | 4 | 1 | 2 | 4 | 1 |
| 3. Volumen | 10% | 4 | 2 | 2 | 5 | 3 | 5 |
| 4. Velocidad | 15% | 3 | 3 | 5 | 4 | 4 | 5 |
| 5. Escalabilidad | 5% | 4 | 2 | 3 | 5 | 3 | 4 |
| 6. Consistencia (ACID/BASE) | 15% | 4 | 5 | 3 | 2 | 5 | 2 |
| **Resultado ponderado** | **100%** | **4,40** | 3,40 | 2,10 | 2,75 | 4,00 | 2,30 |

**Resultado del control de margen.** Siete de las nueve decisiones se resuelven con holgura. Dos quedan por debajo del umbral de 0,20 y las señalamos como frágiles: **N2 Partidos**, donde el modelo de objetos aventaja al documental por **0,10**, y **N4 Usuarios**, donde el documental aventaja al columnar por la misma diferencia. En ambos casos el resultado se apoya en una sola celda de la matriz, así que la Sección 4 agrega un argumento que no depende del puntaje.

## 4. Justificación de decisiones y alternativas

### N1 · Equipos y jugadores → Documental (MongoDB, 4,40)

Manda el esquema. Los atributos que importan de un jugador cambian según su posición, y el modelo documental admite que dos jugadores del mismo plantel tengan campos distintos sin dejar columnas vacías ni rehacer la estructura. El acceso acompaña: el equipo y su plantel se guardan juntos, así que leer una selección completa es una sola operación, y también se puede buscar por atributo. Volumen y escalabilidad casi no pesan, con 64 equipos y 1.500 jugadores fijos. La alternativa más cercana es el modelo de objetos con 4,00, que representa igual de bien un dato con partes variables y ofrece garantías ACID más firmes. *Trade-off aceptado:* ganamos libertad para cambiar la estructura sin migrar los datos existentes, y cedemos control sobre esa misma estructura. Nada garantiza desde el modelo que todos los arqueros lleven los mismos campos: esa validación queda del lado de la aplicación.

### N2 · Partidos → Objetos (IRIS, 4,25)

El criterio determinante es la consistencia, con 30%. Al cerrar un partido se actualizan resultado, clasificado y tabla de posiciones en conjunto, y no puede haber un momento en el que dos usuarios vean marcadores distintos: es un caso que exige ACID y no tolera BASE. El modelo de objetos ofrece esas garantías y representa el partido como una entidad con sus partes, que es como se lo consulta. El volumen no interviene, son 127 partidos que no crecen. Quedó a **0,10 puntos** el modelo **documental con 4,15**, que también ofrece garantías ACID y gana en escalabilidad. *Trade-off aceptado:* priorizamos la garantía ACID sobre la escalabilidad, y podemos hacerlo porque el conjunto de partidos está acotado de antemano. El costo es que Partidos queda separado de Equipos y Jugadores, con los que se consulta a menudo. **Es la decisión más ajustada de la matriz** y la señalamos como tal.

> **Resuelto en el Hito 3** (a pedido de la corrección de este hito — ver [`correcciones-profesor.md`](./correcciones-profesor.md)): el análisis CAP no vuelve a puntuar, pregunta qué exige el requisito en sí. La consistencia que exige el cierre de un partido es la misma para Documental que para Objetos, así que CAP no desempata por sí solo — pero agrega que la topología (un único nodo autoritativo por partido, sin escritura multi-región) es igual de viable en cualquiera de los dos motores, lo que confirma que el margen de 0,10 no compromete nada crítico. Se sostiene Objetos (IRIS). Detalle en [`../hito-3-arquitectura-distribuida/hito-3-arquitectura-distribuida.md`](../hito-3-arquitectura-distribuida/hito-3-arquitectura-distribuida.md), sección "N2 · Partidos — validación independiente de la decisión frágil".

### N3 · Eventos → Grafo (Neo4j, 4,25)

Un evento vincula jugador, equipo y partido: el vínculo no es un accesorio del dato, es el dato. El modelo de grafo lo representa tal cual, y las consultas que encadenan varios saltos, sin saber de antemano cuántos, son su operación natural. Lo que decide acá es el esquema y el acceso, no el volumen: 127.000 eventos en todo el torneo no exigen a ningún modelo, y por eso volumen y escalabilidad quedan en los pesos más bajos. La alternativa es el modelo de objetos con 3,75, que también representa entidades vinculadas entre sí, pero no está pensado para recorrerlas en profundidad variable. *Trade-off aceptado:* el grafo es el modelo con peor puntuación de volumen y escalabilidad de los seis. En cualquier otra necesidad eso sería descalificante; acá lo tolera un volumen que está acotado por la cantidad de partidos.

### N4 · Usuarios → Documental (MongoDB, 4,10)

El peso mayor va a la escalabilidad: 2 a 3 millones de perfiles servidos desde seis países, con un padrón que crece de forma sostenida. El modelo documental sostiene ese crecimiento repartiendo la carga y, al mismo tiempo, admite que preferencias, idioma y configuración varíen de un usuario a otro. La consistencia pesa poco, el perfil no puede perderse pero tolera propagarse con demora. El modelo **columnar quedó a 0,10 puntos, con 4,00**: gana en volumen y escalabilidad, y pierde en esquema y en acceso, porque el perfil se busca de formas que no siempre están previstas. *Trade-off aceptado:* resignamos parte de la capacidad de crecimiento a cambio de libertad para consultar el perfil por distintos campos. **Es la segunda decisión ajustada de la matriz**: si el padrón creciera bastante más de lo estimado, correspondería revisarla.

> **Resuelto en el Hito 3** (mismo pedido de evidencia, ver [`correcciones-profesor.md`](./correcciones-profesor.md)): Usuarios es un caso AP —el perfil tolera propagarse con demora—, así que sacrificar disponibilidad por consistencia inmediata iría en contra de lo que pide el escenario. Documental y Columnar pueden operar los dos en modo AP eventual, así que CAP tampoco desempata por puntaje acá. Lo que sí agrega peso a Documental es la topología: Equipos y Jugadores ya requieren un núcleo con escritura coordinada en ese motor, y sumar Usuarios ahí evita un segundo sistema replicado por separado. Se sostiene Documental, con la condición explícita de que se revisaría si el padrón crece muy por encima de lo estimado. Detalle en [`../hito-3-arquitectura-distribuida/hito-3-arquitectura-distribuida.md`](../hito-3-arquitectura-distribuida/hito-3-arquitectura-distribuida.md), sección "N4 · Usuarios — validación independiente de la decisión frágil".

### N5 · Sesiones → Clave-valor (Redis, 4,35)

Una sesión es un identificador y su vigencia, y se verifica en cada solicitud de 2 a 3 millones de usuarios. Por eso la velocidad se lleva el 30% y el acceso el 25%: no hay búsqueda ni recorrido, hay acceso directo por clave, que es exactamente para lo que existe el modelo clave-valor. La consistencia queda en 5% porque el Hito 1 estableció que perder sesiones ante una caída es aceptable, el usuario vuelve a autenticarse: es un caso BASE puro. La alternativa es el modelo columnar con 4,00, que también accede por clave y escala mejor, pero responde más lento en la operación individual. *Trade-off aceptado:* el modelo clave-valor sostiene menos volumen que casi todos los demás. Lo damos por bueno porque cada sesión guarda muy poco: lo que pesa es la cantidad simultánea, no el tamaño del dato.

### N6 · Comentarios e interacciones → Columnar (Cassandra, 4,70)

Manda la escalabilidad, con 30%: más de un millón de comentarios por partido concentrados en 90 minutos no los sostiene un servidor único, y la carga tiene que repartirse. El modelo columnar está construido para escritura repartida entre varios servidores y sostiene el volumen acumulado sin degradarse. La consistencia queda en 5%, un comentario perdido en un pico no compromete la plataforma. La segunda posición la ocupa el modelo de series temporales con 3,85, por sus puntuaciones altas de volumen y escalabilidad, pero no lo consideramos alternativa real: su puntuación de esquema es 2 porque un comentario es texto, no una medición. La alternativa que sí evaluamos es el modelo documental (3,65), que representa mejor el dato pero no sostiene el mismo ritmo de escritura. *Trade-off aceptado:* resignamos garantías de consistencia y libertad de consulta a cambio de absorber el pico. Vale la pena señalar el caso: la matriz ordena por puntaje, pero el segundo puesto no siempre es una alternativa viable.

### N7 · Estadísticas en vivo → Series temporales (InfluxDB, 4,75)

El momento en que se genera cada dato es su dimensión principal, y las consultas son por período: la posesión entre los minutos 1 y 45. Esquema y acceso concentran el 55% del peso, y el modelo de series temporales gana los dos con 5, porque está diseñado exactamente para datos que llegan de forma continua y se leen por ventanas de tiempo. También sostiene los más de 10 millones de puntos por partido. La alternativa es el modelo columnar con 3,95, que aguanta el mismo volumen y ritmo de generación pero no ofrece la consulta por período como operación propia: habría que resolverla en la aplicación. *Trade-off aceptado:* es el modelo más especializado de los seis y el que peor puntúa en consistencia. Lo aceptamos porque una estadística en vivo admite corrección posterior, y porque no vamos a guardar acá ningún dato que no tenga dimensión temporal.

### N8 · Entidades complejas → Objetos (IRIS, 4,60)

Gol, Tarjeta y Cambio comparten parte de su estructura y difieren en el resto, y cada tipo tiene reglas propias que deben cumplirse siempre. Esa combinación —estructura parcialmente común y validación obligatoria— es lo que el modelo de objetos resuelve de forma directa, y explica que gane esquema, acceso y consistencia a la vez. **Es la decisión con mayor margen de toda la matriz**, un punto entero sobre el modelo documental (3,60), que puede guardar los tres tipos en una misma colección pero deja las reglas de cada uno fuera del modelo. *Trade-off aceptado:* el modelo de objetos es el que menos escala de los que sostienen volumen, y lo damos por bueno porque el catálogo de tipos es acotado y no crece con la audiencia. Queda anotado que esta decisión y la de N3 se reparten un mismo dominio: el modelo de objetos define qué es cada tipo de evento, el grafo guarda lo que ocurrió en los partidos.

### N9 · Auditoría e históricos → Columnar (Cassandra, 4,50)

Acá el determinante es el volumen, con 30%: unos 260 TB durante el torneo, por encima de lo que sostiene un servidor único, y con crecimiento que no se detiene al terminar el Mundial. La escalabilidad va detrás con 25%, y el modelo columnar gana los dos con 5. El acceso también acompaña, porque la auditoría se escribe de forma continua y se lee de a períodos. El esquema pesa apenas 5%: el registro tiene estructura mínima y estable. La alternativa es el modelo de series temporales con 4,00, que compite porque cada registro lleva un momento asociado, pero pierde en esquema: una auditoría no es una serie de mediciones. *Trade-off aceptado:* resignamos garantías fuertes de consistencia sobre un dato que, según el propio Hito 1, pierde sentido si se pierde. Es una tensión que dejamos abierta entre las preguntas pendientes.

> **Resuelto en el Hito 3** (la contradicción que señaló la corrección de este hito, ver [`correcciones-profesor.md`](./correcciones-profesor.md)): las dos afirmaciones — "es AP" y "no se puede perder" — son incompatibles solo si se tratan como una propiedad única del sistema. Se separan lectura y escritura: Auditoría sigue siendo AP para la lectura, mientras la escritura se configura con quórum (N=3, R=1, W=QUORUM) para que ninguna escritura confirmada se pierda. No se cambia de modelo — se ajustan sus parámetros de réplica. Detalle en [`../hito-3-arquitectura-distribuida/hito-3-arquitectura-distribuida.md`](../hito-3-arquitectura-distribuida/hito-3-arquitectura-distribuida.md), sección "N9 · Auditoría — resolución de la contradicción".

> **Sobre la coincidencia entre N6 y N9.** Las dos eligen el modelo columnar y podría parecer la misma decisión tomada dos veces. No lo es. En N6 el determinante es la escalabilidad, porque la carga se concentra en 90 minutos y hay que repartirla; en N9 el determinante es el volumen acumulado, que crece de forma sostenida y no se detiene al terminar el torneo. La consistencia también pesa distinto: 5% en comentarios, donde perder uno en un pico no compromete nada, y 15% en auditoría, donde un registro perdido invalida el propósito del subsistema. Mismo modelo, razonamiento distinto. **Implica que, aunque ambas necesidades usen Cassandra, corresponden a keyspaces/tablas separados con criterios de partición propios — no a un mismo módulo.**

## 5. Mapa de persistencia y próximos interrogantes

La plataforma queda con una arquitectura políglota que usa los seis modelos evaluados, cada uno asignado a las necesidades cuyo tratamiento del dato le corresponde. El sistema se apoya mayoritariamente en BASE, priorizando disponibilidad y velocidad de respuesta, y reserva las garantías ACID para los dos casos que no las toleran: el resultado oficial de los partidos y las reglas de los tipos de evento.

| Modelo | Tecnología | Responsabilidad en la plataforma | Criterio determinante |
|---|---|---|---|
| Documental | MongoDB | Equipos y jugadores, Usuarios | Esquema variable y lectura integral |
| Grafo | Neo4j | Eventos y sus vínculos | El dato es la vinculación entre entidades |
| Clave-valor | Redis | Sesiones | Velocidad de respuesta por acceso directo |
| Columnar | Cassandra | Comentarios, Auditoría e históricos | Escalabilidad y volumen sostenido |
| Objetos | InterSystems IRIS | **Partidos, Tipos de evento** | Garantías ACID y estructura con partes propias |
| Series temporales | InfluxDB | Estadísticas en vivo | Generación continua y consulta por período |

El mapa tiene dos puntos de contacto que vale la pena señalar, porque son los que pueden fallar. El primero está entre Partidos y Eventos: el resultado oficial vive en el modelo de objetos y los eventos de ese mismo partido en el grafo, así que el estado de un partido queda repartido entre dos modelos. El segundo está entre Eventos y Tipos de evento: el modelo de objetos define qué es un Gol y el grafo guarda los goles que ocurrieron, y los dos tienen que mantenerse alineados cuando un tipo cambia.

### Preguntas a validar durante la implementación

Sobre la implementación documental de equipos y jugadores, que empieza en el próximo hito:

1. ¿El plantel se guarda junto con el equipo o por separado? Guardarlos juntos favorece el acceso dominante, que es leer la selección completa, pero encarece cualquier consulta que empiece por el jugador y no por el equipo. La respuesta depende de qué consultas aparezcan realmente.
2. ¿Hasta dónde conviene la libertad de esquema antes de volverse un problema? Es el trade-off que aceptamos frente al modelo de objetos: sin control, nada impide que dos jugadores de la misma posición terminen con campos distintos por un error de carga. Hay que definir qué grado de control queremos y dónde vive.
3. ¿Qué operaciones de búsqueda por atributo va a necesitar la plataforma? El criterio de acceso se puntuó suponiendo consultas como la del Hito 1, buscar delanteros con más de diez goles, y conviene confirmar esa suposición antes de avanzar.

Sobre el conjunto de la arquitectura:

4. Las dos decisiones frágiles, N2 y N4, se resolvieron por 0,10 puntos. ¿Qué evidencia nueva las cambiaría? Para N2, que el volumen de partidos deje de ser acotado; para N4, que el padrón crezca bastante por encima de lo estimado.
5. ¿Cómo se mantiene alineado el estado de un partido, repartido entre el modelo de objetos y el grafo? Es la contrapartida directa de haber separado Partidos de Eventos, y el Hito 1 ya advirtió que un desajuste así no se corrige solo.
6. La auditoría quedó en un modelo que se apoya en BASE, sobre un dato que pierde sentido si se pierde. ¿Ese nivel de garantía es suficiente, o la necesidad exige revisar el peso que le dimos a la consistencia?
7. ¿La separación entre Tipos de evento y Eventos justifica mantener dos modelos para un mismo dominio? La matriz la sostiene por puntaje en cada necesidad por separado, pero ninguno de los seis criterios mide lo que cuesta mantener dos modelos alineados.

---

## Historial de revisión

**26/09/2026 — cierre de las tres decisiones que pidió reforzar la corrección del profesor** (N2, N4, N9 — ver [`correcciones-profesor.md`](./correcciones-profesor.md)). Las tres preguntas 4 y 6 de arriba pedían justamente esto. Se agregó, dentro de la justificación de cada una (Sección 4), un párrafo **"Resuelto en el Hito 3"** que resume el argumento que las cerró (análisis CAP para N2 y N4, parámetros N/R/W para N9) y linkea a la sección exacta del documento del Hito 3. No se modificó ninguna puntuación, peso ni modelo elegido de la matriz — el cierre es un puntero a dónde se resolvió, no una re-evaluación.
