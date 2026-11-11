# Análisis CAP por subsistema

Para cada subsistema de la arquitectura vigente: qué decidió el [Hito 3](../../docs/hito-3-arquitectura-distribuida/hito-3-arquitectura-distribuida.md) ("Análisis CAP y modelos de consistencia" y "Replicación, particionamiento y quórum"), qué permite el motor que se eligió, y qué se **midió** en este laboratorio. Cuando lo medido no coincide con el Hito 3, se dice acá; el documento del Hito 3 no se modifica.

**Qué se midió y qué no.** Se replicaron las dos bases que pide la guía: MongoDB (N1 Equipos y jugadores) y Cassandra (N6 Comentarios), con su esquema y sus datos reales. Neo4j, Redis e InfluxDB siguen en un nodo (sus módulos de los Hitos 5, 7 y 8): su análisis CAP es de diseño, apoyado en lo que el motor ofrece, y se marca como tal. "Partición" en este laboratorio es **la caída de un nodo**: para los nodos que quedan, un nodo caído y uno aislado por la red son indistinguibles. No se probó una partición con los dos lados vivos (ver §6).

## 1. Resumen

| Subsistema | Fuente vigente | Hito 3 | Qué ofrece el motor | En este laboratorio | ¿Coincide con el Hito 3? |
|---|---|---|---|---|---|
| N1 Equipos y jugadores | MongoDB | CP en escritura / AP en lectura. "3 copias, lectura local, escritura confirma en el primario" | Replica set: un primario elegido por mayoría; `writeConcern`, `readConcern` y `readPreference` por operación | **Medido**: replica set de 3 nodos (§2) | Sí, con una precisión: para ser CP la escritura tiene que confirmarse **por mayoría**, no "en el primario" (§2.4) |
| N2 Partidos | Neo4j | CP en el cierre: 3 copias, confirma la mayoría (2 de 3) | Neo4j Enterprise: clúster con Raft, una escritura se confirma cuando la mayoría de los servidores primarios la tiene. Neo4j Community (la del repo): un solo servidor, sin clúster | Diseño, no medido (§5.2) | Sí: la mayoría Raft es la regla de confirmación que pide el Hito 3 |
| N3 Eventos en vivo | Neo4j | AP, eventual con orden causal; "confirmación de escritura local en la región de ingesta, propagación en segundo plano" | En un clúster Neo4j **toda** escritura pasa por Raft (mayoría de primarios); lo asíncrono son las réplicas secundarias, que solo sirven lecturas | Diseño, no medido (§5.2) | **No del todo**: Neo4j no confirma una escritura "local" sin mayoría (§5.2) |
| N8 Tipos de evento | Neo4j | CP, 3 copias, confirma la mayoría | Igual que N2 | Diseño, no medido | Sí |
| N5 Sesiones | Redis | AP, eventual, TTL, local por región, sin réplica cross-región | Réplica asíncrona primario → réplicas; Sentinel o Cluster promueven una réplica y pueden perder escrituras ya confirmadas | Diseño, no medido (§5.1) | Sí |
| N6 Comentarios | Cassandra | AP, eventual; N=3, R=1, W=1 | Peer-to-peer; nivel de consistencia por operación (ONE, QUORUM, ALL); *hinted handoff*, *read repair* y `nodetool repair` | **Medido**: anillo de 3 nodos, RF = 3 (§3) | Sí (§3.5) |
| N7 Estadísticas en vivo | InfluxDB 3 Core | AP, eventual; "réplica de bajo factor dentro de la región de ingesta" (conceptual) | InfluxDB 3 Core es nodo único, sin réplica (la replicación es de InfluxDB 3 Enterprise) | Diseño; **la edición elegida no lo permite** (§5.3) | El diseño sí; el motor implementado no lo puede cumplir |
| N4 Usuarios | MongoDB (no implementado) | AP, eventual con consistencia de sesión para el propio usuario | El mismo replica set: lectura de secundarios + sesiones causales (`readConcern: "majority"`, `writeConcern: "majority"`) dan "leer lo que yo escribí" | No implementado (ver `docs/ESTADO-CANONICO-NECESIDADES.md`) | — |
| N9 Auditoría | Cassandra (no implementado) | AP en lectura, escritura W = QUORUM | Igual que N6 | No implementado; **sí se midió** que una escritura QUORUM se sostiene con 1 de 3 réplicas caída (§3.1) | Sí en lo medido |
| N2/N8 en IRIS | — | Fuera de la arquitectura desde la reentrega del Hito 3 (13/10/2026, con ok del profesor) | — | No se analiza | — |

## 2. MongoDB — N1 Equipos y jugadores (medido)

Replica set `rs-fixture2030`: 3 nodos con voto y prioridad 1, `electionTimeoutMillis` = 10 000, `writeConcern` por defecto `majority`. Datos del Hito 4: 64 equipos y 1 472 jugadores, iguales en los tres nodos ([`mongo_iniciar`](../evidencia/mongo_iniciar_20261111-103554.txt)).

### 2.1 Failover del primario

Un escritor continuo (`w: "majority"`, cada 200 ms) corre conectado al replica set desde un nodo que no es el primario, mientras se tira el primario. Horas del reloj de la VM de Docker ([`mongo_failover_kill`](../evidencia/mongo_failover_kill_20261111-103757.txt), [`mongo_failover_stop`](../evidencia/mongo_failover_stop_20261111-103939.txt)).

| | `kill` (caída abrupta) | `stop` (apagado ordenado) |
|---|---|---|
| Motivo de la elección | `electionTimeout` | `stepUpRequestSkipDryRun` (el primario cedió el lugar) |
| Elección ganada | 9,99 s después de la caída | 0,59 s después de la orden |
| El primario nuevo acepta `w: "majority"` | 11,61 s | 0,65 s |
| Hueco sin escrituras confirmadas, visto por el cliente | 11,68 s (la operación en curso esperó 11,5 s y se completó) | 0,27 s |
| Escrituras con error / perdidas | 0 de 226 / 0 | 0 de 244 / 0 |
| El nodo caído, al volver | SECONDARY (no recupera el primario); tenía las 226 escrituras 24 ms después | SECONDARY; las 244 escrituras, 19 ms después |

En las corridas de prueba del 10/11 (con la notebook sin memoria libre; esa evidencia no se conserva) la elección por `kill` osciló entre 10,0 y 10,9 s y la primera escritura del cliente llegó entre 12 y 21 s después de la caída.

**Lectura CAP.** Mientras dura la elección **no hay primario y no se acepta ninguna escritura**: el replica set elige consistencia (nunca dos primarios, nunca dos versiones de un equipo) y paga con disponibilidad de escritura. Es la prioridad **CP en escritura** del Hito 3. Lo que hizo falta para que eso no pierda datos fue `w: "majority"`: ninguna escritura confirmada se perdió y el nodo que volvió no tuvo nada que deshacer (*rollback*).

**De dónde sale el tiempo.** Con una caída abrupta (`kill`) los secundarios tienen que esperar `electionTimeoutMillis` (10 s) sin *heartbeats* antes de llamar a elección: la elección se ganó a los 9,99 s. El cliente esperó algo más (11,61 s): el primario nuevo tiene que asumir el término y ponerse al día antes de aceptar `w: "majority"`, y el driver tiene que descubrirlo. Con un apagado ordenado (`stop`) el primario renuncia y le pide a un secundario que asuma (`stepUpRequestSkipDryRun`): 0,59 s y un hueco de 0,27 s. El cliente no recibió **ningún error** en ninguno de los dos casos: la operación quedó esperando y el driver la reintentó (`retryWrites`) en el primario nuevo.

### 2.2 writeConcern

Mediana de 20 `updateOne` sobre `equipos` ([`mongo_lecturas_y_concerns`](../evidencia/mongo_lecturas_y_concerns_20261111-103722.txt)) §2:

| writeConcern | Confirman | Mediana | Máximo |
|---|---|---|---|
| `w: 1` | solo el primario | 2,0 ms | 3,5 ms |
| `w: "majority"` | 2 de 3 nodos | 12,0 ms | 19,0 ms |
| `w: 3` | los 3 nodos | 3,0 ms | 3,5 ms |

Las tres son del orden de los milisegundos en un solo host: confirmar por mayoría no es caro acá. `majority` sale más lento que `w: 3` porque una confirmación por mayoría además espera que el cambio esté en el *journal* de los nodos (`writeConcernMajorityJournalDefault`), y `w: 3` sin `j: true` no. En una red real entre regiones la diferencia la pone la distancia al segundo nodo más cercano.

### 2.3 Lecturas: secundarios, readConcern y consistencia eventual

Para ver una lectura vieja sin depender del azar, se congela la aplicación del oplog en los dos secundarios (`db.fsyncLock()`) y se cambia el DT de Argentina con `w: 1` (se restaura al final). Mismo archivo, §3:

| Lectura | Devuelve | Qué significa |
|---|---|---|
| Primario, `readConcern: "local"` | el valor nuevo | ve lo que el primario aplicó, aunque nadie más lo tenga |
| Primario, `readConcern: "majority"` | el valor **anterior** | solo devuelve lo que ya tiene la mayoría: no puede deshacerse |
| Primario, `readConcern: "linearizable"` | `MaxTimeMSExpired` (no contesta en 3 s) | prefiere **no contestar** a contestar algo que podría no ser lo último: C sobre A |
| Secundario, `readPreference: "secondary"` | el valor **anterior** | lectura vieja: consistencia eventual |
| Escritura con `w: "majority"`, `wtimeout` 3 s | `WriteConcernFailed`, pero el primario la aplicó | el cliente no tiene confirmación: no puede contar con que sobreviva a una caída |

Al liberar la replicación, el secundario tuvo el valor nuevo a los 7 ms. La lectura desde secundarios reparte la carga: en la corrida final (primario mongo3), `secondary` y `secondaryPreferred` alternaron entre mongo1 y mongo2, `primary` y `primaryPreferred` fueron siempre a mongo3, y `nearest` repartió entre los tres (en un solo host todos están a la misma distancia).

### 2.4 Contraste con el Hito 3

- **"CP en escritura / AP en lectura": se confirma.** La escritura se detiene durante la elección y no pierde nada con `majority`; la lectura desde secundarios sigue respondiendo y puede devolver un dato viejo.
- **"Escritura confirma en el primario": lo medido indica que no alcanza.** Literalmente es `w: 1`. Con `w: 1` el primario confirmó un cambio que la mayoría no tenía (§2.3); si ese primario cae antes de replicarlo, el cambio se descarta cuando vuelve. Eso no es CP. Para que N1 sea CP en escritura, como dice el mismo Hito 3, la confirmación tiene que ser por mayoría (`w: "majority"`, que además es el valor por defecto de MongoDB 7 y el que usa el seed del Hito 4).
- **"Ventana de segundos con datos desactualizados tras un cambio": se confirma**, con un dato que el Hito 3 no menciona: además de la lectura vieja, una caída del primario deja **~10 a 20 s sin escrituras** (§2.1). Para un catálogo de 64 equipos que cambia poco es aceptable, pero es el costo concreto de la elección CP.
- **Hallazgo del laboratorio.** Con la notebook sin memoria libre, un primario no pudo tomar el lock de transición de estado durante 28 s y MongoDB lo abortó a propósito (`fassert` 5675600: "stepUp/stepDown is not possible thus calling abort() to allow cluster to progress"); los otros dos eligieron primario y el nodo volvió como secundario al reiniciarlo. Es el mismo mecanismo: ante la duda, un nodo se retira antes que arriesgar dos primarios.

## 3. Cassandra — N6 Comentarios (medido)

Anillo de 3 nodos en `datacenter1`, keyspace `fixture2030_comentarios` con `NetworkTopologyStrategy` y RF = 3: cada nodo guarda una copia de todo (`Owns (effective)` 100 % en los tres). Esquema y carga de muestra del Hito 6: 112 configuraciones y 80 comentarios ([`cassandra_iniciar`](../evidencia/cassandra_iniciar_20261111-102846.txt)).

### 3.1 Un nodo caído: ONE, QUORUM y ALL

Coordinador cas1; cas3 detenido con `docker stop` ([`cassandra_failover`](../evidencia/cassandra_failover_20261111-104419.txt)):

| Nivel | Réplicas que tienen que responder | Escritura | Lectura |
|---|---|---|---|
| ONE | 1 | OK | OK |
| QUORUM | 2 | OK | OK |
| ALL | 3 | **Falla**: `Unavailable`, `required_replicas: 3`, `alive_replicas: 2` | **Falla** (mismo error) |

cas1 vio a cas3 caído (DN) 2 s después del `docker stop`. Al volver: cas3 aceptó CQL a los 11 s del `docker start`, cas1 lo vio UN 2 s después y le entregó el hint 13 s más tarde. Con los tres arriba de nuevo, ALL volvió a funcionar.

Con 2 de 3 réplicas vivas, ONE (1) y QUORUM (2) se pueden cumplir y ALL (3) no. Cassandra rechaza la operación **antes** de ejecutarla (`Unavailable`: requiere 3, hay 2 vivas) en vez de aceptarla a medias. Las escrituras aceptadas con ONE y QUORUM mientras cas3 estaba caído quedaron como *hints* en cas1 y se le entregaron cuando volvió (`Finished hinted handoff`); a partir de ahí ALL volvió a funcionar.

### 3.2 R + W frente a N

| Escritura (W) | Lectura (R) | R + W | ¿Lee siempre lo último? | ¿Sigue con 1 nodo caído? |
|---|---|---|---|---|
| ONE (1) | ONE (1) | 2 ≤ 3 | No (medido, §3.3) | Sí |
| QUORUM (2) | ONE (1) | 3 = 3 | No | Sí |
| ONE (1) | QUORUM (2) | 3 = 3 | No | Sí |
| QUORUM (2) | QUORUM (2) | 4 > 3 | Sí | Sí |
| ALL (3) | ONE (1) | 4 > 3 | Sí | **No** escribe |

El Hito 3 eligió la primera fila para Comentarios (máxima disponibilidad y menor latencia) y la segunda para Auditoría (no perder la escritura). Con QUORUM/QUORUM los comentarios serían consistentes y seguirían disponibles con un nodo caído; se pagaría con latencia en cada escritura del minuto 90, que es justo lo que el Hito 3 quiso evitar.

### 3.3 Consistencia eventual, medida

Un comentario se escribe con ONE mientras cas3 está caído, y se lee **en cas3** antes y después de que las réplicas se pongan de acuerdo ([`cassandra_consistencia_eventual`](../evidencia/cassandra_consistencia_eventual_20261111-103148.txt)). "Leer en cas3" se verifica con la traza de la consulta (`TRACING ON`): con ONE el coordinador consulta una sola réplica, pero no siempre la propia, así que la lectura se repite hasta que la traza muestra que la partición la leyó solo cas3. En la primera corrida del script esto no se verificaba y la lectura "vieja" la contestó en realidad cas2; esa evidencia se descartó.

| Paso | Lectura en cas3 (solo cas3, verificado por traza) |
|---|---|
| **A.** Escritura con ONE (coordinador cas1) con cas3 caído. El hint queda en disco en cas1. cas3 vuelve con la entrega de hints **pausada** | **0 filas**: lectura vieja. La misma lectura solo en cas1: 1 fila |
| **A.** Se reanuda la entrega (`resumehandoff`) | cas1 entrega el hint 13 s después (`Finished hinted handoff`); cas3 tiene la fila a los 14 s |
| **B.** Hints **desactivados** (`disablehandoff`); escritura con ONE con cas3 caído | ningún archivo de hints en cas1 |
| **B.** cas3 vuelve | **0 filas**; 30 s después, **0 filas**: no se repara sola |
| **B.** `nodetool repair -full` en cas3 (5 s) | **1 fila** |

Dos conclusiones para el diseño:

1. **El *hinted handoff* repara solo, pero no siempre.** Un coordinador guarda hints para una réplica caída hasta `max_hint_window` = 3 h. Si un nodo está caído más que eso, o el coordinador que tenía el hint también cae, lo que se perdió queda desactualizado **indefinidamente** (caso B: 30 s después seguía sin el comentario).
2. **Por eso hace falta `nodetool repair` periódico.** Es la única reparación completa: compara las réplicas por árboles de Merkle y copia lo que falta. Tiene que correr en cada nodo dentro de `gc_grace_seconds` (10 días por defecto) para que un borrado no "resucite". El Hito 3 no lo menciona; es una tarea de operación que se agrega acá, no un cambio de diseño.

### 3.4 Memoria

| Contenedor | RAM (docker stats) | Heap usado / máximo |
|---|---|---|
| cas1 | 845 MiB | 103 / 256 MB |
| cas2 | 816 MiB | 151 / 256 MB |
| cas3 | 809 MiB | 152 / 256 MB |
| **Anillo de Cassandra** | **~2,4 GB** | |
| mongo1 / mongo2 / mongo3 | 178 / 157 / 172 MiB (límite 512 MiB) | caché de WiredTiger 256 MB |

Con volúmenes vacíos el anillo se formó en 113 s; el día anterior, con la notebook sin memoria libre, había tardado 539 s.

Heap fijado en 256 MB por nodo (`MAX_HEAP_SIZE`), contra ~2 GB que Cassandra tomaría por defecto en esta VM. Sirve para la carga de muestra; no es un tamaño de producción. El límite del contenedor quedó en 1 100 MB porque cada `nodetool` que corren los scripts dentro del contenedor levanta otra JVM: con 900 MB, el *cgroup* mató a cas1 (`OOMKilled`) en medio de una prueba.

### 3.5 Contraste con el Hito 3

- **"Comentarios AP, eventual, N=3 R=1 W=1": se confirma.** Con un nodo caído las escrituras y lecturas con ONE siguen; un comentario puede no verse en una réplica hasta que llega el hint o el repair. El impacto que preveía el Hito 3 ("un comentario tarda en aparecer para otros") es exactamente la lectura vieja de §3.3.
- **"Auditoría: con N=3 y W=QUORUM la escritura se sostiene mientras al menos dos réplicas respondan": se confirma para un nodo caído** (escritura QUORUM aceptada con cas3 caído). No se probó con dos caídos.
- **Lo que el Hito 3 no decía:** la reparación por hints tiene un límite (3 h) y hace falta `nodetool repair` periódico (§3.3).

## 4. Qué se resigna en cada subsistema, en una línea

| Subsistema | Durante una partición o caída… | Medido |
|---|---|---|
| N1 Equipos y jugadores | no se escribe hasta que hay primario (~10 s); se lee de secundarios, quizás viejo | Sí |
| N2 Partidos / N8 Tipos | el cierre de un partido espera a tener mayoría | No (Neo4j Community) |
| N3 Eventos | se siguen leyendo eventos de réplicas, quizás atrasados; la escritura necesita mayoría (ver §5.2) | No |
| N5 Sesiones | se sigue respondiendo; una sesión puede perderse y el usuario vuelve a entrar | No (Redis de un nodo) |
| N6 Comentarios | se sigue escribiendo y leyendo con ONE; un comentario puede tardar en aparecer en otra réplica | Sí |
| N7 Estadísticas | sin réplica, si cae el nodo no hay estadísticas | No (InfluxDB 3 Core) |

## 5. Subsistemas que el laboratorio no replica

### 5.1 Redis (N5 Sesiones)

Redis replica de forma **asíncrona**: el primario confirma antes de que la réplica tenga el dato. Si Sentinel (o Redis Cluster) promueve una réplica después de una caída, las escrituras que no habían llegado se pierden. Es AP sin vuelta: incluso `WAIT` (esperar a N réplicas) no lo hace CP, porque una réplica promovida puede no tener lo último. Coincide con el Hito 3: la sesión es un dato que se acepta perder (el usuario vuelve a autenticarse) y por eso no se replica entre regiones. El módulo del Hito 7 es un nodo, sin réplica ni Sentinel ([`fixture2030-redis/docs/memoria_y_escalabilidad.md`](../../fixture2030-redis/docs/memoria_y_escalabilidad.md) §5).

### 5.2 Neo4j (N2 Partidos, N3 Eventos, N8 Tipos de evento)

El clúster de Neo4j (solo en Enterprise) replica con Raft: una transacción se confirma cuando la tiene la **mayoría de los servidores primarios** de la base; las réplicas secundarias copian de forma asíncrona y sirven lecturas, con *bookmarks* para leer lo propio. El repo usa Neo4j Community, que no tiene clúster: nada de esto se pudo levantar.

- **N2 Partidos y N8 Tipos de evento (CP, mayoría 2 de 3): el motor lo cumple** con un clúster de 3 primarios.
- **N3 Eventos: el Hito 3 pide algo que Neo4j no hace.** El Hito 3 define el registro de un evento como "confirma en la región de ingesta del partido y se propaga a las demás en segundo plano", y lo llama AP. En un clúster Neo4j no hay confirmación local sin mayoría: **toda escritura** pasa por Raft, también la de un evento. Lo que sí es asíncrono son las lecturas desde réplicas secundarias en otras regiones. Por lo tanto, con Neo4j los eventos quedan **CP en escritura y AP en lectura**, no AP en escritura. El Hito 3 eligió poner Partidos y Eventos en el mismo motor con garantías distintas por operación; con Neo4j esa diferencia existe para la lectura, no para la escritura. No se reescribe el Hito 3: se deja anotado para revisarlo con el equipo. Si la ingesta de eventos tuviera que seguir aceptando escrituras en una región aislada, haría falta una cola de ingesta por región delante de Neo4j, que hoy no forma parte de la arquitectura.

### 5.3 InfluxDB (N7 Estadísticas en vivo)

El Hito 3 describe una réplica conceptual "de bajo factor dentro de la región de ingesta". InfluxDB 3 Core, la edición que usa el módulo del Hito 8, es nodo único y no replica: la réplica y la alta disponibilidad son de InfluxDB 3 Enterprise ([`fixture2030-influxdb/docs/cardinalidad_y_escalabilidad.md`](../../fixture2030-influxdb/docs/cardinalidad_y_escalabilidad.md)). Con la edición elegida, una caída del nodo deja a N7 **sin disponibilidad**, que es lo contrario de lo que pide AP. El diseño del Hito 3 sigue siendo válido, pero no se puede implementar con InfluxDB 3 Core.

## 6. Qué no se probó y por qué

| No se probó | Por qué |
|---|---|
| Partición de red con los dos lados vivos (p. ej. el primario de MongoDB aislado pero funcionando) | Se probaron caídas de nodo. Aislar un contenedor con `docker network disconnect` era posible, pero la guía pide failover y consistencia eventual; queda como siguiente paso. Lo esperado: el primario aislado renuncia al no ver mayoría y del otro lado se elige uno nuevo |
| Dos nodos caídos a la vez | En MongoDB no habría primario (ni escritura); en Cassandra QUORUM fallaría y ONE seguiría. No medido |
| Varias regiones o datacenters (el Hito 3 replica por región) | Todo corre en una notebook; un solo datacenter de Cassandra y un solo replica set |
| Pérdida de una escritura `w: 1` por *rollback* en MongoDB | Se mostró que `w: 1` confirma sin mayoría (§2.3); no se provocó la caída del primario en ese estado |
| Failover bajo carga real | El escritor de la prueba hace 5 escrituras por segundo, no la carga del Hito 12 |
| Replicación de Neo4j, Redis e InfluxDB | Neo4j Community e InfluxDB 3 Core no replican; Redis sí podría, pero la guía pide MongoDB y Cassandra |
| N4 Usuarios y N9 Auditoría | No están implementados en el repo |
