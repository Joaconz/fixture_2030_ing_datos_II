# Correcciones del profesor — Hito 5

**Fuente:** transmitidas por el grupo (Joaquín Núñez) el 26/09/2026, como texto.

---

Corrigieron la idempotencia observada en el Hito 4 mediante MERGE y una carga determinística. Para mejorar, deben resolver la trazabilidad de jugadores: el Hito 5 afirma reutilizar `jugadores.dni`, pero en el Hito 4 esos identificadores no habían resultado estables entre cargas. Para el próximo hito deben fijar una identidad determinística y demostrar la correspondencia MongoDB–Neo4j.

---

## Lectura para las skills de validación — parcialmente resuelto, resto diferido a propósito (26/09/2026)

Este módulo usa `MERGE` para que su **propia** carga sea idempotente (correcto, y confirmado en [`decisiones.md`](./decisiones.md) §3.1, tabla de trazabilidad, fila "Hito 4 → Clave natural..."). Pero la idempotencia de Neo4j sobre sí mismo no es lo mismo que la correspondencia con MongoDB que el profesor pide demostrar.

- `decisiones.md` línea ~129 dice que los 1.282 jugadores de este módulo son **"Sintéticos, generados con fórmulas deterministas"** — es decir, Neo4j **no lee los jugadores reales desde MongoDB**, genera los suyos propios con un formato compatible (`dni` con patrón `^[0-9]{7,8}$`).
- El `seed.js` de MongoDB (Hito 4) **ya se corrigió** — ver [`../../fixture2030-mongodb/docs/correcciones_profesor_hito4.md`](../../fixture2030-mongodb/docs/correcciones_profesor_hito4.md): ahora genera `dni` con una fórmula fija (`30000000 + equipoIndex*100 + dorsal`, donde `equipoIndex` es la posición 0-63 del equipo en la lista `EQUIPOS_DATA` de Mongo), sin Faker ni azar. Eso resuelve la primera mitad del pedido del profesor ("fijar una identidad determinística"), del lado de Mongo.
- **La segunda mitad ("demostrar la correspondencia MongoDB–Neo4j") es más difícil de lo que parecía, y no es solo la fórmula del dni.** Al revisar [`../queries/carga.cypher`](../queries/carga.cypher) (PASO 4 y PASO 5) para copiar la fórmula, se encontró que **el listado de 64 equipos de este módulo no es el mismo que el de Mongo**: usa códigos FIFA distintos para el mismo país en varios casos (`URU` acá vs. `URY` en Mongo para Uruguay; `CHI` vs. `CHL` para Chile; `PAR` vs. `PRY` para Paraguay; `KSA` vs. `SAU` para Arabia Saudita), incluye países que Mongo no tiene (Grecia, Rumania, Gales, Malí, RD Congo, Emiratos Árabes) y le faltan países que Mongo sí tiene (India, China, Papúa Nueva Guinea, Nueva Caledonia). La asignación de grupos tampoco usa el mismo criterio (acá `i % 16`, en Mongo `Math.floor(i/4)`). Además, el propio tamaño de plantel de este módulo (`18 + rankingFifa % 5`, es decir 18 a 22) no coincide con el de Mongo (fijo en 23). Con equipos distintos por debajo, "usar la misma fórmula de dni" no alcanzaría para que los jugadores correspondan de verdad — el "equipo con índice 5" de un lado y del otro ni siquiera es el mismo país.

**Por qué se deja así:** corregir esto de fondo implica reescribir el listado de equipos de este módulo para que sea idéntico al de Mongo (mismos códigos, mismo orden, mismos 64 países) y unificar el tamaño de plantel — no es un cambio menor sobre un hito (5) ya entregado y aprobado. El equipo decidió (26/09/2026) dejarlo para el hito donde se integren las bases entre sí, en vez de forzar ahora un parche parcial (como igualar solo la fórmula del dni) que daría una falsa sensación de correspondencia sin que los equipos de fondo coincidan. Es una decisión de alcance razonable, no un bug: no se modificó nada en este módulo. Ver [`docs/ESTADO-CANONICO-NECESIDADES.md`](../../docs/ESTADO-CANONICO-NECESIDADES.md), Hallazgo H1, para el estado completo y qué falta.
