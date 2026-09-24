# Datos — Hito 6 · Módulo de Comentarios

Los comentarios son **sintéticos** y **deterministas**: salen de [`scripts/generador.py`](../scripts/generador.py) con semilla fija por partido. Mismo criterio que los Hitos 4 y 5: se necesita volumen y no existe una fuente real de comentarios de 2030.

## Archivos

| Archivo | Contenido |
|---|---|
| `muestra_comentarios.csv` | Los 80 comentarios de `scripts/carga_muestra.cql`, para inspeccionarlos sin Cassandra |

La carga masiva **no** se guarda como archivo: se genera en memoria y se escribe directo en Cassandra (`scripts/carga_masiva.py`). Un CSV de 1.050.000 filas no aporta nada que el generador no garantice, y el determinismo asegura que dos corridas producen exactamente las mismas filas.

## Distribución de la carga masiva (1.050.000 comentarios)

| Dimensión | Distribución |
|---|---|
| Partidos | Los 112 del Hito 5: `PAR-{A..P}-{1..6}` (96 de grupos) y `PAR-D16-01..16` (dieciseisavos), con sus fechas exactas |
| Audiencia | 1 partido MÁXIMA (`PAR-D16-01`, 300.000 comentarios, 4 buckets) · 15 ALTA (20.000 c/u, 1 bucket) · 96 NORMAL (~4.690 c/u, 1 bucket) |
| Instantes | Desde 15' antes hasta 125' después del inicio. Curva: previa 0,6×, juego 1×, entretiempo 0,5×, cierre (85'–100') 3×, y explosión de ~7× durante 3–4 minutos después de cada gol (1 a 5 goles por partido) |
| Usuarios | 250.000 (`USR-0000001` …). Actividad sesgada: `u = 250.000 × r^1,5` — pocos usuarios muy activos, la mayoría con 1–2 comentarios |
| Estado de moderación | PUBLICADO 93 % · PENDIENTE 4 % · OCULTO 2 % · ELIMINADO 1 % |
| Idioma | es 55 % · pt 15 % · en 15 % · fr 8 % · ar 7 % |
| Hinchada | LOCAL 45 % · VISITANTE 40 % · NEUTRAL 15 % |
| Respuestas | 10 % de los comentarios responde a uno de los 200 anteriores del mismo partido |
| Identificador | `'{partido_id}-C{secuencia de 7 dígitos}'` — determinista, base de la idempotencia |

## Relación muestra ↔ carga masiva

La muestra es un **subconjunto exacto** de la carga masiva (1 de cada 200 comentarios de `PAR-A-1`, 1 de cada 8.000 de `PAR-D16-01`, más todos los de `USR-0000038`, que comenta en ambos partidos y sirve para la consulta de historial). Por eso se pueden cargar las dos en cualquier orden sin duplicar comentarios.
