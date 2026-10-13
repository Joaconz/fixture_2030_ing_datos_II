# Correcciones del profesor — Hito 3

**Fuente:** transmitidas por el grupo (Joaquín Núñez) el 26/09/2026, como texto.

---

Deben revisar N/R/W en Estadísticas (InfluxDB): lo presentan como N=3, R=1, W=1 aunque el hito indica aplicarlo solo cuando la tecnología lo permita, y en Clase 3 se trabaja principalmente como modelo de quórum para Cassandra. Para el próximo hito conviene expresar en InfluxDB réplica y consistencia conceptualmente y reservar N/R/W explícito para Cassandra. El resto está bien alineado y trazable.

---

## Lectura para las skills de validación

Esta corrección **ya está aplicada** en [`hito-3-arquitectura-distribuida.md`](./hito-3-arquitectura-distribuida.md): la nota introductoria del documento la referencia explícitamente, y la tabla de replicación describe Estadísticas en vivo (InfluxDB) de forma conceptual ("Réplica conceptual (no N/R/W explícito)"), reservando N/R/W numérico para Cassandra (Comentarios y Auditoría). No requiere acción adicional.

**Punto crítico para `/validar-hito` y `/auditar-hito`:** la frase final, *"el resto está bien alineado y trazable"*, es la evaluación del profesor sobre el documento tal como fue entregado — **no vio, o no marcó, la contradicción entre este documento y el Hito 2 sobre N2 Partidos** (corregida el 26/09/2026, ver "Historial de revisión" en [`hito-3-arquitectura-distribuida.md`](./hito-3-arquitectura-distribuida.md)). Que una corrección docente no mencione algo no significa que ese algo esté bien: significa que no fue el foco de esa revisión puntual. Cualquier chequeo de consistencia automatizado tiene que seguir comparando contra la matriz del Hito 2 directamente, no asumir que "el resto está bien" cubre absolutamente todo.

---

## 13/10/2026 — Aprobación de la reentrega sin el modelo de objetos

**Fuente:** transmitida por el grupo (Joaquín Núñez) el 13/10/2026: el profesor dio el ok a la propuesta del grupo.

**Qué se propuso y quedó aprobado:** sacar IRIS (modelo de objetos) de la arquitectura. Partidos (N2) y Tipos de evento (N8) pasan a Neo4j, junto con Eventos (N3). Estadísticas en vivo (N7) **sigue en InfluxDB**.

**Aplicada** en [`hito-3-arquitectura-distribuida.md`](./hito-3-arquitectura-distribuida.md): nueva sección "Revisión de la asignación del modelo de objetos (reentrega)" y entrada del 13/10/2026 en el "Historial de revisión".

## Lectura para las skills de validación (reentrega)

Desde el 13/10/2026 la asignación vigente de N2 y N8 es **Grafo (Neo4j)**, no la de la matriz del Hito 2. La matriz sigue siendo la fuente de **puntajes y márgenes**, pero ya no de la asignación final de esas dos necesidades: un documento posterior que ubique Partidos o Tipos de evento en Neo4j **no** contradice la arquitectura vigente. Uno que los ubique en IRIS describe la arquitectura anterior a la reentrega (válido solo para el Hito 9, que se entregó antes).

