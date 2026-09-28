"""
Fixture 2030 — Hito 8 · Series temporales (InfluxDB 2)
ARCHIVO: scripts/agregaciones.py
PROPÓSITO: (1) agregaciones justificadas por la semántica de cada medida (RF9);
           (2) MATERIALIZAR los resúmenes de la política de granularidad (RF10):
               fixture2030_vivo (1 s, 45 días) -> fixture2030_historico (1 min, 5 min
               y por partido, sin vencimiento);
           (3) registrar la TASK nativa de InfluxDB 2 que hace ese resumen en producción.

USO:
    docker compose run --rm herramientas scripts/agregaciones.py --perfil muestra
    docker compose run --rm herramientas scripts/agregaciones.py --perfil completo

DOS DISPARADORES, UNA MISMA LÓGICA
  · En producción: la task `fixture2030_resumen_1m` corre cada hora sobre la última
    hora (range(start: -task.every)) y escribe con to() en el bucket histórico.
  · En el laboratorio: el torneo está fechado en 2030, así que una task basada en
    "la última hora real" no encuentra datos. Este script ejecuta los MISMOS pasos
    Flux, acotados a cada partido, y escribe con to(). Es la carga histórica
    (backfill) de los resúmenes.

IDEMPOTENCIA POR REEMPLAZO EXPLÍCITO: antes de escribir los resúmenes de un partido
(o de un día de operación) se BORRA ese tramo en el bucket histórico con la API
/api/v2/delete, y recién después se escribe con to(). Así el resultado no depende
de que InfluxDB unifique dos escrituras del mismo punto: en la prueba real, una
segunda corrida después de reiniciar el servidor dejó un resumen duplicado
(detectado por validacion.py V8). Correr este script 1 o 10 veces deja lo mismo.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import (AUDIENCIA_DESDE, AUDIENCIA_HASTA, DB_HISTORICO, DB_VIVO, UTC,  # noqa: E402
                   _peticion, calendario, consultar, cronometro, encabezado,
                   guardar_evidencia, org, rfc3339, tabla_md)

NOMBRE_TASK = "fixture2030_resumen_1m"


def rango(p) -> tuple[str, str]:
    return (rfc3339(p.inicio + timedelta(seconds=AUDIENCIA_DESDE)),
            rfc3339(p.inicio + timedelta(seconds=AUDIENCIA_HASTA)))


def base(meas: str, a: str, b: str, extra: str = "") -> str:
    return (f'from(bucket: "{DB_VIVO}")\n  |> range(start: {a}, stop: {b})\n'
            f'  |> filter(fn: (r) => r._measurement == "{meas}"{extra})')


# ---------------------------------------------------------------------------
# 1) Agregaciones de análisis (no escriben nada)
# ---------------------------------------------------------------------------
def analisis(p) -> list[tuple[str, str, str]]:
    a, b = rango(p)
    pid = f' and r.partido_id == "{p.partido_id}"'
    est, aud = base("estadisticas_equipo", a, b, pid), base("audiencia_partido", a, b, pid)
    return [
        ("A1 · Posesión: último valor contra promedio (medida: porcentaje ACUMULADO)",
         "posesion_pct ya es el acumulado desde el inicio. El valor correcto al cierre es last(); "
         "mean() mezcla los valores volátiles de los primeros minutos y da otro número.",
         f'''datos = {est}
  |> filter(fn: (r) => r._field == "posesion_pct")
correcto = datos |> last() |> set(key: "_field", value: "posesion_final_correcta")
incorrecto = datos |> mean() |> set(key: "_field", value: "promedio_de_acumulados_incorrecto")
union(tables: [correcto, incorrecto])
  |> keep(columns: ["equipo_id", "_field", "_value"])
  |> group(columns: ["equipo_id"])
  |> pivot(rowKey: ["equipo_id"], columnKey: ["_field"], valueColumn: "_value")
  |> group()
  |> sort(columns: ["equipo_id"])'''),

        ("A2 · Pases: contador acumulado -> total y ritmo",
         "Un contador acumulado se resume con max() (total) o spread() (lo ocurrido en el tramo). "
         "sum() contaría miles de veces los mismos pases.",
         f'''datos = {est}
  |> filter(fn: (r) => r._field == "pases_acum")
correcto = datos |> max() |> toFloat() |> set(key: "_field", value: "pases_totales_correcto")
incorrecto = datos |> sum() |> toFloat() |> set(key: "_field", value: "suma_del_acumulado_incorrecta")
ritmo = datos |> spread() |> toFloat() |> map(fn: (r) => ({{r with _value: r._value / 95.0}}))
  |> set(key: "_field", value: "pases_por_minuto_jugado")
union(tables: [correcto, incorrecto, ritmo])
  |> keep(columns: ["equipo_id", "_field", "_value"])
  |> group(columns: ["equipo_id"])
  |> pivot(rowKey: ["equipo_id"], columnKey: ["_field"], valueColumn: "_value")
  |> group()
  |> sort(columns: ["equipo_id"])'''),

        ("A3 · Recuperaciones: evento por segundo -> suma por tramo",
         "recuperaciones vale 1 en el segundo en que ocurre y 0 en el resto: acá SÍ corresponde sumar.",
         f'''{est}
  |> filter(fn: (r) => r._field == "recuperaciones")
  |> aggregateWindow(every: 15m, fn: sum, timeSrc: "_start", createEmpty: false)
  |> group()
  |> keep(columns: ["_time", "equipo_id", "_value"])
  |> rename(columns: {{_value: "recuperaciones"}})
  |> sort(columns: ["_time", "equipo_id"])'''),

        ("A4 · Pico de audiencia: sumar regiones por segundo y DESPUÉS tomar el máximo",
         "El pico real es el máximo del total simultáneo. Sumar los máximos de cada región da un número "
         "más alto que nunca existió, porque cada región tiene su pico en un segundo distinto.",
         f'''datos = {aud}
  |> filter(fn: (r) => r._field == "usuarios_conectados")
correcto = datos
  |> group(columns: ["_time"]) |> sum() |> group() |> max()
  |> map(fn: (r) => ({{partido: "{p.partido_id}", _field: "pico_simultaneo_correcto", _value: r._value}}))
incorrecto = datos
  |> max() |> group() |> sum()
  |> map(fn: (r) => ({{partido: "{p.partido_id}", _field: "suma_de_picos_incorrecta", _value: r._value}}))
union(tables: [correcto, incorrecto])
  |> group()
  |> pivot(rowKey: ["partido"], columnKey: ["_field"], valueColumn: "_value")'''),

        ("A5 · Latencia p95: no se promedian percentiles",
         "latencia_p95_ms ya es un percentil calculado por el servicio. Para el tramo se informa el "
         "peor valor (max); el promedio escondería los minutos malos. solicitudes es un evento: se suma.",
         f'''datos = {base("operacion_plataforma", a, b, ' and (r.servicio == "api" or r.servicio == "sesiones")')}
peor = datos |> filter(fn: (r) => r._field == "latencia_p95_ms")
  |> aggregateWindow(every: 15m, fn: max, timeSrc: "_start", createEmpty: false)
  |> set(key: "_field", value: "p95_peor")
prom = datos |> filter(fn: (r) => r._field == "latencia_p95_ms")
  |> aggregateWindow(every: 15m, fn: mean, timeSrc: "_start", createEmpty: false)
  |> set(key: "_field", value: "p95_promedio_enganoso")
rps = datos |> filter(fn: (r) => r._field == "solicitudes")
  |> aggregateWindow(every: 15m, fn: sum, timeSrc: "_start", createEmpty: false)
  |> toFloat() |> map(fn: (r) => ({{r with _value: r._value / 900.0}}))
  |> set(key: "_field", value: "solicitudes_por_segundo")
union(tables: [peor, prom, rps])
  |> keep(columns: ["_time", "servicio", "_field", "_value"])
  |> group(columns: ["servicio"])
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> group()
  |> sort(columns: ["_time", "servicio"])'''),
    ]


# ---------------------------------------------------------------------------
# 2) Pasos de resumen (Flux). Se usan igual en la task y en el backfill.
# ---------------------------------------------------------------------------
def pasos_resumen_1m(a: str, b: str, filtro_partido: str = "") -> str:
    """Resumen por minuto de feed y audiencia, escrito con to() en el bucket histórico.
    Cada field se resume con la función que corresponde a su semántica."""
    est = base("estadisticas_equipo", a, b, filtro_partido)
    aud = base("audiencia_partido", a, b, filtro_partido)
    def ventana(src: str, campo: str, fn: str, nuevo_meas: str, nuevo_campo: str | None = None) -> str:
        return (f'{src}\n  |> filter(fn: (r) => r._field == "{campo}")\n'
                f'  |> aggregateWindow(every: 1m, fn: {fn}, timeSrc: "_start", createEmpty: false)\n'
                f'  |> set(key: "_measurement", value: "{nuevo_meas}")\n'
                + (f'  |> set(key: "_field", value: "{nuevo_campo}")\n' if nuevo_campo else "")
                + f'  |> to(bucket: "{DB_HISTORICO}", org: "{org()}")')
    partes = [
        ventana(est, "posesion_pct", "last", "estadisticas_equipo_1m"),
        ventana(est, "pases_acum", "max", "estadisticas_equipo_1m"),
        ventana(est, "tiros_acum", "max", "estadisticas_equipo_1m"),
        ventana(est, "goles_acum", "max", "estadisticas_equipo_1m"),
        ventana(est, "recuperaciones", "sum", "estadisticas_equipo_1m"),
        ventana(est, "posesion_pct", "count", "estadisticas_equipo_1m", "puntos"),
        ventana(aud, "usuarios_conectados", "max", "audiencia_partido_1m", "usuarios_max"),
        ventana(aud, "usuarios_conectados", "mean", "audiencia_partido_1m", "usuarios_prom"),
        ventana(aud, "comentarios", "sum", "audiencia_partido_1m"),
        ventana(aud, "sesiones_nuevas", "sum", "audiencia_partido_1m"),
    ]
    # En Flux una asignación (x = ...) NO se ejecuta si nadie la usa: cada flujo que escribe
    # con to() termina en su propio yield() para que se ejecute.
    return "\n".join(f'{x}\n  |> yield(name: "r{i}")' for i, x in enumerate(partes))


def flux_task() -> str:
    return (f'option task = {{name: "{NOMBRE_TASK}", every: 1h, offset: 5m}}\n\n'
            + pasos_resumen_1m("-task.every", "now()"))


def registrar_task() -> str:
    """Crea (o actualiza) la task nativa. Idempotente: busca por nombre."""
    import urllib.parse
    q = urllib.parse.urlencode({"org": org(), "name": NOMBRE_TASK})
    estado, resp = _peticion("GET", f"/api/v2/tasks?{q}")
    tareas = json.loads(resp).get("tasks", []) if estado == 200 else []
    cuerpo = {"flux": flux_task(), "status": "active"}
    if tareas:
        estado, resp = _peticion("PATCH", f"/api/v2/tasks/{tareas[0]['id']}", json.dumps(cuerpo).encode(),
                                 {"Content-Type": "application/json"})
        accion = "actualizada"
    else:
        cuerpo["org"] = org()
        estado, resp = _peticion("POST", "/api/v2/tasks", json.dumps(cuerpo).encode(),
                                 {"Content-Type": "application/json"})
        accion = "creada"
    if estado not in (200, 201):
        return f"no se pudo registrar (HTTP {estado}: {resp[:200]!r})"
    return f"{accion} (id {json.loads(resp).get('id')}, cada 1 h, estado activo)"


def borrar(a: str, b: str, predicado: str) -> None:
    """POST /api/v2/delete: borra del bucket histórico los puntos del tramo [a, b) que
    cumplen el predicado (solo admite igualdades unidas con AND)."""
    import urllib.parse
    q = urllib.parse.urlencode({"org": org(), "bucket": DB_HISTORICO})
    cuerpo = json.dumps({"start": a, "stop": b, "predicate": predicado}).encode()
    estado, resp = _peticion("POST", f"/api/v2/delete?{q}", cuerpo, {"Content-Type": "application/json"})
    if estado not in (200, 204):
        raise RuntimeError(f"No se pudo borrar {predicado} (HTTP {estado}: {resp[:200]!r})")


def materializar_partido(p) -> None:
    a, b = rango(p)
    for meas in ("estadisticas_equipo_1m", "audiencia_partido_1m",
                 "resumen_partido_equipo", "resumen_partido_audiencia"):
        borrar(a, b, f'_measurement="{meas}" AND partido_id="{p.partido_id}"')
    pid = f' and r.partido_id == "{p.partido_id}"'
    consultar(pasos_resumen_1m(a, b, pid))
    # Resumen por partido: un punto por equipo y uno de audiencia, fechados al inicio del partido
    t0 = rfc3339(p.inicio)
    est = base("estadisticas_equipo", a, b, pid)
    aud = base("audiencia_partido", a, b, pid)
    fijar = (f'  |> map(fn: (r) => ({{r with _time: {t0}, _measurement: "resumen_partido_equipo"}}))\n'
             f'  |> set(key: "sede_id", value: "{p.sede_id}")\n'
             f'  |> to(bucket: "{DB_HISTORICO}", org: "{org()}", tagColumns: ["partido_id", "equipo_id", "condicion", "fase", "sede_id"])')
    flux = "\n".join(f'{x}\n  |> yield(name: "f{i}")' for i, x in enumerate([
        f'{est}\n  |> filter(fn: (r) => r._field == "posesion_pct") |> last() |> set(key: "_field", value: "posesion_final")\n{fijar}',
        f'{est}\n  |> filter(fn: (r) => r._field == "pases_acum") |> max() |> set(key: "_field", value: "pases")\n{fijar}',
        f'{est}\n  |> filter(fn: (r) => r._field == "tiros_acum") |> max() |> set(key: "_field", value: "tiros")\n{fijar}',
        f'{est}\n  |> filter(fn: (r) => r._field == "goles_acum") |> max() |> set(key: "_field", value: "goles")\n{fijar}',
        f'{est}\n  |> filter(fn: (r) => r._field == "recuperaciones") |> sum() |> set(key: "_field", value: "recuperaciones")\n{fijar}',
    ]))
    consultar(flux)
    fijar_aud = (f'  |> map(fn: (r) => ({{_time: {t0}, _measurement: "resumen_partido_audiencia", _field: r._field, '
                 f'_value: r._value, partido_id: "{p.partido_id}", fase: "{p.fase}", sede_id: "{p.sede_id}"}}))\n'
                 f'  |> to(bucket: "{DB_HISTORICO}", org: "{org()}", tagColumns: ["partido_id", "fase", "sede_id"])')
    flux_aud = "\n".join(f'{x}\n  |> yield(name: "a{i}")' for i, x in enumerate([
        f'{aud}\n  |> filter(fn: (r) => r._field == "usuarios_conectados")\n'
        f'  |> group(columns: ["_time"]) |> sum() |> group() |> max() |> set(key: "_field", value: "pico_usuarios")\n{fijar_aud}',
        f'{aud}\n  |> filter(fn: (r) => r._field == "comentarios") |> group() |> sum() |> set(key: "_field", value: "comentarios")\n{fijar_aud}',
        f'{aud}\n  |> filter(fn: (r) => r._field == "sesiones_nuevas") |> group() |> sum() |> set(key: "_field", value: "sesiones_nuevas")\n{fijar_aud}',
    ]))
    consultar(flux_aud)


def materializar_operacion(archivo: dict) -> None:
    """operacion_plataforma (10 s) -> operacion_plataforma_5m, un día por vez."""
    a = rfc3339(datetime.fromtimestamp(archivo["t_min"], UTC))
    b = rfc3339(datetime.fromtimestamp(archivo["t_max"] + 1, UTC))
    borrar(a, b, '_measurement="operacion_plataforma_5m"')
    src = base("operacion_plataforma", a, b)
    def v(campo, fn, nuevo):
        return (f'{src}\n  |> filter(fn: (r) => r._field == "{campo}")\n'
                f'  |> aggregateWindow(every: 5m, fn: {fn}, timeSrc: "_start", createEmpty: false)\n'
                f'  |> set(key: "_measurement", value: "operacion_plataforma_5m")\n'
                f'  |> set(key: "_field", value: "{nuevo}")\n'
                f'  |> to(bucket: "{DB_HISTORICO}", org: "{org()}")')
    consultar("\n".join([v('latencia_p95_ms', 'max', 'latencia_p95_max') + '\n  |> yield(name: "o0")',
                         v('solicitudes', 'sum', 'solicitudes') + '\n  |> yield(name: "o1")',
                         v('errores', 'sum', 'errores') + '\n  |> yield(name: "o2")']))


def contar_historico(desde: str, hasta: str) -> list[dict]:
    """Puntos (filas) escritos por measurement del histórico: se cuenta un field por measurement."""
    return consultar(f'''from(bucket: "{DB_HISTORICO}")
  |> range(start: {desde}, stop: {hasta})
  |> filter(fn: (r) => (r._measurement == "estadisticas_equipo_1m" and r._field == "puntos")
                       or (r._measurement == "audiencia_partido_1m" and r._field == "usuarios_max")
                       or (r._measurement == "operacion_plataforma_5m" and r._field == "solicitudes")
                       or (r._measurement == "resumen_partido_equipo" and r._field == "goles")
                       or (r._measurement == "resumen_partido_audiencia" and r._field == "pico_usuarios"))
  |> group(columns: ["_measurement"])
  |> count()
  |> keep(columns: ["_measurement", "_value"])
  |> rename(columns: {{_measurement: "measurement", _value: "puntos"}})''')


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
    for titulo, explicacion, flux in analisis(foco):
        reloj = cronometro()
        try:
            filas, error = consultar(flux), None
        except RuntimeError as e:
            filas, error = [], str(e)
        ms = round(reloj() * 1000, 1)
        print(f"\n== {titulo} ({ms} ms)\n" + (tabla_md(filas, max_filas=12) if not error else f"ERROR: {error}"))
        md += [f"### {titulo}", "", explicacion, "", "```flux", flux, "```", "",
               f"Tiempo de respuesta observado: {ms} ms", "",
               tabla_md(filas) if not error else f"**Error:** {error}", ""]

    print("\n== Materialización de resúmenes en fixture2030_historico (backfill con to())")
    reloj = cronometro()
    for i, p in enumerate(partidos, start=1):
        materializar_partido(p)
        print(f"   [{i:>3}/{len(partidos)}] {p.partido_id:<11} resumido · {reloj():6.1f} s")
    for a in manifiesto["archivos"]:
        if a["tabla"] == "operacion_plataforma":
            materializar_operacion(a)
    seg = round(reloj(), 1)
    desde = min(x["t_min"] for x in manifiesto["archivos"]) - 3600
    hasta = max(x["t_max"] for x in manifiesto["archivos"]) + 3600
    conteo = contar_historico(rfc3339(datetime.fromtimestamp(desde, UTC)),
                              rfc3339(datetime.fromtimestamp(hasta, UTC)))
    print(f"   {len(partidos)} partidos en {seg} s\n" + tabla_md(conteo))

    estado_task = registrar_task()
    print(f"\n== Task nativa {NOMBRE_TASK}: {estado_task}")

    top_audiencia = consultar(f'''from(bucket: "{DB_HISTORICO}")
  |> range(start: 2030-06-01T00:00:00Z, stop: 2030-08-01T00:00:00Z)
  |> filter(fn: (r) => r._measurement == "resumen_partido_audiencia")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> group()
  |> keep(columns: ["partido_id", "fase", "pico_usuarios", "comentarios"])
  |> sort(columns: ["pico_usuarios"], desc: true)
  |> limit(n: 5)''')
    top_posesion = consultar(f'''from(bucket: "{DB_HISTORICO}")
  |> range(start: 2030-06-01T00:00:00Z, stop: 2030-08-01T00:00:00Z)
  |> filter(fn: (r) => r._measurement == "resumen_partido_equipo" and r._field == "posesion_final")
  |> group(columns: ["equipo_id"])
  |> reduce(fn: (r, accumulator) => ({{partidos: accumulator.partidos + 1, suma: accumulator.suma + r._value}}),
            identity: {{partidos: 0, suma: 0.0}})
  |> map(fn: (r) => ({{equipo_id: r.equipo_id, partidos: r.partidos, posesion_media: r.suma / float(v: r.partidos)}}))
  |> group()
  |> sort(columns: ["posesion_media"], desc: true)
  |> limit(n: 5)''')

    md += ["## 2. Materialización de resúmenes (vivo -> histórico)", "",
           f"Partidos resumidos: {len(partidos)} · tiempo: {seg} s. Cada tramo se borra con `/api/v2/delete` "
           "y se reescribe con `to()` de Flux (reemplazo explícito: idempotente).", "",
           tabla_md(conteo), "",
           f"Task nativa `{NOMBRE_TASK}` (producción, cada 1 h sobre la última hora): {estado_task}", "",
           "```flux", flux_task(), "```", "",
           "## 3. Consultas de torneo sobre el bucket histórico", "",
           "### Top 5 partidos por pico de audiencia simultánea", "", tabla_md(top_audiencia), "",
           "### Top 5 equipos por posesión media (promedio de la posesión FINAL de cada partido)", "",
           "Acá sí corresponde promediar: cada partido aporta su posesión final y pesa lo mismo.", "",
           tabla_md(top_posesion), ""]
    print("\nTop audiencia:\n" + tabla_md(top_audiencia) + "\n\nTop posesión:\n" + tabla_md(top_posesion))
    ruta = guardar_evidencia(f"agregaciones_{args.perfil}", "\n".join(md) + "\n",
                             {"segundos": seg, "conteo_historico": conteo, "task": estado_task})
    print(f"\nEvidencia: {ruta}")


if __name__ == "__main__":
    main()
