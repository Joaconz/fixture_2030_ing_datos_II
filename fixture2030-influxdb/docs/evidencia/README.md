# Evidencia — Hito 8 · Series temporales (InfluxDB 3 Core)

Cada script deja acá su salida con **fecha de ejecución, versión del servidor y recursos visibles** (RNF10). No hay que copiar nada a mano: los archivos se generan solos.

| # | Qué demuestra | Cómo se genera | Archivo |
|---|---|---|---|
| 1 | Ambiente, versión de `influxdb:3-core`, bases de datos y retención, volumen, recursos de Docker | `sh scripts/inicializacion.sh` | `01_inicializacion.txt` |
| 1b | Persistencia: mismo conteo antes y después de `down` + `up -d`, y tiempo de reinicio | `sh scripts/prueba_persistencia.sh` | `02_persistencia.txt` |
| 2 | Carga: puntos esperados y confirmados, tasa, latencia por lote, errores | `carga_lotes.py --perfil …` | `carga_<perfil>_<fecha>.md/.json` |
| 2b | Barrido de tamaño de lote y concurrencia | `carga_lotes.py --perfil muestra --lote N --hilos H` | `barrido/carga_muestra_<fecha>.md/.json` |
| 3 | Conteos, cardinalidad, tipos, retención configurada y real, dato tardío y repetido, archivos Parquet, pregunta de torneo vivo vs. histórico | `validacion.py --perfil …` | `validacion_<perfil>_<fecha>.md/.json` |
| 4 | Consultas P1–P6 (SQL) con tiempo de respuesta | `consultas_temporales.py` | `consultas_<partido>_<fecha>.md/.json` |
| 5 | Agregaciones A1–A5 (correcta vs. incorrecta), resúmenes escritos y consultas de torneo | `agregaciones.py --perfil …` | `agregaciones_<perfil>_<fecha>.md/.json` |

Ninguno de estos archivos contiene el token.

## Registro de corridas

| Fecha | Versión | CPU / RAM de Docker | Perfil | Puntos confirmados | Tasa (puntos/s) | Validación |
|---|---|---|---|---:|---:|---|
| 09/10/2026 | InfluxDB 3 Core 3.12.0 | 12 CPUs / 7,7 GB | muestra (lote 10.000, 4 hilos) | 176.400 | 33.676 | todo ✅ |
| 09/10/2026 | InfluxDB 3 Core 3.12.0 | 12 CPUs / 7,7 GB | completo (lote 50.000, 8 hilos) | 10.094.400 | 182.726 | todo ✅ |

## Archivos de la entrega (corridas finales del 09/10/2026)

Se conserva **una corrida por script y perfil**: la última, que es la que respaldan las cifras de `docs/`.

| Paso | Perfil muestra | Perfil completo |
|---|---|---|
| Ambiente y persistencia | `01_inicializacion.txt` | `02_persistencia.txt` (reinicio con los 10 M de puntos cargados) |
| Carga | `carga_muestra_20261009-223210` | `carga_completo_20261009-223721` |
| Barrido de lote e hilos | `barrido/` (5 corridas) | — |
| Agregaciones | `agregaciones_muestra_20261009-223350` (2ª corrida, después de un reinicio) | `agregaciones_completo_20261009-224349` (2ª corrida, después de un reinicio) |
| Validación (todo ✅) | `validacion_muestra_20261009-223400` | `validacion_completo_20261009-224414` |
| Consultas P1–P6 (sobre el perfil completo) | — | `consultas_PAR-D16-01_20261009-224356` |

Cada archivo existe en `.md` (legible) y `.json` (datos). La evidencia de la primera versión del módulo (InfluxDB 2.9.1, 28/09/2026) se reemplazó por esta. Queda en el historial de git (commit `6e46888`).
