"""
Fixture 2030 — Hito 12 · validación de integridad (RF15, RNF4)
ARCHIVO: scripts/validar_integridad.py

"Un HTTP exitoso no garantiza que el dato se guardó" (consigna §5.8). Para la
corrida indicada se lee Cassandra DIRECTO (no la API) y se verifica:
  I1  escritos en Cassandra (vista por usuario) = POST confirmados con 201 por k6
  I2  sin comentario_id duplicados
  I3  cada fila de la vista por usuario existe en la vista por partido (las dos
      tablas del LOGGED BATCH del Hito 6 quedaron consistentes)
  I4  contenido sin alterar (coincide con lo que generó k6)
  I5  sin escrituras fuera de la ventana pico ni de otro partido
Usuarios de la corrida: USR-LT<CORRIDA><VU>, mes '2030-06' (partición de comentarios_por_usuario).

USO (lo llama ejecutar_carga.sh):
  <venv de la API>/bin/python scripts/validar_integridad.py --corrida 1530 --vus 20 \
      --resumen docs/evidencia/resultados_linea_base/k6_resumen.json --salida .../integridad
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

from cassandra.cluster import Cluster
from cassandra.query import dict_factory

KS = "fixture2030_comentarios"
PARTIDO = "PAR-D16-01"
PICO_DESDE = datetime(2030, 6, 29, 17, 30)
PICO_HASTA = datetime(2030, 6, 29, 17, 40)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corrida", required=True)
    ap.add_argument("--vus", type=int, required=True)
    ap.add_argument("--resumen", required=True)
    ap.add_argument("--salida", required=True)
    a = ap.parse_args()

    k6 = json.load(open(a.resumen, encoding="utf-8"))["metrics"]
    cuenta = lambda m: int(k6.get(m, {}).get("values", {}).get("count", 0))  # noqa: E731
    p201, p200, perr = cuenta("posts_201_creados"), cuenta("posts_200_reintento"), cuenta("posts_error")

    sesion = Cluster([os.getenv("CASSANDRA_HOST", "127.0.0.1")], port=int(os.getenv("CASSANDRA_PORT", "9042"))).connect(KS)
    sesion.row_factory = dict_factory
    por_usuario = sesion.prepare("SELECT usuario_id, comentario_id, partido_id, ventana, bucket, creado_en, contenido "
                                 "FROM comentarios_por_usuario WHERE usuario_id = ? AND mes = '2030-06'")
    en_partido = sesion.prepare("SELECT comentario_id, contenido FROM comentarios_por_partido "
                                "WHERE partido_id = ? AND ventana = ? AND bucket = ? AND creado_en = ? AND comentario_id = ?")

    filas = []
    for vu in range(1, a.vus + 1):
        filas += list(sesion.execute(por_usuario, (f"USR-LT{a.corrida.upper()}{vu:03d}",)))
    ids = [f["comentario_id"] for f in filas]
    duplicados = len(ids) - len(set(ids))
    patron = re.compile(rf"^prueba de carga h12-{a.corrida.upper()}-\d+-\d+$")
    faltan_en_partido, alterados, fuera = [], [], []
    for f in filas:
        r = sesion.execute(en_partido, (f["partido_id"], f["ventana"], f["bucket"], f["creado_en"], f["comentario_id"])).one()
        if r is None:
            faltan_en_partido.append(f["comentario_id"])
        elif r["contenido"] != f["contenido"] or not patron.match(f["contenido"] or ""):
            alterados.append(f["comentario_id"])
        if f["partido_id"] != PARTIDO or not (PICO_DESDE <= f["creado_en"] < PICO_HASTA):
            fuera.append(f["comentario_id"])

    checks = [
        ("I1 escritos en Cassandra = POST 201 de k6", len(set(ids)) == p201,
         f"{len(set(ids))} filas únicas · {p201} POST 201 · {p200} reintentos 200 · {perr} POST con error"),
        ("I2 sin comentario_id duplicados", duplicados == 0, f"{duplicados} duplicados"),
        ("I3 vista por usuario = vista por partido", not faltan_en_partido, f"{len(faltan_en_partido)} filas sin su par"),
        ("I4 contenido sin alterar", not alterados, f"{len(alterados)} alterados"),
        ("I5 todo en PAR-D16-01, ventana 17:30", not fuera, f"{len(fuera)} fuera de rango"),
    ]
    ok = all(c[1] for c in checks)
    if perr and len(set(ids)) > p201:
        checks.append(("Nota", True, f"{len(set(ids)) - p201} filas se guardaron aunque el cliente vio error/timeout"))
    md = [f"# Integridad — corrida {a.corrida}", "",
          f"Validado leyendo Cassandra directo el {datetime.now(timezone.utc).isoformat(timespec='seconds')}.", "",
          "| Verificación | Resultado | Detalle |", "|---|:-:|---|",
          *[f"| {n} | {'✅' if b else '❌'} | {d} |" for n, b, d in checks],
          "", f"**Resultado: {'✅ integridad verificada' if ok else '❌ hay diferencias'}**"]
    open(a.salida + ".md", "w", encoding="utf-8").write("\n".join(md) + "\n")
    json.dump({"corrida": a.corrida, "ok": ok, "filas": len(set(ids)), "posts_201": p201, "posts_200": p200,
               "posts_error": perr, "duplicados": duplicados, "sin_par": len(faltan_en_partido),
               "alterados": len(alterados), "fuera_de_rango": len(fuera)},
              open(a.salida + ".json", "w", encoding="utf-8"), indent=2)
    print("\n".join(md))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
