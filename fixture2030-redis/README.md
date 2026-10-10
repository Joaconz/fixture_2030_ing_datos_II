# Fixture 2030 — Hito 7 · Caché de Usuarios y Sesiones (Redis)

**Ingeniería de Datos II · Grupo 2** — Santiago Pazos, Valentina Frisoli, Joaquín Núñez

Módulo clave/valor en memoria para **sesiones de usuario** (vigencia por inactividad), **caché de consultas frecuentes** (ficha de partido, perfil) con invalidación, **votación MVP concurrente** y **ranking temporal de partidos en tendencia**. Redis guarda estado transitorio y copias; **la fuente de verdad sigue en los módulos anteriores** (MongoDB para Usuarios e IRIS para Partidos, según la matriz del Hito 2; ninguno está implementado todavía).

> **Nodo único de laboratorio.** Sin réplicas, Sentinel ni Cluster: no es alta disponibilidad. Diferencias con un despliegue real en [`docs/memoria_y_escalabilidad.md`](./docs/memoria_y_escalabilidad.md) §5.

---

## 1. Estructura del módulo

```
fixture2030-redis/
├── docker-compose.yml           redis:latest · 127.0.0.1:6379 · volumen nombrado respaldado por ~/docker/data/redis
├── config/redis.conf            maxmemory 256mb · volatile-lru · AOF everysec
├── scripts/
│   ├── inicializacion.redis     verificación del ambiente y versión
│   ├── carga_muestra.sh         genera la muestra determinista (awk -> redis-cli) y la verifica
│   ├── carga_muestra.redis      verificación de la muestra cargada
│   ├── sesiones.redis           ciclo de vida completo de una sesión (MULTI/EXEC)
│   ├── cache.redis              cache-aside: miss, hit, invalidación con DEL, lector lento
│   ├── concurrencia.redis       voto único (SADD como guarda), ranking MVP, tendencia por hora
│   ├── concurrencia_paralela.sh 20 clientes simultáneos: no atómico vs SADD como guarda
│   ├── metricas.redis           INFO, TTL, encoding, MEMORY USAGE, SLOWLOG (sin KEYS)
│   ├── benchmark.sh             redis-benchmark + corrección bajo concurrencia
│   ├── memoria_prueba.sh        TTL vs evicción (baja maxmemory temporalmente y la restaura)
│   ├── limpieza.redis / .sh     limpieza opcional (SCAN + UNLINK, nunca KEYS/FLUSHALL)
│   ├── verificar_persistencia.sh  volumen nombrado, restart y down/up sin perder datos
│   └── correr_todo.sh           todo lo anterior en orden, guardando la evidencia
├── docs/
│   ├── patrones_de_acceso.md          problema de concurrencia y patrones P1–P11 (se escribió primero)
│   ├── modelo_clave_valor.md          convención de claves, estructuras, operaciones atómicas
│   ├── ciclo_de_vida_e_invalidacion.md  sesiones, TTL, invalidación, clave ausente
│   ├── memoria_y_escalabilidad.md     TTL vs evicción, política elegida, nodo único vs producción
│   ├── concurrencia_y_pruebas.md      atomicidad, datos cargados, mediciones, coherencia con el TPO
│   └── evidencia/                     salidas reales de cada etapa (01_ … 09_)
├── .gitattributes                  los scripts siempre con finales de línea LF (también al clonar en Windows)
└── README.md
```

---

## 2. Requisitos

- Docker Desktop (o Docker Engine) con Docker Compose V2.
- ~300 MB de RAM libres (Redis está limitado a 256 MB por configuración).
- Puerto `6379` libre en el host. Si está ocupado: `REDIS_PORT=16379 docker compose up -d`.
- La carpeta `~/docker/data/redis` **debe existir antes** del primer `docker compose up` (`mkdir -p ~/docker/data/redis`, ya está en §3). Si falta, Docker falla con `no such file or directory`. Otra ubicación: `REDIS_DATA_DIR=/ruta docker compose up -d`. En Windows, usar WSL2 (la variable `HOME` debe existir) o definir `REDIS_DATA_DIR`.
- **No** hace falta instalar `redis-cli`: se usa el del contenedor. Ni Python: los scripts son `.redis` y `sh`.
- **Windows con Git Bash:** antes de correr los `.sh`, `export MSYS_NO_PATHCONV=1`. Si no, Git Bash convierte las rutas Linux de los comandos `docker` (por ejemplo `/scripts/…`) en rutas de Windows.

---

## 3. Levantar el ambiente y verificar el servidor (RF1)

```bash
cd fixture2030-redis
mkdir -p ~/docker/data/redis          # carpeta de persistencia (RNF2)
docker compose up -d
```

```bash
docker compose ps                                        # STATUS debe decir "healthy"
```

```bash
docker compose exec redis redis-cli ping                 # PONG
```

```bash
docker compose exec redis redis-cli INFO server | grep redis_version   # versión observada
```

```bash
docker compose exec redis redis-cli                      # cliente interactivo (salir: exit)
```

---

## 4. Ejecutar el módulo, paso a paso

El módulo usa solo comandos de Redis: comandos nativos atómicos (`INCR`/`HINCRBY`, `ZINCRBY`, `SADD`, `SET … EX`, `DEL`) y transacciones `MULTI/EXEC`. No hay nada que instalar en el servidor antes de empezar.

Los `.redis` se ejecutan **filtrando comentarios** (`redis-cli` no los admite). Orden recomendado:

```bash
docker compose exec -T redis sh -c "grep -v '^#' /scripts/inicializacion.redis | redis-cli"   # 1. inicio
docker compose exec -T redis sh /scripts/carga_muestra.sh                                    # 2. carga
docker compose exec -T redis sh -c "grep -v '^#' /scripts/sesiones.redis       | redis-cli"   # 3. sesiones (~10 s: espera vencimientos)
docker compose exec -T redis sh -c "grep -v '^#' /scripts/cache.redis          | redis-cli"   # 4. caché
docker compose exec -T redis sh -c "grep -v '^#' /scripts/concurrencia.redis   | redis-cli"   # 5. concurrencia
docker compose exec -T redis sh /scripts/concurrencia_paralela.sh 20                          # 5b. clientes paralelos
sh scripts/benchmark.sh                                                                        # 6. medición
docker compose exec -T redis sh /scripts/memoria_prueba.sh                                     # 7. memoria (degrada la muestra)
docker compose exec -T redis sh /scripts/carga_muestra.sh                                    #    restaurar la muestra
docker compose exec -T redis sh -c "grep -v '^#' /scripts/metricas.redis       | redis-cli"   # 8. métricas
```

**O todo junto**, dejando la evidencia en `docs/evidencia/`:

```bash
sh scripts/correr_todo.sh
```

Cada `.redis` imprime marcadores `== N.M … ==` que dicen qué paso se está viendo.

### 4.1 Idempotencia

`carga_muestra.sh` y `sesiones.redis` se pueden repetir: los conteos finales (`DBSIZE = 4203` tras la carga) y los valores no cambian. Solo varían los TTL restantes.

---

## 5. Detener y reiniciar sin perder datos (RNF2)

**Cómo se guarda (RNF2):** los datos van a un **volumen nombrado** de Docker, `fixture2030_redis_data`, cuyo respaldo es la carpeta `~/docker/data/redis` del host (montaje que exige el enunciado). Redis escribe ahí el AOF y el RDB; sobreviven a `down`, a un reinicio del contenedor y a reiniciar Docker.

```bash
docker compose down          # detener (conserva los datos)
docker compose up -d         # volver a levantar: sesiones y votación siguen
```

```bash
docker compose restart redis # reinicio rápido del servicio
```

Comprobación (`sh scripts/verificar_persistencia.sh`): [`docs/evidencia/09_persistencia.txt`](./docs/evidencia/09_persistencia.txt) muestra el volumen y su carpeta, y que una clave con TTL y la votación siguen tras `restart` y tras `down` + `up`. Se acepta perder hasta ~1 s de escrituras (`appendfsync everysec`); las sesiones vencen por TTL igual que antes (el TTL restante se conserva en el AOF).

**Empezar de cero (borra todo).** `down -v` borra el volumen pero **no** los archivos de la carpeta del host, por eso hacen falta los tres pasos:

```bash
docker compose down -v && rm -rf ~/docker/data/redis && mkdir -p ~/docker/data/redis
```

**Limpieza parcial** sin bajar el servicio: `docker compose exec -T redis sh /scripts/limpieza.sh` (borra `f30:*` con `SCAN` + `UNLINK`).

---

## 6. Registro de la versión probada (RNF1, RNF10)

El enunciado exige `redis:latest` y, a cambio, registrar con qué versión concreta se validó:

```bash
docker compose exec redis redis-cli INFO server | grep -E "redis_version|os:"
```

| Fecha de prueba | Versión (`redis_version`) | Observaciones |
|---|---|---|
| 2026-09-25 | **8.10.2** · Linux aarch64 (Docker Desktop, Apple M4) | Primera versión del módulo, con Redis Functions |
| 2026-10-10 | **8.10.2** · Linux x86_64 (Docker Desktop WSL2, Windows 11) | Versión corregida: solo comandos nativos y `MULTI/EXEC`. Las 9 etapas de `correr_todo.sh` corrieron sin errores desde un ambiente vacío. `EXPIRE … NX` requiere Redis ≥ 7.0 |

---

## 7. Decisiones principales (resumen)

| Tema | Decisión | Detalle |
|---|---|---|
| Sesión | HASH, **30 min de inactividad** renovables, **tope de 12 h**, vencimiento nativo (sin barridos) | [`ciclo_de_vida_e_invalidacion.md`](./docs/ciclo_de_vida_e_invalidacion.md) §1 |
| Sesión inexistente | 401 → login; nada se crea implícitamente | ídem §1.6 |
| Caché | cache-aside sobre la fuente de verdad (IRIS para Partidos, MongoDB para Usuarios); coherencia por **invalidación en escritura** (`DEL`); TTL 60 s como permanencia máxima de una copia vieja | ídem §2 |
| Atomicidad | Comandos nativos (`SADD` como guarda del voto único, `ZINCRBY`, `HINCRBY`) y `MULTI/EXEC` para las secuencias (crear, renovar y cerrar sesión, visita a tendencia) | [`concurrencia_y_pruebas.md`](./docs/concurrencia_y_pruebas.md) §2 |
| Memoria | `maxmemory 256mb` + `volatile-lru`: se desaloja sólo lo reconstruible; la votación abierta no vence ni se desaloja | [`memoria_y_escalabilidad.md`](./docs/memoria_y_escalabilidad.md) §2 |
| Ranking | ZSET por hora con TTL de 2 h | [`modelo_clave_valor.md`](./docs/modelo_clave_valor.md) |

Resultados clave observados (detalle y limitaciones en [`concurrencia_y_pruebas.md`](./docs/concurrencia_y_pruebas.md) §4): 20 clientes simultáneos con el mismo usuario dieron puntaje **20** sin atomicidad y **1** con `SADD` como guarda; 100.000 `ZINCRBY` concurrentes dieron exactamente 100.000; bajo presión de memoria la votación abierta quedó intacta mientras se desalojaron ~16.000 claves con TTL.

---

## 8. Comandos útiles

```bash
docker compose logs -f redis                                   # logs
docker compose exec redis redis-cli INFO memory | head -20     # memoria
docker compose exec redis redis-cli DBSIZE                     # cantidad de claves (O(1))
docker compose exec redis redis-cli TTL f30:ses:demo-ses-0000001-1   # TTL de una sesión
docker compose exec redis redis-cli --scan --pattern 'f30:rank:*'    # inspección con SCAN (no KEYS)
```

**No** usar `KEYS *` ni `FLUSHALL` como operación normal (RNF8): el primero bloquea el servidor recorriendo todo el keyspace y el segundo borra también lo que no se quería.

---

## 9. Reproducir el hito desde cero (RNF3)

```bash
git clone <repo> && cd <repo>/fixture2030-redis
mkdir -p ~/docker/data/redis
docker compose up -d && docker compose ps                    # esperar "healthy"
sh scripts/correr_todo.sh                                     # carga, sesiones, caché, concurrencia, medición, memoria, métricas
ls docs/evidencia                                             # 01_ … 09_
```

---

## 10. Relación con los hitos previos

- **Hito 2/3** — Sesiones (N5) → clave/valor, **AP, eventual, TTL, local por región, sin réplica cross-región**; Usuarios (N4) → MongoDB y Partidos (N2) → IRIS (matriz del Hito 2) son la fuente de verdad de las copias; ninguno está implementado todavía. **Discrepancia heredada:** el Hito 3 lista N2 como MongoDB; este módulo sigue el Hito 2 ([`concurrencia_y_pruebas.md`](./docs/concurrencia_y_pruebas.md) §5).
- **Hito 4** — MongoDB implementa hoy sólo `equipos` y `jugadores`. Las fuentes de verdad de las copias de este módulo, **Partidos (N2, IRIS)** y **Usuarios (N4, MongoDB)**, **todavía no están implementadas**; los identificadores `PAR-…` de la muestra provienen del grafo del Hito 5 (Neo4j). La integración es sólo conceptual (fuera de alcance).
- **Hito 5/6** — mismos identificadores `PAR-…` y `USR-…`; el Hito 6 ya preveía cachear la configuración de partición de cada partido (Q0).
- **Caso abierto heredado del Hito 3:** qué pasa con una sesión cuando el usuario cambia de región durante un partido. **No se resuelve en este hito.**

---

## 11. Alcance y seguridad

Fuera de alcance por el enunciado: API REST, interfaz web, integración física con los otros servicios, despliegue multirregional. El nodo **no tiene contraseña** y sólo se publica en `127.0.0.1`: es configuración de **desarrollo**. Los ids de sesión de la muestra son ficticios (`demo-ses-…`); no hay tokens, contraseñas ni datos personales reales en el repo (RNF7).
