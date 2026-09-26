# Correcciones del profesor — Hito 2

**Fuente:** transmitidas por el grupo (Joaquín Núñez) el 26/09/2026, como texto.

---

Deben revisar especialmente las decisiones N2 Partidos y N4 Usuarios, cuyos márgenes son apenas 0,10, para validar que no dependan excesivamente de una única ponderación. También deberían resolver la contradicción de Auditoría: reconocen que perder registros invalida su propósito, pero seleccionan un enfoque con garantías BASE. Estas tres decisiones necesitan mayor evidencia antes de implementarse.

---

## Estado — ✅ aplicada en el documento (26/09/2026)

Las tres decisiones (N2, N4, N9) tienen ahora un párrafo "Resuelto en el Hito 3" en [`hito-2-matriz-decision.md`](./hito-2-matriz-decision.md), Sección 4, que cierra el pedido de más evidencia con un resumen del argumento y un link a la sección exacta del Hito 3. Ver "Historial de revisión" al final de ese documento.

## Lectura para las skills de validación

El profesor confirma acá, con sus propias palabras, que **el margen real de N2 y N4 es 0,10** — coincide exactamente con la matriz (sección 3 de [`hito-2-matriz-decision.md`](./hito-2-matriz-decision.md)). Esto es evidencia adicional, independiente del PDF del Hito 2, de que la cifra correcta es 0,10 y no 0,20 — el Hito 3 tenía "0,20" en varios lugares y ya se corrigió, ver "Historial de revisión" en [`../hito-3-arquitectura-distribuida/hito-3-arquitectura-distribuida.md`](../hito-3-arquitectura-distribuida/hito-3-arquitectura-distribuida.md).

Las tres decisiones que el profesor pide reforzar con evidencia son exactamente las que el Hito 3 aborda en su sección de "Análisis CAP": N2 (§ N2 · Partidos), N4 (§ N4 · Usuarios) y N9 (§ N9 · Auditoría). Es la corrección de un hito resuelta *en* el hito siguiente — el patrón incremental que hay que tener en cuenta al validar: que un hito posterior no repita un valor de un hito anterior no es necesariamente un error, puede ser la resolución de este pedido. Lo que sí fue un error (ya corregido) es que, al resolverlo, el Hito 3 haya invertido el ganador de N2 — ver "Historial de revisión" en el documento del Hito 3.
