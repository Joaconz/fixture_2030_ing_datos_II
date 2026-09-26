# Estado canónico de las necesidades N1–N9 — Fixture 2030

**Este es el documento que consultan `/validar-hito` y `/auditar-hito` antes de tocar código.** Consolida, para cada necesidad de datos, qué se decidió, qué lo confirmó o corrigió después, y qué existe *realmente* en el repositorio hoy — verificado leyendo el código y la configuración, no repitiendo lo que dice la documentación de cada módulo.

## Reglas de este documento (leer antes de editarlo)

1. **Nunca se reescribe una decisión pasada para que coincida con una nueva.** Si un hito futuro cambia una decisión de forma legítima (con evidencia nueva, como el propio Hito 3 hizo con N2/N4 a pedido del profesor), se agrega una fila nueva fechada en la necesidad correspondiente citando la fuente del cambio — la fila vieja queda, tachada o marcada como superada, no se borra.
2. **La fuente de un puntaje/margen siempre es el Hito 2** ([`hito-2-matriz-decision/hito-2-matriz-decision.md`](./hito-2-matriz-decision/hito-2-matriz-decision.md)). Si cualquier otro documento del repo cita un puntaje o margen distinto, ese documento tiene un error — el Hito 3 ya tuvo uno (N2 Partidos) y quedó corregido, ver "Historial de revisión" en [`hito-3-arquitectura-distribuida/hito-3-arquitectura-distribuida.md`](./hito-3-arquitectura-distribuida/hito-3-arquitectura-distribuida.md).
3. **"Estado real de implementación" se verifica contra el repositorio**, no contra lo que un README afirma. Un módulo "implementado" tiene código/config que corre; una entidad "fuente de verdad en X" solo cuenta como implementada si X existe en el repo con datos reales, no como intención documentada.
4. Este documento no reemplaza los documentos de cada hito — es el índice que dice dónde está la verdad de cada cosa y si hoy coincide con lo implementado.

---

## Tabla por necesidad

| # | Necesidad | Decisión Hito 2 (fuente) | Confirmación/ajuste Hito 3 | Estado real de implementación (verificado 26/09/2026) |
|---|---|---|---|---|
| N1 | Equipos y jugadores | **Documental (MongoDB)**, 4,40, margen 0,40 sobre Objetos (4,00) | CP en escritura / AP en lectura; réplica por región; N=3 | ✅ Implementado — Hito 4, `fixture2030-mongodb/`. **Con bug abierto**: ver Hallazgo H1 (carga de `jugadores` no determinística) |
| N2 | **Partidos** | **Objetos (IRIS)**, 4,25, margen **0,10** sobre Documental (4,15) | ✅ CP, nodo autoritativo único, réplica síncrona hacia 2 réplicas, N=3. (El documento original invertía esto — decía "Documental por 0,20" — corregido el 26/09/2026, ver "Historial de revisión" en [`hito-3-arquitectura-distribuida.md`](./hito-3-arquitectura-distribuida/hito-3-arquitectura-distribuida.md)) | ❌ No implementado. No existe módulo IRIS en el repo. Las referencias en Redis (Hito 7) ya fueron corregidas para apuntar a IRIS (commit `f94309e`) |
| N3 | Eventos | Grafo (Neo4j), 4,25, margen 0,50 | AP con consistencia causal; partición por partido; réplica multi-región asíncrona | ✅ Implementado — Hito 5, `fixture2030-neo4j/`. Jugadores propios generados sintéticamente (ver Hallazgo H1) |
| N4 | Usuarios | Documental (MongoDB), 4,10, margen **0,10** sobre Columnar (4,00) | AP, eventual + consistencia de sesión propia. (El documento original decía margen "0,20" y citaba a Partidos como parte del mismo núcleo documental — las dos cosas corregidas el 26/09/2026, ver "Historial de revisión" en [`hito-3-arquitectura-distribuida.md`](./hito-3-arquitectura-distribuida/hito-3-arquitectura-distribuida.md); no cambia el ganador) | ❌ No implementado. Hito 4 sólo implementó `equipos` y `jugadores`; no existe colección `usuarios` |
| N5 | Sesiones | Clave-valor (Redis), 4,35, margen 0,35 | AP, eventual, TTL, local por región, sin réplica cross-región | ✅ Implementado — Hito 7, `fixture2030-redis/` |
| N6 | Comentarios | Columnar (Cassandra), 4,70, margen 0,85 | AP eventual; partición compuesta (partido + ventana temporal); N=3, R=1, W=1 | ✅ Implementado — Hito 6, `fixture2030-cassandra/`. RNF2 (volumen nombrado) estaba incumplido, corregido 26/09/2026 (ver Hallazgos, resuelto) |
| N7 | Estadísticas en vivo | Series temporales (InfluxDB), 4,75, margen 0,80 | AP eventual con orden monótono por partido; partición por partido+intervalo; **réplica conceptual, sin N/R/W explícito** (corrección del profesor al Hito 3, ya aplicada en el doc) | ❌ No implementado. No existe módulo InfluxDB en el repo |
| N8 | Entidades complejas (Tipos de evento) | Objetos (IRIS), 4,60, margen 1,00 | CP; fuerte sobre el catálogo de tipos; réplica síncrona de baja frecuencia | ❌ No implementado. Mismo módulo IRIS pendiente que N2 — **decisión de diseño a confirmar: ¿un solo módulo IRIS para N2+N8, o dos separados?** (la matriz los trata como necesidades distintas, pero comparten motor) |
| N9 | Auditoría e históricos | Columnar (Cassandra), 4,50, margen 0,50 | AP con escritura reforzada; N=3, R=1, W=QUORUM; partición por ventana temporal + entidad afectada | ❌ No implementado. El Cassandra actual (Hito 6) es sólo el keyspace de Comentarios — la propia matriz del Hito 2 aclara que N6 y N9, aunque compartan motor, **son keyspaces/tablas separados con criterio de partición propio** (ver Hito 2 §4, nota "Sobre la coincidencia entre N6 y N9") |

## Hitos restantes conocidos (a confirmar con el equipo)

Necesidades sin implementar hoy: **N2 y N8 (IRIS)**, **N4 (Usuarios, MongoDB)**, **N7 (InfluxDB)**, **N9 (Auditoría, Cassandra separado de Comentarios)**.

> ⚠️ Esta lista salió de leer la matriz real y el estado del repo, y ya se le preguntó al equipo si coincide con lo que tienen planeado — la respuesta fue "es distinto" sin precisar en qué. **Falta esa aclaración** para saber, por ejemplo, si estas cinco necesidades son 5 hitos separados, se agrupan en menos entregas, o alguna tiene un alcance distinto al de la matriz. Actualizar esta sección en cuanto se confirme.

---

## Hallazgos abiertos

### H1 — `jugadores.dni` no es determinístico entre corridas (MongoDB), y la correspondencia con Neo4j no está demostrada

- **Origen:** corrección del profesor al Hito 4 (ver [`../fixture2030-mongodb/docs/correcciones_profesor_hito4.md`](../fixture2030-mongodb/docs/correcciones_profesor_hito4.md)), retomado en la corrección al Hito 5 (ver [`../fixture2030-neo4j/docs/correcciones_profesor_hito5.md`](../fixture2030-neo4j/docs/correcciones_profesor_hito5.md)).
- **Estado verificado (26/09/2026):** sigue abierto. `fixture2030-mongodb/load/seed.js` genera `dni` con Faker sin semilla fija (y también genera una cantidad aleatoria de jugadores por equipo en cada corrida) → no es idempotente. `fixture2030-neo4j` no lee jugadores desde Mongo: genera los suyos propios, sintéticos, con el mismo formato de `dni` pero sin correspondencia de valores verificada.
- **Por qué no se corrigió solo:** toca el generador de datos de un hito ya entregado y evaluado (Hito 4) y la decisión de diseño de otro (Hito 5, que asume esa clave como estable). Según las reglas de auditoría de este proyecto (ver [`../fixture2030-mongodb/docs/HITO4_AUDIT_SPEC.md`](../fixture2030-mongodb/docs/HITO4_AUDIT_SPEC.md), sección "Reglas de la auditoría"), esto se señala para que el equipo lo decida, no se reescribe en silencio.
- **Pendiente de decisión del equipo:** cómo fijar la identidad — ¿`dni` determinístico por fórmula (p. ej. derivado de `equipoId` + dorsal), Mongo como única fuente y Neo4j leyendo/replicando su `dni` real, o algo distinto? Cualquier hito que en adelante dependa de `jugadores.dni` como clave estable (por ejemplo, si Usuarios o Auditoría llegaran a referenciar jugadores) hereda este problema hasta que se resuelva.

### Resueltos

- **RNF2 Cassandra (bind mount, no volumen nombrado).** Origen: corrección del profesor al Hito 6. Corregido 26/09/2026 en `fixture2030-cassandra/docker-compose.yml` y su README, siguiendo el patrón ya usado en Redis. Ver [`../fixture2030-cassandra/docs/correcciones_profesor_hito6.md`](../fixture2030-cassandra/docs/correcciones_profesor_hito6.md).
- **N2 Partidos apuntando a MongoDB en vez de IRIS** en el módulo Redis. Origen: error heredado del Hito 3. Corregido antes de esta sesión, en los commits `f94309e` y `73c7d9d`.
- **N2 Partidos apuntando a MongoDB en vez de IRIS, dentro del propio documento del Hito 3** (tabla resumen, párrafo de validación, diagrama, y un efecto de segundo orden en el argumento de N4). Corregido el 26/09/2026 — ver "Historial de revisión" en [`hito-3-arquitectura-distribuida/hito-3-arquitectura-distribuida.md`](./hito-3-arquitectura-distribuida/hito-3-arquitectura-distribuida.md).
- **Margen de N4 Usuarios citado como "0,20" en vez de "0,10"** en el Hito 3 (tabla resumen, nota de márgenes frágiles, párrafo de validación). Corregido el 26/09/2026, mismo lugar. No cambiaba el modelo ganador.

---

## Cómo usan esto las skills

- **`/validar-hito`** (antes de implementar): lee este documento completo antes que nada, ubica la(s) necesidad(es) que el hito nuevo va a cubrir, y verifica cada afirmación del plan contra la fila correspondiente y contra el estado real (no contra lo que otro doc de hito *dice* que hay). Si el hito nuevo depende de un hallazgo abierto (como H1), no lo hereda en silencio: lo confirma resuelto, o lo señala explícitamente como limitación conocida.
- **`/auditar-hito`** (después de implementar): además de auditar el hito nuevo contra sus propios requisitos, actualiza este documento — cierra hallazgos resueltos, agrega los que encuentre.
