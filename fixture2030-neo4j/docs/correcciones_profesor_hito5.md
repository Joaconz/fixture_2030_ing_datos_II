# Correcciones del profesor — Hito 5

**Fuente:** transmitidas por el grupo (Joaquín Núñez) el 26/09/2026, como texto.

---

Corrigieron la idempotencia observada en el Hito 4 mediante MERGE y una carga determinística. Para mejorar, deben resolver la trazabilidad de jugadores: el Hito 5 afirma reutilizar `jugadores.dni`, pero en el Hito 4 esos identificadores no habían resultado estables entre cargas. Para el próximo hito deben fijar una identidad determinística y demostrar la correspondencia MongoDB–Neo4j.

---

## Lectura para las skills de validación — ⚠️ hallazgo abierto, no resuelto

Este módulo usa `MERGE` para que su **propia** carga sea idempotente (correcto, y confirmado en [`decisiones.md`](./decisiones.md) §3.1, tabla de trazabilidad, fila "Hito 4 → Clave natural..."). Pero la idempotencia de Neo4j sobre sí mismo no es lo mismo que la correspondencia con MongoDB que el profesor pide demostrar, y esa parte sigue sin resolverse:

- `decisiones.md` línea ~129 dice que los 1.282 jugadores de este módulo son **"Sintéticos, generados con fórmulas deterministas"** — es decir, Neo4j **no lee los jugadores reales desde MongoDB**, genera los suyos propios con un formato compatible (`dni` con patrón `^[0-9]{7,8}$`).
- El propio `seed.js` de MongoDB (Hito 4) todavía genera `dni` con Faker sin semilla fija — ver [`../../fixture2030-mongodb/docs/correcciones_profesor_hito4.md`](../../fixture2030-mongodb/docs/correcciones_profesor_hito4.md). Como los valores no son estables ahí tampoco, no hay ningún conjunto de `dni` real contra el cual demostrar que este módulo "reutiliza" el mismo identificador — sólo comparten el patrón del formato, no valores concretos verificados entre los dos sistemas.

**Conclusión:** la frase "se reutilizan las mismas claves (`jugadores.dni`)" en `decisiones.md` §3.1 es más fuerte de lo que el estado real del repo sostiene. No es una integración por código (explícitamente fuera de alcance, y está bien que lo esté), pero tampoco hay evidencia de una correspondencia real dato-a-dato — son dos generadores sintéticos independientes que coinciden en formato.

**No se modificó nada en este módulo.** Es una decisión de diseño de datos que involucra a dos módulos ya entregados (Hito 4 y Hito 5); corresponde señalarla, no tocarla en silencio — ver [`docs/ESTADO-CANONICO-NECESIDADES.md`](../../docs/ESTADO-CANONICO-NECESIDADES.md), hallazgo H1, para la decisión pendiente sobre cómo resolverlo.
