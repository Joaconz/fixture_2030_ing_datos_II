# Capas 3-6 — protocolo, identidad, contexto y operación (drivers)

- Fecha (UTC) de inicio: 2026-10-22T20:31:14Z
- Commit: `sin-git`
- Entorno: notebook-docker-desktop
- Origen de la prueba: notebook (host) · Darwin arm64 · python 3.12.15
- Timeouts: conexión 2 s · operación 3 s · API 8 s
- Secretos: ninguno se imprime; toda salida pasa por `registro.redactar` (RNF7/RNF8).

| Fecha (UTC) | Producto | Capa | Prueba | Objetivo / contexto | Resultado | ms | Detalle | Interpretación | No demuestra |
|---|---|---|---|---|---|---:|---|---|---|
| 2026-10-22T20:31:14Z | iris | protocolo | `Management Portal (HTTP)` | `http://127.0.0.1:52773/csp/sys/UtilHome.csp` | **OK** | 53.2 | HTTP 200 | el portal web responde | que el Superserver ni el namespace estén disponibles |
| 2026-10-22T20:31:14Z | iris | autenticacion | `usuario IRIS` | `docker exec iris session` | **N/C** |  | la terminal del contenedor entra como irisowner (sin contraseña): no prueba la credencial de un cliente externo | un cliente SQL/Native API externo exigiría usuario y contraseña |  |
| 2026-10-22T20:31:14Z | iris | autorizacion | `roles del namespace` | `USER` | **N/C** |  | no evaluado (no hay cliente externo) |  |  |
| 2026-10-22T20:31:14Z | iris | contexto | `namespace USER` | `fixture2030-iris` | **OK** | 79.8 | namespace activo: USER | namespace correcto (origen: dentro del contenedor) |  |
| 2026-10-22T20:31:14Z | iris | operacion | `%Dictionary.CompiledClass.%ExistsId(Fixture.Partido)` | `USER` | **OK** | 79.8 | existe=1 | lectura de metadato de la clase persistente |  |
| 2026-10-22T20:31:14Z | iris | protocolo | `Management Portal (HTTP)` | `http://127.0.0.1:52773/csp/sys/UtilHome.csp` | **OK** | 26.1 | HTTP 200 | el portal web responde | que el Superserver ni el namespace estén disponibles |
| 2026-10-22T20:31:14Z | iris | autenticacion | `usuario IRIS` | `docker exec iris session` | **N/C** |  | la terminal del contenedor entra como irisowner (sin contraseña): no prueba la credencial de un cliente externo | un cliente SQL/Native API externo exigiría usuario y contraseña |  |
| 2026-10-22T20:31:14Z | iris | autorizacion | `roles del namespace` | `USER` | **N/C** |  | no evaluado (no hay cliente externo) |  |  |
| 2026-10-22T20:31:14Z | iris | contexto | `namespace USER` | `fixture2030-iris` | **OK** | 67.4 | namespace activo: USER | namespace correcto (origen: dentro del contenedor) |  |
| 2026-10-22T20:31:15Z | iris | operacion | `%Dictionary.CompiledClass.%ExistsId(Fixture.Partido)` | `USER` | **OK** | 67.4 | existe=1 | lectura de metadato de la clase persistente |  |
