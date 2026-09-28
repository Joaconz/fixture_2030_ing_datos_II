# Fixture 2030 — Hito 8 · Series temporales de estadísticas en vivo (InfluxDB)

**Repositorio:** https://github.com/Joaconz/fixture_2030_ing_datos_II
**Ingeniería de Datos II · Grupo 2** — Santiago Pazos, Valentina Frisoli, Joaquín Núñez

Módulo que registra y consulta las estadísticas que cambian segundo a segundo durante los partidos: el **juego** (posesión, pases, tiros, goles, recuperaciones), la **audiencia** (usuarios conectados, comentarios y sesiones nuevas por región) y la **operación** de los servicios (latencia, solicitudes, errores).

**Resultado de la prueba (28/09/2026):** 10.094.400 puntos cargados en 12,9 s (780.255 puntos/s) sin errores; todas las validaciones en ✅. Detalle en [`docs/pruebas_y_rendimiento.md`](./docs/pruebas_y_rendimiento.md).

> **Versión:** `influxdb:latest` resolvió a **InfluxDB v2.9.1** (ver `docs/evidencia/01_inicializacion.txt`). Consultas en **Flux**.
> **Nodo único de laboratorio.** InfluxDB 2 OSS no tiene réplicas ni clúster; la escala fuera del laboratorio está en [`docs/cardinalidad_y_escalabilidad.md`](./docs/cardinalidad_y_escalabilidad.md) §6.

---

## 1. Estructura

```
fixture2030-influxdb/
├── docker-compose.yml            influxdb:latest (v2.9.1) + servicio "herramientas" (Python)
├── .env.example                  puerto y carpeta de datos (opcional; sin secretos)
├── .gitignore                    excluye secrets/, .env y data/lp/
├── secrets/README.md             acá se genera la autorización local (ignorada por git)
├── scripts/
│   ├── inicializacion.sh         carpetas, `up -d`, verificación con la CLI, buckets con retención, evidencia
│   ├── autorizacion_local.sh     `influx setup`: usuario, organización y token (secrets/)
│   ├── comun.py                  conexión HTTP, calendario canónico del Hito 5, evidencia
│   ├── generacion_puntos.py      GENERA line protocol determinista + manifiesto
│   ├── carga_lotes.py            CARGA por lotes, concurrente, con reintentos y medición
│   ├── consultas_temporales.py   P1–P6 en Flux: ventana, último valor, filtros, comparaciones, huecos
│   ├── agregaciones.py           A1–A5 por semántica + resúmenes con to() + task nativa
│   ├── validacion.py             V1–V8: conteos, cardinalidad, tipos, retención, tardíos, shards, torneo
│   ├── prueba_persistencia.sh    cuenta, `down` + `up -d`, vuelve a contar (RNF2)
│   └── limpieza.sh               opcional: borra archivos generados, buckets o todo
├── data/README.md                origen y distribución de los datos
└── docs/
    ├── patrones_de_acceso.md
    ├── modelo_multidimensional.md
    ├── cardinalidad_y_escalabilidad.md
    ├── retencion_y_granularidad.md
    ├── consultas_y_agregaciones.md   resultados e interpretación de P1–P6, A1–A5 y consultas de torneo
    ├── pruebas_y_rendimiento.md      método, hipótesis, resultados, hallazgos y limitaciones
    └── evidencia/                    salidas de cada corrida (con fecha, versión y ambiente)
```

---

## 2. Requisitos

- Docker Desktop con Docker Compose V2 (≥ 4 GB de RAM asignados a Docker para el perfil completo).
- Puerto `8086` libre (si no: `INFLUX_PORT=18086` en un `.env`).
- **No** hace falta Python en la notebook: los scripts corren en el servicio `herramientas`.

---

## 3. Paso a paso

Todos los comandos se ejecutan **desde esta carpeta**.

### 3.1 Inicializar: servidor, autorización local y buckets

```bash
sh scripts/inicializacion.sh
```

En orden: crea `~/docker/data/influxdb/{data,config}`, las carpetas que respaldan los volúmenes nombrados (RNF2); levanta el servicio con **`docker compose up -d`** y espera a *healthy*; verifica la disponibilidad con la **CLI incluida en el contenedor** (`influx ping`, `influxd version`; RF1); crea la **autorización local** con `influx setup` (usuario, organización `fixture2030` y token, en `secrets/admin-token.json`, sin imprimirlos; RNF7); crea los tres buckets con su retención; y guarda en `docs/evidencia/01_inicializacion.txt` la versión, los buckets, los volúmenes y los recursos de Docker. Es idempotente.

El servicio también arranca solo con `docker compose up -d`, sin pasos previos: la inicialización agrega la autorización y los buckets con el servidor ya arriba.

| Bucket | Retención | Shard | Contenido |
|---|---|---|---|
| `fixture2030_vivo` | 45 días | 1 día | Puntos originales, 1 s / 10 s |
| `fixture2030_historico` | sin vencimiento | 7 días | Resúmenes por minuto, 5 minutos y partido |
| `fixture2030_prueba_retencion` | 1 hora | 1 hora | Solo para demostrar la retención |

Verificar el estado y usar la CLI en cualquier momento:

```bash
docker compose ps                                          # STATUS: healthy
docker compose exec influxdb influx ping                   # OK
docker compose exec influxdb influx bucket list           # la CLI del contenedor ya quedó configurada por el setup
```

**Interfaz web:** http://localhost:8086 (usuario y contraseña en `secrets/admin-token.json`).

### 3.2 Muestra (2 partidos, 176.400 puntos)

```bash
docker compose run --rm herramientas scripts/generacion_puntos.py --perfil muestra
docker compose run --rm herramientas scripts/carga_lotes.py --perfil muestra
docker compose run --rm herramientas scripts/validacion.py --perfil muestra
docker compose run --rm herramientas scripts/consultas_temporales.py
docker compose run --rm herramientas scripts/agregaciones.py --perfil muestra
docker compose run --rm herramientas scripts/validacion.py --perfil muestra     # ahora con la V8
sh scripts/prueba_persistencia.sh                                                # 11400 antes y después
```

La primera validación muestra la V8 recién cuando el bucket histórico tiene los resúmenes; la segunda tiene que terminar **toda en ✅**.

### 3.3 Volumen objetivo: 10.094.400 puntos

```bash
docker compose run --rm herramientas scripts/generacion_puntos.py --perfil completo      # < 1 min, ~100 MB
docker compose run --rm herramientas scripts/carga_lotes.py --perfil completo           # ~15 s en la prueba
docker compose run --rm herramientas scripts/agregaciones.py --perfil completo          # ~6 min (112 partidos)
docker compose run --rm herramientas scripts/validacion.py --perfil completo
docker compose run --rm herramientas scripts/consultas_temporales.py
```

Parámetros de carga: `--lote` (líneas por POST, por defecto 10.000), `--hilos` (por defecto 4), `--gzip`, `--tabla`.

### 3.4 Idempotencia

Recargar no duplica: un punto con la misma serie y el mismo timestamp se sobrescribe (V6), y los resúmenes se reemplazan de forma explícita (se borra el tramo y se reescribe). Repetir la carga o las agregaciones y volver a validar da los mismos conteos.

### 3.5 Consultas manuales (Flux)

```bash
docker compose exec influxdb influx query 'from(bucket: "fixture2030_vivo")
  |> range(start: 2030-06-29T16:00:00Z, stop: 2030-06-29T18:10:00Z)
  |> filter(fn: (r) => r._measurement == "estadisticas_equipo" and r.partido_id == "PAR-D16-01" and r._field == "goles_acum")
  |> last()'
```

### 3.6 Detener y reiniciar sin perder datos (RNF2)

```bash
docker compose down        # apaga; los datos quedan en ~/docker/data/influxdb (volúmenes fixture2030_influxdb_data/_config)
docker compose up -d       # vuelve con los mismos datos y la misma autorización
sh scripts/prueba_persistencia.sh   # lo demuestra -> docs/evidencia/02_persistencia.txt
```

`docker compose down -v` borra los volúmenes de Docker pero **no** los archivos de `~/docker/data/influxdb`. Para empezar de cero: `sh scripts/limpieza.sh todo`.

---

## 4. Seguridad local (RNF7)

- Usuario, contraseña y token se generan al azar en cada notebook (`influx setup` en `scripts/autorizacion_local.sh`) y se escriben directo a `secrets/admin-token.json` (permisos 600), **excluido por `.gitignore`**. En el repositorio solo está `secrets/README.md`.
- Ningún script imprime el token ni lo escribe en la evidencia.
- El puerto se publica solo en `127.0.0.1`: no queda accesible desde la red. La telemetría hacia InfluxData está desactivada.
- `.env` (opcional) no contiene secretos y también está excluido. Los datos generados (`data/lp/`) no se versionan: se regeneran con el mismo resultado.
- **Al subir por la web de GitHub**, verificar que no aparezcan `secrets/admin-token.json` ni `data/lp/` (la subida por arrastre no aplica el `.gitignore`).

---

## 5. Evidencia y registro del ambiente (RNF10)

| Fecha de prueba | Versión observada | Recursos de Docker | Perfil cargado | Tasa medida | Validación |
|---|---|---|---|---|---|
| 28/09/2026 | InfluxDB v2.9.1 | 8 CPUs, 3,8 GB | completo (10.094.400 puntos) | 780.255 puntos/s | todo ✅ |

Cada script deja su salida en `docs/evidencia/` con fecha, versión y recursos visibles. El método, las hipótesis y el análisis están en [`docs/pruebas_y_rendimiento.md`](./docs/pruebas_y_rendimiento.md).

---

## 6. Relación con los hitos anteriores

- **Hito 1** — 2–3 M usuarios y 100.000+ solicitudes/s: el pico simulado de `PAR-D16-01` es de 2,56 M usuarios y la operación supera las 100.000 solicitudes/s.
- **Hito 2** — N7 → series temporales (4,75): la consulta por período es la operación central del módulo.
- **Hito 3** — N7 **AP, eventual, orden monótono por partido, partición por partido + intervalo**: tag `partido_id` + shards de 1 día; carga cronológica por partido; un punto se corrige sobrescribiéndolo. Responde la pregunta que dejó abierta sobre retención y resumen.
- **Hito 5** — mismos `partido_id`, `equipo_id`, `sede_id`, fechas y goles de grupos que `carga.cypher`. `PAR-D16-01` = ARG vs BEL, igual que en el grafo.
- **Hito 6** — `comentarios` mide la tasa de escritura que recibe Cassandra; `PAR-D16-01` es el partido de audiencia MÁXIMA en ambos módulos.
- **Hito 7** — `sesiones_nuevas` mide la creación de sesiones en Redis; `sesiones` y `cache` son servicios de `operacion_plataforma`.

---

## 7. Alcance

Fuera de alcance por el enunciado: API REST, interfaz web propia, Grafana, nube y monitoreo de producción.
