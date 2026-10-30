# Integración con un Data Mart (RF12, RF13, RNF12)

## Pregunta analítica
**¿Cómo evoluciona la actividad de comentarios, minuto a minuto, alrededor de los goles de cada partido, y cuánto pesa la audiencia conectada en ese pico?**
Sirve para dimensionar la moderación (Hito 6) y la capacidad de la plataforma en los partidos que vienen.

## Fuentes, atributos y procedencia

| Fuente (hito) | Dato | Atributo en el Data Mart |
|---|---|---|
| Cassandra (6) · `comentarios_por_partido` | `partido_id`, `creado_en`, `estado_moderacion` | `comentarios` y `comentarios_moderados` por minuto |
| Neo4j (5) · `(:Evento {tipo: 'GOL'})-[:OCURRE_EN]->(:Partido)` | `partidoId`, `minuto`, `condicionEquipo` | `gol_en_el_minuto` (0/1), `equipo_que_marco` |
| InfluxDB (8) · `audiencia_partido_1m` (resumen ya existente) | `usuarios_max` por región y minuto | `usuarios_max` del minuto |
| Neo4j (5) · `:Partido` | `fase`, `fechaHora`, sede, equipos | dimensiones del partido |

**Grano:** una fila por **partido × minuto del partido** (≈ 112 × 145 ≈ 16.240 filas para el torneo).
**Clave de unión:** `partido_id` (el mismo en los tres módulos desde el Hito 5) + minuto calculado desde la fecha de inicio del partido. `fecha_hora` del partido sale de Neo4j.

## Transformaciones
1. Cassandra: contar comentarios por minuto (`floor((creado_en − inicio) / 60 s)`), separando los no publicados. Se lee **por partición** (ventana × bucket), nunca con `ALLOW FILTERING`.
2. Neo4j: eventos de tipo GOL por partido, convertidos a minuto del partido.
3. InfluxDB: `usuarios_max` del resumen de 1 minuto, sumado entre regiones.
4. Unión por `(partido_id, minuto)`; los minutos sin goles quedan con 0, y los minutos sin audiencia con nulo (no con 0).

## Procedencia (RNF12)
Cada fila del Data Mart lleva `fuente_comentarios`, `fuente_eventos`, `fuente_audiencia` (producto de origen), `extraido_en` (cuándo se leyó), `lote_carga` (identificador del lote que la escribió) y `version_transformacion` (versión de las reglas de la sección anterior). Con esas columnas se contesta de dónde vino un dato, cuándo, con qué transformación y en qué lote, y se puede reconstruir la vista si cambia una regla o se corrige una fuente.

## Actualización
| Aspecto | Decisión |
|---|---|
| Frecuencia | Batch **al terminar cada partido**, más un recálculo nocturno de los partidos del día |
| Retraso aceptable | Hasta 15 minutos después del final: la pregunta es de análisis, no de la pantalla en vivo |
| Datos tardíos | Un comentario que llega después del cierre se toma en el recálculo nocturno |
| Duplicados | La carga **reemplaza** la partición `(partido_id)` del Data Mart (borrar y escribir), así repetirla no duplica: el mismo patrón que la V8 del Hito 8 |
| Punto de control | Por partido: el último `lote_carga` publicado y su `extraido_en`; una carga interrumpida se reanuda desde el primer partido sin publicar |
| Fallas parciales | Si una fuente no responde, no se publica ese partido y queda marcado como pendiente (nunca filas a medias) |
| Validación | Suma de `comentarios` por partido = conteo del partido en Cassandra; cantidad de minutos con gol = goles del partido en Neo4j |

## Fuentes operacionales contra proyección analítica
Responder la pregunta en línea, para cada consulta, implicaría leer las ~56 particiones de comentarios de un partido (14 ventanas × 4 buckets), recorrer los eventos en Neo4j y consultar InfluxDB: **tres bases en serie por cada consulta**, compitiendo con el tráfico de la app justo en los partidos más pesados. Es el antipatrón que advierte la consigna. La proyección lo resuelve una vez por partido y deja una tabla chica y estable (≈ 145 filas por partido) para consultar todas las veces que haga falta.
