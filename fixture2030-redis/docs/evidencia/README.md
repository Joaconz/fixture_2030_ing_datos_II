# Evidencia — Hito 7 · Caché de Usuarios y Sesiones (Redis)

Salidas **reales** generadas por [`scripts/correr_todo.sh`](../../scripts/correr_todo.sh). Cada archivo trae la fecha de ejecución. No se editan a mano: si cambia un script, se regeneran.

```bash
cd fixture2030-redis
sh scripts/correr_todo.sh        # regenera 01_ … 09_ (tarda ~2 min)
```

| # | Archivo | Qué muestra | RF/RNF |
|---|---|---|---|
| 1 | `01_inicializacion.txt` | PING, versión, nodo único (rol master, 0 réplicas), política de memoria y persistencia | RF1, RNF10 |
| 2 | `02_carga_muestra.txt` | Dataset cargado: conteos, atributos y TTL de una sesión | RF11 |
| 3 | `03_sesiones.txt` | Crear, leer, renovar (`MULTI/EXEC`), sesión inexistente, carrera validar/renovar, bloqueo, vencimiento (`TTL -2`), tope absoluto, cierre | RF3–RF5 |
| 4 | `04_cache.txt` | miss → hit → invalidación (`DEL`) → miss; lector lento acotado por el TTL; vencimiento; perfil | RF6, RF7 |
| 5 | `05_concurrencia.txt` | Voto único, ranking, tendencia, y 20 clientes paralelos (no atómico = 20, `SADD` como guarda = 1) | RF8, RF9 |
| 6 | `06_benchmark.txt` | Entorno, throughput/latencia, corrección bajo concurrencia, método de hit ratio | RF12, RNF10 |
| 7 | `07_memoria.txt` | Evicción vs TTL (`evicted_keys` vs `expired_keys`), votación intacta, OOM | RF10 |
| 8 | `08_metricas.txt` | INFO memory/stats/keyspace/commandstats, TTL, encoding, MEMORY USAGE, SLOWLOG | RF13 |
| 9 | `09_persistencia.txt` | Volumen nombrado `fixture2030_redis_data` respaldado por `~/docker/data/redis`; tras `restart` y tras `down` + `up` siguen una clave con TTL y la votación | RNF2 |

## Registro del ambiente (RNF10)

| Fecha | Redis (`redis_version`) | Equipo | Corrida |
|---|---|---|---|
| 2026-09-25 | **8.10.2** (`redis:latest`, Linux aarch64 en Docker Desktop) | Apple M4 · 10 CPUs · 24 GB RAM; Docker con 10 CPUs y ~7,75 GB | Primera versión (con Redis Functions); evidencia reemplazada, queda en el historial de git |
| 2026-10-10 | **8.10.2** (`redis:latest`, Linux x86_64 en Docker Desktop WSL2) | Notebook Windows 11 · 12 CPUs; Docker con 12 CPUs y ~7,7 GB | **Archivos actuales**: versión corregida (comandos nativos y `MULTI/EXEC`) |

`latest` cambia con el tiempo: al repetir la prueba, agregar una fila con la versión que reporte `INFO server`.

## Procedencia de cada archivo

Los nueve archivos (`01_` a `09_`) salen de **una sola corrida** de `correr_todo.sh` del 2026-10-10 (00:09–00:10 UTC), sobre un ambiente vacío (`docker compose down -v`, carpeta `~/docker/data/redis` borrada y vuelta a crear). Las fechas son UTC y figuran en la primera línea de cada archivo.

En `09_persistencia.txt` la carpeta del host se muestra como `~/docker/data/redis`: la salida original tenía la ruta absoluta del usuario de la notebook (el script ya la abrevia).
