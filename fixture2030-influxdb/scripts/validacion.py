"""
Fixture 2030 — Hito 8 · Series temporales (InfluxDB 2)
ARCHIVO: scripts/validacion.py
PROPÓSITO: verificar que lo cargado coincide con lo declarado (RF11, RF13, RF14):
  V1 puntos por measurement y por partido contra el manifiesto
  V2 cardinalidad de series medida con influxdb.cardinality() contra la estimada
  V3 tipo de cada field (long / double) y de cada tag (string)
  V4 retención configurada en cada bucket
  V5 prueba de retención real (bucket con 1 h de retención)
  V6 dato tardío y dato repetido (orden de llegada y deduplicación)
  V7 shards y espacio en disco por bucket (endpoint /metrics del servidor)
  V8 costo de una pregunta de TORNEO: bucket vivo contra bucket histórico

USO:
    docker compose run --rm herramientas scripts/validacion.py --perfil muestra
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import (DB_HISTORICO, DB_PRUEBA_RETENCION, DB_VIVO, UTC, buckets,  # noqa: E402
                   consultar, cronometro, encabezado, escribir_lp, guardar_evidencia,
                   metricas, rfc3339, tabla_md)

RETENCION_ESPERADA = {DB_VIVO: 45 * 86400, DB_HISTORICO: 0, DB_PRUEBA_RETENCION: 3600}
CAMPOS = {
    "estadisticas_equipo": {"posesion_pct": "double", "pases_acum": "long", "tiros_acum": "long",
                            "goles_acum": "long", "recuperaciones": "long", "minuto_juego": "long"},
    "audiencia_partido": {"usuarios_conectados": "long", "comentarios": "long", "sesiones_nuevas": "long"},
    "operacion_plataforma": {"latencia_p95_ms": "double", "solicitudes": "long", "errores": "long"},
}
TAGS = {"estadisticas_equipo": ["partido_id", "equipo_id", "condicion", "fase", "sede_id"],
        "audiencia_partido": ["partido_id", "region", "fase"], "operacion_plataforma": ["servicio"]}


def dur(seg: int) -> str:
    if not seg:
        return "infinita"
    return f"{seg // 86400} d" if seg % 86400 == 0 else f"{seg // 3600} h"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--perfil", default="muestra")
    ap.add_argument("--entrada", default="data/lp")
    args = ap.parse_args()
    man = json.loads((Path(args.entrada) / args.perfil / "manifiesto.json").read_text(encoding="utf-8"))
    n_partidos = len(man["partidos"])
    ini = rfc3339(datetime.fromtimestamp(min(a["t_min"] for a in man["archivos"]), UTC))
    fin = rfc3339(datetime.fromtimestamp(max(a["t_max"] for a in man["archivos"]) + 1, UTC))
    rango = f'range(start: {ini}, stop: {fin})'
    resultados: list[tuple[str, bool, str]] = []
    md = encabezado(f"Validación — perfil {args.perfil}")
    n_enc = len(md)

    # ── V1: puntos por partido (se cuenta UN field por measurement: 1 línea = 1 valor de ese field)
    def por_partido(meas: str, campo: str) -> dict:
        filas = consultar(f'''from(bucket: "{DB_VIVO}") |> {rango}
  |> filter(fn: (r) => r._measurement == "{meas}" and r._field == "{campo}")
  |> group(columns: ["partido_id"]) |> count()
  |> keep(columns: ["partido_id", "_value"])''')
        return {f["partido_id"]: f["_value"] for f in filas}
    est_real = por_partido("estadisticas_equipo", "posesion_pct")
    aud_real = por_partido("audiencia_partido", "usuarios_conectados")
    ops_real = consultar(f'''from(bucket: "{DB_VIVO}") |> {rango}
  |> filter(fn: (r) => r._measurement == "operacion_plataforma" and r._field == "solicitudes")
  |> group() |> count()''')
    ops_real = ops_real[0]["_value"] if ops_real else 0
    esperado = {(a["tabla"], a["partido_id"]): a["puntos"] for a in man["archivos"] if a["partido_id"]}
    filas_v1, difs = [], 0
    for x in man["partidos"]:
        pid = x["partido_id"]
        e, ee = est_real.get(pid, 0), esperado[("estadisticas_equipo", pid)]
        a, ea = aud_real.get(pid, 0), esperado[("audiencia_partido", pid)]
        ok = e == ee and a == ea
        difs += 0 if ok else 1
        filas_v1.append({"partido_id": pid, "feed": f"{e}/{ee}", "audiencia": f"{a}/{ea}", "ok": "✅" if ok else "❌"})
    totales = {"estadisticas_equipo": sum(est_real.values()), "audiencia_partido": sum(aud_real.values()),
               "operacion_plataforma": ops_real}
    for t, n in totales.items():
        resultados.append((f"V1 puntos {t}", n == man["puntos_por_tabla"][t],
                           f"{n:,} cargados / {man['puntos_por_tabla'][t]:,} esperados"))
    md += ["## V1 · Puntos por partido (cargados / esperados)", "", f"Partidos con diferencias: {difs}", "",
           tabla_md(filas_v1, max_filas=20), ""]

    # ── V2: cardinalidad. influxdb.cardinality() cuenta las series del índice (TSI), que en
    # InfluxDB 2 se identifican por measurement + conjunto de tags. Cada field de una serie se
    # guarda aparte en los archivos TSM (clave serie+field), pero NO suma series al índice.
    tagsets = {"estadisticas_equipo": 2 * n_partidos, "audiencia_partido": 8 * n_partidos, "operacion_plataforma": 5}
    filas_v2 = []
    for meas, campos in CAMPOS.items():
        r = consultar(f'''import "influxdata/influxdb"
influxdb.cardinality(bucket: "{DB_VIVO}", start: {ini}, stop: {fin},
                     predicate: (r) => r._measurement == "{meas}")''')
        medida = r[0]["_value"] if r else 0
        esperada = tagsets[meas]
        resultados.append((f"V2 series {meas}", medida == esperada,
                           f"{medida:,} medidas / {esperada:,} esperadas (combinaciones de tags)"))
        filas_v2.append({"measurement": meas, "series_esperadas": esperada, "series_medidas": medida,
                         "fields_por_serie": len(campos), "claves_tsm_serie_x_field": medida * len(campos)})
    md += ["## V2 · Cardinalidad (influxdb.cardinality)", "", tabla_md(filas_v2), ""]

    # ── V3: tipos (anotación #datatype del CSV de respuesta)
    filas_v3, mal = [], []
    for meas, campos in CAMPOS.items():
        for campo, tipo in campos.items():
            filas, tipos = consultar(f'''from(bucket: "{DB_VIVO}") |> {rango}
  |> filter(fn: (r) => r._measurement == "{meas}" and r._field == "{campo}")
  |> limit(n: 1) |> group() |> limit(n: 1)''', tipos=True)
            real = tipos.get("_value", "sin datos")
            tags_ok = all(tipos.get(t) == "string" for t in TAGS[meas])
            if real != tipo or not tags_ok:
                mal.append(f"{meas}.{campo}: {real}")
            filas_v3.append({"measurement": meas, "field": campo, "esperado": tipo, "observado": real,
                             "tags_string": "✅" if tags_ok else "❌"})
    resultados.append(("V3 tipos de fields y tags", not mal, "todos consistentes" if not mal else "; ".join(mal)))
    md += ["## V3 · Tipos (anotación #datatype)", "", tabla_md(filas_v3, max_filas=20), ""]

    # ── V4: retención configurada
    bks = {b["name"]: b for b in buckets()}
    filas_v4, ok4 = [], True
    for nombre, seg in RETENCION_ESPERADA.items():
        b = bks.get(nombre)
        reglas = (b or {}).get("retentionRules") or [{}]
        real = reglas[0].get("everySeconds", 0) or 0
        shard = reglas[0].get("shardGroupDurationSeconds")
        ok4 &= b is not None and real == seg
        filas_v4.append({"bucket": nombre, "retencion_esperada": dur(seg), "retencion_real": dur(real) if b else "NO EXISTE",
                         "shard_group": dur(shard) if shard else "por defecto"})
    resultados.append(("V4 retención configurada", ok4, ", ".join(f"{f['bucket']}={f['retencion_real']}" for f in filas_v4)))
    md += ["## V4 · Retención por bucket (API /api/v2/buckets)", "", tabla_md(filas_v4), ""]

    # ── V5 + V6: retención real, dato tardío y repetido (bucket de prueba, 1 h)
    ahora = int(time.time())
    serie = f"prueba,corrida=c{ahora},partido_id=PAR-A-1"   # tag por corrida: no se mezclan pruebas
    # Cada escritura por separado: si el servidor rechaza el punto viejo, no arrastra a los demás.
    e1, c1 = escribir_lp(DB_PRUEBA_RETENCION, f"{serie} valor=1i {ahora - 2 * 3600}\n".encode())  # fuera de la retención
    escribir_lp(DB_PRUEBA_RETENCION, f"{serie} valor=2i {ahora - 600}\n".encode())
    escribir_lp(DB_PRUEBA_RETENCION, f"{serie} valor=3i {ahora - 1800}\n".encode())            # tardío
    e2, _ = escribir_lp(DB_PRUEBA_RETENCION, f"{serie} valor=20i {ahora - 600}\n".encode())     # repetido
    time.sleep(1.0)
    visibles = consultar(f'''from(bucket: "{DB_PRUEBA_RETENCION}") |> range(start: -3h)
  |> filter(fn: (r) => r._measurement == "prueba" and r.corrida == "c{ahora}")
  |> keep(columns: ["_time", "_value"]) |> sort(columns: ["_time"])''')
    valores = [v["_value"] for v in visibles]
    detalle_e1 = c1.decode("utf-8", "replace")[:160] if c1 else ""
    resultados.append(("V5 la retención de 1 h no admite el punto de hace 2 h", 1 not in valores,
                       f"escritura HTTP {e1} {detalle_e1}; valores visibles en orden temporal: {valores}"))
    resultados.append(("V6 dato tardío aceptado y ordenado por tiempo", valores[:1] == [3],
                       "el punto de hace 30 min llegó último y se devuelve primero"))
    resultados.append(("V6 dato repetido: misma serie + timestamp se sobrescribe", valores.count(20) == 1 and 2 not in valores,
                       f"escritura HTTP {e2}; queda un único punto con valor 20 (última escritura)"))
    md += ["## V5–V6 · Retención real, dato tardío y dato repetido", "",
           "Se escribieron, en este orden: valor=1 (hace 2 h), valor=2 (hace 10 min), valor=3 (hace 30 min) "
           "y luego valor=20 con el MISMO timestamp que valor=2.", "",
           f"Respuesta del servidor a la primera escritura: HTTP {e1} {detalle_e1}", "", tabla_md(visibles), ""]

    # ── V7: shards y disco por bucket (/metrics)
    id_a_nombre = {b["id"]: b["name"] for b in bks.values()}
    shards: dict[str, dict] = {}
    for ln in metricas().splitlines():
        m = re.match(r'storage_shard_disk_size\{([^}]*)\}\s+([0-9.e+]+)', ln)
        if m:
            etiquetas = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
            nombre = id_a_nombre.get(etiquetas.get("bucket", ""), etiquetas.get("bucket", "?"))
            d = shards.setdefault(nombre, {"shards": 0, "bytes": 0.0})
            d["shards"] += 1
            d["bytes"] += float(m.group(2))
    filas_v7 = [{"bucket": k, "shards": v["shards"], "mb_en_disco": round(v["bytes"] / 1e6, 1)}
                for k, v in sorted(shards.items()) if k.startswith("fixture2030")]
    md += ["## V7 · Shards y espacio en disco (/metrics: storage_shard_disk_size)", "",
           "Cada bucket se divide en shards por período de tiempo (1 día para una retención de 45 días; "
           "7 días para retención infinita). Lo recién escrito puede estar todavía en el caché/WAL.", "",
           tabla_md(filas_v7), ""]

    # ── V8: pregunta de torneo (total de comentarios) en el vivo contra el histórico
    reloj = cronometro()
    vivo = consultar(f'''from(bucket: "{DB_VIVO}") |> {rango}
  |> filter(fn: (r) => r._measurement == "audiencia_partido" and r._field == "comentarios")
  |> group() |> sum()''')
    t_vivo = round(reloj() * 1000, 1)
    reloj = cronometro()
    hist = consultar(f'''from(bucket: "{DB_HISTORICO}") |> {rango}
  |> filter(fn: (r) => r._measurement == "resumen_partido_audiencia" and r._field == "comentarios")
  |> group() |> sum()''')
    t_hist = round(reloj() * 1000, 1)
    v_vivo = vivo[0]["_value"] if vivo else None
    v_hist = hist[0]["_value"] if hist else None
    if v_hist is None:
        texto_v8 = "el bucket histórico todavía está vacío: correr agregaciones.py y repetir"
    else:
        texto_v8 = (f"vivo: {v_vivo:,} en {t_vivo} ms · histórico: {v_hist:,} en {t_hist} ms "
                    f"(mismo resultado leyendo {n_partidos} puntos en lugar de {man['puntos_por_tabla']['audiencia_partido']:,})")
        resultados.append(("V8 la pregunta de torneo da igual en el histórico", v_vivo == v_hist, texto_v8))
    md += ["## V8 · Pregunta de torneo: vivo contra histórico", "", texto_v8, ""]

    resumen = ["## Resumen", "", "| Verificación | Resultado | Detalle |", "|---|:-:|---|",
               *[f"| {n} | {'✅' if ok else '❌'} | {d} |" for n, ok, d in resultados], ""]
    md = md[:n_enc] + resumen + md[n_enc:]
    ruta = guardar_evidencia(f"validacion_{args.perfil}", "\n".join(md) + "\n",
                             {"resultados": [{"verificacion": n, "ok": ok, "detalle": d} for n, ok, d in resultados],
                              "shards": filas_v7})
    print("\n".join(resumen))
    print(f"Evidencia: {ruta}")
    sys.exit(0 if all(ok for _, ok, _ in resultados) else 1)


if __name__ == "__main__":
    main()
