# Correcciones del profesor — Hito 4

**Fuente:** transmitidas por el grupo (Joaquín Núñez) el 26/09/2026, como texto.

---

Deben corregir la carga reproducible: la evidencia contradice la idempotencia declarada; una ejecución agrega 1.306 jugadores y termina con 2.673, señal de que Faker genera nuevas identidades y el upsert no converge al mismo dataset. Además, incorporan estadísticas de goles/partidos/asistencias fuera del alcance del Hito 4. Para el próximo hito deben usar datos deterministas y limitar el modelo a equipos y jugadores.

---

## Lectura para las skills de validación — ✅ lado Mongo corregido (26/09/2026)

Se verificó el estado de [`load/seed.js`](../load/seed.js) contra esta corrección, y se corrigió lo que estaba mal:

- **Equipos:** el `upsert` filtra por `_id: codigo`, y `codigo` sale de la lista estática `EQUIPOS_DATA` — es determinístico. Re-ejecutar el seed no duplica equipos. Ya estaba bien, no se tocó.
- **Jugadores (era el bug, ya corregido):** `generarDniUnico()` generaba el `dni` con `faker.number.int({...})` sin semilla fija, así que cada corrida daba un `dni` nuevo al azar y el `upsert` (que filtra por `{ dni }`) nunca encontraba al jugador de la corrida anterior — insertaba de nuevo en vez de actualizar. **Se reemplazó por `generarDni(equipoIndex, dorsal)`**: una fórmula fija (`30000000 + equipoIndex*100 + dorsal`), sin ninguna aleatoriedad — mismo equipo y mismo dorsal dan siempre el mismo `dni`, en cualquier corrida. También se fijó la cantidad de jugadores por equipo (`TAMANO_PLANTEL = 23`, antes era al azar entre 15 y 26), porque una cantidad variable por corrida era la otra causa de que el total nunca convergiera. Se agregó además `faker.seed(2030)` para que nombre/apellido/fecha de nacimiento (los únicos campos que siguen usando Faker) también sean estables entre corridas.
- Sobre el segundo punto (estadísticas fuera de alcance): el `seed.js` sólo llena `estadisticas: {partidos: 0, goles: 0, asistencias: 0}` en cero, sin datos falsos de rendimiento — ya estaba acotado al alcance de equipos/jugadores. No se encontró evidencia de consultas o cálculos de goles/partidos/asistencias en este módulo.

**Validación (26/09/2026):** no se pudo levantar un Mongo real en este entorno (sin daemon de Docker disponible), así que se validó la lógica de generación por separado — 64 equipos × 23 jugadores = 1.472 DNIs, cero colisiones, resultado idéntico simulando dos corridas — y se verificó la sintaxis del archivo (`node --check`). **Falta la validación final, la real:** correr `node load/seed.js` dos veces seguidas contra un Mongo real y confirmar que `db.jugadores.countDocuments()` da el mismo número las dos veces (1.472) — dejarlo como parte de la evidencia de este hito.

**Lo que queda deliberadamente sin tocar:** la corrección del Hito 5 también pedía *"demostrar la correspondencia MongoDB–Neo4j"* — Neo4j sigue generando sus propios jugadores sintéticos, independientes de Mongo (ver [`../../fixture2030-neo4j/docs/correcciones_profesor_hito5.md`](../../fixture2030-neo4j/docs/correcciones_profesor_hito5.md)). El equipo decidió (26/09/2026) dejar esa parte para el hito donde se integren las bases entre sí, no ahora. Queda registrado en [`docs/ESTADO-CANONICO-NECESIDADES.md`](../../docs/ESTADO-CANONICO-NECESIDADES.md), Hallazgo H1, como parcialmente resuelto.
