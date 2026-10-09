# Patrones de acceso — Hito 8 · Series temporales (InfluxDB 3 Core)

**Ingeniería de Datos II · Grupo 2** — Santiago Pazos, Valentina Frisoli, Joaquín Núñez

> Se escribió **antes** del modelo (RF2). Cada tabla, tag, field y política de [`modelo_multidimensional.md`](./modelo_multidimensional.md) se justifica con uno de estos patrones (RNF4).

---

## 1. Problema temporal

Durante cada partido llegan tres flujos de observaciones que cambian segundo a segundo y vienen de **fuentes distintas**:

| Flujo | Fuente | Frecuencia | Qué decisiones en tiempo real habilita |
|---|---|---|---|
| **Estadísticas del juego** (posesión, pases, tiros, goles, recuperaciones) | Proveedor de datos deportivos (feed) | 1 punto por equipo por segundo **de juego**. En el entretiempo el feed no envía nada | Pantalla del partido en la app, gráficos de la transmisión, alertas de gol |
| **Audiencia** (usuarios conectados, comentarios, sesiones nuevas) | La propia plataforma (Hitos 6 y 7) | 1 punto por región por segundo, desde 15' antes hasta 20' después del partido | Escalar los servicios antes de un pico, reforzar la moderación de comentarios tras un gol |
| **Operación** (latencia p95, solicitudes, errores por servicio) | Observabilidad de los servicios | 1 punto por servicio cada 10 s, continuo durante el torneo | Detectar degradación antes de incumplir los 100 ms del Hito 1 |

**Volumen objetivo** (RF12): 10.094.400 puntos para los 112 partidos del Hito 5 (96 de grupos + 16 de dieciseisavos):

| Tabla | Cálculo | Puntos |
|---|---|---:|
| `estadisticas_equipo` | 112 partidos × 2 equipos × 5.700 s de juego (47' + 48') | 1.276.800 |
| `audiencia_partido` | 112 partidos × 8 regiones × 8.700 s (−15' a +130') | 7.795.200 |
| `operacion_plataforma` | 5 servicios × 204.480 instantes (cada 10 s durante 568 h de torneo) | 1.022.400 |
| **Total** | | **10.094.400** |

**Vínculo con los hitos anteriores.** El Hito 1 fijó "decenas de millones de estadísticas en vivo" y 2–3 millones de usuarios simultáneos. El Hito 2 asignó N7 al modelo de series temporales (4,75, el mayor puntaje de la matriz) porque *el momento en que se genera el dato es su dimensión principal y se consulta por período*. El Hito 3 lo definió como **AP, eventual, con orden monótono por partido**, particionado por **partido + intervalo**. Todo eso se respeta abajo.

---

## 2. Patrones de acceso

| # | Pregunta | Quién | Rango temporal | Dimensiones para localizar / segmentar | Medidas y agregación | Frecuencia | Precisión | Ausencia, retraso o dato tardío |
|---|---|---|---|---|---|---|---|---|
| **P1** | ¿Qué pasó en los últimos 2 minutos? | App (pantalla del partido) | Ventana deslizante de 2 min | `partido_id` | Puntos crudos: posesión, pases, tiros, goles | Muy alta: cada lector, cada pocos segundos | 1 s | Sin puntos en la ventana = partido detenido o entretiempo: se muestra "sin datos", no un valor viejo |
| **P2** | ¿Cómo va el partido ahora? | App, transmisión | Desde el inicio hasta ahora | `partido_id`, `equipo_id` | **Último valor** de cada contador (`last_value`) | Muy alta | 1 s | Si el feed se atrasa, se informa el `time` del último punto para que el cliente sepa cuán fresco es |
| **P3** | ¿Cuánta audiencia hay por región? | Organización, área comercial | Partido completo, tramos de 5 min | `partido_id`, `region` | Pico (`max`) y promedio (`avg`) de conectados; comentarios (`sum`) | Media | 1 s capturado, 5 min consultado | Región sin puntos en un tramo = sin datos (no se inventa un 0) |
| **P4** | ¿Quién domina cada cuarto de hora? | Analistas, transmisión | Partido, tramos de 15 min | `partido_id`, `condicion` (local/visitante) | Posesión al cierre del tramo (`last_value`), pases del tramo (`max − min`), recuperaciones (`sum`) | Media | 1 s | El entretiempo aparece como tramo con pocos puntos |
| **P5** | ¿Cómo reacciona la audiencia a un gol? | Producto, moderación (Hito 6) | 15 min alrededor de un gol | `partido_id` en **dos tablas** | Goles del feed (`max` por equipo) contra comentarios por minuto (`sum`) | Baja (análisis) | 1 min | Si el feed llega tarde, el gol aparece después del pico de comentarios: el cruce lo deja visible |
| **P6** | ¿Se cortó el feed o es el entretiempo? | Operación del feed | Minutos 44' a 65' | `partido_id` | Puntos por minuto de cada fuente (`count`) | Baja | 1 min | Es justamente el patrón que **detecta la ausencia**: audiencia con puntos y feed en 0 |
| **P7** | ¿Qué partidos tuvieron más audiencia en el torneo? ¿Qué equipos tuvieron más la pelota? | Organización, prensa | Todo el torneo | `partido_id`, `equipo_id`, `fase` | Pico simultáneo, comentarios totales, posesión final por partido | Baja | 1 punto por partido | Se responde en la base **histórica** (resúmenes); si un partido todavía no se resumió, no figura |
| **P8** | ¿Algún servicio se está degradando? | Operación de la plataforma | Última hora, tramos de 5–15 min | `servicio` | Latencia p95 (**`max`**, nunca `avg`), solicitudes y errores (`sum`) | Alta durante partidos | 10 s | Un servicio que deja de reportar se ve como hueco, que es en sí mismo una alerta |

### Respuesta ante dato tardío o repetido (todos los patrones)

- **Tardío**: InfluxDB acepta puntos fuera de orden; las consultas ordenan por `time`, no por llegada. Verificado en `validacion.py` (V6).
- **Repetido** (reintento de una carga): misma `tabla + tags + timestamp` = mismo punto; la segunda escritura **sobrescribe** los campos, no duplica. Es lo que hace la carga idempotente (V6).

---

## 3. De los patrones al modelo

- P1, P2, P4 y P6 siempre traen **`partido_id` y un rango de tiempo** → `partido_id` es tag (primera columna de la clave de serie) y todas las consultas acotan el tiempo al partido con `WHERE time >= … AND time < …`: InfluxDB 3 descarta sin leerlos los datos de otros tramos de tiempo.
- P3 y P8 segmentan por **una dimensión de pocos valores** (`region`: 8, `servicio`: 5) → tags.
- P4 compara **local contra visitante** → `condicion` como tag, además de `equipo_id`.
- P5 cruza **dos fuentes con frecuencias distintas** → tablas separadas, unidas por minuto en la consulta (`JOIN` sobre `date_bin()`).
- P7 recorre **todo el torneo** → no se responde sobre el dato por segundo (25 días y 7,8 M de puntos solo de audiencia), sino sobre **resúmenes por partido** en otra base: 112 puntos, mismo resultado y unas 100 veces más rápido (V8).
- Ningún patrón busca por jugador, por usuario ni por comentario → **no son dimensiones** del módulo (ver [`cardinalidad_y_escalabilidad.md`](./cardinalidad_y_escalabilidad.md) §2).
