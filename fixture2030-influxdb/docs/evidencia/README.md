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
