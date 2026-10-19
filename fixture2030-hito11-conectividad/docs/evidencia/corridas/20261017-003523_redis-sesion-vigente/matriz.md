# Matriz de conectividad — corrida `20261017-003523_redis-sesion-vigente`

- Fecha (UTC): 2026-10-17T00:35:24Z → 2026-10-17T00:35:54Z
- Commit: `ea51b8f` · Entorno: notebook-docker-desktop · Origen: notebook (host) · Windows AMD64 · python 3.13.7
- Archivos: [`resultados_api.md`](resultados_api.md), [`resultados_clientes.md`](resultados_clientes.md)
- OK = esa prueba concreta funcionó en ese momento; no es garantía de rendimiento ni de disponibilidad permanente (RNF17).

| Dependencia | Estado | Config | DNS | TCP | Protocolo | Autent. | Autoriz. | Contexto | Operación | API | ms TCP | ms operación (driver) | ms API | Controles | Diagnóstico | Siguiente paso | Observaciones (no cambian el estado) |
|---|---|---|---|---|---|---|---|---|---|---|---:|---:|---:|---|---|---|---|
| **mongodb** | **NO_PROBADO** | — | — | — | — | — | — | — | — | — | — | — | — | 0/0 | no incluido en esta corrida (filtro --producto o modo parcial) | instalar la herramienta o completar la configuración y repetir | — |
| **neo4j** | **NO_PROBADO** | — | — | — | — | — | — | — | — | — | — | — | — | 0/0 | no incluido en esta corrida (filtro --producto o modo parcial) | instalar la herramienta o completar la configuración y repetir | — |
| **cassandra** | **NO_PROBADO** | — | — | — | — | — | — | — | — | — | — | — | — | 0/0 | no incluido en esta corrida (filtro --producto o modo parcial) | instalar la herramienta o completar la configuración y repetir | — |
| **redis** | **DISPONIBLE** | — | — | — | OK | N/C | N/C | OK | OK | OK | — | 2.9 | 1026–1058 | 2/2 | todas las pruebas ejecutadas terminaron bien en esta corrida (no garantiza rendimiento) | — | — |
| **influxdb** | **NO_PROBADO** | — | — | — | — | — | — | — | — | — | — | — | — | 0/0 | no incluido en esta corrida (filtro --producto o modo parcial) | instalar la herramienta o completar la configuración y repetir | — |
| **iris** | **NO_PROBADO** | — | — | — | — | — | — | — | — | — | — | — | — | 0/0 | no incluido en esta corrida (filtro --producto o modo parcial) | instalar la herramienta o completar la configuración y repetir | — |
| **api** | **DISPONIBLE** | — | — | — | — | — | — | — | — | OK | — | — | 1032–1060 | 1/1 | todas las pruebas ejecutadas terminaron bien en esta corrida (no garantiza rendimiento) | — | — |

Totales de la corrida: OK 14 · WARN 0 · FAIL 0 · SKIP 0 · N/C 2

SKIP = prueba no ejecutada por falta de herramienta o configuración; NO significa producto caído. N/C = la capa no aplica en este entorno (p. ej. laboratorio sin autenticación) o el producto no está configurado.
