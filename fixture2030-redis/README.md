# Fixture 2030 — Hito 7 · Caché de Usuarios y Sesiones (Redis)

**Ingeniería de Datos II · Grupo 2** — Santiago Pazos, Valentina Frisoli, Joaquín Núñez

Módulo clave/valor en memoria para **sesiones de usuario** (vigencia por inactividad), **caché de consultas frecuentes** (ficha de partido, perfil) con invalidación, **votación MVP concurrente** y **ranking temporal de partidos en tendencia**. Redis guarda estado transitorio y copias; **la fuente de verdad sigue en los módulos anteriores** (MongoDB para usuarios y partidos).

> **Nodo único de laboratorio.** Sin réplicas, Sentinel ni Cluster: no es alta disponibilidad. Diferencias con un despliegue real en [`docs/memoria_y_escalabilidad.md`](./docs/memoria_y_escalabilidad.md) §5.

---

## 1. Estructura del módulo

```
fixture2030-redis/
├── docker-compose.yml           redis:latest · 127.0.0.1:6379 · datos en ~/docker/data/redis
├── config/redis.conf            maxmemory 256mb · volatile-lru · AOF everysec
├── scripts/
│   ├── funciones_f30.lua        librería `f30`: 8 funciones atómicas (sesión, caché, voto, tendencia)
│   ├── carga_muestra.lua        librería `f30carga`: generador determinista del dataset
│   ├── inicializacion.redis     verificación del ambiente y versión
│   ├── carga_muestra.redis      carga y verificación de la muestra
│   ├── sesiones.redis           ciclo de vida completo de una sesión
│   ├── cache.redis              cache-aside: miss, hit, invalidación, carrera evitada
│   ├── concurrencia.redis       voto único, ranking MVP, tendencia por hora
│   ├── concurrencia_paralela.sh 20 clientes simultáneos: no atómico vs atómico
│   ├── metricas.redis           INFO, TTL, encoding, MEMORY USAGE, SLOWLOG (sin KEYS)
│   ├── benchmark.sh             redis-benchmark + corrección bajo concurrencia
│   ├── memoria_prueba.sh        TTL vs evicción (baja maxmemory temporalmente y la restaura)
│   ├── limpieza.redis / .sh     limpieza opcional (SCAN + UNLINK, nunca KEYS/FLUSHALL)
│   └── correr_todo.sh           todo lo anterior en orden, guardando la evidencia
├── docs/
│   ├── patrones_de_acceso.md          problema de concurrencia y patrones P1–P11 (se escribió primero)
│   ├── modelo_clave_valor.md          convención de claves, estructuras, funciones
│   ├── ciclo_de_vida_e_invalidacion.md  sesiones, TTL, invalidación, clave ausente
│   ├── memoria_y_escalabilidad.md     TTL vs evicción, política elegida, nodo único vs producción
│   ├── concurrencia_y_pruebas.md      atomicidad, datos cargados, mediciones, coherencia con el TPO
│   └── evidencia/                     salidas reales de cada etapa (01_ … 09_)
└── README.md
```

---

## 2. Requisitos

- Docker Desktop (o Docker Engine) con Docker Compose V2.
- ~300 MB de RAM libres (Redis está limitado a 256 MB por configuración).
- Puerto `6379` libre en el host. Si está ocupado: `REDIS_PORT=16379 docker compose up -d`.
- **No** hace falta instalar `redis-cli`: se usa el del contenedor. Ni Python: los scripts son `.redis`, Lua y `sh`.

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

Las **funciones** se cargan una vez (y otra vez si se edita un `.lua`; `REPLACE` es idempotente):

```bash
docker compose exec -T redis redis-cli -x FUNCTION LOAD REPLACE < scripts/funciones_f30.lua
docker compose exec -T redis redis-cli -x FUNCTION LOAD REPLACE < scripts/carga_muestra.lua
```

Los `.redis` se ejecutan **filtrando comentarios** (`redis-cli` no los admite). Orden recomendado:

```bash
docker compose exec -T redis sh -c "grep -v '^#' /scripts/inicializacion.redis | redis-cli"   # 1. inicio
docker compose exec -T redis sh -c "grep -v '^#' /scripts/carga_muestra.redis  | redis-cli"   # 2. carga
docker compose exec -T redis sh -c "grep -v '^#' /scripts/sesiones.redis       | redis-cli"   # 3. sesiones (~10 s: espera vencimientos)
docker compose exec -T redis sh -c "grep -v '^#' /scripts/cache.redis          | redis-cli"   # 4. caché
docker compose exec -T redis sh -c "grep -v '^#' /scripts/concurrencia.redis   | redis-cli"   # 5. concurrencia
docker compose exec -T redis sh /scripts/concurrencia_paralela.sh 20                          # 5b. clientes paralelos
sh scripts/benchmark.sh                                                                        # 6. medición
docker compose exec -T redis sh /scripts/memoria_prueba.sh                                     # 7. memoria (degrada la muestra)
docker compose exec -T redis sh -c "grep -v '^#' /scripts/carga_muestra.redis  | redis-cli"   #    restaurar la muestra
docker compose exec -T redis sh -c "grep -v '^#' /scripts/metricas.redis       | redis-cli"   # 8. métricas
```

**O todo junto**, dejando la evidencia en `docs/evidencia/`:

```bash
sh scripts/correr_todo.sh
```

Cada `.redis` imprime marcadores `== N.M … ==` que dicen qué paso se está viendo.

### 4.1 Idempotencia

`carga_muestra.redis` y `sesiones.redis` se pueden repetir: los conteos finales (`DBSIZE = 4203` tras la carga) no cambian. Sólo varían timestamps y TTL restantes.

---

## 5. Detener y reiniciar sin perder datos (RNF2)

Los datos y el AOF están en `~/docker/data/redis`; sobreviven a `down`, a un reinicio del contenedor y a reiniciar Docker.

```bash
docker compose down          # detener (conserva los datos)
docker compose up -d         # volver a levantar: sesiones, votación y funciones siguen
```

```bash
docker compose restart redis # reinicio rápido del servicio
```

Comprobación: [`docs/evidencia/09_persistencia.txt`](./docs/evidencia/09_persistencia.txt). Se acepta perder hasta ~1 s de escrituras (`appendfsync everysec`); las sesiones vencen por TTL igual que antes (el TTL restante se conserva en el AOF).

**Empezar de cero (borra todo):**

```bash
docker compose down && rm -rf ~/docker/data/redis
```

**Limpieza parcial** sin bajar el servicio: `docker compose exec -T redis sh /scripts/limpieza.sh` (borra `f30:*` con `SCAN` + `UNLINK`; conserva las funciones).

---

## 6. Registro de la versión probada (RNF1, RNF10)

El enunciado exige `redis:latest` y, a cambio, registrar con qué versión concreta se validó:

```bash
docker compose exec redis redis-cli INFO server | grep -E "redis_version|os:"
```

| Fecha de prueba | Versión (`redis_version`) | Observaciones |
|---|---|---|
| 2026-09-25 | **8.10.2** · Linux aarch64 (Docker Desktop) | Las 9 etapas de `correr_todo.sh` corrieron sin errores. Las Redis Functions (`FUNCTION LOAD`) requieren Redis ≥ 7.0; `EXPIRE … NX/GT` requiere ≥ 7.0. Si `latest` resolviera a algo anterior, el módulo no carga |

---

## 7. Decisiones principales (resumen)

| Tema | Decisión | Detalle |
|---|---|---|
| Sesión | HASH, **30 min de inactividad** renovables, **tope de 12 h**, vencimiento nativo (sin barridos) | [`ciclo_de_vida_e_invalidacion.md`](./docs/ciclo_de_vida_e_invalidacion.md) §1 |
| Sesión inexistente | 401 → login; nada se crea implícitamente | ídem §1.6 |
| Caché | cache-aside sobre MongoDB; TTL 60 s como **red de seguridad**, coherencia por **invalidación en escritura + versión** | ídem §2 |
| Atomicidad | Redis Functions (voto único, renovar sesión, repoblar con versión) | [`concurrencia_y_pruebas.md`](./docs/concurrencia_y_pruebas.md) §2 |
| Memoria | `maxmemory 256mb` + `volatile-lru`: se desaloja sólo lo reconstruible; la votación abierta no vence ni se desaloja | [`memoria_y_escalabilidad.md`](./docs/memoria_y_escalabilidad.md) §2 |
| Ranking | ZSET por hora con TTL de 2 h | [`modelo_clave_valor.md`](./docs/modelo_clave_valor.md) |

Resultados clave observados (detalle y limitaciones en [`concurrencia_y_pruebas.md`](./docs/concurrencia_y_pruebas.md) §4): 20 clientes simultáneos con el mismo usuario dieron puntaje **20** sin atomicidad y **1** con la función; 100.000 incrementos concurrentes dieron exactamente 100.000; bajo presión de memoria la votación abierta quedó intacta mientras se desalojaron ~16.000 claves con TTL.

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

- **Hito 2/3** — Sesiones (N5) → clave/valor, **AP, eventual, TTL, local por región, sin réplica cross-región**; Usuarios (N4) y Partidos (N2) son la fuente de verdad de las copias.
- **Hito 4** — MongoDB: origen de lo que se cachea (integración sólo conceptual, fuera de alcance).
- **Hito 5/6** — mismos identificadores `PAR-…` y `USR-…`; el Hito 6 ya preveía cachear la configuración de partición de cada partido (Q0).
- **Caso abierto heredado del Hito 3:** qué pasa con una sesión cuando el usuario cambia de región durante un partido. **No se resuelve en este hito.**

---

## 11. Alcance y seguridad

Fuera de alcance por el enunciado: API REST, interfaz web, integración física con los otros servicios, despliegue multirregional. El nodo **no tiene contraseña** y sólo se publica en `127.0.0.1`: es configuración de **desarrollo**. Los ids de sesión de la muestra son ficticios (`demo-ses-…`); no hay tokens, contraseñas ni datos personales reales en el repo (RNF7).
