# Fixture 2030 — Hito 6 · Módulo de Comentarios (Cassandra)

**Ingeniería de Datos II · Grupo 2** — Santiago Pazos, Valentina Frisoli, Joaquín Núñez

Módulo tabular de comentarios masivos del Mundial 2030: publicación y lectura de mensajes por partido, historial por usuario, moderación y métricas de interacción, diseñado para escritura intensiva y consultas acotadas por patrones de acceso conocidos.

> **Nodo único de laboratorio.** Este ambiente no es de alta disponibilidad ni multirregional. La topología de producción (RF=3 por región, N=3 / R=1 / W=1) está descrita en [`docs/modelo_tabular.md`](./docs/modelo_tabular.md) §1.

---

## 1. Estructura del módulo

```
fixture2030-cassandra/
├── docker-compose.yml              cassandra:latest + persistencia en ~/docker/data/cassandra + cargador
├── scripts/
│   ├── esquema.cql                 keyspace, 4 tablas, índice SAI (idempotente)
│   ├── carga_muestra.cql           112 configs + 80 comentarios de 2 partidos (idempotente)
│   ├── crud.cql                    create / read / update / moderación / borrado lógico y físico (repetible)
│   ├── consultas.cql               Q0..Q7: últimos N, rango, paginación, moderación, historial, agrupadas
│   ├── carga_masiva.py             carga de 1.050.000 comentarios + medición de escrituras/s
│   ├── generador.py                generador determinista compartido por muestra y carga masiva
│   └── generar_muestra.py          regenera carga_muestra.cql y data/muestra_comentarios.csv
├── data/
│   ├── muestra_comentarios.csv     los 80 comentarios de la muestra, para inspección
│   └── README.md                   origen y distribución de los datos
├── docs/
│   ├── patrones_de_acceso.md       problema de volumen y consultas prioritarias (se escribió primero)
│   ├── modelo_tabular.md           keyspace, tablas, claves, índice, lab vs producción
│   ├── decisiones_de_particionamiento.md   partición, buckets, duplicación, TTL, tombstones, preguntas guía
│   ├── rendimiento.md              método de medición, ambiente, resultados, distribución de particiones
│   └── evidencia/                  salidas de las corridas y capturas
└── README.md
```

---

## 2. Requisitos

- Docker Desktop (o Docker Engine) con Docker Compose V2.
- ~3 GB de RAM libres (el compose limita el heap de Cassandra a 1 GB).
- Puerto `9042` libre. Si está ocupado: `CASSANDRA_CQL_PORT=19042 docker compose up -d`.
- **No** hace falta Python en la notebook: la carga masiva corre en un contenedor.

---

## 3. Levantar el ambiente y verificar el nodo (RF1)

```bash
cd fixture2030-cassandra
docker compose up -d

# Esperar a que STATUS diga "healthy" (60-90 s la primera vez)
docker compose ps

# Estado del nodo: debe aparecer "UN" (Up / Normal)
docker compose exec cassandra nodetool status

# Abrir el cliente CQL interactivo
docker compose exec cassandra cqlsh
```

Los datos quedan en `~/docker/data/cassandra` (RNF2): sobreviven a `docker compose down`.

---

## 4. Crear el esquema y cargar la muestra

Los `.cql` del repositorio están montados en `/scripts` dentro del contenedor.

```bash
# 1) Keyspace, tablas e índice
docker compose exec cassandra cqlsh -f /scripts/esquema.cql

# 2) Carga de muestra (80 comentarios + configuración de los 112 partidos)
docker compose exec cassandra cqlsh -f /scripts/carga_muestra.cql

# 3) CRUD de demostración (crea, lee, edita, modera, borra y verifica)
docker compose exec cassandra cqlsh -f /scripts/crud.cql

# 4) Consultas por patrón de acceso
docker compose exec cassandra cqlsh -f /scripts/consultas.cql
```

### 4.1 Demostrar la idempotencia (RNF7)

```bash
docker compose exec cassandra cqlsh -f /scripts/esquema.cql        # no falla ni borra nada
docker compose exec cassandra cqlsh -f /scripts/carga_muestra.cql  # mismos conteos al final
```

Los tres `SELECT count(*)` del final de `carga_muestra.cql` deben dar lo mismo en cada corrida: **112**, **24** y **20** (antes de la carga masiva; después dan más porque la muestra es un subconjunto de ella). No se duplica porque en Cassandra `INSERT` es un *upsert* sobre la clave primaria y todas las claves son deterministas (no hay `uuid()` ni `now()`). `crud.cql` también es repetible: su bloque 7 termina en `0` y `0`.

---

## 5. Carga masiva y medición (RF11, RF12)

```bash
# Prueba corta: 100.000 comentarios
docker compose --profile carga run --rm cargador --limite 100000

# Carga completa: 1.050.000 comentarios = 2.100.000 escrituras (dos vistas)
docker compose --profile carga run --rm cargador
```

El script imprime la tasa por lote mientras carga y, al terminar, guarda en `docs/evidencia/carga_masiva_<fecha>.md` y `.json`: versión de Cassandra, CPUs y RAM visibles, concurrencia, filas, errores, tiempo, **escrituras por segundo** y distribución de filas por partición. El método y la interpretación están en [`docs/rendimiento.md`](./docs/rendimiento.md).

Distribución de los datos: 112 partidos (los mismos del Hito 5), 1 de audiencia máxima (300.000 comentarios, 4 buckets), 15 de audiencia alta (20.000 c/u), 96 normales (~4.700 c/u); 250.000 usuarios con actividad sesgada; estados 93 % publicado, 4 % pendiente, 2 % oculto, 1 % eliminado. Detalle en [`data/README.md`](./data/README.md).

Verificar tamaños de partición después de la carga:

```bash
docker compose exec cassandra nodetool flush fixture2030_comentarios
docker compose exec cassandra nodetool tablehistograms fixture2030_comentarios comentarios_por_partido
docker compose exec cassandra nodetool tablestats fixture2030_comentarios.comentarios_por_partido
```

---

## 6. Registro de la versión probada (RNF1, RNF9)

El enunciado exige `cassandra:latest` y, a cambio, registrar con qué versión concreta se validó:

```bash
docker compose exec cassandra cqlsh -e "SHOW VERSION"
```

| Fecha de prueba | Versión (`SHOW VERSION`) | Observaciones |
|---|---|---|
| 2026-09-24 | Cassandra **5.0.9** · cqlsh 6.2.0 · CQL spec 3.4.7 · protocolo nativo v5 | Esquema, muestra, CRUD, consultas y carga masiva ejecutados sin errores. SAI disponible (5.0+), no hizo falta el reemplazo de abajo |

**Dependencia de versión conocida:** el índice de `esquema.cql` usa **SAI** (`USING 'sai'`), disponible desde Cassandra 5.0. Si `latest` resolviera a una versión anterior, reemplazar esa línea por `CREATE INDEX IF NOT EXISTS idx_comentarios_estado ON comentarios_por_partido (estado_moderacion);` — como la consulta Q4 siempre trae la partición completa, el comportamiento es equivalente.

---

## 7. Comandos útiles

```bash
docker compose ps                                   # estado
docker compose logs -f cassandra                    # logs (flushes, compactaciones, errores)
docker compose exec cassandra cqlsh                 # cliente interactivo
docker compose exec cassandra nodetool status       # estado del nodo
docker compose down                                 # detener, conservando los datos
docker compose down && rm -rf ~/docker/data/cassandra   # BORRAR TODO y reproducir desde cero
```

---

## 8. Reproducir el hito desde cero (RNF3)

```bash
git clone <repo> && cd <repo>/fixture2030-cassandra
docker compose up -d
docker compose ps                                                   # esperar "healthy"
docker compose exec cassandra cqlsh -e "SHOW VERSION"
docker compose exec cassandra cqlsh -f /scripts/esquema.cql
docker compose exec cassandra cqlsh -f /scripts/carga_muestra.cql
docker compose exec cassandra cqlsh -f /scripts/carga_muestra.cql   # idempotencia
docker compose exec cassandra cqlsh -f /scripts/crud.cql
docker compose exec cassandra cqlsh -f /scripts/consultas.cql
docker compose --profile carga run --rm cargador                    # 1.050.000 comentarios
docker compose exec cassandra cqlsh -f /scripts/consultas.cql       # mismas consultas, con volumen
```

Para regenerar la muestra (solo si se cambia el generador): `python3 scripts/generar_muestra.py` (Python 3.9+, sin librerías externas).

---

## 9. Relación con los hitos previos

- **Hito 2** — Comentarios (N6) asignado al modelo **columnar** por escalabilidad y volumen de escritura.
- **Hito 3** — N6 es **AP con consistencia eventual**, **N=3 / R=1 / W=1**, partición **"partido + ventana temporal"**. Este hito implementa esa partición y le agrega el **bucket**, después de medir que la ventana sola no reparte el pico ([`decisiones_de_particionamiento.md`](./docs/decisiones_de_particionamiento.md) §2).
- **Hito 4** — Claves naturales y carga por *upsert*: `comentario_id` es determinista y la carga es idempotente.
- **Hito 5** — Mismos 112 `partido_id` y mismas fechas que el grafo de Neo4j. **No hay integración por código**: la relación es por identificador.

---

## 10. Alcance

Fuera de alcance por decisión del enunciado: API REST, interfaz web, grafos, caché, series temporales y monitoreo. Credenciales: el nodo de laboratorio usa la autenticación por defecto de la imagen (sin usuario ni contraseña); es una configuración de **desarrollo** y no se publica ningún secreto (RNF8).
