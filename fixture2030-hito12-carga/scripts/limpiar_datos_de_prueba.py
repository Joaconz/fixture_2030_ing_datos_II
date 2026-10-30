"""
Fixture 2030 — Hito 12 · limpieza SEGURA de los datos de prueba (RNF7, RNF11)
ARCHIVO: scripts/limpiar_datos_de_prueba.py

Borra SOLO los comentarios escritos por las corridas registradas en
docs/evidencia/resultados_*/corrida.txt y docs/evidencia/anteriores/*/corrida.txt
(usuarios USR-LT<CORRIDA><VU>), de las
dos tablas, por clave primaria completa. No toca los 1.050.000 comentarios del
Hito 6, ni volúmenes, ni configuración. La evidencia NO se borra.

USO:  bash scripts/limpiar_datos_de_prueba.sh            (pide confirmación)
"""
from __future__ import annotations

import glob
import os

from cassandra.cluster import Cluster
from cassandra.query import dict_factory

KS = "fixture2030_comentarios"
BASE = os.path.join(os.path.dirname(__file__), "..", "docs", "evidencia")

corridas = []
for f in glob.glob(os.path.join(BASE, "resultados_*", "corrida.txt")) + \
        glob.glob(os.path.join(BASE, "anteriores", "*", "corrida.txt")):
    d = dict(l.strip().split("=", 1) for l in open(f) if "=" in l)
    corridas.append((d["corrida"].upper(), int(d["vus"])))
if not corridas:
    print("No hay corridas registradas: nada para limpiar."); raise SystemExit(0)

s = Cluster([os.getenv("CASSANDRA_HOST", "127.0.0.1")], port=int(os.getenv("CASSANDRA_PORT", "9042"))).connect(KS)
s.row_factory = dict_factory
sel = s.prepare("SELECT usuario_id, mes, creado_en, comentario_id, partido_id, ventana, bucket "
                "FROM comentarios_por_usuario WHERE usuario_id = ? AND mes = '2030-06'")
del_u = s.prepare("DELETE FROM comentarios_por_usuario WHERE usuario_id = ? AND mes = ? AND creado_en = ? AND comentario_id = ?")
del_p = s.prepare("DELETE FROM comentarios_por_partido WHERE partido_id = ? AND ventana = ? AND bucket = ? "
                  "AND creado_en = ? AND comentario_id = ?")
total = 0
for corrida, vus in corridas:
    for vu in range(1, vus + 1):
        for f in s.execute(sel, (f"USR-LT{corrida}{vu:03d}",)):
            s.execute(del_p, (f["partido_id"], f["ventana"], f["bucket"], f["creado_en"], f["comentario_id"]))
            s.execute(del_u, (f["usuario_id"], f["mes"], f["creado_en"], f["comentario_id"]))
            total += 1
print(f"Borrados {total} comentarios de prueba de {len(corridas)} corrida(s): {[c for c, _ in corridas]}")
