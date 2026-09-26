# Correcciones del profesor — Hito 4

**Fuente:** transmitidas por el grupo (Joaquín Núñez) el 26/09/2026, como texto.

---

Deben corregir la carga reproducible: la evidencia contradice la idempotencia declarada; una ejecución agrega 1.306 jugadores y termina con 2.673, señal de que Faker genera nuevas identidades y el upsert no converge al mismo dataset. Además, incorporan estadísticas de goles/partidos/asistencias fuera del alcance del Hito 4. Para el próximo hito deben usar datos deterministas y limitar el modelo a equipos y jugadores.

---

## Lectura para las skills de validación — ⚠️ hallazgo abierto, no resuelto

Se verificó el estado actual de [`load/seed.js`](../load/seed.js) (26/09/2026) contra esta corrección:

- **Equipos:** el `upsert` filtra por `_id: codigo`, y `codigo` sale de la lista estática `EQUIPOS_DATA` — es determinístico. Re-ejecutar el seed no duplica equipos. Esto está bien.
- **Jugadores:** `generarDniUnico()` (línea ~134-142) genera el `dni` con `faker.number.int({...})` **sin fijar semilla** (no hay ningún `faker.seed(...)` en el archivo). El `Set dnisGenerados` sólo evita colisiones *dentro de una misma corrida*, no entre corridas distintas. El `upsert` filtra por `{ dni }`, así que cada ejecución nueva genera un `dni` distinto al azar y el filtro nunca matchea un jugador de la corrida anterior → inserta jugadores nuevos en vez de actualizar los existentes. **Es exactamente el bug que describe esta corrección, y sigue presente.**
- Sobre el segundo punto (estadísticas fuera de alcance): el `seed.js` actual sólo llena `estadisticas: {partidos: 0, goles: 0, asistencias: 0}` en cero, sin datos falsos de rendimiento — parece ya acotado al alcance de equipos/jugadores. No se encontró evidencia de consultas o cálculos de goles/partidos/asistencias en este módulo.

**Por qué sigue abierto pese al Hito 5:** la corrección del Hito 5 dice *"Corrigieron la idempotencia observada en el Hito 4 mediante MERGE y una carga determinística"* — pero esa corrección es del lado de **Neo4j** (su propio cargador genera jugadores sintéticos con fórmulas deterministas, no lee `dni` real de Mongo — ver [`../../fixture2030-neo4j/docs/decisiones.md`](../../fixture2030-neo4j/docs/decisiones.md) §3.1). No corrigió `seed.js` de Mongo. La corrección del Hito 5 pide además *"demostrar la correspondencia MongoDB–Neo4j"*, que tampoco está demostrada: son dos generadores independientes que coinciden en el **formato** del `dni` (`^[0-9]{7,8}$`), no en los valores concretos.

**Acción pendiente (no aplicada automáticamente — afecta el generador de datos, no un bug mecánico):** fijar una fuente determinística para `dni` en `seed.js` — por ejemplo derivarlo de una fórmula estable por `(equipoId, dorsal)` en vez de `faker.number.int` puro, o `faker.seed(<constante>)` al inicio del script combinado con generar la misma cantidad de jugadores por equipo cada vez (hoy `cantJugadores` también es aleatorio por corrida vía `faker.number.int({min:15,max:26})`, lo que agrava el problema: ni la cantidad ni los DNI son estables). Esto se deja señalado para que el equipo lo decida — ver [`docs/ESTADO-CANONICO-NECESIDADES.md`](../../docs/ESTADO-CANONICO-NECESIDADES.md), hallazgo H1.
