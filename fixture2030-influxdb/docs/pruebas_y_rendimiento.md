# Pruebas y rendimiento — Hito 8 · InfluxDB 2

**Ingeniería de Datos II · Grupo 2** — Santiago Pazos, Valentina Frisoli, Joaquín Núñez

> **Regla del enunciado:** no se declara ninguna tasa, latencia ni volumen sin método, ambiente y resultado observado. Todas las cifras de este documento salen de los archivos de `docs/evidencia/` de la corrida del 28/09/2026.

---

## 1. Método

### 1.1 Carga (RF12, RF13)

| Aspecto | Decisión | Por qué |
|---|---|---|
| Herramienta | `carga_lotes.py`, Python con biblioteca estándar, en el contenedor `herramientas` | Reproducible sin instalar nada (RNF3) |
| Qué se cronometra | La carga completa (lectura de `.lp.gz` + envío + confirmación del servidor) y la latencia de cada POST | Es el tiempo real de ingestar el volumen |
| Unidad | **Puntos por segundo** = líneas de line protocol confirmadas (HTTP 204) por segundo | Un punto es una línea con todos sus fields |
| Confirmación | El 204 llega cuando el punto está en el WAL (en disco) y en el caché del motor | No se mide una escritura que se podría perder; la compactación a TSM ocurre después |
| Parámetros | Lote 10.000 líneas, 4 hilos, sin gzip | Ver `cardinalidad_y_escalabilidad.md` §4 |
| Validación | `validacion.py` compara lo cargado con el manifiesto, partido por partido | Una tasa alta no sirve si faltan puntos |

### 1.2 Consultas

| Aspecto | Decisión |
|---|---|
| Herramienta | `consultas_temporales.py`, Flux por `POST /api/v2/query` |
| Repeticiones | 10 por consulta. La **1ª** se informa aparte (caché fría); p50 y p95 sobre las 9 restantes |
| Alcance | P1–P6 sobre `PAR-D16-01`, con el perfil completo cargado |
| Qué incluye el tiempo | Viaje HTTP + planificación + lectura + serialización CSV: lo que ve un cliente |

---

## 2. Ambiente

| Dato | Valor |
|---|---|
| Fecha de la prueba | 28/09/2026 (inicialización 19:03 UTC, carga completa 19:14 UTC) |
| Versión de `influxdb:latest` | **InfluxDB v2.9.1** (git d4fa1941fd, build 2026-05-11). CLI `influx` dev (8cdf401). Imagen `sha256:05d6fb73…` |
| Equipo | Notebook con macOS y Docker Desktop (Linux aarch64 virtualizado) |
| Recursos de Docker (compartidos por servidor y cliente) | **8 CPUs, 3,8 GB de RAM** |
| Nodos / réplicas | 1 / ninguna (InfluxDB 2 OSS) |
| Cliente | Contenedor `python:3.12-slim` (Python 3.12.14) en la misma notebook |

**Condiciones para interpretar los números:** cliente y servidor comparten CPU y memoria; un solo nodo sin réplicas (cada punto se escribe una vez); Docker Desktop en macOS agrega una capa de virtualización; el servidor compacta a TSM en segundo plano mientras se carga.

---

## 3. Hipótesis (escritas antes de medir)

1. **En vivo, la ingesta es chica; lo exigente es la carga masiva.** En el calendario del Hito 5 nunca hay más de **2 partidos simultáneos**, así que en tiempo real llegan unos **20 puntos por segundo**. Los 10 M de puntos son el acumulado del torneo: el desafío aparece al cargarlo de una vez. Se espera que un nodo en una notebook cargue decenas de miles de puntos por segundo.
2. **Más hilos ayudan hasta un techo.**
3. **gzip no mejora en la misma notebook.**
4. **La 1ª ejecución de cada consulta es más lenta** que las siguientes.
5. **P3 y P5 son las más lentas**: recorren la audiencia de un partido completo y P5 además cruza dos measurements.
6. **Recargar no cambia los conteos** (idempotencia).

---

## 4. Resultados

### 4.1 Carga

| Corrida | Puntos esperados | Puntos confirmados | Tiempo | **Puntos/s** | Latencia POST p50 / p95 / máx | Lotes / reintentos | Error |
|---|---:|---:|---:|---:|---|---|---|
| Muestra | 176.400 | 176.400 | 0,27 s | **647.828** | 0,046 / 0,077 / 0,095 s | 20 / 0 | ninguno |
| **Completo** | **10.094.400** | **10.094.400** | **12,94 s** | **780.255** | 0,045 / 0,069 / 0,172 s | 1.127 / 0 | ninguno |

Por measurement (completo): `estadisticas_equipo` 1.276.800 puntos en 3,7 s · `audiencia_partido` 7.795.200 en 7,9 s · `operacion_plataforma` 1.022.400 en 1,2 s. Datos enviados: 1.429,7 MB de line protocol.

**Objetivo de 10 M+:** cumplido con el volumen completo, no por proyección.

### 4.2 Consultas (perfil completo cargado)

| Consulta | Filas | 1ª ejecución (ms) | p50 (ms) | p95 (ms) |
|---|---:|---:|---:|---:|
| P1 ventana de 2 min | 10 | 12,1 | 5,6 | 9,4 |
| P2 último valor | 2 | 5,1 | 4,4 | 4,6 |
| P3 audiencia por región | 58 | 194,8 | 190,0 | 212,5 |
| P4 local contra visitante | 8 | 230,9 | 228,4 | 241,9 |
| P5 dos fuentes | 16 | 12,4 | 11,0 | 16,0 |
| P6 ausencia de puntos | 21 | 11,9 | 12,7 | 18,3 |

### 4.3 Otras mediciones

| Medición | Resultado |
|---|---|
| Espacio en disco (V7, `/metrics`) | Bucket vivo **35,0 MB en 25 shards** (1,43 GB de line protocol: compresión ~40×) · histórico 6,5 MB en 5 shards |
| Resumen histórico (backfill de 112 partidos) | **378,1 s**; 21.280 + 129.920 + 34.080 puntos por minuto/5 min, igual a lo calculado en `retencion_y_granularidad.md` |
| Persistencia (`prueba_persistencia.sh`) | **11.400 puntos antes y 11.400 después** de `docker compose down` + `up -d` |

### 4.4 Validación

| Verificación | Muestra | Completo |
|---|:-:|:-:|
| V1 puntos por measurement = manifiesto | ✅ | ✅ |
| V2 series = estimación (4 / 16 / 5 en la muestra; 224 / 896 / 5 en el completo) | ✅ | ✅ |
| V3 tipos (long / double / string) | ✅ | ✅ |
| V4 retención 45 d / infinita / 1 h | ✅ | ✅ |
| V5 la retención de 1 h rechaza el punto de hace 2 h (HTTP 422) | ✅ | ✅ |
| V6 dato tardío y dato repetido | ✅ | ✅ |
| V7 shards y disco | informativo | informativo |
| V8 pregunta de torneo: vivo = histórico | ✅ | ✅ |

### 4.5 Contraste con las hipótesis

| Hipótesis | ¿Se cumplió? | Lectura |
|---|---|---|
| 1 · La carga masiva supera por mucho la ingesta en vivo | **Sí** | 780.255 puntos/s contra ~20 puntos/s del escenario en vivo: unas 38.000 veces. El cuello de botella del módulo no es la ingesta |
| 2 · Más hilos ayudan hasta un techo | **No verificada** | No se corrió el barrido de hilos (queda como mejora) |
| 3 · gzip no mejora en local | **No verificada** | Ídem |
| 4 · La 1ª ejecución es más lenta | **Parcial** | Sí en P1 (12,1 contra 5,6 ms), P2, P3, P4 y P5. No en P6 (11,9 contra 12,7 ms): con consultas tan cortas, la diferencia queda dentro de la variación |
| 5 · P3 y P5 las más lentas | **Parcial** | P3 sí (190 ms). **P5 no** (11 ms): lee solo 15 minutos. La otra lenta fue **P4** (228 ms), porque recorre el partido completo con tres agregaciones. Lo que decide el costo es el **rango temporal** que se lee, no la cantidad de measurements |
| 6 · Idempotencia | **Sí** | La carga completa reescribió los 2 partidos de la muestra y V1 dio exacto (sin duplicados). Los resúmenes, después de la corrección del reemplazo explícito, también (V8) |

---

## 5. Hallazgos de la prueba real

| Hallazgo | Qué pasó | Qué se cambió |
|---|---|---|
| `influxdb:latest` no era InfluxDB 3 | El primer diseño apuntaba a InfluxDB 3; la imagen real es v2.9.1 (el contenedor no encontraba `influxdb3`) | Se reescribió el módulo para InfluxDB 2: `influx setup`, buckets, Flux, tasks |
| Cardinalidad en InfluxDB 2 | V2 esperaba "series × fields"; `influxdb.cardinality()` cuenta measurement + tags | Se corrigió la expectativa (los datos estaban bien) |
| Resumen duplicado | Una segunda corrida de los resúmenes, después de reiniciar el servidor, dejó un punto duplicado; lo detectó la V8 | Reemplazo explícito: borrar el tramo con `/api/v2/delete` y reescribir |
| Retención al escribir | InfluxDB 2 rechaza con HTTP 422 los puntos que ya nacen fuera de la retención | Documentado en V5 y en `retencion_y_granularidad.md` |

## 6. Limitaciones y mejoras

| Limitación | Mejora |
|---|---|
| Cliente y servidor en la misma máquina | Cargar desde otra máquina; ahí sí tendría sentido gzip |
| Barrido de hilos y gzip sin correr | `carga_lotes.py --hilos 1 / 8` y `--gzip` sobre la muestra |
| Un solo proceso cliente | Varios procesos cargadores, uno por measurement |
| Una sola corrida por medición | Repetir la carga completa 3 veces y reportar la mediana |
| Tiempos de consulta incluyen serializar CSV | Para comparar solo el motor, medir con `influx query --raw` dentro del contenedor |
