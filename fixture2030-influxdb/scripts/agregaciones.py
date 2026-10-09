"""
Fixture 2030 — Hito 8 · Series temporales (InfluxDB 3 Core)
ARCHIVO: scripts/agregaciones.py
PROPÓSITO: (1) agregaciones justificadas por la semántica de cada medida (RF9);
           (2) MATERIALIZAR los resúmenes de la política de granularidad (RF10):
               fixture2030_vivo (1 s, 45 días) -> fixture2030_historico (1 min, 5 min
               y por partido, sin vencimiento).

USO:
    docker compose run --rm herramientas scripts/agregaciones.py --perfil muestra
    docker compose run --rm herramientas scripts/agregaciones.py --perfil completo

CÓMO SE MATERIALIZA EL RESUMEN EN INFLUXDB 3
  El SQL de InfluxDB 3 es de solo lectura (no hay INSERT … SELECT). El resumen se hace
  en dos pasos: (a) una consulta SQL con date_bin() + GROUP BY calcula cada ventana con
  la función que corresponde a la semántica de la medida; (b) el resultado se vuelve a
  escribir como line protocol en la base histórica (POST /api/v3/write_lp).
  En el laboratorio se ejecuta una vez después de la carga, acotado a cada partido
  (los datos están fechados en 2030). En operación real, el mismo paso correría al
  cierre de cada partido; en InfluxDB 3 Core eso se programa con un disparador del
  Processing Engine, que queda fuera del alcance del hito.

IDEMPOTENCIA: cada resumen tiene la misma serie (tabla + tags) y el mismo timestamp en
cada corrida. InfluxDB 3 deduplica por serie + timestamp: la segunda escritura
reemplaza a la primera. Correr este script 1 o 10 veces deja lo mismo (V8 lo verifica,
también después de reiniciar el servidor).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import (AUDIENCIA_DESDE, AUDIENCIA_HASTA, DB_HISTORICO, UTC,  # noqa: E402
                   calendario, consultar, cronometro, encabezado, escribir_lp,
                   guardar_evidencia, tabla_md, ts, ts_epoch)


def filtro_partido(p) -> str:
    return (f"partido_id = '{p.partido_id}' AND time >= {ts(p.inicio + timedelta(seconds=AUDIENCIA_DESDE))} "
            f"AND time < {ts(p.inicio + timedelta(seconds=AUDIENCIA_HASTA))}")


# ---------------------------------------------------------------------------
# 1) Agregaciones de análisis (no escriben nada)
# ---------------------------------------------------------------------------
def analisis(p) -> list[tuple[str, str, str]]:
    f = filtro_partido(p)
    return [
        ("A1 · Posesión: último valor contra promedio (medida: porcentaje ACUMULADO)",
         "posesion_pct ya es el acumulado desde el inicio. El valor correcto al cierre es "
         "last_value(); avg() mezcla los valores volátiles de los primeros minutos y da otro número.",
         f"""SELECT equipo_id,
       last_value(posesion_pct ORDER BY time) AS posesion_final_correcta,
       round(avg(posesion_pct), 1)            AS promedio_de_acumulados_incorrecto
FROM estadisticas_equipo
WHERE {f}
GROUP BY equipo_id
ORDER BY equipo_id"""),

        ("A2 · Pases: contador acumulado -> total y ritmo",
         "Un contador acumulado se resume con max() (total) o max − min (lo ocurrido en el tramo). "
         "sum() contaría miles de veces los mismos pases.",
         f"""SELECT equipo_id,
       max(pases_acum)                          AS pases_totales_correcto,
       sum(pases_acum)                          AS suma_del_acumulado_incorrecta,
       round((max(pases_acum) - min(pases_acum)) / 95.0, 2) AS pases_por_minuto_jugado
FROM estadisticas_equipo
WHERE {f}
GROUP BY equipo_id
ORDER BY equipo_id"""),

        ("A3 · Recuperaciones: evento por segundo -> suma por tramo",
         "recuperaciones vale 1 en el segundo en que ocurre y 0 en el resto: acá SÍ corresponde sumar.",
         f"""SELECT date_bin(INTERVAL '15 minutes', time) AS tramo, equipo_id,
       sum(recuperaciones) AS recuperaciones
FROM estadisticas_equipo
WHERE {f}
GROUP BY tramo, equipo_id
ORDER BY tramo, equipo_id"""),

        ("A4 · Pico de audiencia: sumar regiones por segundo y DESPUÉS tomar el máximo",
         "El pico real es el máximo del total simultáneo. Sumar los máximos de cada región da un número "
         "más alto que nunca existió, porque cada región tiene su pico en un segundo distinto.",
         f"""WITH por_segundo AS (
  SELECT time, sum(usuarios_conectados) AS total FROM audiencia_partido WHERE {f} GROUP BY time
), por_region AS (
  SELECT region, max(usuarios_conectados) AS pico FROM audiencia_partido WHERE {f} GROUP BY region
), correcto AS (SELECT max(total) AS pico_simultaneo_correcto FROM por_segundo),
   incorrecto AS (SELECT sum(pico) AS suma_de_picos_incorrecta FROM por_region)
SELECT '{p.partido_id}' AS partido, pico_simultaneo_correcto, suma_de_picos_incorrecta
FROM correcto CROSS JOIN incorrecto"""),

        ("A5 · Latencia p95: no se promedian percentiles",
         "latencia_p95_ms ya es un percentil calculado por el servicio. Para el tramo se informa el "
         "peor valor (max); el promedio escondería los minutos malos. solicitudes es un evento: se suma.",
         f"""SELECT date_bin(INTERVAL '15 minutes', time) AS tramo, servicio,
       max(latencia_p95_ms)     AS p95_peor,
       round(avg(latencia_p95_ms), 2)     AS p95_promedio_enganoso,
       round(sum(solicitudes) / 900.0) AS solicitudes_por_segundo
FROM operacion_plataforma
WHERE servicio IN ('api', 'sesiones')
  AND time >= {ts(p.inicio + timedelta(seconds=AUDIENCIA_DESDE))}
  AND time < {ts(p.inicio + timedelta(seconds=AUDIENCIA_HASTA))}
GROUP BY tramo, servicio
ORDER BY tramo, servicio"""),
    ]


# ---------------------------------------------------------------------------
# 2) Resúmenes: consulta SQL en el vivo -> line protocol en el histórico
# ---------------------------------------------------------------------------
def epoch(iso: str) -> int:
    return int(datetime.fromisoformat(iso).replace(tzinfo=UTC).timestamp())


def linea(tabla: str, tags: dict, enteros: dict, reales: dict, t: int) -> str:
    """Una línea de line protocol con tipos explícitos: entero con 'i', real con punto."""
    etiquetas = ",".join(f"{k}={v}" for k, v in tags.items())
    campos = [f"{k}={int(v)}i" for k, v in enteros.items() if v is not None]
    campos += [f"{k}={float(v)!r}" for k, v in reales.items() if v is not None]
    return f"{tabla},{etiquetas} {','.join(campos)} {t}\n"


def escribir(lineas: list[str]) -> int:
    for i in range(0, len(lineas), 10_000):
        estado, cuerpo = escribir_lp(DB_HISTORICO, "".join(lineas[i:i + 10_000]).encode("utf-8"))
        if estado not in (200, 204):
            raise RuntimeError(f"Escritura en {DB_HISTORICO}: HTTP {estado} {cuerpo[:300]!r}")
    return len(lineas)


def materializar_partido(p) -> int:
    f = filtro_partido(p)
    t0 = p.inicio_epoch
    lineas = []
    # Por minuto y equipo. Cada field con la función de su semántica (retencion_y_granularidad.md §3)
    for r in consultar(f"""SELECT date_bin(INTERVAL '1 minute', time) AS minuto, equipo_id, condicion, fase,
       last_value(posesion_pct ORDER BY time) AS posesion_pct,
       max(pases_acum) AS pases_acum, max(tiros_acum) AS tiros_acum, max(goles_acum) AS goles_acum,
       sum(recuperaciones) AS recuperaciones, count(posesion_pct) AS puntos
FROM estadisticas_equipo WHERE {f}
GROUP BY minuto, equipo_id, condicion, fase"""):
        lineas.append(linea("estadisticas_equipo_1m",
                            {"partido_id": p.partido_id, "equipo_id": r["equipo_id"],
                             "condicion": r["condicion"], "fase": r["fase"]},
                            {k: r[k] for k in ("pases_acum", "tiros_acum", "goles_acum", "recuperaciones", "puntos")},
                            {"posesion_pct": r["posesion_pct"]}, epoch(r["minuto"])))
    # Por minuto y región
    for r in consultar(f"""SELECT date_bin(INTERVAL '1 minute', time) AS minuto, region, fase,
       max(usuarios_conectados) AS usuarios_max, avg(usuarios_conectados) AS usuarios_prom,
       sum(comentarios) AS comentarios, sum(sesiones_nuevas) AS sesiones_nuevas
FROM audiencia_partido WHERE {f}
GROUP BY minuto, region, fase"""):
        lineas.append(linea("audiencia_partido_1m",
                            {"partido_id": p.partido_id, "region": r["region"], "fase": r["fase"]},
                            {k: r[k] for k in ("usuarios_max", "comentarios", "sesiones_nuevas")},
                            {"usuarios_prom": r["usuarios_prom"]}, epoch(r["minuto"])))
    # Un punto por partido y equipo, fechado al inicio del partido
    for r in consultar(f"""SELECT equipo_id, condicion,
       last_value(posesion_pct ORDER BY time) AS posesion_final,
       max(pases_acum) AS pases, max(tiros_acum) AS tiros, max(goles_acum) AS goles,
       sum(recuperaciones) AS recuperaciones
FROM estadisticas_equipo WHERE {f}
GROUP BY equipo_id, condicion"""):
        lineas.append(linea("resumen_partido_equipo",
                            {"partido_id": p.partido_id, "equipo_id": r["equipo_id"], "condicion": r["condicion"],
                             "fase": p.fase, "sede_id": p.sede_id},
                            {k: r[k] for k in ("pases", "tiros", "goles", "recuperaciones")},
                            {"posesion_final": r["posesion_final"]}, t0))
    # Un punto de audiencia por partido: pico = suma entre regiones por segundo, después max
    for r in consultar(f"""WITH por_segundo AS (
  SELECT time, sum(usuarios_conectados) AS total, sum(comentarios) AS comentarios,
         sum(sesiones_nuevas) AS sesiones_nuevas
  FROM audiencia_partido WHERE {f} GROUP BY time
)
SELECT max(total) AS pico_usuarios, sum(comentarios) AS comentarios, sum(sesiones_nuevas) AS sesiones_nuevas
FROM por_segundo"""):
        lineas.append(linea("resumen_partido_audiencia",
                            {"partido_id": p.partido_id, "fase": p.fase, "sede_id": p.sede_id},
                            {k: r[k] for k in ("pico_usuarios", "comentarios", "sesiones_nuevas")}, {}, t0))
    return escribir(lineas)


def materializar_operacion(archivo: dict) -> int:
    """operacion_plataforma (10 s) -> operacion_plataforma_5m, un día por vez."""
    lineas = [linea("operacion_plataforma_5m", {"servicio": r["servicio"]},
                    {"solicitudes": r["solicitudes"], "errores": r["errores"]},
                    {"latencia_p95_max": r["latencia_p95_max"]}, epoch(r["tramo"]))
              for r in consultar(f"""SELECT date_bin(INTERVAL '5 minutes', time) AS tramo, servicio,
       max(latencia_p95_ms) AS latencia_p95_max, sum(solicitudes) AS solicitudes, sum(errores) AS errores
FROM operacion_plataforma
WHERE time >= {ts_epoch(archivo['t_min'])} AND time < {ts_epoch(archivo['t_max'] + 1)}
GROUP BY tramo, servicio""")]
    return escribir(lineas)


TABLAS_HISTORICO = ["estadisticas_equipo_1m", "audiencia_partido_1m", "operacion_plataforma_5m",
                    "resumen_partido_equipo", "resumen_partido_audiencia"]


def contar_historico(desde: int, hasta: int) -> list[dict]:
    """Puntos (filas) de cada tabla del histórico en el rango del perfil."""
    return [{"tabla": t, "puntos": consultar(
        f"SELECT count(*) AS n FROM {t} WHERE time >= {ts_epoch(desde)} AND time < {ts_epoch(hasta)}",
        DB_HISTORICO)[0]["n"]} for t in TABLAS_HISTORICO]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--perfil", default="muestra")
    ap.add_argument("--entrada", default="data/lp")
    ap.add_argument("--partido-analisis", default="PAR-D16-01")
    args = ap.parse_args()

    manifiesto = json.loads((Path(args.entrada) / args.perfil / "manifiesto.json").read_text(encoding="utf-8"))
    ids = {x["partido_id"] for x in manifiesto["partidos"]}
    partidos = [p for p in calendario() if p.partido_id in ids]
    foco = next((p for p in partidos if p.partido_id == args.partido_analisis), partidos[0])

    md = encabezado(f"Agregaciones y resúmenes — perfil {args.perfil}")
    md += ["## 1. Agregaciones según la semántica de cada medida", "",
           f"Partido analizado: {foco.partido_id} ({foco.local} vs {foco.visitante}).", ""]
    for titulo, explicacion, sql in analisis(foco):
        reloj = cronometro()
        try:
            filas, error = consultar(sql), None
        except RuntimeError as e:
            filas, error = [], str(e)
        ms = round(reloj() * 1000, 1)
        print(f"\n== {titulo} ({ms} ms)\n" + (tabla_md(filas, max_filas=12) if not error else f"ERROR: {error}"))
        md += [f"### {titulo}", "", explicacion, "", "```sql", sql, "```", "",
               f"Tiempo de respuesta observado: {ms} ms", "",
               tabla_md(filas) if not error else f"**Error:** {error}", ""]

    print("\n== Materialización de resúmenes en fixture2030_historico (SQL -> line protocol)")
    reloj = cronometro()
    escritas = 0
    for i, p in enumerate(partidos, start=1):
        escritas += materializar_partido(p)
        print(f"   [{i:>3}/{len(partidos)}] {p.partido_id:<11} resumido · {reloj():6.1f} s")
    for a in manifiesto["archivos"]:
        if a["tabla"] == "operacion_plataforma":
            escritas += materializar_operacion(a)
    seg = round(reloj(), 1)
    desde = min(x["t_min"] for x in manifiesto["archivos"]) - 3600
    hasta = max(x["t_max"] for x in manifiesto["archivos"]) + 3600
    conteo = contar_historico(desde, hasta)
    print(f"   {len(partidos)} partidos en {seg} s · {escritas:,} líneas escritas\n" + tabla_md(conteo))

    rango_torneo = "time >= '2030-06-01T00:00:00Z' AND time < '2030-08-01T00:00:00Z'"
    top_audiencia = consultar(f"""SELECT partido_id, fase, pico_usuarios, comentarios
FROM resumen_partido_audiencia
WHERE {rango_torneo}
ORDER BY pico_usuarios DESC
LIMIT 5""", DB_HISTORICO)
    top_posesion = consultar(f"""SELECT equipo_id, count(*) AS partidos, round(avg(posesion_final), 2) AS posesion_media
FROM resumen_partido_equipo
WHERE {rango_torneo}
GROUP BY equipo_id
ORDER BY posesion_media DESC
LIMIT 5""", DB_HISTORICO)

    md += ["## 2. Materialización de resúmenes (vivo -> histórico)", "",
           f"Partidos resumidos: {len(partidos)} · tiempo: {seg} s · líneas escritas: {escritas:,}. "
           "Cada resumen se calcula con SQL en `fixture2030_vivo` y se escribe como line protocol en "
           "`fixture2030_historico` (misma serie y timestamp en cada corrida: idempotente).", "",
           tabla_md(conteo), "",
           "## 3. Consultas de torneo sobre la base histórica", "",
           "### Top 5 partidos por pico de audiencia simultánea", "", tabla_md(top_audiencia), "",
           "### Top 5 equipos por posesión media (promedio de la posesión FINAL de cada partido)", "",
           "Acá sí corresponde promediar: cada partido aporta su posesión final y pesa lo mismo.", "",
           tabla_md(top_posesion), ""]
    print("\nTop audiencia:\n" + tabla_md(top_audiencia) + "\n\nTop posesión:\n" + tabla_md(top_posesion))
    ruta = guardar_evidencia(f"agregaciones_{args.perfil}", "\n".join(md) + "\n",
                             {"segundos": seg, "lineas_escritas": escritas, "conteo_historico": conteo})
    print(f"\nEvidencia: {ruta}")


if __name__ == "__main__":
    main()
