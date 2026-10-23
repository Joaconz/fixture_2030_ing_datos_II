# Evidencia del Hito 11

Todo lo que está versionado en esta carpeta lo generaron los scripts y pasó por `registro.redactar()`: no contiene contraseñas, tokens, URI con credenciales ni rutas personales (RNF7/RNF8). Las salidas crudas (logs JSON de la API) quedan en `crudo/`, que está ignorado por git, y de ellas se versionan sólo las líneas asociadas a cada request-id, ya filtradas.

Cada fila de cada `.jsonl` / `.md` tiene: fecha (UTC), commit, entorno, origen de la prueba, producto, capa, prueba, objetivo y contexto, resultado, latencia, detalle, interpretación y lo que la prueba **no** demuestra (RNF18).

## Corridas

| Corrida | Commit | Qué contiene | Resultado |
|---|---|---|---|
| [`20261017-001129_completa`](corridas/20261017-001129_completa/matriz.md) | `71a1625` | `--config --tcp --escenarios --nativos --api --matriz` contra la API en `:8001`, con su log | 148 pruebas: 128 OK · 2 WARN (observaciones) · 0 FAIL · 0 SKIP · 18 N/C |
| [`20261017-001625_fallas-controladas`](corridas/20261017-001625_fallas-controladas/fallas_controladas.md) | `e1de5d6` | stop/start de Redis y MongoDB, pause/unpause de InfluxDB y 10 configuraciones incorrectas | 81/81 como se esperaba |
| [`20261017-003523_redis-sesion-vigente`](corridas/20261017-003523_redis-sesion-vigente/matriz.md) | `ea51b8f` | RF20, antes: `--nativos --api --matriz --producto redis` con la sesión de demo recién cargada | 14 OK · 2 N/C · `EXISTS 1`, TTL > 0, `GET /sesiones/demo-ses-0000001-1` = 200 |
| [`20261019-192936_redis-sesion-vencida`](corridas/20261019-192936_redis-sesion-vencida/matriz.md) | `ea51b8f` | RF20, después: la misma corrida con la sesión ya vencida (ver [`../matriz_de_conectividad.md`](../matriz_de_conectividad.md) §3) | 14 OK · 2 N/C · `EXISTS 0`, TTL -2, API 404 `SESSION_NOT_FOUND`; Redis sigue DISPONIBLE |
| [`20261023-181555_controles-5-4`](corridas/20261023-181555_controles-5-4/matriz.md) | `ae58c26` | §5.4: `--nativos --matriz --producto mongodb --producto cassandra`, con los controles de colección inexistente (Mongo) y timeout de conexión (Cassandra). Se corrió en Windows | 24 pruebas: 20 OK · 4 N/C |

Archivos por corrida:

| Archivo | Capa |
|---|---|
| `resultados_config.md` / `.jsonl` | 0 — configuración |
| `resultados_tcp.md` / `.jsonl` | 1–2 — resolución y TCP, incluidos los escenarios de §5.3 |
| `resultados_clientes.md` / `.jsonl` | 3–6 — drivers de la API y clientes nativos |
| `resultados_api.md` / `.jsonl` | API: método, path, status, tiempo, request-id, resumen, interpretación y, al final, la tabla de log por request-id |
| `resultados_api_logs.jsonl` | líneas de log de la API asociadas a cada request-id (campos sin datos sensibles) |
| `resultados_falla_controlada.md` / `.jsonl` · `fallas_controladas.md` | §5.7: una fila por prueba, y el relato por escenario (condición inicial, cambio, respuesta, log, recuperación, datos conservados) |
| `matriz.md` / `.json` | estado por dependencia de esa corrida |

## Capturas redactadas

[`capturas_redactadas/`](capturas_redactadas/) tiene respuestas HTTP completas (cabeceras + cuerpo) de `/health`, `/health/ready` y `/health/dependencias`, y la salida de consola de la repetición de Redis, todas pasadas por el filtro de redacción. No hay capturas de pantalla: la evidencia textual es reproducible y se puede comparar entre corridas.

## Repetir

```bash
bash scripts/evaluar_conectividad.sh --escenarios --log docs/evidencia/crudo/api.log
bash scripts/evaluar_conectividad.sh --falla --producto redis --producto mongodb --log docs/evidencia/crudo/api.log
bash scripts/evaluar_conectividad.sh --limpiar      # borra sólo crudo/
```
