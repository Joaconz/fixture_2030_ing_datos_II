# Matriz de conectividad — corrida `20261017-001129_completa`

- Fecha (UTC): 2026-10-17T00:11:29Z → 2026-10-17T00:11:46Z
- Commit: `71a1625` · Entorno: notebook-docker-desktop · Origen: notebook (host) · Darwin arm64 · python 3.14.5
- Archivos: [`resultados_api.md`](resultados_api.md), [`resultados_clientes.md`](resultados_clientes.md), [`resultados_config.md`](resultados_config.md), [`resultados_tcp.md`](resultados_tcp.md)
- OK = esa prueba concreta funcionó en ese momento; no es garantía de rendimiento ni de disponibilidad permanente (RNF17).

| Dependencia | Estado | Config | DNS | TCP | Protocolo | Autent. | Autoriz. | Contexto | Operación | API | ms TCP | ms operación (driver) | ms API | Controles | Diagnóstico | Siguiente paso | Observaciones (no cambian el estado) |
|---|---|---|---|---|---|---|---|---|---|---|---:|---:|---:|---|---|---|---|
| **mongodb** | **DISPONIBLE** | OK | OK | OK | OK | N/C | N/C | OK | OK | OK | 0.4 | 2.5–4.1 | 1.2–3.4 | 3/3 | todas las pruebas ejecutadas terminaron bien en esta corrida (no garantiza rendimiento) | — | — |
| **neo4j** | **DISPONIBLE** | OK | OK | OK | OK | OK | OK | OK | OK | OK | 0.4–0.5 | 1.8–20 | 4.4–15 | 2/2 | todas las pruebas ejecutadas terminaron bien en esta corrida (no garantiza rendimiento) | — | NEO4J_PASSWORD distinto de los valores públicos: es la credencial de desarrollo documentada en un .env.example versionado; archivo del secreto fuera de git: legible por otros usuarios (0o644) |
| **cassandra** | **DISPONIBLE** | OK | OK | OK | OK | N/C | N/C | OK | OK | OK | 0.2 | 1.6–1.8 | 2.6–8.5 | 3/3 | todas las pruebas ejecutadas terminaron bien en esta corrida (no garantiza rendimiento) | — | — |
| **redis** | **DISPONIBLE** | OK | OK | OK | OK | N/C | N/C | OK | OK | OK | 0.2 | 3.0 | 2.0–2.3 | 3/3 | todas las pruebas ejecutadas terminaron bien en esta corrida (no garantiza rendimiento) | — | — |
| **influxdb** | **DISPONIBLE** | OK | OK | OK | OK | OK | OK | OK | OK | OK | 0.2 | 19 | 1.3–9.9 | 5/5 | todas las pruebas ejecutadas terminaron bien en esta corrida (no garantiza rendimiento) | — | — |
| **iris** | **NO_CONFIGURADO** | OK | OK | N/C | N/C | N/C | N/C | N/C | N/C | OK | — | — | 1.0 | 0/0 | fuera del entorno de prueba: no se inventan resultados | levantar el módulo y poner IRIS_HABILITADO=1 sólo si vuelve a la arquitectura | — |
| **api** | **DISPONIBLE** | OK | — | — | — | — | — | — | — | OK | — | — | 1.7–49 | 1/1 | todas las pruebas ejecutadas terminaron bien en esta corrida (no garantiza rendimiento) | — | — |

Escenarios de red provocados (§5.3): 7/7 se comportaron como se esperaba (ver `resultados_tcp.md`).

Totales de la corrida: OK 128 · WARN 2 · FAIL 0 · SKIP 0 · N/C 18

SKIP = prueba no ejecutada por falta de herramienta o configuración; NO significa producto caído. N/C = la capa no aplica en este entorno (p. ej. laboratorio sin autenticación) o el producto no está configurado.
