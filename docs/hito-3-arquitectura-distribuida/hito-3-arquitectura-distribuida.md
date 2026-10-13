# 🏗️ Hito 3 — Arquitectura Distribuida del Fixture 2030

**Plataforma Fixture Mundial 2030 — Ingeniería de Datos II**

**Alumnos:** Santiago Pazos, Joaquín Núñez y Valentina Frisoli

> Este documento transcribe el contenido del Hito 3 (arquitectura distribuida) y queda como contexto persistente del proyecto en el repositorio. Incluye la corrección pedida por la corrección del hito: los parámetros **N/R/W** se expresan de forma explícita únicamente donde la tecnología los expone como parámetro nativo por operación (**Cassandra**); en el resto de los modelos (InfluxDB, MongoDB, Redis) réplica y consistencia se describen conceptualmente.
>
> La entrega original tenía un error en la sección "N2 · Partidos" (decía que Partidos quedó en MongoDB; en realidad quedó en Objetos/IRIS según el Hito 2) que ya está corregido en este documento — ver "Historial de revisión" al final. La corrección real del profesor a este hito (sobre N/R/W en InfluxDB) está en [`correcciones-profesor.md`](./correcciones-profesor.md).
>
> **Reentrega (13/10/2026).** Con el profesor de acuerdo, esta versión **saca el modelo de objetos (IRIS) de la arquitectura**: Partidos (N2) y Tipos de evento (N8) pasan al **grafo (Neo4j)**, junto con Eventos (N3). El resto de las asignaciones del Hito 2 no cambia. La justificación está en la sección [Revisión de la asignación del modelo de objetos](#-revisión-de-la-asignación-del-modelo-de-objetos-reentrega) y el detalle de qué se modificó, en el "Historial de revisión".

---

## 📋 Resumen de decisiones previas

En el Hito 2 se asignó cada necesidad de datos a uno de los seis modelos NoSQL. La tabla siguiente recupera esa asignación, indica las dos que esta reentrega revisa y agrega qué decisión de diseño distribuido quedaba pendiente para este hito.

| Necesidad (Hito 1/2) | Modelo elegido en el Hito 2 | Modelo en esta revisión | Qué quedaba pendiente en Hito 3 |
|---|---|---|---|
| N1 Equipos y jugadores | Documental (MongoDB) | = | Topología de réplicas y alcance de la consistencia en escritura |
| N2 Partidos | Objetos (IRIS) | **Grafo (Neo4j)** | Decisión frágil (margen 0,10). Validar con CAP, no solo con la matriz |
| N3 Eventos | Grafo (Neo4j) | = | Consistencia de las relaciones frente a escrituras concurrentes |
| N4 Usuarios | Documental (MongoDB) | = | Decisión frágil (margen 0,10). Validar con CAP y topología multi-región |
| N5 Sesiones | Clave-valor (Redis) | = | Alcance de la réplica por región y parámetros N, R, W |
| N6 Comentarios | Columnar (Cassandra) | = | Criterio de partición y parámetros N, R, W para el pico |
| N7 Estadísticas en vivo | Series temporales (InfluxDB) | = | Partición por período y estrategia de downsampling |
| N8 Entidades complejas (tipos de evento) | Objetos (IRIS) | **Grafo (Neo4j)** | Alcance de la consistencia frente a Eventos (N3) |
| N9 Auditoría e históricos | Columnar (Cassandra) | = | Contradicción a resolver: BASE vs. "no se puede perder" |

**Sobre el margen de las decisiones frágiles.** El control de margen del Hito 2 fue correcto en señalar N2 y N4: un resultado que depende de 0,10 puntos sobre 5 no es una base sólida por sí sola. Lo que agrega este hito no es una nueva puntuación, sino un criterio de naturaleza distinta — qué exige el teorema CAP para cada necesidad — que puede confirmar la elección por una razón independiente del puntaje, o señalar que conviene revisarla (ver validaciones de N2 y N4 más abajo).

**Sobre la contradicción de Auditoría.** En el Hito 2 conviven dos cosas que no encajan del todo: que un registro de auditoría perdido invalida el propósito del subsistema, y que se elige igual un modelo orientado a BASE. La herramienta para resolverlo sin cambiar de modelo son los parámetros N, R y W: permiten configurar, dentro de un motor que en general prioriza disponibilidad, un comportamiento de escritura con la garantía de durabilidad que este dato necesita (desarrollado más abajo).

---

## 🔄 Revisión de la asignación del modelo de objetos (reentrega)

La matriz del Hito 2 puntuó cada necesidad por separado. Así ganó Objetos en N2 Partidos (4,25, por 0,10 sobre Documental) y en N8 Tipos de evento (4,60, por 1,00). El mismo Hito 2 dejó anotado lo que la matriz no medía: su pregunta 7 dice que "ninguno de los seis criterios mide lo que cuesta mantener dos modelos alineados", y su pregunta 5 pregunta cómo se mantiene alineado un partido "repartido entre el modelo de objetos y el grafo". Esta revisión responde esas dos preguntas con evidencia que en el Hito 2 no existía.

**1. El costo de integración ya es observable.** El módulo de grafos (Hito 5) necesitó guardar los partidos (programación, sede, estado, marcador) y el catálogo de tipos de evento para poder recorrer eventos. Con Objetos como fuente, esos dos datos quedan **duplicados en dos modelos**. La duplicación ya produjo una inconsistencia real: el módulo de objetos (Hito 9) tomó los equipos del roster documental y el calendario de los partidos quedó distinto del que usan el grafo, Cassandra, Redis e InfluxDB (por ejemplo, el mismo `PAR-A-1` enfrenta a equipos distintos en un módulo y en otro). Es exactamente el riesgo que el Hito 2 señaló en sus dos "puntos de contacto que pueden fallar": Partidos↔Eventos y Eventos↔Tipos de evento. Con los tres datos en el grafo, **los dos puntos de contacto desaparecen**.

**2. La ventaja del modelo de objetos depende de quién lo consume.** Lo que el Hito 2 le reconoció a Objetos es representar una entidad con sus partes y sus reglas sin traducción entre la aplicación y la base. Esa ventaja aparece cuando la aplicación trabaja con esas mismas clases. La plataforma expone sus datos con una API REST en Python (Hito 10): la API consulta cada base y valida las entradas en su propia capa, antes de escribir. Con ese consumidor, el motor de objetos se usa como una fuente más y la herencia y las reglas se terminan escribiendo igual en la capa de servicio. Mantener un sexto motor solo para eso agrega una base que operar y replicar sin agregar una garantía que la arquitectura no tenga por otro lado.

**3. Lo que exigía cada necesidad lo cubre el grafo.**

- **N2 Partidos** se eligió por consistencia: el cierre de un partido no admite dos resultados oficiales. El grafo trabaja con transacciones ACID y, además, el marcador ya **no se guarda aparte**: se calcula contando los eventos `GOL` del partido. Un resultado que se deriva de los eventos no puede contradecirlos. La validación CAP de N2 (más abajo) explica cómo convive el cierre CP con la ingesta AP de eventos en el mismo motor.
- **N8 Tipos de evento** se eligió por esquema: los tipos comparten parte de su estructura y tienen reglas propias. En el grafo, cada tipo es un nodo del catálogo y los eventos se vinculan a él. La unicidad de cada tipo la garantiza el motor con una restricción. **Las reglas de cada tipo** (qué campos lleva un Gol y cuáles una Tarjeta) **pasan a validarse en la API**, que es la única que escribe eventos.

**Lo que se resigna (trade-off aceptado).** La diferencia de N8 en la matriz no era chica: Objetos 4,60 contra Grafo 2,95. Lo que se pierde es real. Las reglas de cada tipo de evento dejan de vivir en el modelo de datos, y una escritura que no pase por la API no queda validada por la base. Se acepta porque el catálogo es chico (doce tipos) y estable, todas las escrituras de eventos entran por un único servicio, y el costo de la alternativa ya no es hipotético: es la inconsistencia de calendario del punto 1. Para N2 la diferencia es mayor en puntaje (Objetos 4,25 contra Grafo 3,45), pero el criterio que decidió (la consistencia del cierre) lo cumple el grafo, como se valida más abajo.

**Qué no cambia.** La matriz del Hito 2 no se vuelve a puntuar ni se corrige: sigue siendo el registro de la decisión tomada con la información de ese momento. Esta revisión agrega un criterio que la matriz no tenía (el costo de mantener alineado un dato repartido entre dos modelos) y deja constancia de que, con ese criterio, la asignación cambia. Las demás siete necesidades mantienen su modelo.

---

## 🔀 Análisis CAP y modelos de consistencia

Para cada subsistema priorizado se define qué propiedad de CAP se sacrifica durante una partición de red, qué modelo de consistencia corresponde y qué impacto tendría una lectura desactualizada. El sacrificio nunca es "ninguno": en un sistema realmente distribuido, si la red se particiona hay que elegir entre responder con un dato posiblemente viejo o no responder.

| Subsistema | Prioridad CAP | Se sacrifica | Modelo de consistencia | Impacto de una lectura vieja |
|---|---|---|---|---|
| Partidos (N2) | CP | Disponibilidad | Fuerte (linealizable) en el cierre | Inaceptable: dos marcadores oficiales distintos |
| Equipos y jugadores (N1) | CP en escritura / AP en lectura | Disponibilidad de escritura | Sesión en lectura, fuerte en la confirmación del cambio | Tolerable: se ve el dato anterior unos segundos |
| Eventos en vivo (N3) | AP | Consistencia | Eventual con orden causal (gol antes que asistencia) | Tolerable: el evento aparece con demora, no al revés. Al restablecerse la comunicación, los eventos se propagan y reconcilian respetando el orden causal |
| Usuarios (N4) | AP | Consistencia | Eventual, con consistencia de sesión para el propio usuario | Tolerable entre usuarios; no tolerable para uno mismo |
| Sesiones (N5) | AP | Consistencia | Eventual, ventana de segundos | Tolerable: en el peor caso se repite un login |
| Comentarios (N6) | AP | Consistencia | Eventual | Tolerable: un comentario tarda en aparecer para otros |
| Estadísticas en vivo (N7) | AP | Consistencia | Eventual, con orden monótono por partido | Tolerable: la posesión del minuto 40 llega con la del 41 |
| Tipos de evento (N8) | CP | Disponibilidad | Fuerte sobre el catálogo de tipos | Inaceptable: dos definiciones distintas de "Gol" a la vez |
| Auditoría (N9) | AP con escritura reforzada | Consistencia de lectura (no la de escritura) | Eventual en lectura; escritura con quórum (ver sección de Replicación) | Tolerable en lectura; inaceptable perder la escritura |

Tres pares comparten el mismo patrón CAP y conviene explicarlo una sola vez:

- **Partidos y Tipos de evento son CP por la misma razón**: los dos son catálogos donde dos versiones simultáneas del mismo hecho —un marcador o la definición de un tipo de evento— generan una contradicción visible para el usuario, no solo un dato viejo.
- **Eventos es AP con consistencia causal**: no garantiza sincronización global, pero sí que una asistencia nunca aparece antes que su gol.
- **Comentarios, Estadísticas y Sesiones son AP con eventual pura** porque su dato es aditivo o transitorio sin dependencia entre instancias.
- La única entidad que no encaja en ninguno de los dos patrones es **Auditoría**, y por eso se trata aparte.

### N2 · Partidos — validación independiente de la decisión frágil

La matriz del Hito 2 mostró Objetos (IRIS) por 0,10 sobre Documental (MongoDB), y esta reentrega mueve Partidos al grafo (ver la sección de revisión, más arriba). El análisis CAP no vuelve a puntuar: pregunta qué necesita el requisito en sí. La propiedad que no se puede resignar es la consistencia — se prefiere que el cierre falle o quede en espera antes que mostrar dos resultados oficiales distintos. Lo que hace viable cumplirla es la **topología**: un partido no necesita escribirse desde más de una región a la vez —el cierre lo confirma un único árbitro digital, no una audiencia distribuida—, así que el diseño CP se resuelve con un único nodo autoritativo por partido y replicación síncrona hacia el resto, sin pagar el costo de coordinar entre regiones en cada escritura. Esa topología no depende del modelo: era igual de viable en IRIS que en MongoDB, y lo es en el grafo.

Al quedar Partidos y Eventos en el mismo motor, hay que explicar cómo conviven un dato CP y uno AP. Se resuelve igual que Auditoría: **son operaciones distintas con garantías distintas**, no una propiedad única del motor.

- **Registrar un evento** es AP: confirma en la región de ingesta del partido y se propaga a las demás en segundo plano, con el orden causal ya definido para N3.
- **Cerrar el partido** es CP: pasa el estado a `FINALIZADO` y fija el marcador oficial en una sola transacción, confirmada por mayoría en el nodo autoritativo del partido. Como el marcador se calcula a partir de los eventos, el cierre solo se confirma cuando ese nodo tiene todos los eventos del partido (hasta el de fin de partido). Si no los tiene, el cierre espera: se sacrifica disponibilidad, que es lo que exige N2.

Lo que se gana frente a la asignación anterior: en el Hito 2 el resultado oficial vivía en un modelo y los eventos que lo explican en otro, y hacía falta un mecanismo para propagarlos y reconciliarlos (era la pregunta abierta 2 de este documento). Con los dos en el grafo, el marcador no puede contradecir a los eventos porque sale de ellos.

### N4 · Usuarios — validación independiente de la decisión frágil

Acá el margen de 0,10 favoreció a Documental (MongoDB) sobre Columnar (Cassandra). El análisis CAP muestra que Usuarios es un caso AP: el perfil se lee en cada request desde seis países y tolera propagarse con demora, así que sacrificar disponibilidad para mantener consistencia inmediata sería resignar justamente lo que el escenario pide (100 ms para el 95% de las consultas). Los dos modelos pueden operar en modo AP con consistencia eventual, así que otra vez CAP no desempata por sí solo. La razón que sí agrega peso a Documental es de **topología, no de puntaje**: Equipos y Jugadores ya requieren un núcleo con escritura coordinada en el mismo motor documental, y agregar Usuarios ahí evita un segundo sistema replicado de forma independiente, con su propio mecanismo de reconciliación — a diferencia de Partidos que, por su propio requisito de consistencia y por su vínculo con los eventos (N2, más arriba), vive en el grafo y no en el documental. Se sostiene Documental, pero se identifica la condición que la haría caer: si el padrón de usuarios creciera muy por encima de lo estimado, la escalabilidad de escritura de un modelo columnar volvería a ser competitiva (pregunta abierta, ver más abajo).

### N9 · Auditoría — resolución de la contradicción

En el Hito 2 se eligió un modelo columnar orientado a AP y, en la misma sección, se reconoció que perder un registro invalida el propósito del subsistema. Las dos afirmaciones son incompatibles si se entienden como una propiedad única del sistema. Dejan de serlo si se separan lectura y escritura, que es lo que permiten los parámetros N, R y W. Auditoría puede seguir siendo AP para la lectura, mientras la escritura se configura con una combinación donde el número de réplicas que deben confirmar sea suficiente para que ninguna escritura confirmada se pierda, incluso si el sistema en su conjunto no ofrece consistencia fuerte para el resto de las operaciones. El principio: la contradicción no se resuelve eligiendo entre AP y "no se puede perder", se resuelve reconociendo que esos dos requisitos aplican a operaciones distintas del mismo subsistema (el detalle numérico está en la sección siguiente).

---

## 🔁 Replicación, particionamiento y quórum

Para cada subsistema se define el criterio de partición, la topología de réplica y, **donde la tecnología lo admite como parámetro configurable por operación**, los valores de N, R y W.

> **Sobre el uso de N/R/W en esta sección.** No todos los modelos exponen réplica y consistencia de la misma manera. **Cassandra** expone N, R y W directamente como parámetro por operación, y es el modelo de quórum que se trabajó en profundidad en Clase 3 — por eso Comentarios (N6) y Auditoría (N9) sí llevan valores explícitos de N/R/W. El resto de los modelos logra el mismo efecto (cuántas copias deben confirmar antes de responder) con mecanismos propios: MongoDB con factor de réplica y *write concern*/*read preference* sobre su replica set, Neo4j con un grupo de copias que confirma cada escritura por mayoría más réplicas de lectura por región, Redis con réplicas y expiración (TTL) sin quórum de lectura, e **InfluxDB con factor de réplica y consistencia eventual entre nodos de ingesta, sin un parámetro de quórum por escritura equivalente al de Cassandra**. Por eso, para Estadísticas en vivo (N7, InfluxDB) la réplica y la consistencia se describen a continuación de forma conceptual, y no con la notación N/R/W explícita. Con el mismo criterio, en esta reentrega Partidos, Tipos de evento (los dos en Neo4j) y Equipos y jugadores (MongoDB) se describen por cantidad de copias y regla de confirmación, sin la notación N/R/W.

| Subsistema | Criterio de partición | Topología de réplica | Réplica y consistencia | Riesgo principal |
|---|---|---|---|---|
| Partidos (Neo4j) | Por partido, junto con sus eventos — volumen bajo, un nodo por partido | Un nodo autoritativo por partido, síncrona hacia 2 réplicas | 3 copias; el cierre confirma con mayoría (2 de 3) y solo con todos los eventos del partido presentes | Ninguna partición por hotspot; riesgo es de coordinación en el cierre (que el nodo autoritativo no haya recibido todavía un evento) |
| Equipos y jugadores | Ninguno — catálogo de 64 equipos | Réplica por región para lectura, escritura en nodo primario | 3 copias, lectura local, escritura confirma en el primario | Ventana de segundos con datos desactualizados tras un cambio |
| Eventos en vivo (Neo4j) | Por partido; los eventos de un mismo partido conviven con su partido | Réplica multi-región asíncrona | Confirmación de escritura local en la región de ingesta, propagación en segundo plano | Recorrido de un evento reciente en una región que aún no lo recibió |
| Usuarios | Por identificador de usuario (distribución uniforme) | Réplica multi-región, un primario por usuario según su región de alta | Lectura local mayoritaria, escritura confirma en el primario | Usuario que viaja y escribe desde una región distinta a la de su primario |
| Sesiones | Por identificador de sesión, sin replicar entre regiones | Local a la región donde se generó, sin réplica cross-región | Vigencia automática (TTL), sin quórum | Pérdida de la sesión si cae el nodo local; el usuario reautentica |
| Comentarios | Compuesta: identificador de partido + ventana temporal | Distribuida entre varios nodos por región de origen del pico | **N=3, R=1, W=1** (prioriza velocidad, tolera inconsistencia breve) | Concentración de escritura en la ventana del minuto 90 de un partido popular |
| **Estadísticas en vivo** | Por partido + intervalo temporal | Réplica de bajo factor dentro de la región de ingesta, agregados propagados luego | **Réplica conceptual (no N/R/W explícito):** escritura confirma rápido dentro de la región de ingesta para priorizar disponibilidad y throughput; propagación entre réplicas es eventual; el ajuste fino de consistencia se maneja vía downsampling y política de retención, no vía quórum de lectura/escritura | Pérdida de puntos individuales del segundo, aceptable por el downsampling |
| Tipos de evento (Neo4j) | Ninguno — catálogo acotado y estable (doce tipos) | Réplica síncrona de baja frecuencia | 3 copias, escritura confirma con mayoría | Cambios de tipo poco frecuentes; al estar en el mismo motor que Eventos, un cambio de tipo y los eventos que lo usan se validan contra el mismo catálogo |
| Auditoría | Compuesta: ventana temporal + entidad afectada | Distribuida entre nodos, sin restricción geográfica estricta | **N=3, R=1, W=QUORUM** (2 de 3) en la escritura | Retraso o rechazo de una escritura si no hay quórum disponible |

**Sobre el quórum de Auditoría.** La combinación N=3, R=1, W=QUORUM está elegida a propósito y permite reforzar la durabilidad de las escrituras. Con W=QUORUM, dos de las tres réplicas deben confirmar antes de aceptar la escritura como exitosa. En este caso R=1 y W=2, por lo que R+W=N: alcanza para sostener la durabilidad de la escritura, pero no garantiza que una lectura vea siempre el dato más reciente —eso exigiría R+W>N—, algo que acá no hace falta porque el objetivo es no perder el registro, no leerlo actualizado al instante. La lectura puede seguir siendo rápida al consultar una sola réplica, aunque puede existir un retraso temporal en la propagación hacia las demás.

**Sobre el hotspot de Comentarios.** Particionar únicamente por identificador de partido concentraría el millón de comentarios de la final en una sola porción del sistema, mientras el resto permanece ocioso. Combinar el identificador del partido con una ventana temporal reparte esa carga entre varias porciones sin perder la localidad por partido, que es el acceso dominante.

**Sobre sesiones sin réplica cross-región.** Es una decisión deliberada, no una omisión: el Hito 2 estableció que perder una sesión ante una falla es aceptable, porque el usuario vuelve a autenticarse. Replicar sesiones entre regiones agregaría costo de coordinación para un dato cuya pérdida ya se asume como tolerable.

---

## 📈 Escalabilidad, fallos y métricas

### Plan de escalabilidad

El escenario exige sostener entre 2 y 3 millones de usuarios simultáneos y picos de más de 100.000 solicitudes por segundo, con crecimiento concentrado en las horas de partidos de alta audiencia. Eso descarta el escalamiento vertical como estrategia principal para cualquier subsistema de audiencia. El escalamiento horizontal es la estrategia de base para Comentarios, Eventos, Estadísticas, Sesiones y Auditoría. Partidos, Equipos/Jugadores y Tipos de evento son la excepción: su volumen es bajo y fijo, así que no necesitan escalar y el diseño prioriza la consistencia por sobre la capacidad de crecer.

| Subsistema | Cuello de botella previsible | Respuesta de escalamiento |
|---|---|---|
| Sesiones | Volumen de escritura de login/logout en el arranque de un partido popular | Horizontal, agregando nodos por región antes del horario de partidos de alta audiencia |
| Comentarios | Escritura concentrada en la ventana de goles o del final del partido | Horizontal, con la partición compuesta ya prevista repartiendo el pico entre nodos |
| Estadísticas en vivo | Ingesta sostenida de millones de puntos por partido en simultáneo con otros partidos | Horizontal por partido; cada partido ingiere en una porción distinta del clúster |
| Auditoría | Volumen acumulado a lo largo de todo el torneo, no solo en picos | Horizontal continuo, con el particionamiento por ventana temporal facilitando agregar capacidad sin reorganizar el histórico completo |
| Usuarios | Lectura en cada request desde seis países | Horizontal por región, con réplicas de lectura locales; la escritura no es el cuello de botella |
| Eventos | Ninguno significativo: volumen bajo y acotado por la cantidad de partidos | Se prioriza el escalamiento horizontal de las réplicas de lectura y la distribución de las consultas entre regiones |

### Escenarios de fallo y resiliencia

| Escenario | Subsistemas afectados | Respuesta esperada |
|---|---|---|
| Caída del nodo primario de un partido durante el cierre | Partidos | El cierre queda en espera hasta que se elige un nuevo nodo autoritativo por mayoría; no se confirma un resultado sin esa elección |
| El nodo autoritativo de un partido todavía no recibió todos sus eventos al momento del cierre | Partidos, Eventos | El cierre no se confirma hasta que lleguen (hasta el evento de fin de partido). Los eventos se siguen registrando en la región de ingesta; solo el resultado oficial espera |
| Aislamiento temporal de una región completa (partición de red) | Usuarios, Sesiones, Comentarios, Estadísticas, Eventos | Cada región sigue respondiendo con sus réplicas y su primario local donde exista; lo que no puede resolver localmente queda en cola y se reconcilia al restablecerse la conexión. Se prioriza A sobre C |
| Pico de escritura muy superior al estimado en un partido inesperadamente masivo | Comentarios | La partición compuesta limita el impacto a las porciones del pico; si aun así se satura, W=1 permite seguir aceptando escrituras a costa de una consistencia de lectura más floja, no de rechazar comentarios |
| Falla de una réplica durante la escritura de un registro de auditoría | Auditoría | Con N=3 y W=QUORUM, la escritura se sostiene mientras al menos dos de las tres réplicas respondan; solo se pierde disponibilidad de escritura si fallan dos réplicas a la vez |

### Métricas propuestas

Las métricas se definen por lo que cada subsistema prioriza según su análisis CAP: los subsistemas CP necesitan métricas de tiempo de coordinación, los AP necesitan métricas de retraso de propagación.

| Métrica | Qué mide | Dónde importa más |
|---|---|---|
| Latencia de confirmación de escritura (P95, P99) | Tiempo entre la solicitud y la confirmación al cliente | Partidos, Tipos de evento (CP): un aumento indica riesgo de incumplir el cierre a tiempo |
| Retraso de propagación (replication lag) | Diferencia de tiempo entre la escritura primaria y su visibilidad en cada réplica | Usuarios, Eventos, Comentarios, Estadísticas (AP) |
| Tasa de escrituras rechazadas por falta de quórum | Proporción de escrituras de auditoría que no alcanzan W=QUORUM | Auditoría: valida en producción que la garantía de durabilidad se cumple |
| Throughput por partición (operaciones por segundo) | Carga que recibe cada porción del sistema en un pico | Comentarios, Estadísticas: detecta si el criterio de partición sigue repartiendo bien la carga |
| Disponibilidad efectiva (%) por región | Proporción de solicitudes respondidas dentro del objetivo de 100 ms | Sesiones, Usuarios: valida el objetivo de 99,99% del escenario, desagregado por región |
| Cantidad de réplicas activas por partición | Estado de salud de cada conjunto de réplicas | Todos los subsistemas replicados: anticipa el escenario de "falla una réplica más" antes de que ocurra |

---

## 📐 Diagrama de arquitectura

**Fixture 2030 — Arquitectura distribuida conceptual.** Regiones de audiencia, subsistemas por necesidad y rol de consistencia (C) / disponibilidad (A).

```mermaid
flowchart TB
    subgraph AM["🌎 Región Américas (audiencia)"]
        AM_S["Sesiones (Redis)<br/>local · TTL"]
        AM_R["Réplica de lectura<br/>Comentarios / Stats"]
        AM_U["Usuarios<br/>(réplica de lectura)"]
        AM_C["CDN / cache de<br/>consultas frecuentes"]
    end

    subgraph EU["🌍 Región Europa (audiencia)"]
        EU_S["Sesiones (Redis)<br/>local · TTL"]
        EU_R["Réplica de lectura<br/>Comentarios / Stats"]
        EU_U["Usuarios<br/>(réplica de lectura)"]
        EU_C["CDN / cache de<br/>consultas frecuentes"]
    end

    subgraph AP_["🌏 Región Asia-Pacífico (audiencia)"]
        AP_S["Sesiones (Redis)<br/>local · TTL"]
        AP_R["Réplica de lectura<br/>Comentarios / Stats"]
        AP_U["Usuarios<br/>(réplica de lectura)"]
        AP_C["CDN / cache de<br/>consultas frecuentes"]
    end

    NUCLEO["**Núcleo autoritativo (single-writer por dato crítico)**"]

    EquiposJug["Equipos / Jugadores (MongoDB)<br/>CP en escritura, AP en lectura"]
    Usuarios["Usuarios (MongoDB)<br/>AP — replicado multi-región"]

    subgraph GRAFO["Grafo (Neo4j) — partición por partido"]
        Partidos["Partidos<br/>CP en el cierre — mayoría, ACID<br/>marcador derivado de los eventos"]
        Eventos["Eventos en vivo<br/>AP — confirmación local,<br/>orden causal"]
        Tipos["Tipos de evento<br/>CP — catálogo, baja escritura"]
    end
    Comentarios["Comentarios (Cassandra)<br/>AP — N=3 R=1 W=1<br/>hash(partido) + ventana"]
    Estadisticas["Estadísticas en vivo (InfluxDB)<br/>AP — réplica de ingesta,<br/>consistencia eventual, downsampling"]

    Auditoria["**Auditoría e históricos (Cassandra)**<br/>AP con W=QUORUM reforzado en la escritura (R+W sobre N)<br/>partición por ventana temporal + entidad afectada"]

    AM --> NUCLEO
    EU --> NUCLEO
    AP_ --> NUCLEO

    NUCLEO --- Partidos
    NUCLEO --- EquiposJug
    NUCLEO --- Usuarios

    Eventos -->|cierre| Partidos
    Eventos -.valida contra.- Tipos
    Partidos --> Comentarios
    Partidos --> Estadisticas
    EquiposJug --> Eventos

    Eventos -.registro.-> Auditoria
    Comentarios -.registro.-> Auditoria
    Estadisticas -.registro.-> Auditoria
    Tipos -.registro.-> Auditoria

    classDef cp fill:#ffe8b3,stroke:#c9911d,color:#3a2c00;
    classDef ap fill:#ffd9cc,stroke:#c9531d,color:#3a1400;
    class Partidos,Tipos cp;
    class Auditoria ap;
```

- Línea sólida: escritura confirmada / propagación autoritativa.
- Línea fina: lectura / propagación asíncrona.
- Línea punteada: registro de auditoría (todas las escrituras).

---

## 🧩 Supuestos que sostiene este diseño

- El cierre de un partido lo confirma un proceso único (un "árbitro digital"), no una operación iniciada de forma concurrente desde varias regiones. Si el escenario cambiara —por ejemplo, jueces de línea distribuidos que confirman en paralelo— el diseño CP de Partidos necesitaría revisarse.
- El padrón de usuarios crece de forma sostenida. Es el mismo supuesto que quedó abierto en el Hito 2 para N4, y este hito lo hereda sin validarlo.
- La ventana de comentarios que reparte la partición compuesta alcanza para distribuir el pico de un partido de máxima audiencia. No se midió ese pico contra datos reales de un evento comparable.
- Todas las escrituras de eventos y de tipos de evento entran por un único servicio (la API de la plataforma), que valida las reglas de cada tipo antes de escribir. Si apareciera otro camino de escritura directo al grafo, esas reglas no las controlaría nadie, y habría que llevarlas al modelo o volver a evaluar un motor que las haga cumplir.

## ❓ Preguntas a validar durante los próximos hitos

1. ¿Cuántas réplicas concretas conviene usar para Auditoría — N=3 alcanza, o el volumen acumulado (260 TB) exige un N mayor para no comprometer W=QUORUM cuando una réplica esté en mantenimiento?
2. ~~¿Qué mecanismo reconcilia Partidos con Eventos si la propagación desde el núcleo autoritativo hacia la capa de Eventos falla?~~ **Resuelta en la reentrega:** con Partidos y Eventos en el mismo motor ya no hay propagación entre dos modelos que reconciliar; el marcador se calcula a partir de los eventos. Queda en su lugar una pregunta más acotada: ¿cuánto puede esperar un cierre a que el nodo autoritativo reciba los últimos eventos del partido, antes de considerarlo una falla?
3. La condición que haría caer la decisión de N4 Usuarios (padrón muy por encima de lo estimado) ¿a partir de qué cifra concreta correspondería reevaluarla? ¿La réplica local de Usuarios en cada región alcanza para el objetivo de 100 ms, o hace falta un primario por región además de la réplica de lectura?
4. ¿Qué pasa con una sesión activa cuando el usuario cambia de región durante un partido (por ejemplo, viajando)? El diseño actual no contempla ese caso y lo deja para el hito de implementación.
5. ¿Los valores de N, R y W propuestos para Comentarios y Auditoría (Cassandra) siguen siendo razonables si dos partidos de alta audiencia se superponen en el calendario?

---

## Historial de revisión

**26/09/2026 — corrección de N/R/W en InfluxDB (ver [`correcciones-profesor.md`](./correcciones-profesor.md)).** El profesor pidió expresar réplica y consistencia de Estadísticas en vivo de forma conceptual, reservando N/R/W explícito para Cassandra. Aplicado en la nota introductoria, en la sección "Sobre el uso de N/R/W en esta sección" y en la fila de Estadísticas en vivo de la tabla de replicación.

**26/09/2026 — corrección de un error propio, no señalado por el profesor.** La entrega original de este documento invertía el resultado del Hito 2 para **N2 Partidos**: decía "la matriz del Hito 2 mostró Documental (MongoDB) por 0,20 sobre Objetos (IRIS)", cuando la matriz real ([`../hito-2-matriz-decision/hito-2-matriz-decision.md`](../hito-2-matriz-decision/hito-2-matriz-decision.md), Sección 3) muestra **Objetos (IRIS) con 4,25 por 0,10 sobre Documental (4,15)** — el ganador y el margen estaban los dos invertidos. Se corrigió en cuatro lugares de este documento:

- La tabla "Resumen de decisiones previas" (N2: Documental → Objetos/IRIS).
- El párrafo de validación de N2 (ganador y margen).
- El diagrama de arquitectura (el nodo de Partidos pasó de "(MongoDB)" a "(IRIS)").
- Un efecto de segundo orden en el párrafo de validación de **N4 Usuarios**, que citaba "Equipos, Jugadores y Partidos" como el núcleo ya coordinado en el motor documental para justificar sumar Usuarios ahí — con Partidos en IRIS, ese núcleo es solo Equipos y Jugadores. La conclusión de N4 (se sostiene Documental) no cambia: sigue siendo válido evitar un segundo sistema replicado por separado, ahora con dos entidades en el núcleo en lugar de tres.

De paso, se corrigió también el margen citado para **N4 Usuarios**: el documento original decía "0,20" en dos lugares (tabla resumen y párrafo de validación) y en la nota "Sobre el margen de las decisiones frágiles"; el margen real, según la misma matriz del Hito 2 y confirmado por el texto de la corrección del profesor al Hito 2 ("márgenes son apenas 0,10"), es **0,10**. No cambia el modelo ganador (Documental/MongoDB se mantiene).

El profesor no marcó el error de N2 en su corrección a este hito (ver [`correcciones-profesor.md`](./correcciones-profesor.md)) — el foco de esa revisión fue otro. Se corrige igual porque la matriz del Hito 2 es la fuente de esta decisión, y porque las referencias a Partidos en Objetos/IRIS ya se habían corregido en el módulo de Redis (Hito 7, commits `f94309e` y `73c7d9d`) antes de que este documento se pusiera al día.

**13/10/2026 — reentrega: el modelo de objetos (IRIS) sale de la arquitectura.** Propuesto por el grupo y aprobado por el profesor. Partidos (N2) y Tipos de evento (N8) pasan del modelo de objetos (IRIS) al grafo (Neo4j); las otras siete necesidades no cambian. La justificación está en la nueva sección "Revisión de la asignación del modelo de objetos (reentrega)", que responde las preguntas 5 y 7 del Hito 2 (el costo de mantener un mismo dominio repartido entre dos modelos). Cambios en este documento:

- Nota introductoria y tabla "Resumen de decisiones previas" (nueva columna con el modelo de esta revisión).
- Nueva sección de revisión, con el trade-off que se acepta en N8 (las reglas de cada tipo de evento pasan a validarse en la API).
- Validación de N2: cómo conviven en el mismo motor el cierre CP del partido y la ingesta AP de eventos (operaciones distintas con garantías distintas, como en Auditoría).
- Validación de N4: la referencia a Partidos "en un motor de objetos" pasa a "en el grafo".
- Tabla de replicación: Partidos, Eventos y Tipos de evento indican Neo4j. Partidos y Tipos de evento, junto con Equipos y jugadores, se describen por cantidad de copias y regla de confirmación, sin la notación N/R/W, siguiendo el criterio de la corrección del profesor (N/R/W explícito solo para Cassandra).
- Escenarios de fallo: nuevo escenario de cierre con eventos todavía no recibidos.
- Diagrama: Partidos, Eventos y Tipos de evento quedan dentro de un mismo bloque "Grafo (Neo4j)".
- Supuestos: nuevo supuesto sobre la API como único camino de escritura de eventos y tipos.
- Pregunta abierta 2 (reconciliación Partidos–Eventos): marcada como resuelta y reemplazada por una más acotada.

La matriz del Hito 2 no se modificó: queda como registro de la decisión tomada con la información de ese momento, con una nota que apunta a esta revisión.
