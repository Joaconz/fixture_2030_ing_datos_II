# Capas 1-2 — resolución y TCP

- Fecha (UTC) de inicio: 2026-10-22T20:31:14Z
- Commit: `sin-git`
- Entorno: notebook-docker-desktop
- Origen de la prueba: notebook (host) · Darwin arm64 · python 3.9.6
- Timeouts: conexión 2 s · operación 3 s · API 8 s
- Secretos: ninguno se imprime; toda salida pasa por `registro.redactar` (RNF7/RNF8).

| Fecha (UTC) | Producto | Capa | Prueba | Objetivo / contexto | Resultado | ms | Detalle | Interpretación | No demuestra |
|---|---|---|---|---|---|---:|---|---|---|
| 2026-10-22T20:31:14Z | iris | resolucion | `getaddrinfo 127.0.0.1` | `127.0.0.1` | **OK** | 3.6 | → 127.0.0.1 | el nombre resuelve desde el mismo origen que la API | que haya un proceso escuchando |
| 2026-10-22T20:31:14Z | iris | tcp | `TCP Superserver` | `127.0.0.1:1972 (IRIS Superserver (SQL/objetos))` | **OK** | 3.1 | conexión TCP establecida | hay un listener aceptando en ese host:puerto desde este origen | protocolo, autenticación, contexto ni consulta (solo hay un socket) |
| 2026-10-22T20:31:14Z | iris | resolucion | `getaddrinfo 127.0.0.1` | `127.0.0.1` | **OK** | 0.0 | → 127.0.0.1 | el nombre resuelve desde el mismo origen que la API | que haya un proceso escuchando |
| 2026-10-22T20:31:14Z | iris | tcp | `TCP Management Portal` | `127.0.0.1:52773 (HTTP)` | **OK** | 2.0 | conexión TCP establecida | hay un listener aceptando en ese host:puerto desde este origen | protocolo, autenticación, contexto ni consulta (solo hay un socket) |
