# Rendimiento básico — Hito 10

**Ingeniería de Datos II · Fixture 2030** — Santiago Pazos, Valentina Frisoli, Joaquín Núñez

> RNF18 / restricción "Rendimiento": ninguna cifra sin método, volumen, configuración y entorno. Datos crudos: [`evidencia/latencia_20261013-194117.md`](./evidencia/latencia_20261013-194117.md).

## 1. Método

- **Herramienta:** `scripts/medir_latencia.sh` → `curl -w '%{time_total}'`, una conexión nueva por request (incluye el handshake TCP, no reutiliza conexiones).
- **Volumen:** 200 requests **secuenciales** por endpoint (2 de calentamiento descartadas). No es una prueba de carga ni de concurrencia: mide la latencia de una request aislada.
- **Estadísticos:** p50, p95 y máximo por rango más cercano sobre los 200 tiempos.
- **Caché:** `partido-HIT` mide el detalle con la copia en Redis; `partido-MISS` borra la clave antes de cada request (fuera del tiempo medido) para forzar Neo4j + `SET`.

## 2. Entorno y configuración

- MacBook Air (Apple Silicon, arm64), 10 CPUs visibles, 24 GB; macOS (Darwin 25.6.0); Docker Desktop.
- API: uvicorn con 1 worker, Python 3.12, `DEP_TIMEOUT_S=2.0`, `LOG_LEVEL=INFO` (cada request escribe 2–4 líneas de log a stdout).
- Fuentes: un contenedor por base, nodo único, en la misma notebook que la API y el cliente (sin red real de por medio).
- Datos: cargas de **muestra** de cada hito — Mongo 64 equipos / 1.472 jugadores; Neo4j 112 partidos / 1.152 eventos; Cassandra 80 comentarios (2 partidos); Redis 2.000 usuarios de sesiones; InfluxDB 176.400 puntos (2 partidos).

## 3. Resultados (13/10/2026)

| Endpoint | Fuente | p50 (ms) | p95 (ms) | máx (ms) |
|---|---|---:|---:|---:|
| `GET /equipos/ARG` | MongoDB | 2,2 | 2,9 | 12,6 |
| `GET /partidos/PAR-A-1/eventos?limit=20` | Neo4j | 7,1 | 10,4 | 48,4 |
| `GET /partidos/PAR-A-1/comentarios?limit=20` | Cassandra (1 bucket, 15 ventanas) | 10,0 | 22,1 | 46,2 |
| `GET /sesiones/demo-ses-0000001-1` | Redis | 1,5 | 1,9 | 11,4 |
| `GET /partidos/PAR-A-1/estadisticas` (30 min, `1m`) | InfluxDB 3 | 8,4 | 9,4 | 14,5 |
| `GET /partidos/PAR-A-1` — caché **HIT** | Redis | 1,5 | 1,7 | 4,0 |
| `GET /partidos/PAR-A-1` — caché **MISS** | Neo4j + Redis | 5,9 | 8,6 | 15,7 |

Lectura:
- La caché del detalle reduce la mediana de 5,9 a 1,5 ms (≈ 4×) — es la justificación medida de la única integración de dos fuentes (CU4).
- Comentarios es el más lento porque una página puede recorrer varias ventanas de 10 minutos (cada una, una partición) hasta completar `limit`; en PAR-A-1 los 24 comentarios de la carga (más los que crearon las pruebas) se reparten entre las 15 ventanas del partido. Es el costo de la partición compuesta del Hito 6, que en producción evita particiones gigantes.
- Dependencia caída: el peor caso de una request es el timeout (2,0 s), no una espera indefinida.

## 4. Limitaciones (pregunta guía 20)

Estas cifras **no** permiten afirmar que la API soporte millones de usuarios:
- un solo cliente secuencial; no se midió throughput ni comportamiento bajo concurrencia (contención de pools, GIL, colas);
- cliente, API y bases comparten la misma máquina (sin latencia de red, compiten por CPU);
- volúmenes de muestra, muy por debajo del Hito 1 (≥ 1 millón de comentarios por partido de alta audiencia);
- nodos únicos sin réplica: no aplica el costo de consistencia entre réplicas (N=3) que definió el Hito 3;
- 1 worker de uvicorn; sin balanceador.

Siguiente paso natural (hitos de carga): una herramienta de carga concurrente (k6/Locust) sobre los perfiles completos de cada módulo y varios workers.
