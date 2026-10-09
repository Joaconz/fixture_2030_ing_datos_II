"""
Fixture 2030 — Hito 8 · Series temporales (InfluxDB 3 Core)
ARCHIVO: scripts/validacion.py
PROPÓSITO: verificar que lo cargado coincide con lo declarado (RF11, RF13, RF14):
  V1 puntos por tabla y por partido contra el manifiesto
  V2 cardinalidad de series (combinaciones distintas de tags) contra la estimada
  V3 tipo de cada field (integer / float) y de cada tag (system.influxdb_schema)
  V4 retención configurada en cada base (system.databases)
  V5 prueba de retención real (base con 1 h de retención)
  V6 dato tardío y dato repetido (orden de llegada y deduplicación)
  V7 archivos Parquet y espacio por tabla (system.parquet_files)
  V8 costo de una pregunta de TORNEO: base viva contra base histórica

USO:
    docker compose run --rm herramientas scripts/validacion.py --perfil muestra

Los conteos de V1 y V2 se hacen POR DÍA del torneo: cada consulta acota el tiempo
(RNF8) y el resultado se suma en el script.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import (DB_HISTORICO, DB_PRUEBA_RETENCION, DB_VIVO,  # noqa: E402
                   consultar, cronometro, encabezado, escribir_lp, guardar_evidencia,
                   tabla_md, ts_epoch)

DIA = 86400
NS = 1_000_000_000
RETENCION_ESPERADA = {DB_VIVO: 45 * DIA, DB_HISTORICO: None, DB_PRUEBA_RETENCION: 3600}
CAMPOS = {
    "estadisticas_equipo": {"posesion_pct": "float", "pases_acum": "integer", "tiros_acum": "integer",
                            "goles_acum": "integer", "recuperaciones": "integer", "minuto_juego": "integer"},
    "audiencia_partido": {"usuarios_conectados": "integer", "comentarios": "integer", "sesiones_nuevas": "integer"},
    "operacion_plataforma": {"latencia_p95_ms": "float", "solicitudes": "integer", "errores": "integer"},
}
TAGS = {"estadisticas_equipo": ["partido_id", "equipo_id", "condicion", "fase", "sede_id"],
        "audiencia_partido": ["partido_id", "region", "fase"], "operacion_plataforma": ["servicio"]}
SERIE = {"estadisticas_equipo": ["partido_id", "equipo_id"], "audiencia_partido": ["partido_id", "region"],
         "operacion_plataforma": ["servicio"]}


def dur(seg: int | None) -> str:
    if not seg:
        return "infinita"
    return f"{seg // DIA} d" if seg % DIA == 0 else f"{seg // 3600} h"


def main() -> None:
    # Nota: en las respuestas JSON de InfluxDB 3 las columnas con valor NULL no aparecen
    # en la fila: por eso se leen con .get().
    ap = argparse.ArgumentParser()
    ap.add_argument("--perfil", default="muestra")
    ap.add_argument("--entrada", default="data/lp")
    args = ap.parse_args()
    man = json.loads((Path(args.entrada) / args.perfil / "manifiesto.json").read_text(encoding="utf-8"))
    n_partidos = len(man["partidos"])
    ini = min(a["t_min"] for a in man["archivos"])
    fin = max(a["t_max"] for a in man["archivos"]) + 1
    dias = [(d, min(d + DIA, fin)) for d in range(ini - ini % DIA, fin, DIA)]
    resultados: list[tuple[str, bool, str]] = []
    md = encabezado(f"Validación — perfil {args.perfil}")
    n_enc = len(md)

    def por_dia(sql: str) -> list[dict]:
        """Ejecuta `sql` (con {desde} y {hasta}) una vez por día del perfil y junta las filas."""
        filas = []
        for a, b in dias:
            filas += consultar(sql.format(desde=ts_epoch(a), hasta=ts_epoch(b)))
        return filas

    # ── V1: puntos por partido (1 fila = 1 punto, con todos sus fields)
    def por_partido(tabla: str) -> dict:
        total: dict[str, int] = {}
        for f in por_dia(f"SELECT partido_id, count(*) AS n FROM {tabla} "
                         "WHERE time >= {desde} AND time < {hasta} GROUP BY partido_id"):
            total[f["partido_id"]] = total.get(f["partido_id"], 0) + f["n"]
        return total
    est_real = por_partido("estadisticas_equipo")
    aud_real = por_partido("audiencia_partido")
    ops_real = sum(f["n"] for f in por_dia("SELECT count(*) AS n FROM operacion_plataforma "
                                            "WHERE time >= {desde} AND time < {hasta}"))
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

    # ── V2: cardinalidad. En InfluxDB 3 una serie es tabla + combinación de valores de tags
    # (la "clave de serie" de la tabla, en system.tables). Se cuentan las combinaciones
    # DISTINTAS que aparecen en los datos y se comparan con la estimación.
    claves = {f["table_name"]: f["series_key_columns"] for f in consultar(
        f"SELECT table_name, series_key_columns FROM system.tables WHERE database_name = '{DB_VIVO}'", "_internal")}
    esperadas = {"estadisticas_equipo": 2 * n_partidos, "audiencia_partido": 8 * n_partidos, "operacion_plataforma": 5}
    filas_v2 = []
    for tabla, tags in TAGS.items():
        combinaciones = {tuple(f[t] for t in tags) for f in por_dia(
            f"SELECT DISTINCT {', '.join(tags)} FROM {tabla} WHERE time >= {{desde}} AND time < {{hasta}}")}
        identidad = {tuple(c[: len(SERIE[tabla])]) for c in combinaciones}
        medida, esperada = len(combinaciones), esperadas[tabla]
        resultados.append((f"V2 series {tabla}", medida == esperada == len(identidad),
                           f"{medida:,} medidas / {esperada:,} esperadas; "
                           f"{' + '.join(SERIE[tabla])} solo ya da {len(identidad):,}"))
        filas_v2.append({"tabla": tabla, "clave_de_serie": claves.get(tabla, "?"), "series_esperadas": esperada,
                         "series_medidas": medida, "identidad": " + ".join(SERIE[tabla]),
                         "combinaciones_identidad": len(identidad), "fields_por_fila": len(CAMPOS[tabla])})
    md += ["## V2 · Cardinalidad (combinaciones distintas de tags)", "",
           "La columna `clave_de_serie` sale de `system.tables`: son los tags que identifican cada serie, "
           "en el orden en que InfluxDB 3 ordena los datos dentro de cada archivo.", "",
           tabla_md(filas_v2), ""]

    # ── V3: tipos (system.influxdb_schema: tag / integer / float / time)
    esquema = {(f["measurement"], f["key"]): f["data_type"]
               for f in consultar("SELECT measurement, key, data_type FROM system.influxdb_schema")}
    filas_v3, mal = [], []
    for tabla, campos in CAMPOS.items():
        tags_ok = all(esquema.get((tabla, t)) == "tag" for t in TAGS[tabla])
        for campo, tipo in campos.items():
            real = esquema.get((tabla, campo), "sin datos")
            if real != tipo or not tags_ok:
                mal.append(f"{tabla}.{campo}: {real}")
            filas_v3.append({"tabla": tabla, "field": campo, "esperado": tipo, "observado": real,
                             "tags_son_tag": "✅" if tags_ok else "❌"})
    resultados.append(("V3 tipos de fields y tags", not mal, "todos consistentes" if not mal else "; ".join(mal)))
    md += ["## V3 · Tipos (system.influxdb_schema)", "", tabla_md(filas_v3, max_filas=20), ""]

    # ── V4: retención configurada (se fija al crear la base; en Core no se cambia después)
    bases = {f["database_name"]: f.get("retention_period_ns") for f in consultar(
        "SELECT database_name, retention_period_ns FROM system.databases WHERE deleted = false", "_internal")}
    filas_v4, ok4 = [], True
    for nombre, seg in RETENCION_ESPERADA.items():
        existe = nombre in bases
        real = bases[nombre] // NS if existe and bases[nombre] else None
        ok4 &= existe and real == seg
        filas_v4.append({"base": nombre, "retencion_esperada": dur(seg),
                         "retencion_real": dur(real) if existe else "NO EXISTE"})
    resultados.append(("V4 retención configurada", ok4, ", ".join(f"{f['base']}={f['retencion_real']}" for f in filas_v4)))
    md += ["## V4 · Retención por base (system.databases)", "", tabla_md(filas_v4), ""]

    # ── V5 + V6: retención real, dato tardío y repetido (base de prueba, 1 h)
    ahora = int(time.time())
    serie = f"prueba,corrida=c{ahora},partido_id=PAR-A-1"   # tag por corrida: no se mezclan pruebas
    # Cada escritura por separado, para ver la respuesta del servidor a cada una.
    e1, c1 = escribir_lp(DB_PRUEBA_RETENCION, f"{serie} valor=1i {ahora - 2 * 3600}\n".encode())  # fuera de la retención
    escribir_lp(DB_PRUEBA_RETENCION, f"{serie} valor=2i {ahora - 600}\n".encode())
    escribir_lp(DB_PRUEBA_RETENCION, f"{serie} valor=3i {ahora - 1800}\n".encode())            # tardío
    e2, _ = escribir_lp(DB_PRUEBA_RETENCION, f"{serie} valor=20i {ahora - 600}\n".encode())     # repetido
    visibles = consultar(f"""SELECT time, valor FROM prueba
WHERE corrida = 'c{ahora}' AND time >= {ts_epoch(ahora - 3 * 3600)} AND time < {ts_epoch(ahora + 60)}
ORDER BY time""", DB_PRUEBA_RETENCION)
    valores = [v["valor"] for v in visibles]
    detalle_e1 = c1.decode("utf-8", "replace")[:160] if c1 else "(sin cuerpo)"
    resultados.append(("V5 la retención de 1 h no conserva el punto de hace 2 h", 1 not in valores,
                       f"escritura HTTP {e1} {detalle_e1}; valores visibles en orden temporal: {valores}"))
    resultados.append(("V6 dato tardío aceptado y ordenado por tiempo", valores[:1] == [3],
                       "el punto de hace 30 min llegó último y se devuelve primero"))
    resultados.append(("V6 dato repetido: misma serie + timestamp se sobrescribe", valores.count(20) == 1 and 2 not in valores,
                       f"escritura HTTP {e2}; queda un único punto con valor 20 (última escritura)"))
    md += ["## V5–V6 · Retención real, dato tardío y dato repetido", "",
           "Se escribieron, en este orden: valor=1 (hace 2 h), valor=2 (hace 10 min), valor=3 (hace 30 min) "
           "y luego valor=20 con el MISMO timestamp que valor=2.", "",
           f"Respuesta del servidor a la primera escritura: HTTP {e1} {detalle_e1}", "", tabla_md(visibles), ""]

    # ── V7: archivos Parquet y espacio por tabla (lo recién escrito puede estar todavía en el WAL)
    filas_v7 = []
    for base in (DB_VIVO, DB_HISTORICO):
        try:
            for f in consultar("""SELECT table_name, count(*) AS archivos, sum(row_count) AS filas,
       sum(size_bytes) AS bytes FROM system.parquet_files GROUP BY table_name ORDER BY table_name""", base):
                filas_v7.append({"base": base, "tabla": f["table_name"], "archivos_parquet": f["archivos"],
                                 "filas_persistidas": f["filas"], "mb": round(f["bytes"] / 1e6, 1)})
        except RuntimeError as e:
            filas_v7.append({"base": base, "tabla": "error", "archivos_parquet": str(e)[:200]})
    md += ["## V7 · Archivos Parquet y espacio (system.parquet_files)", "",
           "InfluxDB 3 confirma cada escritura cuando está en el WAL; los puntos pasan a archivos Parquet "
           "(uno por tabla y por tramo de 10 minutos de datos) cuando el servidor hace un snapshot del WAL. "
           "Lo que todavía no tiene archivo se sigue consultando desde memoria.", "",
           tabla_md(filas_v7, max_filas=20), ""]

    # ── V8: pregunta de torneo (total de comentarios) en el vivo contra el histórico
    sql_torneo = (f"SELECT sum(comentarios) AS total FROM audiencia_partido "
                  f"WHERE time >= {ts_epoch(ini)} AND time < {ts_epoch(fin)}")
    reloj = cronometro()
    try:
        v_vivo, error_vivo = consultar(sql_torneo)[0].get("total"), None
    except RuntimeError as e:
        v_vivo, error_vivo = None, str(e)
    t_vivo = round(reloj() * 1000, 1)
    if error_vivo:   # el rango completo no se pudo leer de una vez: se suma día por día
        reloj = cronometro()
        v_vivo = sum(f.get("total") or 0 for f in por_dia(
            "SELECT sum(comentarios) AS total FROM audiencia_partido WHERE time >= {desde} AND time < {hasta}"))
        t_vivo = round(reloj() * 1000, 1)
    reloj = cronometro()
    hist = consultar(f"SELECT sum(comentarios) AS total, count(*) AS puntos FROM resumen_partido_audiencia "
                     f"WHERE time >= {ts_epoch(ini - DIA)} AND time < {ts_epoch(fin)}", DB_HISTORICO) \
        if any(f["table_name"] == "resumen_partido_audiencia" for f in consultar(
            f"SELECT table_name FROM system.tables WHERE database_name = '{DB_HISTORICO}'", "_internal")) else []
    t_hist = round(reloj() * 1000, 1)
    v_hist = hist[0].get("total") if hist else None
    if v_hist is None:
        texto_v8 = "la base histórica todavía está vacía: correr agregaciones.py y repetir"
    else:
        texto_v8 = (f"vivo: {v_vivo:,} en {t_vivo} ms · histórico: {v_hist:,} en {t_hist} ms "
                    f"(mismo resultado leyendo {hist[0]['puntos']} puntos en lugar de "
                    f"{man['puntos_por_tabla']['audiencia_partido']:,})")
        if error_vivo:
            texto_v8 += f". La consulta del torneo entero sobre el vivo falló ({error_vivo[:200]}) y se sumó día por día"
        resultados.append(("V8 la pregunta de torneo da igual en el histórico", v_vivo == v_hist, texto_v8))
    md += ["## V8 · Pregunta de torneo: vivo contra histórico", "", texto_v8, ""]

    resumen = ["## Resumen", "", "| Verificación | Resultado | Detalle |", "|---|:-:|---|",
               *[f"| {n} | {'✅' if ok else '❌'} | {d} |" for n, ok, d in resultados], ""]
    md = md[:n_enc] + resumen + md[n_enc:]
    ruta = guardar_evidencia(f"validacion_{args.perfil}", "\n".join(md) + "\n",
                             {"resultados": [{"verificacion": n, "ok": ok, "detalle": d} for n, ok, d in resultados],
                              "parquet": filas_v7})
    print("\n".join(resumen))
    print(f"Evidencia: {ruta}")
    sys.exit(0 if all(ok for _, ok, _ in resultados) else 1)


if __name__ == "__main__":
    main()
