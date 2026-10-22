# Matriz de conectividad — corrida `20261022-203113_config-tcp-nativos-api-matriz-iris`

- Fecha (UTC): 2026-10-22T20:31:13Z → 2026-10-22T20:31:17Z
- Commit: `sin-git` · Entorno: notebook-docker-desktop · Origen: notebook (host) · Darwin arm64 · python 3.9.6
- Archivos: [`resultados_api.md`](resultados_api.md), [`resultados_clientes.md`](resultados_clientes.md), [`resultados_config.md`](resultados_config.md), [`resultados_tcp.md`](resultados_tcp.md)
- OK = esa prueba concreta funcionó en ese momento; no es garantía de rendimiento ni de disponibilidad permanente (RNF17).

| Dependencia | Estado | Config | DNS | TCP | Protocolo | Autent. | Autoriz. | Contexto | Operación | API | ms TCP | ms operación (driver) | ms API | Controles | Diagnóstico | Siguiente paso | Observaciones (no cambian el estado) |
|---|---|---|---|---|---|---|---|---|---|---|---:|---:|---:|---|---|---|---|
| **mongodb** | **NO_PROBADO** | OK | — | — | — | — | — | — | — | — | — | — | — | 0/0 | sólo se comparó su configuración (corrida filtrada con --producto) | instalar la herramienta o completar la configuración y repetir | — |
| **neo4j** | **NO_PROBADO** | OK | — | — | — | — | — | — | — | — | — | — | — | 0/0 | sólo se comparó su configuración (corrida filtrada con --producto) | instalar la herramienta o completar la configuración y repetir | — |
| **cassandra** | **NO_PROBADO** | OK | — | — | — | — | — | — | — | — | — | — | — | 0/0 | sólo se comparó su configuración (corrida filtrada con --producto) | instalar la herramienta o completar la configuración y repetir | — |
| **redis** | **NO_PROBADO** | OK | — | — | — | — | — | — | — | — | — | — | — | 0/0 | sólo se comparó su configuración (corrida filtrada con --producto) | instalar la herramienta o completar la configuración y repetir | — |
| **influxdb** | **NO_PROBADO** | OK | — | — | — | — | — | — | — | — | — | — | — | 0/0 | sólo se comparó su configuración (corrida filtrada con --producto) | instalar la herramienta o completar la configuración y repetir | — |
| **iris** | **DISPONIBLE** | OK | OK | OK | OK | N/C | N/C | OK | OK | OK | 2.0–3.1 | 67–80 | 4.6 | 0/0 | todas las pruebas ejecutadas terminaron bien en esta corrida (no garantiza rendimiento) | — | — |
| **api** | **DEGRADADO** | OK | — | — | — | — | — | — | — | WARN | — | — | 14 | 1/1 | api: HTTP 503 · salud_degradada · estado=NO_LISTA · noDisponibles=['mongodb', 'neo4j', 'cassandra', 'redis', 'influxdb'] · requestId=h11-20261022-203115-02 | el cliente nativo funciona pero la API no: revisar .env de la API, adaptador y log con el requestId | — |

Totales de la corrida: OK 28 · WARN 2 · FAIL 0 · SKIP 1 · N/C 4

SKIP = prueba no ejecutada por falta de herramienta o configuración; NO significa producto caído. N/C = la capa no aplica en este entorno (p. ej. laboratorio sin autenticación) o el producto no está configurado.
