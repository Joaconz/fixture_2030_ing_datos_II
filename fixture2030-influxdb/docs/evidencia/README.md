# Evidencia — Hito 8 · Series temporales (InfluxDB 2)

Cada script deja acá su salida con **fecha de ejecución, versión del servidor y recursos visibles** (RNF10). No hay que copiar nada a mano: los archivos se generan solos.

| # | Qué demuestra | Cómo se genera | Archivo |
|---|---|---|---|
| 1 | Ambiente, versión de `influxdb:latest`, buckets, retención y shards, volúmenes, recursos de Docker | `sh scripts/inicializacion.sh` | `01_inicializacion.txt` |
| 1b | Persistencia: mismo conteo antes y después de `down` + `up -d` | `sh scripts/prueba_persistencia.sh` | `02_persistencia.txt` |
| 2 | Carga: puntos esperados y confirmados, tasa, latencia por lote, errores | `carga_lotes.py --perfil …` | `carga_<perfil>_<fecha>.md/.json` |
| 3 | Idempotencia: segunda carga, mismos conteos | repetir carga + validación | segundo `carga_…` + `validacion_…` |
| 4 | Conteos, cardinalidad, tipos, retención configurada y real, dato tardío y repetido, shards y disco, pregunta de torneo vivo vs. histórico | `validacion.py --perfil …` | `validacion_<perfil>_<fecha>.md/.json` |
| 5 | Consultas P1–P6 con tiempo de respuesta | `consultas_temporales.py` | `consultas_<partido>_<fecha>.md/.json` |
| 6 | Agregaciones A1–A5 (correcta vs. incorrecta), resúmenes escritos, task nativa y consultas de torneo | `agregaciones.py --perfil …` | `agregaciones_<perfil>_<fecha>.md/.json` |

Ninguno de estos archivos contiene el token ni la contraseña.

## Registro de corridas

| Fecha | Versión | CPU / RAM de Docker | Perfil | Puntos confirmados | Tasa (puntos/s) | Validación |
|---|---|---|---|---:|---:|---|
| 28/09/2026 | InfluxDB v2.9.1 | 8 CPUs / 3,8 GB | muestra | 176.400 | 647.828 | todo ✅ |
| 28/09/2026 | InfluxDB v2.9.1 | 8 CPUs / 3,8 GB | completo | 10.094.400 | 780.255 | todo ✅ |

## Archivos de la entrega (corridas finales del 28/09/2026)

Se conserva **una corrida por script y perfil**: la última, que es la que respaldan las cifras de `docs/` (por ejemplo, los tiempos de P1–P6 de `consultas_y_agregaciones.md` y los 378 s del backfill de `retencion_y_granularidad.md`). Las corridas intermedias equivalentes se borraron para que no haya que adivinar cuál vale.

| Paso | Perfil muestra | Perfil completo |
|---|---|---|
| Ambiente y persistencia | `01_inicializacion.txt`, `02_persistencia.txt` | — |
| Carga | `carga_muestra_20260928-190428` | `carga_completo_20260928-191438` |
| Agregaciones | `agregaciones_muestra_20260928-191239` | `agregaciones_completo_20260928-192105` |
| Validación (todo ✅) | `validacion_muestra_20260928-191241` | `validacion_completo_20260928-192535` |
| Consultas P1–P6 (sobre el perfil completo) | — | `consultas_PAR-D16-01_20260928-192540` |

Cada archivo existe en `.md` (legible) y `.json` (datos).

### `hallazgos/` — corridas con fallas, conservadas a propósito

Son la evidencia de los hallazgos de `docs/pruebas_y_rendimiento.md` §5. Las fallas son esperables: se corrigieron después y las corridas finales de arriba están en ✅.

| Archivo | Qué muestra |
|---|---|
| `hallazgos/validacion_muestra_20260928-190430` | V2 en ❌: la primera versión esperaba "series × fields" (24 / 48 / 15) y `influxdb.cardinality()` cuenta series del índice (4 / 16 / 5). Se corrigió la expectativa, no los datos |
| `hallazgos/validacion_muestra_20260928-190807` | V8 en ❌: una segunda corrida de los resúmenes después de reiniciar el servidor dejó un punto duplicado en el histórico (499.413 contra 300.766 comentarios). Se corrigió con el reemplazo explícito (`/api/v2/delete` + reescritura) |

En `01_inicializacion.txt` y `02_persistencia.txt`, la carpeta del host se muestra como `~/docker/data/influxdb` (la salida original tenía la ruta absoluta del usuario de la notebook).

