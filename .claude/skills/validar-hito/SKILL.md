---
name: validar-hito
description: Valida el plan de un hito nuevo (o de una extensión de un módulo existente) del proyecto Fixture 2030 contra las decisiones canónicas de hitos anteriores, ANTES de escribir código o documentación de implementación. Usar siempre que se vaya a implementar un hito restante (IRIS para Partidos/Tipos de evento, InfluxDB para Estadísticas, Usuarios en MongoDB, Auditoría en Cassandra) o a modificar el alcance de un módulo ya entregado. No usar para dudas generales de la materia ni para auditar un hito ya terminado (para eso existe /auditar-hito).
---

# Validar hito — chequeo previo a la implementación

Este proyecto (Ingeniería de Datos II, Fixture 2030) construye los hitos de forma incremental: cada módulo nuevo hereda decisiones de los hitos 1-3 (qué motor le corresponde a cada necesidad, qué garantías CAP y de replicación tiene que respetar) y a veces datos o identificadores de módulos ya implementados. Dos veces ya se implementó un hito nuevo confiando en una cita de "el Hito X dice tal cosa" sin volver a leer la fuente real, y las dos veces la cita estaba mal (ver "Historial de revisión" en `docs/hito-3-arquitectura-distribuida/hito-3-arquitectura-distribuida.md`). Esta skill existe para que eso no pase una tercera vez: audita el **plan**, antes de que se convierta en código.

No es una skill de diseño — no toma la decisión de qué modelo usar (eso ya está decidido en el Hito 2) ni cómo implementarlo (eso lo decide el equipo). Es un chequeo de consistencia: lo que se está por construir, ¿coincide con lo que ya se decidió y con lo que realmente existe en el repo?

## Paso 1 — Identificar qué necesidad(es) cubre el hito nuevo

Antes de leer nada más, identificar a qué fila (o filas) de `docs/ESTADO-CANONICO-NECESIDADES.md` corresponde el trabajo que se va a hacer (N1–N9). Si no es obvio por el pedido del usuario, preguntar. Un hito puede cubrir más de una necesidad (por ejemplo, un módulo IRIS cubriría N2 y N8 a la vez).

## Paso 2 — Leer las fuentes canónicas, completas, no solo la fila resumen

1. **`docs/ESTADO-CANONICO-NECESIDADES.md` completo** — no solo la fila de la necesidad en cuestión. La sección "Hallazgos abiertos" aplica a cualquier hito que dependa de esos datos, no solo al que los originó.
2. La sección de esa necesidad en `docs/hito-2-matriz-decision/hito-2-matriz-decision.md` (Sección 4) — el modelo, el puntaje, el margen y el criterio determinante salen de ahí, de ningún otro lado.
3. La sección de esa necesidad en `docs/hito-3-arquitectura-distribuida/hito-3-arquitectura-distribuida.md` (CAP, replicación, N/R/W) — **y su "Historial de revisión"**, por si esa sección tuvo un error corregido.
4. Si el hito nuevo va a reusar un identificador, dato o supuesto de un módulo ya implementado (por ejemplo, un `PAR-*`, un `USR-*`, una relación a `equipos._id`), no alcanza con leer el README de ese módulo: hay que abrir el código/config real (script de carga, esquema, docker-compose) y confirmar que lo que se va a asumir es cierto hoy, no lo que un doc dice que debería ser cierto. `docs/ESTADO-CANONICO-NECESIDADES.md` § Hallazgos abiertos ya tiene un ejemplo de por qué esto importa (H1: `jugadores.dni`).

## Paso 3 — Construir la tabla de verificación

Antes de escribir una sola línea de implementación, producir esta tabla (en la respuesta al usuario, no hace falta guardarla como archivo salvo que el usuario lo pida):

| Afirmación del plan nuevo | Fuente citada | Verificado contra | Resultado | Acción |
|---|---|---|---|---|
| (ej: "Partidos vive en MongoDB") | Un doc de hito viejo, sin re-verificar | Hito 2 §4 (matriz con puntajes) | **Contradice** | Es Objetos/IRIS por 0,10 — este error concreto ya se corrigió (ver Historial de revisión del Hito 3), pero sirve de ejemplo de qué buscar |
| (ej: "se reutiliza jugadores.dni de Mongo") | README Neo4j | `fixture2030-mongodb/load/seed.js` | **No verificable / conocido como falso** | Ver Hallazgo H1: dni no es estable. No asumir sin resolver primero |
| (ej: "Sesiones no replica entre regiones") | Hito 3 §CAP | Hito 3 §CAP (sin contradicción) | **Consistente** | Ninguna |

Resultado posibles: **Consistente** (coincide con la fuente y con el estado real), **Contradice** (una fuente dice una cosa, otra dice otra, o el plan afirma algo que el repo desmiente), **No verificable — falta insumo** (no hay manera de confirmarlo con lo que hay en el repo; no inventar una respuesta).

## Paso 4 — Actuar sobre el resultado

- Si hay filas **Contradice**: parar y mostrarle la tabla al usuario antes de escribir código. No decidir unilateralmente cuál de las dos fuentes tiene razón si ambas parecen legítimas — mostrar la evidencia de las dos y preguntar, salvo que ya exista una errata documentada que lo resuelva (como la de N2/Partidos, donde el Hito 2 ya es la fuente confirmada).
- Si hay filas **No verificable**: decirlo explícitamente en el plan de implementación ("esto se asume sin poder verificarlo porque X"), igual que pide `HITO4_AUDIT_SPEC.md` para las auditorías. No inventar un valor ni asumir que "seguramente está bien".
- Si todo es **Consistente**: recién ahí proceder con la implementación.

## Paso 5 — Dejar trazabilidad en lo que se construye

Todo hito nuevo debe poder responder, en su propia documentación, de dónde sale cada decisión heredada (mismo criterio que pide RNF5 en `fixture2030-mongodb/docs/HITO4_AUDIT_SPEC.md`). Como mínimo, citar el hito y la sección exacta, no solo "según hitos anteriores".

## Reglas que esta skill no puede saltarse

- Nunca editar una decisión histórica en `docs/ESTADO-CANONICO-NECESIDADES.md` o en los docs de hitos pasados para que coincida con el hito nuevo. Si el hito nuevo cambia algo legítimamente, se agrega una entrada nueva y fechada, citando la evidencia — la vieja queda visible.
- Nunca tratar "no lo mencionó la corrección del profesor" como sinónimo de "está bien" — ver el caso de N2/Partidos en el "Historial de revisión" del Hito 3, que el profesor no marcó y aun así estaba mal.
- Al terminar, si se encontró o resolvió algo que afecta a `docs/ESTADO-CANONICO-NECESIDADES.md` (un hallazgo nuevo, uno cerrado, una necesidad que pasa a implementada), actualizar ese documento como parte del mismo trabajo.
