"""
Fixture 2030 — Hito 8 · Series temporales (InfluxDB 2)
ARCHIVO: scripts/consultas_temporales.py
PROPÓSITO: consultas Flux que responden a los patrones de acceso P1..P6
           (docs/patrones_de_acceso.md). RF8, RNF8.

USO:
    docker compose run --rm herramientas scripts/consultas_temporales.py
    docker compose run --rm herramientas scripts/consultas_temporales.py --partido PAR-A-1

REGLA DE TODAS LAS CONSULTAS (RNF8): siempre acotan el TIEMPO con range() y el
PARTIDO con filter(). En InfluxDB 2 el bucket vivo se divide en shards de 1 día:
acotar a un partido lee 1 shard y solo las series de ese partido (índice TSI).

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
from comun import (AUDIENCIA_DESDE, AUDIENCIA_HASTA, DB_VIVO, calendario,  # noqa: E402
                   consultar, cronometro, encabezado, guardar_evidencia, rfc3339,
                   segundo_de_minuto, tabla_md)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--partido", default="PAR-D16-01")
    ap.add_argument("--minuto", type=int, default=90, help="minuto de juego que se toma como 'ahora'")
    ap.add_argument("--repeticiones", type=int, default=10,
                    help="veces que se ejecuta cada consulta para medir p50/p95 (la 1ª se informa aparte: caché fría)")
    args = ap.parse_args()

    p = next(x for x in calendario() if x.partido_id == args.partido)
    t = lambda seg: rfc3339(p.inicio + timedelta(seconds=seg))  # noqa: E731
    ahora = segundo_de_minuto(args.minuto)
    pid = p.partido_id
    g0 = p.goles[0][0] if p.goles else segundo_de_minuto(45)
    est = f'''from(bucket: "{DB_VIVO}")
  |> range(start: {{a}}, stop: {{b}})
  |> filter(fn: (r) => r._measurement == "estadisticas_equipo" and r.partido_id == "{pid}")'''
    aud = est.replace("estadisticas_equipo", "audiencia_partido")

    consultas = [
        ("P1 · Ventana reciente: últimos 2 minutos del feed de un partido en vivo",
         "Recupera PUNTOS CRUDOS de una ventana corta: range() de 2 minutos + filtro por partido. "
         "pivot() pone cada field como columna (una fila por equipo y segundo).",
         est.format(a=t(ahora - 120), b=t(ahora)) + '''
  |> filter(fn: (r) => r._field == "posesion_pct" or r._field == "pases_acum" or r._field == "tiros_acum"
                       or r._field == "goles_acum" or r._field == "minuto_juego")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> group()
  |> keep(columns: ["_time", "equipo_id", "posesion_pct", "pases_acum", "tiros_acum", "goles_acum", "minuto_juego"])
  |> sort(columns: ["_time", "equipo_id"], desc: true)
  |> limit(n: 10)'''),

        ("P2 · Estado actual del partido: último valor de cada contador por equipo",
         "last() devuelve el valor MÁS RECIENTE de cada serie. Es la agregación correcta para "
         "contadores acumulados y para la posesión acumulada: promediarlos no tiene significado.",
         est.format(a=t(0), b=t(ahora)) + '''
  |> filter(fn: (r) => r._field == "posesion_pct" or r._field == "pases_acum" or r._field == "tiros_acum"
                       or r._field == "goles_acum")
  |> last()
  |> pivot(rowKey: ["equipo_id", "condicion"], columnKey: ["_field"], valueColumn: "_value")
  |> group()
  |> keep(columns: ["equipo_id", "condicion", "posesion_pct", "pases_acum", "tiros_acum", "goles_acum"])
  |> sort(columns: ["condicion"], desc: true)'''),

        ("P3 · Filtro por dimensión: audiencia de dos regiones cada 5 minutos",
         "Filtra por el tag `region` (dimensión indexada) y agrupa con aggregateWindow. "
         "usuarios_conectados es un gauge: se informa el máximo (pico) y el promedio, nunca la suma. "
         "comentarios es un evento: se suma.",
         f'''datos = {aud.format(a=t(AUDIENCIA_DESDE), b=t(AUDIENCIA_HASTA))}
  |> filter(fn: (r) => r.region == "AR" or r.region == "ES")
pico = datos
  |> filter(fn: (r) => r._field == "usuarios_conectados")
  |> aggregateWindow(every: 5m, fn: max, timeSrc: "_start", createEmpty: false)
  |> toFloat()
  |> set(key: "_field", value: "pico_usuarios")
prom = datos
  |> filter(fn: (r) => r._field == "usuarios_conectados")
  |> aggregateWindow(every: 5m, fn: mean, timeSrc: "_start", createEmpty: false)
  |> set(key: "_field", value: "promedio_usuarios")
com = datos
  |> filter(fn: (r) => r._field == "comentarios")
  |> aggregateWindow(every: 5m, fn: sum, timeSrc: "_start", createEmpty: false)
  |> toFloat()
  |> set(key: "_field", value: "comentarios")
union(tables: [pico, prom, com])
  |> group(columns: ["region"])
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> group()
  |> keep(columns: ["_time", "region", "pico_usuarios", "promedio_usuarios", "comentarios"])
  |> sort(columns: ["_time", "region"])'''),

        ("P4 · Comparación entre dimensiones: local contra visitante por cuarto de hora",
         "Pases del tramo = spread() del contador acumulado (máximo − mínimo del tramo; no sum: "
         "el contador ya viene sumado). Posesión al cierre del tramo = last(). Recuperaciones = sum().",
         f'''datos = {est.format(a=t(AUDIENCIA_DESDE), b=t(AUDIENCIA_HASTA))}
pos = datos
  |> filter(fn: (r) => r._field == "posesion_pct" and r.condicion == "LOCAL")
  |> aggregateWindow(every: 15m, fn: last, timeSrc: "_start", createEmpty: false)
  |> map(fn: (r) => ({{r with _field: "posesion_local_cierre"}}))
pases = datos
  |> filter(fn: (r) => r._field == "pases_acum")
  |> aggregateWindow(every: 15m, fn: spread, timeSrc: "_start", createEmpty: false)
  |> toFloat()
  |> map(fn: (r) => ({{r with _field: "pases_" + r.condicion}}))
recup = datos
  |> filter(fn: (r) => r._field == "recuperaciones")
  |> aggregateWindow(every: 15m, fn: sum, timeSrc: "_start", createEmpty: false)
  |> toFloat()
  |> map(fn: (r) => ({{r with _field: "recup_" + r.condicion}}))
union(tables: [pos, pases, recup])
  |> keep(columns: ["_time", "_field", "_value"])
  |> group()
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"])'''),

        ("P5 · Comparación entre FUENTES: goles del feed deportivo contra comentarios de la audiencia",
         "Cruza dos measurements de fuentes distintas por minuto, 5 minutos antes y 10 después del "
         "primer gol: el contador de goles sube y los comentarios por minuto se disparan.",
         f'''feed = {est.format(a=t(g0 - 300), b=t(g0 + 600))}
  |> filter(fn: (r) => r._field == "goles_acum")
  |> aggregateWindow(every: 1m, fn: max, timeSrc: "_start", createEmpty: false)
  |> group(columns: ["_time"])
  |> sum()
  |> toFloat()
  |> map(fn: (r) => ({{_time: r._time, _field: "goles_acumulados", _value: r._value}}))
com = {aud.format(a=t(g0 - 300), b=t(g0 + 600))}
  |> filter(fn: (r) => r._field == "comentarios")
  |> aggregateWindow(every: 1m, fn: sum, timeSrc: "_start", createEmpty: false)
  |> group(columns: ["_time"])
  |> sum()
  |> toFloat()
  |> map(fn: (r) => ({{_time: r._time, _field: "comentarios_minuto", _value: r._value}}))
union(tables: [feed, com])
  |> group()
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"])'''),

        ("P6 · Ausencia de puntos: el entretiempo",
         "El feed deportivo NO envía puntos en el entretiempo; la audiencia sí. aggregateWindow con "
         "createEmpty: true devuelve 0 en los minutos sin puntos: el hueco se ve, no se interpola.",
         f'''feed = {est.format(a=t(44 * 60), b=t(65 * 60))}
  |> filter(fn: (r) => r._field == "posesion_pct")
  |> aggregateWindow(every: 1m, fn: count, timeSrc: "_start", createEmpty: true)
  |> group(columns: ["_time"])
  |> sum()
  |> map(fn: (r) => ({{_time: r._time, _field: "puntos_feed", _value: r._value}}))
aud = {aud.format(a=t(44 * 60), b=t(65 * 60))}
  |> filter(fn: (r) => r._field == "usuarios_conectados")
  |> aggregateWindow(every: 1m, fn: count, timeSrc: "_start", createEmpty: true)
  |> group(columns: ["_time"])
  |> sum()
  |> map(fn: (r) => ({{_time: r._time, _field: "puntos_audiencia", _value: r._value}}))
union(tables: [feed, aud])
  |> group()
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"])'''),
    ]

    md = encabezado(f"Consultas temporales — {p.partido_id} ({p.local} vs {p.visitante})") + [
        f"Inicio programado: {rfc3339(p.inicio)} · 'Ahora' simulado: minuto {args.minuto} ({t(ahora)}) · "
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
        md += [f"## {titulo}", "", explicacion, "", "```flux", sql, "```", "",
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


if __name__ == "__main__":
    main()
