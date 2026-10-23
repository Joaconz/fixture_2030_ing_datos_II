# Matriz de conectividad — corrida `20261023-181555_controles-5-4`

- Fecha (UTC): 2026-10-23T18:15:56Z → 2026-10-23T18:16:05Z
- Commit: `ae58c26` · Entorno: notebook-docker-desktop · Origen: notebook (host) · Windows AMD64 · python 3.13.7
- Archivos: [`resultados_clientes.md`](resultados_clientes.md)
- OK = esa prueba concreta funcionó en ese momento; no es garantía de rendimiento ni de disponibilidad permanente (RNF17).

| Dependencia | Estado | Config | DNS | TCP | Protocolo | Autent. | Autoriz. | Contexto | Operación | API | ms TCP | ms operación (driver) | ms API | Controles | Diagnóstico | Siguiente paso | Observaciones (no cambian el estado) |
|---|---|---|---|---|---|---|---|---|---|---|---:|---:|---:|---|---|---|---|
| **mongodb** | **DISPONIBLE** | — | — | — | OK | N/C | N/C | OK | OK | — | — | 1.7–3.5 | — | 3/3 | todas las pruebas ejecutadas terminaron bien en esta corrida (no garantiza rendimiento) | — | — |
| **neo4j** | **NO_PROBADO** | — | — | — | — | — | — | — | — | — | — | — | — | 0/0 | no incluido en esta corrida (filtro --producto o modo parcial) | instalar la herramienta o completar la configuración y repetir | — |
| **cassandra** | **DISPONIBLE** | — | — | — | OK | N/C | N/C | OK | OK | — | — | 3.0–3.3 | — | 4/4 | todas las pruebas ejecutadas terminaron bien en esta corrida (no garantiza rendimiento) | — | — |
| **redis** | **NO_PROBADO** | — | — | — | — | — | — | — | — | — | — | — | — | 0/0 | no incluido en esta corrida (filtro --producto o modo parcial) | instalar la herramienta o completar la configuración y repetir | — |
| **influxdb** | **NO_PROBADO** | — | — | — | — | — | — | — | — | — | — | — | — | 0/0 | no incluido en esta corrida (filtro --producto o modo parcial) | instalar la herramienta o completar la configuración y repetir | — |
| **iris** | **NO_PROBADO** | — | — | — | — | — | — | — | — | — | — | — | — | 0/0 | no incluido en esta corrida (filtro --producto o modo parcial) | instalar la herramienta o completar la configuración y repetir | — |

Totales de la corrida: OK 20 · WARN 0 · FAIL 0 · SKIP 0 · N/C 4

SKIP = prueba no ejecutada por falta de herramienta o configuración; NO significa producto caído. N/C = la capa no aplica en este entorno (p. ej. laboratorio sin autenticación) o el producto no está configurado.
