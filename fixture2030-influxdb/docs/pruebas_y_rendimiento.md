# Pruebas y rendimiento — Hito 8 · InfluxDB 3 Core

**Ingeniería de Datos II · Grupo 2** — Santiago Pazos, Valentina Frisoli, Joaquín Núñez

> **Regla del enunciado:** no se declara ninguna tasa, latencia ni volumen sin método, ambiente y resultado observado. Todas las cifras de este documento salen de los archivos de `docs/evidencia/` de la corrida del 09/10/2026.

---

## 1. Método

### 1.1 Carga (RF12, RF13)

| Aspecto | Decisión | Por qué |
|---|---|---|
| Herramienta | `carga_lotes.py`, Python con biblioteca estándar, en el contenedor `herramientas` | Reproducible sin instalar nada (RNF3) |
| Qué se cronometra | La carga completa (lectura de `.lp.gz` + envío + confirmación del servidor) y la latencia de cada POST | Es el tiempo real de ingestar el volumen |
| Unidad | **Puntos por segundo** = líneas de line protocol confirmadas (HTTP 204) por segundo | Un punto es una línea con todos sus fields |
| Confirmación | El 204 llega cuando el lote está en el WAL en disco (volcado cada 1 s) | No se mide una escritura que se podría perder |
| Parámetros | Lote 50.000 líneas, 8 hilos, sin gzip, `accept_partial=false` | Elegidos con el barrido del §4.1 (ver `cardinalidad_y_escalabilidad.md` §4) |
| Validación | `validacion.py` compara lo cargado con el manifiesto, partido por partido | Una tasa alta no sirve si faltan puntos, y la retención descarta puntos sin dar error |
| Memoria | `docker stats` del contenedor cada 10 s durante la carga completa | Ver cuánto ocupa el buffer en memoria de InfluxDB 3 |

### 1.2 Consultas

| Aspecto | Decisión |
|---|---|
| Herramienta | `consultas_temporales.py`, SQL por `POST /api/v3/query_sql` (respuesta JSON) |
| Repeticiones | 10 por consulta. La **1ª** se informa aparte (caché fría); p50 y p95 sobre las 9 restantes |
| Alcance | P1–P6 sobre `PAR-D16-01`, con el perfil completo cargado |
| Qué incluye el tiempo | Viaje HTTP + planificación + lectura + serialización JSON: lo que ve un cliente |

---

## 2. Ambiente

| Dato | Valor |
|---|---|
| Fecha de la prueba | 09/10/2026 (inicialización 22:31 UTC, carga completa 22:37 UTC, corridas finales 22:43 UTC) |
| Imagen | `influxdb:3-core` → **InfluxDB 3 Core 3.12.0** (revisión 3ba97c65f1). Imagen `sha256:624d69bc…`, creada el 02/10/2026 |
| Equipo | Notebook con Windows 11 y Docker Desktop (backend WSL2, Linux x86_64) |
| Recursos de Docker (compartidos por servidor y cliente) | **12 CPUs, 7,7 GB de RAM** |
| Nodos / réplicas | 1 / ninguna (InfluxDB 3 Core) |
| Almacenamiento | `--object-store=file` sobre `~/docker/data/influxdb` |
| Cliente | Contenedor `python:3.12-slim` (Python 3.12.15) en la misma notebook |

**Condiciones para interpretar los números:** cliente y servidor comparten CPU y memoria. Es un solo nodo sin réplicas: cada punto se escribe una vez. Docker Desktop en Windows agrega una capa de virtualización (WSL2) y el montaje de la carpeta del host.

---

## 3. Hipótesis (escritas antes de correr en InfluxDB 3)

1. **En vivo, la ingesta es chica; lo exigente es la carga masiva.** En el calendario del Hito 5 nunca hay más de **2 partidos simultáneos**, así que en tiempo real llegan unos **20 puntos por segundo**.
2. **El tamaño del lote y la concurrencia cambian la tasa**, porque cada POST espera el volcado del WAL.
3. **gzip no mejora en la misma notebook.**
4. **La 1ª ejecución de cada consulta es más lenta** que las siguientes.
5. **Las consultas que recorren el partido completo son las más lentas.**
6. **Recargar y volver a resumir no cambia los conteos** (idempotencia), también después de reiniciar el servidor.

---

## 4. Resultados

### 4.1 Barrido de lote y concurrencia (perfil muestra, 176.400 puntos)

| Lote (líneas) | Hilos | Tiempo | **Puntos/s** | Latencia POST p50 / p95 |
|---:|---:|---:|---:|---|
| 10.000 | 4 | 4,36 s | **40.495** | 0,962 / 1,096 s |
| 10.000 | 16 | 1,83 s | **96.621** | 1,361 / 1,718 s |
| 50.000 | 4 | 1,80 s | **98.001** | 0,857 / 0,917 s |
| 50.000 | 8 | 1,89 s | **93.113** | 1,613 / 1,814 s |
| 50.000 | 16 | 1,64 s | **107.528** | 1,489 / 1,610 s |

Archivos en `docs/evidencia/barrido/`. Cada POST tarda alrededor de 1 s, sea cual sea su tamaño: es la espera del volcado del WAL. Lo que sube la tasa es tener **más líneas en vuelo** (lotes más grandes o más hilos). Con 50.000 líneas la muestra entera son 8 lotes (un lote nunca mezcla archivos), así que pasar de 4 a 16 hilos casi no cambia nada: la muestra es chica para distinguir esas configuraciones. Para el perfil completo se eligió **50.000 líneas y 8 hilos**.

La primera carga de la muestra, con los parámetros anteriores (10.000 / 4), está en `carga_muestra_*`: 33.676 puntos/s.

### 4.2 Carga completa

| Corrida | Puntos esperados | Puntos confirmados | Tiempo | **Puntos/s** | Latencia POST p50 / p95 / máx | Lotes / reintentos | Error |
|---|---:|---:|---:|---:|---|---|---|
| **Completo** (50.000 / 8) | **10.094.400** | **10.094.400** | **55,24 s** | **182.726** | 1,154 / 2,097 / 2,640 s | 361 / 0 | ninguno |

Por tabla: `estadisticas_equipo` 1.276.800 puntos en 15,4 s · `audiencia_partido` 7.795.200 en 35,2 s · `operacion_plataforma` 1.022.400 en 3,2 s. Datos enviados: 1.429,7 MB de line protocol. Memoria del contenedor durante la carga: **pico de 1,55 GiB** (de 7,7 GB disponibles).

**Objetivo de 10 M+:** cumplido con el volumen completo, no por proyección.

### 4.3 Consultas (perfil completo cargado)

| Consulta | Filas | 1ª ejecución (ms) | p50 (ms) | p95 (ms) |
|---|---:|---:|---:|---:|
| P1 ventana de 2 min | 10 | 9,6 | 8,2 | 9,7 |
| P2 último valor | 2 | 21,8 | 20,3 | 21,8 |
| P3 audiencia por región | 58 | 22,5 | 22,1 | 23,1 |
| P4 local contra visitante | 8 | 16,3 | 16,2 | 18,2 |
| P5 dos fuentes | 16 | 18,5 | 14,6 | 15,3 |
| P6 ausencia de puntos | 21 | 15,1 | 14,6 | 17,1 |

### 4.4 Otras mediciones

| Medición | Resultado |
|---|---|
| Pregunta de torneo (V8): total de comentarios | Base viva **4.309 ms** (7.795.200 puntos) · base histórica **41 ms** (112 puntos) · mismo resultado: 9.847.799 |
| Resumen histórico (112 partidos) | **136,9 s**; 185.616 puntos, igual a lo calculado en `retencion_y_granularidad.md` §5 |
| Almacenamiento después de la carga | **645 MB** de WAL en `~/docker/data/influxdb` (226 archivos). Ningún archivo Parquet todavía (V7, ver `cardinalidad_y_escalabilidad.md` §3) |
| Persistencia con los 10 M de puntos (`prueba_persistencia.sh`) | **11.400 puntos de PAR-A-1 antes y después** de `docker compose down` + `up -d`; el servidor volvió a *healthy* en **19 s** (9,0 s leyendo el WAL) |

### 4.5 Validación

| Verificación | Muestra | Completo |
|---|:-:|:-:|
| V1 puntos por tabla = manifiesto | ✅ | ✅ |
| V2 series = estimación (4 / 16 / 5 en la muestra; 224 / 896 / 5 en el completo) | ✅ | ✅ |
| V3 tipos (integer / float / tag) | ✅ | ✅ |
| V4 retención 45 d / infinita / 1 h | ✅ | ✅ |
| V5 la retención de 1 h no conserva el punto de hace 2 h | ✅ | ✅ |
| V6 dato tardío y dato repetido | ✅ | ✅ |
| V7 archivos Parquet y espacio | informativo (todavía en WAL) | informativo (todavía en WAL) |
| V8 pregunta de torneo: vivo = histórico | ✅ | ✅ |

### 4.6 Contraste con las hipótesis

| Hipótesis | ¿Se cumplió? | Lectura |
|---|---|---|
| 1 · La carga masiva supera por mucho la ingesta en vivo | **Sí** | 182.726 puntos/s contra ~20 puntos/s del escenario en vivo: unas 9.000 veces. El cuello de botella del módulo no es la ingesta |
| 2 · Lote y concurrencia cambian la tasa | **Sí** | De 40.495 a 98.001 puntos/s solo con pasar de 10.000 a 50.000 líneas por lote (§4.1). Cada POST espera ~1 s el WAL: hay que tener más líneas en vuelo |
| 3 · gzip no mejora en local | **No verificada** | No se corrió con `--gzip` |
| 4 · La 1ª ejecución es más lenta | **Parcial** | Sí en P1 (9,6 contra 8,2 ms) y P5 (18,5 contra 14,6 ms). En P2, P3, P4 y P6 la diferencia queda dentro de la variación: los datos estaban en el buffer en memoria, sin archivos que leer de disco |
| 5 · Las que recorren el partido completo son las más lentas | **Sí, con matices** | P2 y P3 (partido completo) son las más lentas (~20 ms) y P1 (2 minutos) la más rápida. P4 también recorre el partido pero tarda 16 ms: agrupa en 8 tramos en lugar de 58 filas. Lo que decide el costo es el **rango temporal** que se lee |
| 6 · Idempotencia | **Sí** | La muestra se cargó 6 veces (barrido) y después la carga completa la reescribió: V1 dio exacto, sin duplicados. El resumen del completo se corrió dos veces con un reinicio en el medio y dio los mismos 185.616 puntos y la misma V8 |

---

## 5. Hallazgos de la migración a InfluxDB 3 Core

La primera versión del módulo usaba InfluxDB 2.9.1 (`influxdb:latest`), con buckets, organizaciones, Flux y tasks. Por la corrección del profesor y la Clase 9, se migró a `influxdb:3-core`. Estas son las diferencias que aparecieron **en las pruebas reales** y cómo se resolvieron:

| Hallazgo | Qué pasó | Qué se hizo |
|---|---|---|
| `influxdb:latest` sigue siendo InfluxDB 2 | La imagen `latest` no trae el binario `influxdb3` | Se usa `influxdb:3-core` con `pull_policy: always`, como indica la Clase 9 (README §0) |
| La retención no da error | Un punto más viejo que la retención se responde con **HTTP 204** y se descarta. En la versión 2 era un 422 | V5 verifica que el punto no aparezca; V1 compara lo cargado con el manifiesto para que ninguna pérdida pase sin detectar |
| Escritura parcial por defecto | Con una línea inválida en el lote, InfluxDB 3 escribe las válidas y responde 400 | La carga envía `accept_partial=false`: el lote entero se rechaza y la carga se detiene |
| Cada POST tarda ~1 s | El servidor confirma recién cuando vuelca el WAL (cada 1 s) | Lote de 50.000 líneas y 8 hilos, elegidos con el barrido (§4.1) |
| `/health` y `/ping` piden token | El healthcheck de Docker no tiene token | `--disable-authz=health,ping` en el Compose: esos dos endpoints no exponen datos |
| Las columnas `NULL` no vienen en el JSON | La validación falló la primera vez al leer la retención de la base histórica (que no tiene) | Los scripts leen las columnas con `.get()` |
| Sin snapshot a Parquet en una ráfaga | 226 archivos de WAL < 600 que dispara el snapshot | Documentado (`cardinalidad_y_escalabilidad.md` §3). Los datos son durables en el WAL: el reinicio los recupera (19 s) |
| Los resúmenes ya no necesitan borrar antes de reescribir | En la versión 2, reescribir después de un reinicio dejó un punto duplicado | En InfluxDB 3 la deduplicación por clave de serie + `time` funcionó también después del reinicio: se quitó el borrado previo |
| Git Bash en Windows reescribe rutas | `docker exec … --data-dir=/var/lib/…` recibía una ruta de Windows | Al correr los `.sh` desde Git Bash: `export MSYS_NO_PATHCONV=1` (README §2). En macOS y Linux no hace falta |

## 6. Limitaciones y mejoras

| Limitación | Mejora |
|---|---|
| Cliente y servidor en la misma máquina | Cargar desde otra máquina; ahí sí tendría sentido gzip |
| gzip sin medir | `carga_lotes.py --gzip` sobre la muestra |
| La muestra es chica para comparar hilos con lotes de 50.000 | Repetir el barrido sobre un perfil intermedio (`--limite-partidos 20`) |
| Las consultas se midieron con los datos en memoria, antes del snapshot a Parquet | Repetir P1–P6 después de un snapshot (por ejemplo, tras escribir de forma continua más de 10 minutos) |
| Una sola corrida por medición | Repetir la carga completa 3 veces y reportar la mediana |
