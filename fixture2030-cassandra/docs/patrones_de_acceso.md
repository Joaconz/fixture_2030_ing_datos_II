# Patrones de acceso — Hito 6 · Módulo de Comentarios (Cassandra)

**Ingeniería de Datos II · Grupo 2** — Santiago Pazos, Valentina Frisoli, Joaquín Núñez

> En Cassandra este documento va **antes** que el esquema (RF3). Las tablas de [`modelo_tabular.md`](./modelo_tabular.md) salen de acá: cada una existe porque hay una consulta de esta lista que la necesita (RNF4).

---

## 1. Problema de volumen

El Hito 1 fijó el escenario: **más de un millón de comentarios por partido de alta audiencia**, concentrados en los 90 minutos del partido, con 2–3 millones de usuarios simultáneos. El Hito 2 asignó comentarios (N6) al modelo columnar por escalabilidad, y el Hito 3 lo definió como **AP con consistencia eventual** (N=3, R=1, W=1): un comentario que tarda en aparecer no es un comentario incorrecto.

El flujo de un comentario no es uniforme en el tiempo. Tiene cuatro momentos:

| Momento | Qué pasa | Efecto sobre la carga |
|---|---|---|
| Previa (−15' a 0') | Poca actividad, expectativa | ~0,6 × la tasa base |
| Juego (0' a 85') | Tasa base, con **explosiones tras cada gol** (3–4 minutos a ~7× la base) | Picos cortos e imprevisibles |
| Entretiempo | Cae la actividad | ~0,5 × la base |
| Cierre (85' a 100') | Toda la audiencia comenta a la vez | ~3× la base sostenido, más el gol si lo hay |

La consecuencia de diseño es directa: **la carga de un partido no se reparte a lo largo de sus 140 minutos, se concentra en unos pocos**. En el dataset generado, la ventana de 10 minutos más cargada del partido de audiencia máxima concentra el **21,5 %** de sus comentarios, y el minuto pico recibe **15.679 comentarios** (≈ 260 por segundo, solo en ese partido).

### Supuestos de carga declarados (RNF5)

| Supuesto | Valor | Origen |
|---|---|---|
| Comentarios por partido de audiencia máxima (laboratorio) | 300.000 | Escala reducida del Hito 1 para que entre en una notebook |
| Comentarios por partido de audiencia máxima (producción) | ≥ 1.000.000 | Hito 1 |
| Comentarios por partido de audiencia alta / normal | 20.000 / ~4.700 | Supuesto del grupo |
| Fracción del partido en la ventana pico | 20 % (medido: 21,5 %) | Curva de actividad del generador |
| Tamaño medio de una fila | ~300 bytes | 89 bytes de texto en promedio + marcas de tiempo, enteros y overhead por celda |
| Relación lectura / escritura durante el partido | Muchas más lecturas que escrituras: cada comentario lo leen miles | Hito 1 (2–3 M lectores) |
| Duración de un partido para comentarios | 140 minutos (−15' a +125') | Supuesto del grupo |

---

## 2. Patrones de acceso prioritarios

Ordenados por frecuencia. Los parámetros de entrada son los que la aplicación **ya tiene** cuando hace la pregunta; ese es el criterio que define si una consulta puede ir directo a una partición.

| # | Pregunta | Parámetros de entrada | Orden | Límite | Frecuencia | Se resuelve en |
|---|---|---|---|---|---|---|
| **Q1** | Últimos comentarios de un partido en vivo | `partido_id`, instante actual | Más reciente primero | 50 | **Muy alta**: cada lector, cada pocos segundos | `comentarios_por_partido` |
| **W1** | Publicar un comentario | `partido_id`, `usuario_id`, texto | — | 1 | **Muy alta** en picos (≈ 260/s por partido) | `comentarios_por_partido` + `comentarios_por_usuario` |
| **Q2** | Comentarios de un tramo del partido (ej. tras un gol) | `partido_id`, desde, hasta | Más reciente primero | Acotado por el tramo | Alta | `comentarios_por_partido` |
| **Q3** | "Cargar anteriores" (paginación hacia atrás) | `partido_id`, instante del último comentario visto | Más reciente primero | 20 | Alta | `comentarios_por_partido` |
| **Q4** | Cola de moderación de un partido | `partido_id`, estado `PENDIENTE` | Más reciente primero | Por ventana | Media (moderadores) | `comentarios_por_partido` + índice SAI |
| **Q5** | Historial de comentarios de un usuario | `usuario_id`, mes | Más reciente primero | 20 | Media (perfil, moderación de un autor) | `comentarios_por_usuario` |
| **W2** | Moderar / editar / borrar un comentario | clave completa del comentario | — | 1 | Baja | ambas tablas |
| **Q6** | Métricas de interacción de un comentario | `comentario_id` | — | 1 | Alta, pero liviana | `interacciones_por_comentario` |
| **Q7** | Cantidad de comentarios por tramo (agrupado) | `partido_id`, ventanas | Por ventana | — | Baja (panel del organizador, evidencia) | `comentarios_por_partido` |
| **Q0** | Parámetros de partición del partido | `partido_id` | — | 1 | Una vez por partido (se cachea) | `config_particion_partido` |

### Qué preguntas quedan **fuera** del módulo, a propósito

| Pregunta | Por qué no se responde acá | Dónde correspondería |
|---|---|---|
| "Todos los comentarios pendientes del torneo, sin importar el partido" | Sin partición es un recorrido de todo el clúster | Tabla propia `moderacion_pendiente_por_dia` si el producto la pidiera (decisiones §7) |
| "Comentarios que contienen la palabra *penal*" | Búsqueda de texto libre sobre todo el volumen | Motor de búsqueda, fuera del alcance del TPO |
| "Tendencia de comentarios por minuto en todo el torneo" | Es analítica histórica, no operación en vivo | Series temporales (InfluxDB, N7) o proceso batch (decisiones §8) |
| "Hilo completo de respuestas a un comentario" | `responde_a` no es clave; con los volúmenes del lab alcanza con leer la ventana | Tabla `respuestas_por_comentario` si el hilo creciera |

---

## 3. De las preguntas a la clave

Las tres preguntas más frecuentes (Q1, Q2, Q3) tienen la misma forma: **"comentarios de *este* partido, alrededor de *este* instante, del más nuevo al más viejo"**. Eso fija la clave de la tabla principal:

- **`partido_id` en la partición** — todo lo que se lee junto tiene que vivir junto.
- **El tiempo en la partición también** (`ventana`) — si la partición fuera solo `partido_id`, el millón de comentarios de la final sería una única partición (ver decisiones §2).
- **`creado_en DESC` como primera columna de clustering** — Q1 es "las primeras 50 filas", Q2 es un rango y Q3 es "lo anterior a". Las tres son lecturas secuenciales dentro de la partición, sin ordenar nada.

Q5 tiene otra forma ("comentarios de *este usuario*"), y por eso no puede compartir tabla: necesita otra clave de partición. Esa es la razón de la duplicación controlada.
