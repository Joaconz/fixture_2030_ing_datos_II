---
name: auditar-hito
description: Audita un hito del proyecto Fixture 2030 ya implementado contra sus requisitos oficiales (funcionales, no funcionales, y las decisiones heredadas de los Hitos 2/3), señala y corrige lo objetivamente incorrecto, y deja un informe. Usar después de terminar de implementar un hito nuevo, o cuando el profesor devuelve una corrección sobre un hito ya entregado. No usar antes de implementar (para eso existe /validar-hito) ni para decisiones de diseño desde cero.
---

# Auditar hito — chequeo posterior a la implementación

Generaliza el patrón de `fixture2030-mongodb/docs/HITO4_AUDIT_SPEC.md`, que ya funcionó para auditar el Hito 4 (y detectó, entre otras cosas, el bug de carga no determinística que sigue documentado en `docs/ESTADO-CANONICO-NECESIDADES.md`, Hallazgo H1). Esta skill aplica el mismo método a cualquier hito, para no tener que escribir un spec de auditoría nuevo a mano cada vez.

**Leer primero `fixture2030-mongodb/docs/HITO4_AUDIT_SPEC.md` completo como ejemplo de referencia** — el formato de este documento es el mismo, aplicado de forma genérica.

## Regla central (la misma que ya usó el Hito 4)

- **Se corrige directamente:** errores de sintaxis, un `docker-compose.yml` que no levanta, una carga que duplica datos al re-ejecutarse, una consulta pedida en los requisitos que no existe o tira error, un índice que la documentación dice que existe pero no está creado, rutas hardcodeadas que rompen portabilidad, inconsistencias entre lo documentado y lo implementado, incumplimientos literales de un RNF de infraestructura (como el volumen nombrado de RNF2).
- **No se cambia sin señalarlo explícitamente en el informe:** decisiones de modelado (embedding vs. referencias, qué índices crear, reglas de validación de negocio, estructura de colecciones/tablas/nodos), y cualquier cosa que afecte a otro módulo ya entregado (por ejemplo, cambiar cómo se genera un identificador que otro hito ya asume como estable). Estas decisiones las tiene que poder defender el equipo en una evaluación oral — anotarlas como recomendación, no reescribirlas en silencio.
- Si algo no se puede verificar porque falta información (por ejemplo, no hay evidencia de una decisión del Hito 2/3 en el repo), marcarlo como **"No verificable — falta insumo"**, no asumirlo ni inventarlo.

## Paso 1 — Ubicar el hito en el mapa canónico

Leer `docs/ESTADO-CANONICO-NECESIDADES.md` completo. Ubicar qué necesidad(es) N1–N9 cubre el hito a auditar, cuál es su modelo/CAP/N-R-W canónico, y si hay algún hallazgo abierto que lo involucre.

## Paso 2 — Armar el checklist RF/RNF para este hito

No hay un checklist fijo para cada tecnología: se deriva, siguiendo el mismo criterio que usó `HITO4_AUDIT_SPEC.md`, de tres fuentes:

1. **Los requisitos funcionales propios del hito** (qué pidió el enunciado para este módulo: operaciones CRUD, tipos de consulta, volumen mínimo, evidencia).
2. **Los RNF de infraestructura, que son los mismos para todos los módulos de esta materia** (reproducibilidad desde cero — `docker compose up` sin pasos manuales no documentados —, persistencia real entre `down`/`up`, **volumen nombrado, no bind mount** (RNF2 — ver el caso ya encontrado en Cassandra), sin rutas absolutas hardcodeadas (RNF7), carga reproducible sin duplicados/sin crecer en cada corrida, evidencia real de comandos ejecutados y no solo prosa afirmando que se hizo).
3. **Lo heredado de los Hitos 2/3 para la(s) necesidad(es) que este hito cubre**: el modelo correcto (contra la matriz del Hito 2, no contra una cita de segunda mano), la propiedad CAP y los parámetros de réplica/N-R-W del Hito 3, y cualquier identificador o dato que el hito declare "reutilizar" de otro módulo — verificar esa reutilización contra el código real del otro módulo, no contra su documentación (ver el caso de `jugadores.dni`, Hallazgo H1, que se detectó exactamente así).

## Paso 3 — Verificar, con comandos reales, no de memoria

Para cada ítem del checklist: ejecutar el comando (`docker compose config`, `docker compose up -d` desde estado limpio, contar documentos/filas/nodos antes y después de un restart, correr el script de carga dos veces seguidas y comparar conteos, `explain`/`EXPLAIN` de una consulta, etc.) y registrar el resultado real, no una suposición. Esto es lo que distingue una auditoría de una relectura de la documentación.

## Paso 4 — Informe final

Generar `docs/auditoria_hitoN.md` **dentro de la carpeta del módulo auditado** (mismo lugar que `fixture2030-mongodb/docs/`), con:

1. Tabla de requisitos (RF/RNF, numerados igual que en el enunciado del hito si existe una numeración previa): estado (`PASS` / `FAIL` / `No verificable — falta insumo`), evidencia concreta (comando ejecutado + output relevante).
2. Lista de cambios aplicados automáticamente, con el motivo de cada uno.
3. Lista de decisiones de diseño **no tocadas** que quedan señaladas para revisión humana, con la razón.
4. Gaps de documentación o de trazabilidad hacia el Hito 2/3 que el equipo necesita completar a mano.

## Paso 5 — Cerrar el círculo con el mapa canónico

Actualizar `docs/ESTADO-CANONICO-NECESIDADES.md`:
- Marcar la necesidad como implementada (si no lo estaba) o corregir su estado.
- Mover a "Resueltos" cualquier hallazgo abierto que esta auditoría haya efectivamente corregido, citando qué se hizo.
- Agregar como hallazgo nuevo cualquier problema encontrado que no se haya podido corregir en el momento (por ejemplo, por afectar a otro módulo ya entregado).

No dar la auditoría por terminada sin este último paso: es lo que permite que la próxima vez que se use `/validar-hito` para un hito nuevo, ya tenga la información actualizada sin tener que releer todo el repo desde cero.
