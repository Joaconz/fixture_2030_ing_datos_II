# Fixture 2030 — Hito 8 · Series temporales de estadísticas en vivo (InfluxDB 3 Core)

**Repositorio:** https://github.com/Joaconz/fixture_2030_ing_datos_II
**Ingeniería de Datos II · Grupo 2** — Santiago Pazos, Valentina Frisoli, Joaquín Núñez

Módulo que registra y consulta las estadísticas que cambian segundo a segundo durante los partidos: el **juego** (posesión, pases, tiros, goles, recuperaciones), la **audiencia** (usuarios conectados, comentarios y sesiones nuevas por región) y la **operación** de los servicios (latencia, solicitudes, errores).

**Resultado de la prueba (09/10/2026):** 10.094.400 puntos cargados en 55,2 s (182.726 puntos/s) sin errores; todas las validaciones en ✅. Detalle en [`docs/pruebas_y_rendimiento.md`](./docs/pruebas_y_rendimiento.md).

> **Versión:** `influxdb:3-core` → **InfluxDB 3 Core 3.12.0** (ver `docs/evidencia/01_inicializacion.txt`). Bases de datos y tablas; consultas en **SQL**.
> **Nodo único de laboratorio.** InfluxDB 3 Core no tiene réplicas ni clúster; la escala fuera del laboratorio está en [`docs/cardinalidad_y_escalabilidad.md`](./docs/cardinalidad_y_escalabilidad.md) §6.

---

## 0. Imagen: por qué `influxdb:3-core` y no `influxdb:latest`

El enunciado (RNF1, §6) pide la imagen oficial `influxdb:latest`, según el criterio de actualización de la materia. La Clase 9 aclara que **el tag `influxdb:latest` todavía apunta a InfluxDB 2.x** y no trae el binario `influxdb3`: para trabajar con InfluxDB 3 Core hay que usar `influxdb:3-core`. La primera entrega de este hito usó `latest` (InfluxDB 2.9.1, con buckets, Flux y tasks), y la corrección del profesor pidió migrar a 3 Core.

Por eso el Compose usa `image: influxdb:3-core` con **`pull_policy: always`**, igual que el de la Clase 9: cada `docker compose up -d` baja la última versión de la línea 3 Core. Así se mantiene el criterio de actualización del RNF1. La versión efectivamente usada se registra en cada corrida.

---

## 1. Estructura

```
fixture2030-influxdb/
├── docker-compose.yml            influxdb:3-core (3.12.0) + servicio "herramientas" (Python)
├── .env.example                  puerto y carpeta de datos (opcional; sin secretos)
├── .gitignore                    excluye secrets/, .env y data/lp/
├── secrets/README.md             acá se genera la autorización local (ignorada por git)
├── scripts/
│   ├── inicializacion.sh         carpeta, `up -d`, verificación con la CLI, bases con retención, evidencia
│   ├── autorizacion_local.sh     `influxdb3 create token --admin` -> secrets/
│   ├── comun.py                  conexión HTTP (write_lp, query_sql), calendario canónico del Hito 5, evidencia
│   ├── generacion_puntos.py      GENERA line protocol determinista + manifiesto
│   ├── carga_lotes.py            CARGA por lotes, concurrente, con reintentos y medición
│   ├── consultas_temporales.py   P1–P6 en SQL: ventana, último valor, filtros, comparaciones, huecos
│   ├── agregaciones.py           A1–A5 por semántica + resúmenes en la base histórica
│   ├── validacion.py             V1–V8: conteos, cardinalidad, tipos, retención, tardíos, Parquet, torneo
│   ├── prueba_persistencia.sh    cuenta, `down` + `up -d`, vuelve a contar (RNF2)
│   └── limpieza.sh               opcional: borra archivos generados, bases o todo
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

- Docker Desktop con Docker Compose V2 (≥ 4 GB de RAM asignados a Docker para el perfil completo: el servidor llegó a 1,55 GiB durante la carga).
- Puerto `8181` libre (si no: `INFLUX_PORT=18181` en un `.env`).
- **No** hace falta Python en la notebook: los scripts corren en el servicio `herramientas`.
- **Windows con Git Bash:** antes de correr los `.sh`, `export MSYS_NO_PATHCONV=1`. Si no, Git Bash convierte las rutas Linux de los comandos `docker` en rutas de Windows. En macOS y Linux no hace falta.
- **Linux:** si el servidor no puede escribir la carpeta de datos (`PermissionDenied`), `sudo chmod -R 777 ~/docker/data/influxdb` (el proceso del contenedor corre con el uid 1500). `inicializacion.sh` ya lo intenta sin `sudo`.

---

## 3. Paso a paso

Todos los comandos se ejecutan **desde esta carpeta**.

### 3.1 Inicializar: servidor, autorización local y bases de datos

```bash
sh scripts/inicializacion.sh
```

En orden:
1. Crea `~/docker/data/influxdb`, la carpeta que respalda el volumen nombrado (RNF2).
2. Levanta el servicio con **`docker compose up -d`** y espera a *healthy*.
3. Verifica la disponibilidad con las **herramientas incluidas en el contenedor** (`influxdb3 --version`, `curl /health`; RF1).
4. Crea la **autorización local** con `influxdb3 create token --admin`. El token se guarda en `secrets/admin-token.json` sin imprimirlo (RNF7).
5. Crea las tres bases con su retención.
6. Guarda en `docs/evidencia/01_inicializacion.txt` la versión, las bases, la retención, el volumen y los recursos de Docker.

Es idempotente. El servicio también arranca solo con `docker compose up -d`, sin pasos previos: la inicialización agrega la autorización y las bases con el servidor ya arriba.

| Base de datos | Retención | Contenido |
|---|---|---|
| `fixture2030_vivo` | 45 días | Puntos originales, 1 s / 10 s |
| `fixture2030_historico` | sin vencimiento | Resúmenes por minuto, 5 minutos y partido |
| `fixture2030_prueba_retencion` | 1 hora | Solo para demostrar la retención |

En InfluxDB 3 Core la retención **se fija al crear la base y no se puede cambiar después**.

Verificar el estado y usar la CLI en cualquier momento:

```bash
docker compose ps                                                   # STATUS: healthy
docker compose exec influxdb curl -s http://127.0.0.1:8181/health   # OK
TOKEN=$(sed -n 's/.*"token": "\(.*\)".*/\1/p' secrets/admin-token.json)
docker compose exec -e INFLUXDB3_AUTH_TOKEN="$TOKEN" influxdb influxdb3 show databases
docker compose exec -e INFLUXDB3_AUTH_TOKEN="$TOKEN" influxdb influxdb3 show retention
```

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

La primera validación muestra la V8 recién cuando la base histórica tiene los resúmenes; la segunda tiene que terminar **toda en ✅**.

### 3.3 Volumen objetivo: 10.094.400 puntos

```bash
docker compose run --rm herramientas scripts/generacion_puntos.py --perfil completo      # ~1 min, ~100 MB
docker compose run --rm herramientas scripts/carga_lotes.py --perfil completo           # ~1 min en la prueba
docker compose run --rm herramientas scripts/agregaciones.py --perfil completo          # ~2,5 min (112 partidos)
docker compose run --rm herramientas scripts/validacion.py --perfil completo
docker compose run --rm herramientas scripts/consultas_temporales.py
```

Parámetros de carga: `--lote` (líneas por POST, por defecto 50.000), `--hilos` (por defecto 8), `--gzip`, `--tabla`. La validación del perfil `muestra` hay que correrla antes de cargar el completo, porque cuenta por día y el completo agrega otros partidos esos mismos días.

### 3.4 Idempotencia

Recargar no duplica: un punto con la misma serie y el mismo timestamp se sobrescribe (V6). Los resúmenes también se reescriben con la misma serie y el mismo timestamp. Repetir la carga o las agregaciones, incluso después de reiniciar el servidor, y volver a validar da los mismos conteos.

### 3.5 Consultas manuales (SQL)

```bash
TOKEN=$(sed -n 's/.*"token": "\(.*\)".*/\1/p' secrets/admin-token.json)
docker compose exec -e INFLUXDB3_AUTH_TOKEN="$TOKEN" influxdb influxdb3 query --database fixture2030_vivo \
  "SELECT equipo_id, last_value(goles_acum ORDER BY time) AS goles
   FROM estadisticas_equipo
   WHERE partido_id = 'PAR-D16-01' AND time >= '2030-06-29T16:00:00Z' AND time < '2030-06-29T18:10:00Z'
   GROUP BY equipo_id"
```

### 3.6 Detener y reiniciar sin perder datos (RNF2)

```bash
docker compose down        # apaga; los datos quedan en ~/docker/data/influxdb (volumen fixture2030_influxdb_data)
docker compose up -d       # vuelve con los mismos datos y el mismo token
sh scripts/prueba_persistencia.sh   # lo demuestra -> docs/evidencia/02_persistencia.txt
```

`docker compose down -v` borra el volumen de Docker pero **no** los archivos de `~/docker/data/influxdb`. Para empezar de cero: `sh scripts/limpieza.sh todo`.

---

## 4. Seguridad local (RNF7)

- El token de administración lo crea `influxdb3 create token --admin` en cada notebook (`scripts/autorizacion_local.sh`). InfluxDB 3 lo muestra una sola vez: el script lo captura directo a `secrets/admin-token.json` (permisos 600), **excluido por `.gitignore`**. En el repositorio solo está `secrets/README.md`.
- Ningún script imprime el token ni lo escribe en la evidencia.
- El puerto se publica solo en `127.0.0.1`: no queda accesible desde la red. Sin token, el servidor solo responde `/health` y `/ping` (estado y versión), que usa el healthcheck de Docker.
- `.env` (opcional) no contiene secretos y también está excluido. Los datos generados (`data/lp/`) no se versionan: se regeneran con el mismo resultado.
- **Al subir por la web de GitHub**, verificar que no aparezcan `secrets/admin-token.json` ni `data/lp/` (la subida por arrastre no aplica el `.gitignore`).

---

## 5. Evidencia y registro del ambiente (RNF10)

| Fecha de prueba | Versión observada | Recursos de Docker | Perfil cargado | Tasa medida | Validación |
|---|---|---|---|---|---|
| 09/10/2026 | InfluxDB 3 Core 3.12.0 | 12 CPUs, 7,7 GB | completo (10.094.400 puntos) | 182.726 puntos/s | todo ✅ |

Cada script deja su salida en `docs/evidencia/` con fecha, versión y recursos visibles. El método, las hipótesis y el análisis están en [`docs/pruebas_y_rendimiento.md`](./docs/pruebas_y_rendimiento.md).

---

## 6. Relación con los hitos anteriores

- **Hito 1** — 2–3 M usuarios y 100.000+ solicitudes/s: el pico simulado de `PAR-D16-01` es de 2,56 M usuarios y la operación supera las 100.000 solicitudes/s.
- **Hito 2** — N7 → series temporales (4,75): la consulta por período es la operación central del módulo.
- **Hito 3** — N7 **AP, eventual, orden monótono por partido, partición por partido + intervalo**: tag `partido_id` (primera columna de la clave de serie) + archivos Parquet por tramo de tiempo. La carga es cronológica por partido, y un punto se corrige sobrescribiéndolo. Este módulo responde la pregunta que el Hito 3 dejó abierta sobre retención y resumen.
- **Hito 5** — mismos `partido_id`, `equipo_id`, `sede_id`, fechas y goles de grupos que `carga.cypher`. `PAR-D16-01` = ARG vs BEL, igual que en el grafo.
- **Hito 6** — `comentarios` mide la tasa de escritura que recibe Cassandra; `PAR-D16-01` es el partido de audiencia MÁXIMA en ambos módulos.
- **Hito 7** — `sesiones_nuevas` mide la creación de sesiones en Redis; `sesiones` y `cache` son servicios de `operacion_plataforma`.

---

## 7. Alcance

Fuera de alcance por el enunciado: API REST, interfaz web propia, Grafana, nube y monitoreo de producción. Tampoco se usan los disparadores del *Processing Engine* de InfluxDB 3 ni las cachés de último valor: el resumen histórico se ejecuta con `agregaciones.py`.
