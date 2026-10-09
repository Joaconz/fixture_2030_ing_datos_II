"""
Fixture 2030 — Hito 8 · Series temporales (InfluxDB 3 Core)
ARCHIVO: scripts/consultas_temporales.py
PROPÓSITO: consultas SQL que responden a los patrones de acceso P1..P6
           (docs/patrones_de_acceso.md). RF8, RNF8.

USO:
    docker compose run --rm herramientas scripts/consultas_temporales.py
    docker compose run --rm herramientas scripts/consultas_temporales.py --partido PAR-A-1

REGLA DE TODAS LAS CONSULTAS (RNF8): siempre acotan el TIEMPO (WHERE time >= … AND
time < …) y el PARTIDO (WHERE partido_id = …). InfluxDB 3 guarda los datos en archivos
Parquet por tramo de tiempo: acotar el tiempo descarta los archivos de otros partidos
sin abrirlos, y acotar el partido descarta las filas de otras series.

"AHORA" SIMULADO: el torneo está fechado en 2030 (mismas fechas que el Hito 5).
Para las consultas "en vivo" se toma como instante actual el minuto 90 de juego
del partido elegido (parámetro --minuto).
"""
from __future__ import annotations

import argparse
import statistics
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import (AUDIENCIA_DESDE, AUDIENCIA_HASTA, calendario,  # noqa: E402
                   consultar, cronometro, encabezado, guardar_evidencia, ts,
                   segundo_de_minuto, tabla_md)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--partido", default="PAR-D16-01")
    ap.add_argument("--minuto", type=int, default=90, help="minuto de juego que se toma como 'ahora'")
    ap.add_argument("--repeticiones", type=int, default=10,
                    help="veces que se ejecuta cada consulta para medir p50/p95 (la 1ª se informa aparte: caché fría)")
    args = ap.parse_args()

    p = next(x for x in calendario() if x.partido_id == args.partido)
    t = lambda seg: ts(p.inicio + timedelta(seconds=seg))  # noqa: E731
    ahora = segundo_de_minuto(args.minuto)
    pid = f"partido_id = '{p.partido_id}'"
    g0 = p.goles[0][0] if p.goles else segundo_de_minuto(45)
    partido = f"{pid} AND time >= {t(AUDIENCIA_DESDE)} AND time < {t(AUDIENCIA_HASTA)}"

    consultas = [
        ("P1 · Ventana reciente: últimos 2 minutos del feed de un partido en vivo",
         "Recupera PUNTOS CRUDOS de una ventana corta: rango de 2 minutos + filtro por partido. "
         "Cada fila ya trae todos los fields del punto (una fila por equipo y segundo).",
         f"""SELECT time, equipo_id, posesion_pct, pases_acum, tiros_acum, goles_acum, minuto_juego
FROM estadisticas_equipo
WHERE {pid} AND time >= {t(ahora - 120)} AND time < {t(ahora)}
ORDER BY time DESC, equipo_id
LIMIT 10"""),

        ("P2 · Estado actual del partido: último valor de cada contador por equipo",
         "last_value(… ORDER BY time) devuelve el valor MÁS RECIENTE de cada serie. Es la agregación "
         "correcta para contadores acumulados y para la posesión acumulada: promediarlos no tiene "
         "significado. max(time) informa cuán fresco es el dato (si el feed se atrasa, se ve).",
         f"""SELECT equipo_id, condicion,
       last_value(posesion_pct ORDER BY time) AS posesion_pct,
       last_value(pases_acum ORDER BY time)   AS pases_acum,
       last_value(tiros_acum ORDER BY time)   AS tiros_acum,
       last_value(goles_acum ORDER BY time)   AS goles_acum,
       max(time) AS ultimo_punto
FROM estadisticas_equipo
WHERE {pid} AND time >= {t(0)} AND time < {t(ahora)}
GROUP BY equipo_id, condicion
ORDER BY condicion DESC"""),

        ("P3 · Filtro por dimensión: audiencia de dos regiones cada 5 minutos",
         "Filtra por el tag `region` y agrupa con date_bin() en ventanas de 5 minutos. "
         "usuarios_conectados es un gauge: se informa el máximo (pico) y el promedio, nunca la suma. "
         "comentarios es un evento: se suma.",
         f"""SELECT date_bin(INTERVAL '5 minutes', time) AS tramo, region,
       max(usuarios_conectados)        AS pico_usuarios,
       round(avg(usuarios_conectados)) AS promedio_usuarios,
       sum(comentarios)                AS comentarios
FROM audiencia_partido
WHERE {partido} AND region IN ('AR', 'ES')
GROUP BY tramo, region
ORDER BY tramo, region"""),

        ("P4 · Comparación entre dimensiones: local contra visitante por cuarto de hora",
         "Pases del tramo = max − min del contador acumulado (no sum: el contador ya viene sumado). "
         "Posesión al cierre del tramo = last_value(). Recuperaciones = sum(). FILTER separa "
         "LOCAL y VISITANTE en columnas de la misma fila.",
         f"""SELECT date_bin(INTERVAL '15 minutes', time) AS tramo,
       last_value(posesion_pct ORDER BY time) FILTER (WHERE condicion = 'LOCAL') AS posesion_local_cierre,
       max(pases_acum) FILTER (WHERE condicion = 'LOCAL')
         - min(pases_acum) FILTER (WHERE condicion = 'LOCAL')     AS pases_local,
       max(pases_acum) FILTER (WHERE condicion = 'VISITANTE')
         - min(pases_acum) FILTER (WHERE condicion = 'VISITANTE') AS pases_visitante,
       sum(recuperaciones) FILTER (WHERE condicion = 'LOCAL')     AS recup_local,
       sum(recuperaciones) FILTER (WHERE condicion = 'VISITANTE') AS recup_visitante
FROM estadisticas_equipo
WHERE {partido}
GROUP BY tramo
ORDER BY tramo"""),

        ("P5 · Comparación entre FUENTES: goles del feed deportivo contra comentarios de la audiencia",
         "Cruza dos tablas de fuentes distintas por minuto, 5 minutos antes y 10 después del primer "
         "gol: el contador de goles sube y los comentarios por minuto se disparan. FULL JOIN porque "
         "antes del inicio la audiencia tiene puntos y el feed no.",
         f"""WITH por_equipo AS (
  SELECT date_bin(INTERVAL '1 minute', time) AS minuto, equipo_id, max(goles_acum) AS goles
  FROM estadisticas_equipo
  WHERE {pid} AND time >= {t(g0 - 300)} AND time < {t(g0 + 600)}
  GROUP BY minuto, equipo_id
), feed AS (
  SELECT minuto, sum(goles) AS goles_acumulados FROM por_equipo GROUP BY minuto
), com AS (
  SELECT date_bin(INTERVAL '1 minute', time) AS minuto, sum(comentarios) AS comentarios_minuto
  FROM audiencia_partido
  WHERE {pid} AND time >= {t(g0 - 300)} AND time < {t(g0 + 600)}
  GROUP BY minuto
)
SELECT coalesce(feed.minuto, com.minuto) AS minuto, feed.goles_acumulados, com.comentarios_minuto
FROM feed FULL OUTER JOIN com ON feed.minuto = com.minuto
ORDER BY minuto"""),

        ("P6 · Ausencia de puntos: el entretiempo",
         "El feed deportivo NO envía puntos en el entretiempo; la audiencia sí. date_bin_gapfill() "
         "genera TODOS los minutos del rango, también los que no tienen puntos (count = 0): "
         "el hueco se ve, no se interpola.",
         f"""WITH feed AS (
  SELECT date_bin_gapfill(INTERVAL '1 minute', time) AS minuto, count(posesion_pct) AS puntos_feed
  FROM estadisticas_equipo
  WHERE {pid} AND time >= {t(44 * 60)} AND time < {t(65 * 60)}
  GROUP BY minuto
), aud AS (
  SELECT date_bin_gapfill(INTERVAL '1 minute', time) AS minuto, count(usuarios_conectados) AS puntos_audiencia
  FROM audiencia_partido
  WHERE {pid} AND time >= {t(44 * 60)} AND time < {t(65 * 60)}
  GROUP BY minuto
)
SELECT feed.minuto, coalesce(feed.puntos_feed, 0) AS puntos_feed, coalesce(aud.puntos_audiencia, 0) AS puntos_audiencia
FROM feed JOIN aud ON feed.minuto = aud.minuto
ORDER BY feed.minuto"""),
    ]

    md = encabezado(f"Consultas temporales — {p.partido_id} ({p.local} vs {p.visitante})") + [
        f"Inicio programado: {t(0)} · 'Ahora' simulado: minuto {args.minuto} ({t(ahora)}) · "
        f"goles del calendario (segundo de reloj, equipo): {p.goles}", ""]
    datos = {"partido": p.partido_id, "consultas": []}
    resumen_tiempos = []
    for titulo, explicacion, sql in consultas:
        tiempos, filas, error = [], [], None
        for _ in range(max(1, args.repeticiones)):
            reloj = cronometro()
            try:
                filas = consultar(sql)
            except RuntimeError as e:
                filas, error = [], str(e)
                break
            tiempos.append(reloj() * 1000)
        fria = round(tiempos[0], 1) if tiempos else None
        calientes = sorted(tiempos[1:]) or sorted(tiempos)
        p50 = round(statistics.median(calientes), 1) if calientes else None
        p95 = round(calientes[max(0, -(-95 * len(calientes) // 100) - 1)], 1) if calientes else None  # rango más cercano
        codigo = titulo.split(" ")[0]
        resumen_tiempos.append(f"| {codigo} | {len(filas)} | {fria} | {p50} | {p95} |")
        print(f"\n== {titulo}  ({len(filas)} filas · 1ª {fria} ms · p50 {p50} ms · p95 {p95} ms)")
        print(tabla_md(filas, max_filas=15) if not error else f"ERROR: {error}")
        md += [f"## {titulo}", "", explicacion, "", "```sql", sql, "```", "",
               f"Filas: {len(filas)} · 1ª ejecución: {fria} ms · p50: {p50} ms · p95: {p95} ms "
               f"({args.repeticiones} ejecuciones)", "",
               tabla_md(filas) if not error else f"**Error:** {error}", ""]
        datos["consultas"].append({"titulo": titulo, "filas": len(filas), "ms_primera": fria,
                                   "ms_p50": p50, "ms_p95": p95, "repeticiones": args.repeticiones,
                                   "error": error})
    tabla_tiempos = ["## Tiempos de respuesta (ms)", "",
                     "| Consulta | Filas | 1ª ejecución | p50 | p95 |", "|---|---:|---:|---:|---:|",
                     *resumen_tiempos, ""]
    md = md + tabla_tiempos

    ruta = guardar_evidencia(f"consultas_{p.partido_id}", "\n".join(md) + "\n", datos)
    print(f"\nEvidencia: {ruta}")
    if any(c["error"] for c in datos["consultas"]):
        sys.exit(1)


if __name__ == "__main__":
    main()
