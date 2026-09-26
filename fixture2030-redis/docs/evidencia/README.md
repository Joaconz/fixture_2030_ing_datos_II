# Evidencia — Hito 7 · Caché de Usuarios y Sesiones (Redis)

Salidas **reales** generadas por [`scripts/correr_todo.sh`](../../scripts/correr_todo.sh). Cada archivo trae la fecha de ejecución. No se editan a mano: si cambia un script, se regeneran.

```bash
cd fixture2030-redis
sh scripts/correr_todo.sh        # regenera 01_ … 09_ (tarda ~1 min)
```

| # | Archivo | Qué muestra | RF/RNF |
|---|---|---|---|
| 1 | `01_inicializacion.txt` | PING, versión, nodo único (rol master, 0 réplicas), política de memoria, funciones | RF1, RNF10 |
| 2 | `02_carga_muestra.txt` | Dataset cargado: conteos, atributos y TTL de una sesión | RF11 |
| 3 | `03_sesiones.txt` | Crear, leer, renovar, sesión inexistente, bloqueo, vencimiento (`TTL -2`), tope absoluto, cierre | RF3–RF5 |
| 4 | `04_cache.txt` | miss → hit → invalidación → miss; carrera del lector lento rechazada; TTL; perfil | RF6, RF7 |
| 5 | `05_concurrencia.txt` | Voto único, ranking, tendencia, y 20 clientes paralelos (no atómico = 20, atómico = 1) | RF8, RF9 |
| 6 | `06_benchmark.txt` | Entorno, throughput/latencia, corrección bajo concurrencia, método de hit ratio | RF12, RNF10 |
| 7 | `07_memoria.txt` | Evicción vs TTL (`evicted_keys` vs `expired_keys`), votación intacta, OOM | RF10 |
| 8 | `08_metricas.txt` | INFO memory/stats/keyspace/commandstats, TTL, encoding, MEMORY USAGE, SLOWLOG | RF13 |
| 9 | `09_persistencia.txt` | Tras `docker compose restart`: funciones, votación y sesión siguen | RNF2 |

## Registro del ambiente (RNF10)

| Fecha | Redis (`redis_version`) | Equipo | Quién ejecutó |
|---|---|---|---|
| 2026-09-25 | **8.10.2** (`redis:latest`, Linux aarch64 en Docker Desktop) | Apple M4 · 10 CPUs · 24 GB RAM; Docker con 10 CPUs y ~7,75 GB | Joaquín Núñez |

`latest` cambia con el tiempo: al repetir la prueba, agregar una fila con la versión que reporte `INFO server`.
